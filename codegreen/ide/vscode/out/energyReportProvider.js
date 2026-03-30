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
exports.EnergyReportProvider = void 0;
const vscode = __importStar(require("vscode"));
class EnergyReportProvider {
 constructor(context) {
 this.context = context;
 this._onDidChangeTreeData = new vscode.EventEmitter();
 this.onDidChangeTreeData = this._onDidChangeTreeData.event;
 this.currentResults = null;
 }
 updateReport(results) {
 this.currentResults = results;
 this._onDidChangeTreeData.fire();
 }
 clearReport() {
 this.currentResults = null;
 this._onDidChangeTreeData.fire();
 }
 getTreeItem(element) {
 return element;
 }
 getChildren(element) {
 if (!this.currentResults)
 return Promise.resolve([]);
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
 const panel = vscode.window.createWebviewPanel('codegreenReport', 'CodeGreen Detailed Energy Report', vscode.ViewColumn.Beside, { enableScripts: true });
 panel.webview.html = this.getReportHtml(this.currentResults);
 }
 getReportHtml(results) {
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
 <h1> CodeGreen Energy Report</h1>
 <div class="card">
 <h2>Total Consumption: ${results.totalEnergy.toFixed(3)} Joules</h2>
 <p>File: ${results.filePath}</p>
 <p>Measured at: ${results.timestamp.toLocaleString()}</p>
 </div>
 
 <h3> Energy Hotspots</h3>
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
 dispose() { }
}
exports.EnergyReportProvider = EnergyReportProvider;
//# sourceMappingURL=energyReportProvider.js.map