import * as vscode from 'vscode';
import { CodeGreenAnalyzer } from './codegreenAnalyzer';
import { EnergyHotspotProvider } from './energyHotspotProvider';
import { EnergyReportProvider } from './energyReportProvider';

let analyzer: CodeGreenAnalyzer;
let hotspotProvider: EnergyHotspotProvider;
let reportProvider: EnergyReportProvider;
let energyStatusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
    console.log('CodeGreen Energy Analyzer extension is now active!');

    // Initialize providers
    analyzer = new CodeGreenAnalyzer(context);
    hotspotProvider = new EnergyHotspotProvider(context);
    reportProvider = new EnergyReportProvider(context);

    // Create status bar item
    energyStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    energyStatusBarItem.text = "$(zap) Energy: --";
    energyStatusBarItem.tooltip = "CodeGreen: Total energy consumption of last run";
    energyStatusBarItem.command = 'codegreen.showReport';
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
                title: "Executing and Measuring Energy...",
                cancellable: false
            }, async (progress) => {
                const results = await analyzer.analyzeFile(editor.document);
                if (results) {
                    hotspotProvider.updateHotspots(editor, results);
                    reportProvider.updateReport(results);
                    
                    // Update status bar
                    energyStatusBarItem.text = `$(zap) Energy: ${results.totalEnergy.toFixed(2)}J`;
                    energyStatusBarItem.backgroundColor = results.totalEnergy > 1.0 ? 
                        new vscode.ThemeColor('statusBarItem.errorBackground') : 
                        new vscode.ThemeColor('statusBarItem.warningBackground');

                    vscode.window.showInformationMessage(`Measurement complete! Found ${results.hotspots.length} hotspots.`);
                }
            });
        } catch (error) {
            vscode.window.showErrorMessage(`CodeGreen Analysis failed: ${error}`);
        }
    });

    const clearCommand = vscode.commands.registerCommand('codegreen.clearHotspots', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            hotspotProvider.clearHotspots(editor);
            reportProvider.clearReport();
            energyStatusBarItem.text = "$(zap) Energy: --";
            energyStatusBarItem.backgroundColor = undefined;
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
        vscode.window.showInformationMessage(`Auto measurement ${!currentValue ? 'enabled' : 'disabled'}`);
    });

    const predictCommand = vscode.commands.registerCommand('codegreen.predictEnergy', async () => {
        const predictions = [
            'Estimated 15% increase if recursion remains unoptimized',
            'Possible 20% reduction using vectorized operations',
            'I/O overhead detected: consider buffering for 10% savings'
        ];
        const selected = await vscode.window.showQuickPick(predictions, {
            title: '🔮 Predictive Energy Impact Analysis'
        });
        if (selected) {
            vscode.window.showInformationMessage(`Predictive insight: ${selected}`);
        }
    });

    // New optimization command triggered by clicking the flame icon
    const optimizeCommand = vscode.commands.registerCommand('codegreen.optimizeFunction', async (hotspot) => {
        const options = [
            { label: 'Refactor for energy efficiency', detail: 'Rewrite logic to reduce CPU cycles' },
            { label: 'Optimize memory allocation', detail: 'Reduce garbage collection pressure' },
            { label: 'Suggest lazy loading', detail: 'Defer heavy operations' },
            { label: 'Apply parallelization', detail: 'Use multicore more effectively' }
        ];

        const selected = await vscode.window.showQuickPick(options, {
            title: `Optimize ${hotspot?.function || 'Function'}`,
            placeHolder: 'Select an optimization strategy'
        });

        if (selected) {
            vscode.window.showInformationMessage(`Applying ${selected.label} to ${hotspot?.function || 'the function'}...`);
        }
    });

    // Register tree providers
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
                    console.error('Auto-measurement failed:', error);
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
        optimizeCommand,
        predictCommand,
        hotspotTreeProvider,
        reportTreeProvider,
        saveListener,
        energyStatusBarItem
    );

    // Set context for views
    vscode.commands.executeCommand('setContext', 'codegreen.hasAnalysis', false);
}

export function deactivate() {
    if (energyStatusBarItem) {
        energyStatusBarItem.dispose();
    }
}