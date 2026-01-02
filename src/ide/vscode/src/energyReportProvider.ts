import * as vscode from 'vscode';
import { EnergyAnalysisResult } from './codegreenAnalyzer';

export class EnergyReportProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | null | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private currentResults: EnergyAnalysisResult | null = null;

    constructor(private context: vscode.ExtensionContext) {}

    updateReport(results: EnergyAnalysisResult) {
        this.currentResults = results;
        this._onDidChangeTreeData.fire();
    }

    clearReport() {
        this.currentResults = null;
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: vscode.TreeItem): Thenable<vscode.TreeItem[]> {
        if (!this.currentResults) return Promise.resolve([]);

        if (!element) {
            return Promise.resolve([
                new vscode.TreeItem('Analysis Summary', vscode.TreeItemCollapsibleState.Expanded),
                new vscode.TreeItem('Optimization Recommendations', vscode.TreeItemCollapsibleState.Collapsed)
            ]);
        }

        if (element.label === 'Analysis Summary') {
            const items = [
                new vscode.TreeItem(`Energy: ${this.currentResults.totalEnergy.toFixed(3)} J`),
                new vscode.TreeItem(`Avg Power: ${this.currentResults.averagePower.toFixed(3)} W`),
                new vscode.TreeItem(`Analysis Time: ${this.currentResults.analysisTime} ms`)
            ];
            return Promise.resolve(items);
        }

        return Promise.resolve([]);
    }

    showReport() {
        if (!this.currentResults) {
            vscode.window.showWarningMessage("No energy results available to show.");
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'codegreenReport',
            'CodeGreen Detailed Energy Report',
            vscode.ViewColumn.Beside,
            { enableScripts: true }
        );

        panel.webview.html = this.getReportHtml(this.currentResults);
    }

    private getReportHtml(results: EnergyAnalysisResult): string {
        return `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <style>
                    body { font-family: sans-serif; padding: 20px; line-height: 1.6; }
                    .card { background: #333; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
                    .hotspot { border-left: 4px solid #ff4444; padding-left: 15px; margin-bottom: 10px; }
                    h1 { color: #4CAF50; }
                </style>
            </head>
            <body>
                <h1>🌱 CodeGreen Energy Report</h1>
                <div class="card">
                    <h2>Total Consumption: ${results.totalEnergy.toFixed(3)} Joules</h2>
                    <p>File: ${results.filePath}</p>
                    <p>Measured at: ${results.timestamp.toLocaleString()}</p>
                </div>
                
                <h3>🔥 Energy Hotspots</h3>
                ${results.hotspots.map(h => `
                    <div class="hotspot">
                        <strong>${h.function || 'Unknown Function'}</strong> (Line ${h.line})<br>
                        Energy: ${h.energy.toFixed(3)} J | Severity: ${h.severity.toUpperCase()}
                    </div>
                `).join('')}
            </body>
            </html>
        `;
    }

    dispose() {}
}