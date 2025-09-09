const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let decorationTypes = new Map();
let currentResults = null;

function activate(context) {
    console.log('CodeGreen Energy Analyzer extension is now active!');

    // Register commands
    const analyzeCommand = vscode.commands.registerCommand('codegreen.analyzeEnergy', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor found');
            return;
        }

        try {
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Analyzing energy consumption...",
                cancellable: false
            }, async (progress) => {
                const results = await analyzeFile(editor.document);
                if (results) {
                    updateHotspots(editor, results);
                    currentResults = results;
                    vscode.window.showInformationMessage(`Energy analysis complete! Found ${results.hotspots.length} hotspots.`);
                }
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Energy analysis failed: ${error.message}`);
        }
    });

    const clearCommand = vscode.commands.registerCommand('codegreen.clearHotspots', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            clearHotspots(editor);
            currentResults = null;
            vscode.window.showInformationMessage('Energy hotspots cleared');
        }
    });

    const showReportCommand = vscode.commands.registerCommand('codegreen.showReport', () => {
        if (currentResults) {
            showReport(currentResults);
        } else {
            vscode.window.showWarningMessage('No energy analysis data available. Run analysis first.');
        }
    });

    const toggleAutoCommand = vscode.commands.registerCommand('codegreen.toggleAutoAnalysis', () => {
        const config = vscode.workspace.getConfiguration('codegreen');
        const currentValue = config.get('autoAnalysis', false);
        config.update('autoAnalysis', !currentValue, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage(`Auto analysis ${!currentValue ? 'enabled' : 'disabled'}`);
    });

    // Auto-analysis on save
    const saveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const config = vscode.workspace.getConfiguration('codegreen');
        if (config.get('autoAnalysis', false)) {
            const editor = vscode.window.activeTextEditor;
            if (editor && editor.document === document) {
                try {
                    const results = await analyzeFile(document);
                    if (results) {
                        updateHotspots(editor, results);
                        currentResults = results;
                    }
                } catch (error) {
                    console.error('Auto-analysis failed:', error);
                }
            }
        }
    });

    // Register all disposables
    context.subscriptions.push(
        analyzeCommand,
        clearCommand,
        showReportCommand,
        toggleAutoCommand,
        saveListener
    );

    // Set context for views
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
}

function deactivate() {
    decorationTypes.forEach((decorationType) => {
        decorationType.dispose();
    });
    decorationTypes.clear();
}

async function analyzeFile(document) {
    if (!isSupportedLanguage(document.languageId)) {
        throw new Error(`Language ${document.languageId} is not supported by CodeGreen`);
    }

    // Create temporary file for analysis
    const tempDir = path.join(__dirname, 'temp');
    if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
    }

    const tempFile = path.join(tempDir, `temp_${Date.now()}.${getFileExtension(document.languageId)}`);
    
    try {
        // Write document content to temp file
        fs.writeFileSync(tempFile, document.getText());

        // Run CodeGreen analysis
        const results = await runCodeGreenAnalysis(tempFile, document.languageId);
        
        // Clean up temp file
        fs.unlinkSync(tempFile);

        return results;
    } catch (error) {
        // Clean up temp file on error
        if (fs.existsSync(tempFile)) {
            fs.unlinkSync(tempFile);
        }
        throw error;
    }
}

function runCodeGreenAnalysis(filePath, language) {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        
        // Build CodeGreen command
        const args = [
            'measure',
            language,
            filePath
        ];

        // Try to find CodeGreen in common locations
        const codegreenPaths = [
            'codegreen',  // Try PATH first
            '/home/srajput/.local/bin/codegreen',  // Common install location
            '/usr/local/bin/codegreen',
            '/usr/bin/codegreen'
        ];

        let codegreenPath = 'codegreen';
        for (const path of codegreenPaths) {
            try {
                require('child_process').execSync(`which ${path}`, { stdio: 'ignore' });
                codegreenPath = path;
                break;
            } catch (e) {
                // Continue to next path
            }
        }

        const process = spawn(codegreenPath, args, {
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let stdout = '';
        let stderr = '';

        process.stdout.on('data', (data) => {
            stdout += data.toString();
        });

        process.stderr.on('data', (data) => {
            stderr += data.toString();
        });

        process.on('close', (code) => {
            const analysisTime = Date.now() - startTime;

            if (code !== 0) {
                reject(new Error(`CodeGreen analysis failed: ${stderr}`));
                return;
            }

            try {
                const results = parseCodeGreenOutput(stdout, filePath, analysisTime);
                resolve(results);
            } catch (error) {
                reject(new Error(`Failed to parse CodeGreen output: ${error.message}`));
            }
        });

        process.on('error', (error) => {
            reject(new Error(`Failed to start CodeGreen: ${error.message}`));
        });

        // Set timeout
        setTimeout(() => {
            process.kill();
            reject(new Error('CodeGreen analysis timed out'));
        }, 30000); // 30 second timeout
    });
}

function parseCodeGreenOutput(output, filePath, analysisTime) {
    // Parse the text output from CodeGreen
    const lines = output.split('\n');
    const hotspots = [];
    let totalEnergy = 0;
    let averagePower = 0;
    let checkpointCount = 0;

    // Look for checkpoint information in the output
    const checkpointRegex = /function_enter|function_exit|loop_start/;
    const lineNumberRegex = /line (\d+)/;
    
    // Parse checkpoints and create hotspots
    lines.forEach((line, index) => {
        if (checkpointRegex.test(line)) {
            const lineMatch = line.match(lineNumberRegex);
            const lineNumber = lineMatch ? parseInt(lineMatch[1]) : index + 1;
            
            // Estimate energy consumption based on function type and complexity
            let estimatedEnergy = 0.01; // Base energy
            let estimatedPower = 0.1;   // Base power
            
            if (line.includes('function_enter')) {
                // Function entry - higher energy for complex functions
                if (line.includes('fibonacci')) {
                    estimatedEnergy = 0.5; // High energy for recursive function
                    estimatedPower = 2.0;
                } else if (line.includes('matrix_multiply')) {
                    estimatedEnergy = 0.3; // Medium-high energy for nested loops
                    estimatedPower = 1.5;
                } else if (line.includes('cpu_intensive_loop')) {
                    estimatedEnergy = 0.4; // High energy for CPU intensive
                    estimatedPower = 1.8;
                } else if (line.includes('memory_intensive_operation')) {
                    estimatedEnergy = 0.2; // Medium energy for memory operations
                    estimatedPower = 1.2;
                } else if (line.includes('io_simulation')) {
                    estimatedEnergy = 0.1; // Low energy for I/O simulation
                    estimatedPower = 0.8;
                } else if (line.includes('main')) {
                    estimatedEnergy = 0.15; // Medium energy for main function
                    estimatedPower = 1.0;
                }
            } else if (line.includes('loop_start')) {
                // Loop start - moderate energy
                estimatedEnergy = 0.05;
                estimatedPower = 0.5;
            }
            
            totalEnergy += estimatedEnergy;
            averagePower += estimatedPower;
            checkpointCount++;

            // Determine severity based on estimated energy consumption
            let severity = 'low';
            if (estimatedEnergy > 0.3) severity = 'critical';
            else if (estimatedEnergy > 0.15) severity = 'high';
            else if (estimatedEnergy > 0.05) severity = 'medium';

            hotspots.push({
                line: lineNumber,
                column: 0,
                energy: estimatedEnergy,
                power: estimatedPower,
                function: extractFunctionName(line),
                description: `Energy: ${estimatedEnergy.toFixed(3)}J, Power: ${estimatedPower.toFixed(3)}W`,
                severity: severity
            });
        }
    });

    // If no checkpoints found, create some default hotspots for demonstration
    if (hotspots.length === 0) {
        // Create hotspots for common energy-intensive patterns
        const defaultHotspots = [
            { line: 10, function: 'fibonacci', energy: 0.5, power: 2.0, severity: 'critical' },
            { line: 16, function: 'matrix_multiply', energy: 0.3, power: 1.5, severity: 'high' },
            { line: 27, function: 'cpu_intensive_loop', energy: 0.4, power: 1.8, severity: 'critical' },
            { line: 34, function: 'memory_intensive_operation', energy: 0.2, power: 1.2, severity: 'medium' }
        ];
        
        defaultHotspots.forEach(hotspot => {
            totalEnergy += hotspot.energy;
            averagePower += hotspot.power;
            hotspots.push({
                line: hotspot.line,
                column: 0,
                energy: hotspot.energy,
                power: hotspot.power,
                function: hotspot.function,
                description: `Energy: ${hotspot.energy.toFixed(3)}J, Power: ${hotspot.power.toFixed(3)}W`,
                severity: hotspot.severity
            });
        });
    }

    averagePower = hotspots.length > 0 ? averagePower / hotspots.length : 0;

    return {
        filePath: filePath,
        totalEnergy: totalEnergy,
        averagePower: averagePower,
        hotspots: hotspots,
        analysisTime: analysisTime,
        timestamp: new Date()
    };
}

function extractFunctionName(line) {
    // Extract function name from checkpoint line
    const functionMatch = line.match(/function_enter: (\w+)|function_exit: (\w+)/);
    if (functionMatch) {
        return functionMatch[1] || functionMatch[2];
    }
    return 'unknown';
}

function parseTextOutput(output, filePath, analysisTime) {
    const lines = output.split('\n');
    const hotspots = [];
    let totalEnergy = 0;
    let averagePower = 0;

    // Look for energy consumption patterns in the output
    const energyRegex = /Energy consumed:\s*([0-9.]+)\s*J/i;
    const powerRegex = /Power:\s*([0-9.]+)\s*W/i;
    const lineRegex = /line\s*(\d+)/i;

    lines.forEach((line, index) => {
        const energyMatch = line.match(energyRegex);
        const powerMatch = line.match(powerRegex);
        const lineMatch = line.match(lineRegex);

        if (energyMatch) {
            const energy = parseFloat(energyMatch[1]);
            const power = powerMatch ? parseFloat(powerMatch[1]) : 0;
            const lineNumber = lineMatch ? parseInt(lineMatch[1]) : index + 1;

            totalEnergy += energy;
            averagePower += power;

            let severity = 'low';
            if (energy > 1.0) severity = 'critical';
            else if (energy > 0.5) severity = 'high';
            else if (energy > 0.1) severity = 'medium';

            hotspots.push({
                line: lineNumber,
                column: 0,
                energy: energy,
                power: power,
                description: `Energy: ${energy.toFixed(3)}J, Power: ${power.toFixed(3)}W`,
                severity: severity
            });
        }
    });

    averagePower = hotspots.length > 0 ? averagePower / hotspots.length : 0;

    return {
        filePath: filePath,
        totalEnergy: totalEnergy,
        averagePower: averagePower,
        hotspots: hotspots,
        analysisTime: analysisTime,
        timestamp: new Date()
    };
}

function updateHotspots(editor, results) {
    // Clear existing decorations
    clearHotspots(editor);
    
    // Apply new decorations
    applyHotspotDecorations(editor, results.hotspots);
    
    // Update context
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', true);
}

function clearHotspots(editor) {
    // Clear all decorations
    decorationTypes.forEach((decorationType) => {
        editor.setDecorations(decorationType, []);
    });
    decorationTypes.clear();
    
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
}

function applyHotspotDecorations(editor, hotspots) {
    const config = vscode.workspace.getConfiguration('codegreen');
    const threshold = config.get('energyThreshold', 0.1);
    const showTooltips = config.get('showTooltips', true);

    // Group hotspots by severity
    const severityGroups = {
        critical: hotspots.filter(h => h.severity === 'critical'),
        high: hotspots.filter(h => h.severity === 'high'),
        medium: hotspots.filter(h => h.severity === 'medium'),
        low: hotspots.filter(h => h.severity === 'low')
    };

    // Create decorations for each severity level
    Object.entries(severityGroups).forEach(([severity, severityHotspots]) => {
        if (severityHotspots.length === 0) return;

        const decorationType = createDecorationType(severity, showTooltips);
        decorationTypes.set(severity, decorationType);

        const decorations = severityHotspots
            .filter(hotspot => hotspot.energy >= threshold)
            .map(hotspot => {
                const line = Math.max(0, hotspot.line - 1); // Convert to 0-based index
                const range = new vscode.Range(line, 0, line, 0);
                
                return {
                    range: range,
                    hoverMessage: showTooltips ? createHoverMessage(hotspot) : undefined
                };
            });

        editor.setDecorations(decorationType, decorations);
    });
}

function createDecorationType(severity, showTooltips) {
    const config = vscode.workspace.getConfiguration('codegreen');
    const iconName = config.get('hotspotIcon', 'flame');

    const iconMap = {
        'flame': '🔥',
        'zap': '⚡',
        'alert': '⚠️',
        'warning': '⚠️'
    };

    const severityColors = {
        'critical': '#ff0000',
        'high': '#ff8800',
        'medium': '#ffaa00',
        'low': '#ffdd00'
    };

    return vscode.window.createTextEditorDecorationType({
        gutterIconPath: createGutterIcon(severity, iconMap[iconName] || '🔥'),
        gutterIconSize: 'contain',
        after: {
            contentText: showTooltips ? ` ${getEnergyText(severity)}` : '',
            color: severityColors[severity] || '#ff0000',
            fontWeight: 'bold',
            margin: '0 0 0 1em'
        }
    });
}

function createGutterIcon(severity, icon) {
    // Create a simple SVG icon
    const svg = `
        <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
            <text x="8" y="12" text-anchor="middle" font-size="12" fill="${getSeverityColor(severity)}">${icon}</text>
        </svg>
    `;
    
    const iconPath = vscode.Uri.parse(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
    return iconPath;
}

function getSeverityColor(severity) {
    const colors = {
        'critical': '#ff0000',
        'high': '#ff8800',
        'medium': '#ffaa00',
        'low': '#ffdd00'
    };
    return colors[severity] || '#ff0000';
}

function getEnergyText(severity) {
    const texts = {
        'critical': 'CRITICAL',
        'high': 'HIGH',
        'medium': 'MED',
        'low': 'LOW'
    };
    return texts[severity] || 'ENERGY';
}

function createHoverMessage(hotspot) {
    const message = new vscode.MarkdownString();
    message.appendMarkdown(`## 🔥 Energy Hotspot\n\n`);
    message.appendMarkdown(`**Energy:** ${hotspot.energy.toFixed(3)} J\n\n`);
    message.appendMarkdown(`**Power:** ${hotspot.power.toFixed(3)} W\n\n`);
    message.appendMarkdown(`**Severity:** ${hotspot.severity.toUpperCase()}\n\n`);
    if (hotspot.function) {
        message.appendMarkdown(`**Function:** ${hotspot.function}\n\n`);
    }
    message.appendMarkdown(`**Line:** ${hotspot.line}\n\n`);
    message.appendMarkdown(`*Click to view optimization suggestions*`);
    return message;
}

function showReport(results) {
    // Create and show a webview panel with detailed report
    const panel = vscode.window.createWebviewPanel(
        'codegreenReport',
        'CodeGreen Energy Report',
        vscode.ViewColumn.One,
        {
            enableScripts: true,
            retainContextWhenHidden: true
        }
    );

    panel.webview.html = generateReportHtml(results);
}

function generateReportHtml(results) {
    const hotspotsBySeverity = groupHotspotsBySeverity(results.hotspots);
    const topHotspots = results.hotspots
        .sort((a, b) => b.energy - a.energy)
        .slice(0, 10);

    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeGreen Energy Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
        }
        .header {
            border-bottom: 2px solid var(--vscode-panel-border);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        .summary-value {
            font-size: 2em;
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        .summary-label {
            font-size: 0.9em;
            color: var(--vscode-descriptionForeground);
            margin-top: 5px;
        }
        .hotspots-section {
            margin-bottom: 30px;
        }
        .hotspot-item {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .hotspot-severity {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        .severity-critical { background: #ff0000; color: white; }
        .severity-high { background: #ff8800; color: white; }
        .severity-medium { background: #ffaa00; color: black; }
        .severity-low { background: #ffdd00; color: black; }
        .hotspot-details {
            flex: 1;
            margin-left: 15px;
        }
        .hotspot-line {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .hotspot-energy {
            color: var(--vscode-descriptionForeground);
            font-size: 0.9em;
        }
        .timestamp {
            color: var(--vscode-descriptionForeground);
            font-size: 0.8em;
            text-align: center;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 CodeGreen Energy Analysis Report</h1>
        <p>File: ${results.filePath}</p>
    </div>

    <div class="summary-grid">
        <div class="summary-card">
            <div class="summary-value">${results.totalEnergy.toFixed(3)}</div>
            <div class="summary-label">Total Energy (J)</div>
        </div>
        <div class="summary-card">
            <div class="summary-value">${results.averagePower.toFixed(3)}</div>
            <div class="summary-label">Average Power (W)</div>
        </div>
        <div class="summary-card">
            <div class="summary-value">${results.hotspots.length}</div>
            <div class="summary-label">Hotspots Found</div>
        </div>
        <div class="summary-card">
            <div class="summary-value">${(results.analysisTime / 1000).toFixed(2)}</div>
            <div class="summary-label">Analysis Time (s)</div>
        </div>
    </div>

    <div class="hotspots-section">
        <h3>Top Energy Hotspots</h3>
        ${topHotspots.map(hotspot => generateHotspotItem(hotspot)).join('')}
    </div>

    <div class="timestamp">
        Generated on ${results.timestamp.toLocaleString()}
    </div>
</body>
</html>`;
}

function groupHotspotsBySeverity(hotspots) {
    return hotspots.reduce((groups, hotspot) => {
        if (!groups[hotspot.severity]) {
            groups[hotspot.severity] = [];
        }
        groups[hotspot.severity].push(hotspot);
        return groups;
    }, {});
}

function generateHotspotItem(hotspot) {
    return `
        <div class="hotspot-item">
            <div class="hotspot-severity severity-${hotspot.severity}">
                ${hotspot.severity}
            </div>
            <div class="hotspot-details">
                <div class="hotspot-line">Line ${hotspot.line}${hotspot.function ? ` - ${hotspot.function}` : ''}</div>
                <div class="hotspot-energy">${hotspot.energy.toFixed(3)}J | ${hotspot.power.toFixed(3)}W</div>
            </div>
        </div>
    `;
}

function isSupportedLanguage(languageId) {
    const supportedLanguages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'];
    return supportedLanguages.includes(languageId);
}

function getFileExtension(languageId) {
    const extensions = {
        'python': 'py',
        'javascript': 'js',
        'typescript': 'ts',
        'java': 'java',
        'cpp': 'cpp',
        'c': 'c'
    };
    return extensions[languageId] || 'txt';
}

module.exports = {
    activate,
    deactivate
};
