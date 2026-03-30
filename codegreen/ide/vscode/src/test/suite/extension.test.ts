import * as assert from 'assert';
import * as vscode from 'vscode';

suite('CodeGreen Extension Test Suite', () => {
    vscode.window.showInformationMessage('Start all tests.');

    test('Extension should be present', () => {
        assert.ok(vscode.extensions.getExtension('codegreen.codegreen-energy-analyzer'));
    });

    test('Should activate', async () => {
        const extension = vscode.extensions.getExtension('codegreen.codegreen-energy-analyzer');
        if (extension) {
            await extension.activate();
            assert.ok(extension.isActive);
        }
    });

    test('Should register commands', async () => {
        const commands = await vscode.commands.getCommands(true);
        const codegreenCommands = commands.filter(cmd => cmd.startsWith('codegreen.'));
        
        assert.ok(codegreenCommands.includes('codegreen.analyzeEnergy'));
        assert.ok(codegreenCommands.includes('codegreen.clearHotspots'));
        assert.ok(codegreenCommands.includes('codegreen.showReport'));
        assert.ok(codegreenCommands.includes('codegreen.toggleAutoAnalysis'));
    });
});
