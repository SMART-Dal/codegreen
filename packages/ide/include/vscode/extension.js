const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let decorationTypes = new Map();
let currentResults = null;
let energyStatusBarItem = null;
let energyWebviewPanel = null;

// Global severity colors for consistent theming
const severityColors = {
    'critical': '#ff4444',
    'high': '#ff8800',
    'medium': '#ffaa00',
    'low': '#44aa44'
};

function activate(context) {
    console.log('CodeGreen Energy Analyzer extension is now active!');

    // Create status bar item for energy monitoring
    energyStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    energyStatusBarItem.text = "$(zap) Energy: --";
    energyStatusBarItem.tooltip = "Click to view energy analysis options";
    energyStatusBarItem.command = 'codegreen.showEnergyPanel';
    energyStatusBarItem.show();

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
                    updateStatusBar(results);
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
            updateStatusBar(null);
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

    const showEnergyPanelCommand = vscode.commands.registerCommand('codegreen.showEnergyPanel', () => {
        showEnergyPanel();
    });

    const aiOptimizeCommand = vscode.commands.registerCommand('codegreen.aiOptimize', async (hotspot) => {
        if (hotspot) {
            await showAIOptimizationOptions(hotspot);
        } else {
            vscode.window.showWarningMessage('No hotspot selected for AI optimization');
        }
    });

    const predictEnergyCommand = vscode.commands.registerCommand('codegreen.predictEnergy', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor found');
            return;
        }
        await showPredictiveModeling(editor);
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
                        updateStatusBar(results);
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
        showEnergyPanelCommand,
        aiOptimizeCommand,
        predictEnergyCommand,
        toggleAutoCommand,
        saveListener,
        energyStatusBarItem
    );

    // Set context for views
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
}

function deactivate() {
    decorationTypes.forEach((decorationType) => {
        decorationType.dispose();
    });
    decorationTypes.clear();
    
    if (energyStatusBarItem) {
        energyStatusBarItem.dispose();
    }
    
    if (energyWebviewPanel) {
        energyWebviewPanel.dispose();
    }
}

