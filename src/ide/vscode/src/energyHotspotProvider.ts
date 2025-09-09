import * as vscode from 'vscode';
import { EnergyAnalysisResult, EnergyHotspot } from './codegreenAnalyzer';

export class EnergyHotspotProvider implements vscode.TreeDataProvider<EnergyHotspotItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<EnergyHotspotItem | undefined | null | void> = new vscode.EventEmitter<EnergyHotspotItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<EnergyHotspotItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private context: vscode.ExtensionContext;
    private currentResults: EnergyAnalysisResult | null = null;
    private decorationTypes: Map<string, vscode.TextEditorDecorationType> = new Map();

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    updateHotspots(editor: vscode.TextEditor, results: EnergyAnalysisResult) {
        this.currentResults = results;
        this._onDidChangeTreeData.fire();
        
        // Clear existing decorations
        this.clearHotspots(editor);
        
        // Apply new decorations
        this.applyHotspotDecorations(editor, results.hotspots);
        
        // Update context
        vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', true);
    }

    clearHotspots(editor: vscode.TextEditor) {
        // Clear all decorations
        this.decorationTypes.forEach((decorationType) => {
            editor.setDecorations(decorationType, []);
        });
        this.decorationTypes.clear();
        
        this.currentResults = null;
        this._onDidChangeTreeData.fire();
        vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
    }

    private applyHotspotDecorations(editor: vscode.TextEditor, hotspots: EnergyHotspot[]) {
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

            const decorationType = this.createDecorationType(severity, showTooltips);
            this.decorationTypes.set(severity, decorationType);

            const decorations: vscode.DecorationOptions[] = severityHotspots
                .filter(hotspot => hotspot.energy >= threshold)
                .map(hotspot => {
                    const line = Math.max(0, hotspot.line - 1); // Convert to 0-based index
                    const range = new vscode.Range(line, 0, line, 0);
                    
                    return {
                        range: range,
                        hoverMessage: showTooltips ? this.createHoverMessage(hotspot) : undefined
                    };
                });

            editor.setDecorations(decorationType, decorations);
        });
    }

    private createDecorationType(severity: string, showTooltips: boolean): vscode.TextEditorDecorationType {
        const config = vscode.workspace.getConfiguration('codegreen');
        const iconName = config.get('hotspotIcon', 'flame');

        const iconMap: { [key: string]: string } = {
            'flame': '🔥',
            'zap': '⚡',
            'alert': '⚠️',
            'warning': '⚠️'
        };

        const severityColors: { [key: string]: string } = {
            'critical': '#ff0000',
            'high': '#ff8800',
            'medium': '#ffaa00',
            'low': '#ffdd00'
        };

        return vscode.window.createTextEditorDecorationType({
            gutterIconPath: this.createGutterIcon(severity, iconMap[iconName] || '🔥'),
            gutterIconSize: 'contain',
            after: {
                contentText: showTooltips ? ` ${this.getEnergyText(severity)}` : '',
                color: severityColors[severity] || '#ff0000',
                fontWeight: 'bold',
                margin: '0 0 0 1em'
            }
        });
    }

    private createGutterIcon(severity: string, icon: string): vscode.Uri {
        // Create a simple SVG icon
        const svg = `
            <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                <text x="8" y="12" text-anchor="middle" font-size="12" fill="${this.getSeverityColor(severity)}">${icon}</text>
            </svg>
        `;
        
        const iconPath = vscode.Uri.parse(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
        return iconPath;
    }

    private getSeverityColor(severity: string): string {
        const colors: { [key: string]: string } = {
            'critical': '#ff0000',
            'high': '#ff8800',
            'medium': '#ffaa00',
            'low': '#ffdd00'
        };
        return colors[severity] || '#ff0000';
    }

    private getEnergyText(severity: string): string {
        const texts: { [key: string]: string } = {
            'critical': 'CRITICAL',
            'high': 'HIGH',
            'medium': 'MED',
            'low': 'LOW'
        };
        return texts[severity] || 'ENERGY';
    }

    private createHoverMessage(hotspot: EnergyHotspot): vscode.MarkdownString {
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

    getTreeItem(element: EnergyHotspotItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: EnergyHotspotItem): Thenable<EnergyHotspotItem[]> {
        if (!this.currentResults) {
            return Promise.resolve([]);
        }

        if (!element) {
            // Root level - show summary
            return Promise.resolve([
                new EnergyHotspotItem(
                    `Total Energy: ${this.currentResults.totalEnergy.toFixed(3)} J`,
                    vscode.TreeItemCollapsibleState.None,
                    'summary'
                ),
                new EnergyHotspotItem(
                    `Average Power: ${this.currentResults.averagePower.toFixed(3)} W`,
                    vscode.TreeItemCollapsibleState.None,
                    'summary'
                ),
                new EnergyHotspotItem(
                    `Hotspots: ${this.currentResults.hotspots.length}`,
                    vscode.TreeItemCollapsibleState.Expanded,
                    'hotspots'
                )
            ]);
        }

        if (element.contextValue === 'hotspots') {
            // Show individual hotspots
            return Promise.resolve(
                this.currentResults.hotspots.map((hotspot, index) => 
                    new EnergyHotspotItem(
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
        this.decorationTypes.forEach((decorationType) => {
            decorationType.dispose();
        });
        this.decorationTypes.clear();
    }
}

class EnergyHotspotItem extends vscode.TreeItem {
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
            case 'summary':
                return new vscode.ThemeIcon('graph');
            case 'hotspots':
                return new vscode.ThemeIcon('zap');
            case 'hotspot':
                return new vscode.ThemeIcon('flame');
            default:
                return undefined;
        }
    }
}
