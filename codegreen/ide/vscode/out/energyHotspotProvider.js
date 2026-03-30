"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
 if (k2 === undefined) k2 = k;
 var desc = Object.getOwnPropertyDescriptor(m, k);
 if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
 desc = { enumerable: true, get: function() { return m[k]; } };
 }
 Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
 if (k2 === undefined) k2 = k;
 o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
 Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
 o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
 var ownKeys = function(o) {
 ownKeys = Object.getOwnPropertyNames || function (o) {
 var ar = [];
 for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
 return ar;
 };
 return ownKeys(o);
 };
 return function (mod) {
 if (mod && mod.__esModule) return mod;
 var result = {};
 if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
 __setModuleDefault(result, mod);
 return result;
 };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.EnergyHotspotProvider = void 0;
const vscode = __importStar(require("vscode"));
class EnergyHotspotProvider {
 constructor(context) {
 this._onDidChangeTreeData = new vscode.EventEmitter();
 this.onDidChangeTreeData = this._onDidChangeTreeData.event;
 this.currentResults = null;
 this.decorationTypes = new Map();
 this.context = context;
 }
 updateHotspots(editor, results) {
 this.currentResults = results;
 this._onDidChangeTreeData.fire();
 this.clearHotspots(editor);
 this.applyHotspotDecorations(editor, results.hotspots);
 vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', true);
 }
 clearHotspots(editor) {
 this.decorationTypes.forEach((decorationType) => {
 editor.setDecorations(decorationType, []);
 });
 this.decorationTypes.clear();
 this.currentResults = null;
 this._onDidChangeTreeData.fire();
 vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
 }
 applyHotspotDecorations(editor, hotspots) {
 const config = vscode.workspace.getConfiguration('codegreen');
 const threshold = config.get('energyThreshold', 0.1);
 const severityGroups = {
 critical: hotspots.filter(h => h.severity === 'critical'),
 high: hotspots.filter(h => h.severity === 'high'),
 medium: hotspots.filter(h => h.severity === 'medium'),
 low: hotspots.filter(h => h.severity === 'low')
 };
 Object.entries(severityGroups).forEach(([severity, severityHotspots]) => {
 if (severityHotspots.length === 0)
 return;
 const decorationType = this.createDecorationType(severity);
 this.decorationTypes.set(severity, decorationType);
 const decorations = severityHotspots
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
 createDecorationType(severity) {
 const severityColors = {
 'critical': '#ff4444',
 'high': '#ff8800',
 'medium': '#ffaa00',
 'low': '#44aa44'
 };
 // We use a fire emoji in the gutter icon
 const gutterIcon = this.createGutterIcon(severity, '');
 return vscode.window.createTextEditorDecorationType({
 gutterIconPath: gutterIcon,
 gutterIconSize: 'contain',
 after: {
 contentText: ` ${this.getEnergyText(severity)}`,
 color: severityColors[severity] || '#ff0000',
 fontWeight: 'bold',
 margin: '0 0 0 1em',
 textDecoration: 'none; cursor: pointer;'
 }
 });
 }
 createGutterIcon(severity, icon) {
 const color = this.getSeverityColor(severity);
 const svg = `
 <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
 <text x="8" y="12" text-anchor="middle" font-family="Arial" font-size="12" fill="${color}">${icon}</text>
 </svg>
 `;
 return vscode.Uri.parse(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
 }
 getSeverityColor(severity) {
 const colors = {
 'critical': '#ff4444',
 'high': '#ff8800',
 'medium': '#ffaa00',
 'low': '#44aa44'
 };
 return colors[severity] || '#ff0000';
 }
 getEnergyText(severity) {
 const texts = {
 'critical': 'CRITICAL ENERGY',
 'high': 'HIGH ENERGY',
 'medium': 'MEDIUM ENERGY',
 'low': 'LOW ENERGY'
 };
 return texts[severity] || 'ENERGY';
 }
 createHoverMessage(hotspot) {
 const message = new vscode.MarkdownString();
 message.appendMarkdown(`## CodeGreen Energy Analysis\n\n`);
 message.appendMarkdown(`**Function:** \`${hotspot.function}\`\n\n`);
 message.appendMarkdown(`**Energy:** \`${hotspot.energy.toFixed(3)} J\`\n\n`);
 message.appendMarkdown(`**Power:** \`${hotspot.power.toFixed(3)} W\`\n\n`);
 message.appendMarkdown(`**Severity:** \`${hotspot.severity.toUpperCase()}\`\n\n`);
 message.appendMarkdown(`---\n\n`);
 message.appendMarkdown(`[$(zap) Click to Optimize with AI](command:codegreen.optimizeFunction?${encodeURIComponent(JSON.stringify(hotspot))})`);
 message.isTrusted = true;
 return message;
 }
 getTreeItem(element) {
 return element;
 }
 getChildren(element) {
 if (!this.currentResults)
 return Promise.resolve([]);
 if (!element) {
 return Promise.resolve([
 new EnergyHotspotItem(`Total: ${this.currentResults.totalEnergy.toFixed(3)} J`, vscode.TreeItemCollapsibleState.None, 'summary'),
 new EnergyHotspotItem(`Hotspots: ${this.currentResults.hotspots.length}`, vscode.TreeItemCollapsibleState.Expanded, 'hotspots')
 ]);
 }
 if (element.contextValue === 'hotspots') {
 return Promise.resolve(this.currentResults.hotspots.map(hotspot => new EnergyHotspotItem(`Line ${hotspot.line}: ${hotspot.function}`, vscode.TreeItemCollapsibleState.None, 'hotspot', hotspot)));
 }
 return Promise.resolve([]);
 }
 dispose() {
 this.decorationTypes.forEach(d => d.dispose());
 this.decorationTypes.clear();
 }
}
exports.EnergyHotspotProvider = EnergyHotspotProvider;
class EnergyHotspotItem extends vscode.TreeItem {
 constructor(label, collapsibleState, contextValue, hotspot) {
 super(label, collapsibleState);
 this.label = label;
 this.collapsibleState = collapsibleState;
 this.contextValue = contextValue;
 this.hotspot = hotspot;
 this.iconPath = this.getIcon();
 if (hotspot) {
 this.command = {
 command: 'codegreen.optimizeFunction',
 title: 'Optimize',
 arguments: [hotspot]
 };
 }
 }
 getIcon() {
 switch (this.contextValue) {
 case 'summary': return new vscode.ThemeIcon('graph');
 case 'hotspots': return new vscode.ThemeIcon('zap');
 case 'hotspot': return new vscode.ThemeIcon('flame');
 default: return undefined;
 }
 }
}
//# sourceMappingURL=energyHotspotProvider.js.map