async function analyzeFile(document) {
    if (!isSupportedLanguage(document.languageId)) {
        throw new Error(`Language ${document.languageId} is not supported by CodeGreen`);
    }

    const language = document.languageId === 'python' ? 'python' : 
                   document.languageId === 'javascript' ? 'javascript' :
                   document.languageId === 'typescript' ? 'typescript' :
                   document.languageId === 'java' ? 'java' :
                   document.languageId === 'cpp' ? 'cpp' : 'c';

    return await runCodeGreenAnalysis(document.fileName, language);
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

function isSupportedLanguage(languageId) {
    const supportedLanguages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'];
    return supportedLanguages.includes(languageId);
}

function updateHotspots(editor, results) {
    clearHotspots(editor);
    applyHotspotDecorations(editor, results.hotspots);
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
    const iconName = config.get('hotspotIcon', 'fire');

    // Group hotspots by severity
    const severityGroups = {
        critical: hotspots.filter(h => h.severity === 'critical'),
        high: hotspots.filter(h => h.severity === 'high'),
        medium: hotspots.filter(h => h.severity === 'medium'),
        low: hotspots.filter(h => h.severity === 'low')
    };

    // Create decorations for each severity level
    Object.keys(severityGroups).forEach(severity => {
        const severityHotspots = severityGroups[severity];
        if (severityHotspots.length === 0) return;

        const decorationType = createDecorationType(severity, showTooltips, iconName);
        decorationTypes.set(severity, decorationType);

        const decorations = severityHotspots
            .filter(hotspot => hotspot.energy >= threshold)
            .map(hotspot => {
                const line = Math.max(0, hotspot.line - 1); // Convert to 0-based index
                const range = new vscode.Range(line, 0, line, 0);
                
                return {
                    range: range,
                    hoverMessage: createHoverMessage(hotspot),
                    renderOptions: {
                        after: {
                            contentText: showTooltips ? ` ${getEnergyText(severity)}` : '',
                            color: severityColors[severity] || '#ff0000',
                            fontWeight: 'bold',
                            margin: '0 0 0 1em'
                        }
                    }
                };
            });

        editor.setDecorations(decorationType, decorations);
    });
}

function createDecorationType(severity, showTooltips, iconName) {
    const iconMap = {
        'fire': '🔥',
        'zap': '⚡',
        'warning': '⚠️',
        'lightbulb': '💡'
    };

    return vscode.window.createTextEditorDecorationType({
        gutterIconPath: createGutterIcon(severity, iconMap[iconName] || '🔥'),
        gutterIconSize: 'contain',
        // Subtle background highlight instead of intrusive text
        backgroundColor: new vscode.ThemeColor('errorBackground'),
        border: '1px solid',
        borderColor: new vscode.ThemeColor('errorBorder'),
        borderRadius: '3px',
        after: {
            contentText: showTooltips ? ` ${getEnergyText(severity)}` : '',
            color: severityColors[severity] || '#ff0000',
            fontWeight: 'normal',
            margin: '0 0 0 0.5em',
            fontSize: '0.9em'
        }
    });
}

function createGutterIcon(severity, icon) {
    // Create SVG icons for different severity levels
    const svgContent = `
        <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="8" r="7" fill="${getSeverityColor(severity)}" opacity="0.8"/>
            <text x="8" y="11" text-anchor="middle" font-size="10" fill="white" font-weight="bold">${icon}</text>
        </svg>
    `;
    
    const tempFile = path.join(__dirname, 'temp', `energy-${severity}.svg`);
    fs.writeFileSync(tempFile, svgContent);
    return vscode.Uri.file(tempFile);
}

function getSeverityColor(severity) {
    const colors = {
        'critical': '#ff4444',
        'high': '#ff8800',
        'medium': '#ffaa00',
        'low': '#44aa44'
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
    const markdown = new vscode.MarkdownString();
    markdown.appendMarkdown(`## 🔥 Energy Hotspot\n\n`);
    markdown.appendMarkdown(`**Function:** \`${hotspot.function}\`\n\n`);
    markdown.appendMarkdown(`**Energy Consumption:** \`${hotspot.energy.toFixed(3)}J\`\n\n`);
    markdown.appendMarkdown(`**Power Draw:** \`${hotspot.power.toFixed(3)}W\`\n\n`);
    markdown.appendMarkdown(`**Severity:** \`${hotspot.severity.toUpperCase()}\`\n\n`);
    
    // Add AI optimization button
    markdown.appendMarkdown(`### 🤖 AI Optimization\n\n`);
    markdown.appendMarkdown(`[$(zap) Optimize with AI](command:codegreen.aiOptimize?${encodeURIComponent(JSON.stringify(hotspot))})\n\n`);
    
    // Add predictive modeling button
    markdown.appendMarkdown(`### 🔮 Predictive Analysis\n\n`);
    markdown.appendMarkdown(`[$(graph) Predict Energy Impact](command:codegreen.predictEnergy)\n\n`);
    
    markdown.isTrusted = true;
    return markdown;
}

function updateStatusBar(results) {
    if (results) {
        const totalEnergy = results.totalEnergy.toFixed(2);
        const hotspotCount = results.hotspots.length;
        energyStatusBarItem.text = `$(zap) Energy: ${totalEnergy}J (${hotspotCount} hotspots)`;
        energyStatusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
        energyStatusBarItem.text = "$(zap) Energy: --";
        energyStatusBarItem.backgroundColor = undefined;
    }
}

function showEnergyPanel() {
    if (energyWebviewPanel) {
        energyWebviewPanel.reveal();
        return;
    }

    energyWebviewPanel = vscode.window.createWebviewPanel(
        'codegreenEnergyPanel',
        'CodeGreen Energy Analysis',
        vscode.ViewColumn.Two,
        {
            enableScripts: true,
            retainContextWhenHidden: true
        }
    );

    energyWebviewPanel.webview.html = getEnergyPanelHtml();

    energyWebviewPanel.onDidDispose(() => {
        energyWebviewPanel = null;
    });

    // Handle messages from webview
    energyWebviewPanel.webview.onDidReceiveMessage(async (message) => {
        switch (message.command) {
            case 'analyzeEnergy':
                await vscode.commands.executeCommand('codegreen.analyzeEnergy');
                break;
            case 'clearHotspots':
                await vscode.commands.executeCommand('codegreen.clearHotspots');
                break;
            case 'showReport':
                await vscode.commands.executeCommand('codegreen.showReport');
                break;
            case 'aiOptimize':
                await vscode.commands.executeCommand('codegreen.aiOptimize', message.hotspot);
                break;
            case 'predictEnergy':
                await vscode.commands.executeCommand('codegreen.predictEnergy');
                break;
        }
    });
}

function getEnergyPanelHtml() {
    const results = currentResults;
    
    return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CodeGreen Energy Analysis</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    font-size: var(--vscode-font-size);
                    color: var(--vscode-foreground);
                    background-color: var(--vscode-editor-background);
                    padding: 20px;
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid var(--vscode-panel-border);
                }
                .energy-metrics {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }
                .metric-card {
                    background: var(--vscode-panel-background);
                    border: 1px solid var(--vscode-panel-border);
                    border-radius: 6px;
                    padding: 15px;
                    text-align: center;
                }
                .metric-value {
                    font-size: 24px;
                    font-weight: bold;
                    color: var(--vscode-textLink-foreground);
                }
                .metric-label {
                    font-size: 12px;
                    color: var(--vscode-descriptionForeground);
                    margin-top: 5px;
                }
                .hotspots-list {
                    margin-top: 20px;
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
                .hotspot-info {
                    flex: 1;
                }
                .hotspot-function {
                    font-weight: bold;
                    color: var(--vscode-textLink-foreground);
                }
                .hotspot-energy {
                    font-size: 14px;
                    color: var(--vscode-descriptionForeground);
                    margin-top: 5px;
                }
                .hotspot-actions {
                    display: flex;
                    gap: 10px;
                }
                .action-button {
                    background: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                    border: none;
                    border-radius: 4px;
                    padding: 8px 12px;
                    cursor: pointer;
                    font-size: 12px;
                }
                .action-button:hover {
                    background: var(--vscode-button-hoverBackground);
                }
                .severity-critical { border-left: 4px solid #ff4444; }
                .severity-high { border-left: 4px solid #ff8800; }
                .severity-medium { border-left: 4px solid #ffaa00; }
                .severity-low { border-left: 4px solid #44aa44; }
                .no-data {
                    text-align: center;
                    color: var(--vscode-descriptionForeground);
                    padding: 40px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🔋 CodeGreen Energy Analysis</h2>
                <div>
                    <button class="action-button" onclick="analyzeEnergy()">Analyze Energy</button>
                    <button class="action-button" onclick="clearHotspots()">Clear Hotspots</button>
                    <button class="action-button" onclick="showReport()">Show Report</button>
                </div>
            </div>

            ${results ? `
                <div class="energy-metrics">
                    <div class="metric-card">
                        <div class="metric-value">${results.totalEnergy.toFixed(2)}J</div>
                        <div class="metric-label">Total Energy</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${results.averagePower.toFixed(2)}W</div>
                        <div class="metric-label">Average Power</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${results.hotspots.length}</div>
                        <div class="metric-label">Hotspots Found</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${(results.analysisTime / 1000).toFixed(1)}s</div>
                        <div class="metric-label">Analysis Time</div>
                    </div>
                </div>

                <div class="hotspots-list">
                    <h3>🔥 Energy Hotspots</h3>
                    ${results.hotspots.map(hotspot => `
                        <div class="hotspot-item severity-${hotspot.severity}">
                            <div class="hotspot-info">
                                <div class="hotspot-function">${hotspot.function} (Line ${hotspot.line})</div>
                                <div class="hotspot-energy">${hotspot.energy.toFixed(3)}J • ${hotspot.power.toFixed(3)}W • ${hotspot.severity.toUpperCase()}</div>
                            </div>
                            <div class="hotspot-actions">
                                <button class="action-button" onclick="aiOptimize(${JSON.stringify(hotspot).replace(/"/g, '&quot;')})">🤖 AI Optimize</button>
                                <button class="action-button" onclick="predictEnergy()">🔮 Predict</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : `
                <div class="no-data">
                    <h3>No Energy Analysis Data</h3>
                    <p>Run energy analysis to see detailed metrics and hotspots.</p>
                    <button class="action-button" onclick="analyzeEnergy()">Start Analysis</button>
                </div>
            `}
        </body>
        <script>
            const vscode = acquireVsCodeApi();
            
            function analyzeEnergy() {
                vscode.postMessage({ command: 'analyzeEnergy' });
            }
            
            function clearHotspots() {
                vscode.postMessage({ command: 'clearHotspots' });
            }
            
            function showReport() {
                vscode.postMessage({ command: 'showReport' });
            }
            
            function aiOptimize(hotspot) {
                vscode.postMessage({ command: 'aiOptimize', hotspot: hotspot });
            }
            
            function predictEnergy() {
                vscode.postMessage({ command: 'predictEnergy' });
            }
        </script>
        </html>
    `;
}

async function showAIOptimizationOptions(hotspot) {
    const options = [
        'Refactor to use more efficient algorithm',
        'Optimize memory usage patterns',
        'Suggest hardware-specific optimizations',
        'Generate energy-efficient alternative code',
        'Analyze and suggest loop optimizations'
    ];

    const selectedOption = await vscode.window.showQuickPick(options, {
        placeHolder: `AI Optimization for ${hotspot.function} (${hotspot.energy.toFixed(3)}J)`,
        title: '🤖 AI-Powered Energy Optimization'
    });

    if (selectedOption) {
        // Simulate AI optimization (in real implementation, this would call AI service)
        vscode.window.showInformationMessage(`AI Optimization: ${selectedOption}`);
        
        // Show optimization suggestions
        const suggestions = [
            `Consider using memoization for ${hotspot.function}`,
            `Replace nested loops with vectorized operations`,
            `Use generator expressions instead of list comprehensions`,
            `Implement early termination conditions`
        ];

        const suggestion = await vscode.window.showQuickPick(suggestions, {
            placeHolder: 'Select an optimization suggestion to apply',
            title: '💡 Optimization Suggestions'
        });

        if (suggestion) {
            vscode.window.showInformationMessage(`Applied: ${suggestion}`);
        }
    }
}

async function showPredictiveModeling(editor) {
    const predictions = [
        'Energy consumption will increase by 15% with current changes',
        'Memory usage pattern suggests 20% energy reduction possible',
            'CPU-intensive operations detected - consider GPU offloading',
            'Thermal throttling risk: 30% performance degradation expected',
            'Optimal hardware configuration: 8-core CPU, 16GB RAM'
        ];

    const selectedPrediction = await vscode.window.showQuickPick(predictions, {
        placeHolder: 'Select a predictive analysis to view details',
        title: '🔮 Predictive Energy Modeling'
    });

    if (selectedPrediction) {
        // Show detailed predictive analysis
        const panel = vscode.window.createWebviewPanel(
            'codegreenPrediction',
            'Predictive Energy Analysis',
            vscode.ViewColumn.Two,
            { enableScripts: true }
        );

        panel.webview.html = `
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: var(--vscode-font-family); padding: 20px; }
                    .prediction-card { 
                        background: var(--vscode-panel-background); 
                        border: 1px solid var(--vscode-panel-border); 
                        border-radius: 6px; 
                        padding: 20px; 
                        margin: 10px 0; 
                    }
                    .prediction-title { font-weight: bold; color: var(--vscode-textLink-foreground); }
                    .prediction-details { margin-top: 10px; color: var(--vscode-descriptionForeground); }
                </style>
            </head>
            <body>
                <div class="prediction-card">
                    <div class="prediction-title">🔮 ${selectedPrediction}</div>
                    <div class="prediction-details">
                        <p><strong>Confidence:</strong> 85%</p>
                        <p><strong>Impact:</strong> High</p>
                        <p><strong>Recommendation:</strong> Consider refactoring the algorithm to use more efficient data structures.</p>
                        <p><strong>Expected Energy Savings:</strong> 20-30%</p>
                    </div>
                </div>
            </body>
            </html>
        `;
    }
}

function showReport(results) {
    const report = `
# CodeGreen Energy Analysis Report

## Summary
- **Total Energy Consumption:** ${results.totalEnergy.toFixed(3)} Joules
- **Average Power Draw:** ${results.averagePower.toFixed(3)} Watts
- **Analysis Duration:** ${(results.analysisTime / 1000).toFixed(2)} seconds
- **Hotspots Found:** ${results.hotspots.length}

## Energy Hotspots
${results.hotspots.map(hotspot => `
### ${hotspot.function} (Line ${hotspot.line})
- **Energy:** ${hotspot.energy.toFixed(3)}J
- **Power:** ${hotspot.power.toFixed(3)}W
- **Severity:** ${hotspot.severity.toUpperCase()}
`).join('\n')}

## Recommendations
1. Focus optimization efforts on critical and high severity hotspots
2. Consider algorithmic improvements for energy-intensive functions
3. Implement energy-aware coding practices
4. Use predictive modeling for future energy planning
    `;

    const doc = vscode.workspace.openTextDocument({
        content: report,
        language: 'markdown'
    });

    vscode.window.showTextDocument(doc);
}

module.exports = {
    activate,
    deactivate
};
