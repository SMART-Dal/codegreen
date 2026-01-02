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
        
        this.clearHotspots(editor);
        this.applyHotspotDecorations(editor, results.hotspots);
        
        vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', true);
    }

    clearHotspots(editor: vscode.TextEditor) {
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

        const severityGroups = {
            critical: hotspots.filter(h => h.severity === 'critical'),
            high: hotspots.filter(h => h.severity === 'high'),
            medium: hotspots.filter(h => h.severity === 'medium'),
            low: hotspots.filter(h => h.severity === 'low')
        };

        Object.entries(severityGroups).forEach(([severity, severityHotspots]) => {
            if (severityHotspots.length === 0) return;

            const decorationType = this.createDecorationType(severity);
            this.decorationTypes.set(severity, decorationType);

            const decorations: vscode.DecorationOptions[] = severityHotspots
                .filter(hotspot => hotspot.energy >= threshold)
                .map(hotspot => {
                    const line = Math.max(0, hotspot.line - 1);
                    const range = new vscode.Range(line, 0, line, 0);
                    
                    return {
                        range: range,
                        hoverMessage: this.createHoverMessage(hotspot)
                    };
                });

            editor.setDecorations(decorationType, decorations);
        });
    }

    private createDecorationType(severity: string): vscode.TextEditorDecorationType {
        const severityColors: { [key: string]: string } = {
            'critical': '#ff4444',
            'high': '#ff8800',
            'medium': '#ffaa00',
            'low': '#44aa44'
        };

        // We use a fire emoji in the gutter icon
        const gutterIcon = this.createGutterIcon(severity, '🔥');
        
        return vscode.window.createTextEditorDecorationType({
            gutterIconPath: gutterIcon,
            gutterIconSize: 'contain',
            after: {
                contentText: ` 🔥 ${this.getEnergyText(severity)}`,
                color: severityColors[severity] || '#ff0000',
                fontWeight: 'bold',
                margin: '0 0 0 1em',
                textDecoration: 'none; cursor: pointer;'
            }
        });
    }

    private createGutterIcon(severity: string, icon: string): vscode.Uri {
        const color = this.getSeverityColor(severity);
        const svg = `
            <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                <text x="8" y="12" text-anchor="middle" font-family="Arial" font-size="12" fill="${color}">${icon}</text>
            </svg>
        `;
        return vscode.Uri.parse(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
    }

    private getSeverityColor(severity: string): string {
        const colors: { [key: string]: string } = {
            'critical': '#ff4444',
            'high': '#ff8800',
            'medium': '#ffaa00',
            'low': '#44aa44'
        };
        return colors[severity] || '#ff0000';
    }

    private getEnergyText(severity: string): string {
        const texts: { [key: string]: string } = {
            'critical': 'CRITICAL ENERGY',
            'high': 'HIGH ENERGY',
            'medium': 'MEDIUM ENERGY',
            'low': 'LOW ENERGY'
        };
        return texts[severity] || 'ENERGY';
    }

    private createHoverMessage(hotspot: EnergyHotspot): vscode.MarkdownString {
        const message = new vscode.MarkdownString();
        message.appendMarkdown(`## 🔥 CodeGreen Energy Analysis\n\n`);
        message.appendMarkdown(`**Function:** \`${hotspot.function}\`\n\n`);
        message.appendMarkdown(`**Energy:** \`${hotspot.energy.toFixed(3)} J\`\n\n`);
        message.appendMarkdown(`**Power:** \`${hotspot.power.toFixed(3)} W\`\n\n`);
        message.appendMarkdown(`**Severity:** \`${hotspot.severity.toUpperCase()}\`\n\n`);
        
        message.appendMarkdown(`---\n\n`);
        message.appendMarkdown(`[$(zap) Click to Optimize with AI](command:codegreen.optimizeFunction?${encodeURIComponent(JSON.stringify(hotspot))})`);
        
        message.isTrusted = true;
        return message;
    }

    getTreeItem(element: EnergyHotspotItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: EnergyHotspotItem): Thenable<EnergyHotspotItem[]> {
        if (!this.currentResults) return Promise.resolve([]);

        if (!element) {
            return Promise.resolve([
                new EnergyHotspotItem(
                    `Total: ${this.currentResults.totalEnergy.toFixed(3)} J`,
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
            return Promise.resolve(
                this.currentResults.hotspots.map(hotspot => 
                    new EnergyHotspotItem(
                        `Line ${hotspot.line}: ${hotspot.function}`,
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
        this.decorationTypes.forEach(d => d.dispose());
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
        if (hotspot) {
            this.command = {
                command: 'codegreen.optimizeFunction',
                title: 'Optimize',
                arguments: [hotspot]
            };
        }
    }

    iconPath = this.getIcon();

    private getIcon() {
        switch (this.contextValue) {
            case 'summary': return new vscode.ThemeIcon('graph');
            case 'hotspots': return new vscode.ThemeIcon('zap');
            case 'hotspot': return new vscode.ThemeIcon('flame');
            default: return undefined;
        }
    }
}