import * as vscode from 'vscode';
import { CodeGreenAnalyzer } from './codegreenAnalyzer';
import { EnergyHotspotProvider } from './energyHotspotProvider';
import { EnergyReportProvider } from './energyReportProvider';

let analyzer: CodeGreenAnalyzer;
let hotspotProvider: EnergyHotspotProvider;
let reportProvider: EnergyReportProvider;

export function activate(context: vscode.ExtensionContext) {
    console.log('CodeGreen Energy Analyzer extension is now active!');

    // Initialize providers
    analyzer = new CodeGreenAnalyzer(context);
    hotspotProvider = new EnergyHotspotProvider(context);
    reportProvider = new EnergyReportProvider(context);

    // Register commands
    const analyzeCommand = vscode.commands.registerCommand('codegreen.analyzeEnergy', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor found');
            return;
        }

        try {
            vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Analyzing energy consumption...",
                cancellable: false
            }, async (progress) => {
                const results = await analyzer.analyzeFile(editor.document);
                if (results) {
                    hotspotProvider.updateHotspots(editor, results);
                    reportProvider.updateReport(results);
                    vscode.window.showInformationMessage(`Energy analysis complete! Found ${results.hotspots.length} hotspots.`);
                }
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Energy analysis failed: ${error}`);
        }
    });

    const clearCommand = vscode.commands.registerCommand('codegreen.clearHotspots', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            hotspotProvider.clearHotspots(editor);
            reportProvider.clearReport();
            vscode.window.showInformationMessage('Energy hotspots cleared');
        }
    });

    const showReportCommand = vscode.commands.registerCommand('codegreen.showReport', () => {
        reportProvider.showReport();
    });

    const toggleAutoCommand = vscode.commands.registerCommand('codegreen.toggleAutoAnalysis', () => {
        const config = vscode.workspace.getConfiguration('codegreen');
        const currentValue = config.get('autoAnalysis', false);
        config.update('autoAnalysis', !currentValue, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage(`Auto analysis ${!currentValue ? 'enabled' : 'disabled'}`);
    });

    // Register providers
    const hotspotTreeProvider = vscode.window.createTreeView('codegreenEnergyView', {
        treeDataProvider: hotspotProvider
    });

    const reportTreeProvider = vscode.window.createTreeView('codegreenReportView', {
        treeDataProvider: reportProvider
    });

    // Auto-analysis on save
    const saveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const config = vscode.workspace.getConfiguration('codegreen');
        if (config.get('autoAnalysis', false)) {
            const editor = vscode.window.activeTextEditor;
            if (editor && editor.document === document) {
                try {
                    const results = await analyzer.analyzeFile(document);
                    if (results) {
                        hotspotProvider.updateHotspots(editor, results);
                        reportProvider.updateReport(results);
                    }
                } catch (error) {
                    // Silent fail for auto-analysis
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
        hotspotTreeProvider,
        reportTreeProvider,
        saveListener
    );

    // Set context for views
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
}

export function deactivate() {
    if (analyzer) {
        analyzer.dispose();
    }
    if (hotspotProvider) {
        hotspotProvider.dispose();
    }
    if (reportProvider) {
        reportProvider.dispose();
    }
}
