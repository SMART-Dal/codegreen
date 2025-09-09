import * as vscode from 'vscode';
import { EnergyAnalysisResult, EnergyHotspot } from './codegreenAnalyzer';

export class EnergyReportProvider implements vscode.TreeDataProvider<EnergyReportItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<EnergyReportItem | undefined | null | void> = new vscode.EventEmitter<EnergyReportItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<EnergyReportItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private context: vscode.ExtensionContext;
    private currentResults: EnergyAnalysisResult | null = null;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    updateReport(results: EnergyAnalysisResult) {
        this.currentResults = results;
        this._onDidChangeTreeData.fire();
    }

    clearReport() {
        this.currentResults = null;
        this._onDidChangeTreeData.fire();
    }

    showReport() {
        if (!this.currentResults) {
            vscode.window.showWarningMessage('No energy analysis data available. Run analysis first.');
            return;
        }

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

        panel.webview.html = this.generateReportHtml(this.currentResults);
    }

    private generateReportHtml(results: EnergyAnalysisResult): string {
        const hotspotsBySeverity = this.groupHotspotsBySeverity(results.hotspots);
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
        .chart-container {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .chart-bar {
            background: var(--vscode-progressBar-background);
            height: 20px;
            border-radius: 10px;
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        .chart-fill {
            height: 100%;
            background: linear-gradient(90deg, #ffdd00, #ffaa00, #ff8800, #ff0000);
            border-radius: 10px;
            transition: width 0.3s ease;
        }
        .chart-label {
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.8em;
            font-weight: bold;
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
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

    <div class="chart-container">
        <h3>Energy Distribution by Severity</h3>
        ${this.generateSeverityChart(hotspotsBySeverity)}
    </div>

    <div class="hotspots-section">
        <h3>Top Energy Hotspots</h3>
        ${topHotspots.map(hotspot => this.generateHotspotItem(hotspot)).join('')}
    </div>

    <div class="timestamp">
        Generated on ${results.timestamp.toLocaleString()}
    </div>

    <script>
        // Add any interactive functionality here
        console.log('CodeGreen Energy Report loaded');
    </script>
</body>
</html>`;
    }

    private groupHotspotsBySeverity(hotspots: EnergyHotspot[]): { [key: string]: EnergyHotspot[] } {
        return hotspots.reduce((groups, hotspot) => {
            if (!groups[hotspot.severity]) {
                groups[hotspot.severity] = [];
            }
            groups[hotspot.severity].push(hotspot);
            return groups;
        }, {} as { [key: string]: EnergyHotspot[] });
    }

    private generateSeverityChart(hotspotsBySeverity: { [key: string]: EnergyHotspot[] }): string {
        const totalHotspots = Object.values(hotspotsBySeverity).reduce((sum, hotspots) => sum + hotspots.length, 0);
        
        return Object.entries(hotspotsBySeverity)
            .map(([severity, hotspots]) => {
                const percentage = (hotspots.length / totalHotspots) * 100;
                return `
                    <div class="chart-bar">
                        <div class="chart-fill" style="width: ${percentage}%"></div>
                        <div class="chart-label">${severity.toUpperCase()}: ${hotspots.length} (${percentage.toFixed(1)}%)</div>
                    </div>
                `;
            })
            .join('');
    }

    private generateHotspotItem(hotspot: EnergyHotspot): string {
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

    getTreeItem(element: EnergyReportItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: EnergyReportItem): Thenable<EnergyReportItem[]> {
        if (!this.currentResults) {
            return Promise.resolve([
                new EnergyReportItem(
                    'No analysis data available',
                    vscode.TreeItemCollapsibleState.None,
                    'empty'
                )
            ]);
        }

        if (!element) {
            return Promise.resolve([
                new EnergyReportItem(
                    `File: ${this.currentResults.filePath}`,
                    vscode.TreeItemCollapsibleState.None,
                    'file'
                ),
                new EnergyReportItem(
                    `Total Energy: ${this.currentResults.totalEnergy.toFixed(3)} J`,
                    vscode.TreeItemCollapsibleState.None,
                    'energy'
                ),
                new EnergyReportItem(
                    `Hotspots: ${this.currentResults.hotspots.length}`,
                    vscode.TreeItemCollapsibleState.Expanded,
                    'hotspots'
                )
            ]);
        }

        if (element.contextValue === 'hotspots') {
            return Promise.resolve(
                this.currentResults.hotspots
                    .sort((a, b) => b.energy - a.energy)
                    .map(hotspot => 
                        new EnergyReportItem(
                            `Line ${hotspot.line}: ${hotspot.energy.toFixed(3)}J (${hotspot.severity})`,
                            vscode.TreeItemCollapsibleState.None,
                            'hotspot',
                            hotspot
                        )
                    )
            );
        }

        return Promise.resolve([]);
    }

    dispose() {
        // Clean up resources
    }
}

class EnergyReportItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly contextValue: string,
        public readonly hotspot?: EnergyHotspot
    ) {
        super(label, collapsibleState);
        
        this.tooltip = hotspot ? 
            `Energy: ${hotspot.energy.toFixed(3)}J, Power: ${hotspot.power.toFixed(3)}W` : 
            this.label;
        
        this.iconPath = this.getIcon();
    }

    private getIcon(): vscode.ThemeIcon | undefined {
        switch (this.contextValue) {
            case 'file':
                return new vscode.ThemeIcon('file');
            case 'energy':
                return new vscode.ThemeIcon('graph');
            case 'hotspots':
                return new vscode.ThemeIcon('zap');
            case 'hotspot':
                return new vscode.ThemeIcon('flame');
            case 'empty':
                return new vscode.ThemeIcon('info');
            default:
                return undefined;
        }
    }
}
