import * as vscode from 'vscode';
import * as child_process from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export interface EnergyHotspot {
    line: number;
    column: number;
    energy: number;
    power: number;
    function?: string;
    description: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface EnergyAnalysisResult {
    filePath: string;
    totalEnergy: number;
    averagePower: number;
    hotspots: EnergyHotspot[];
    analysisTime: number;
    timestamp: Date;
}

export class CodeGreenAnalyzer {
    private context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    private getCodeGreenPath(): string {
        const config = vscode.workspace.getConfiguration('codegreen');
        return config.get('codegreenPath', 'codegreen');
    }

    async analyzeFile(document: vscode.TextDocument): Promise<EnergyAnalysisResult | null> {
        if (!this.isSupportedLanguage(document.languageId)) {
            vscode.window.showErrorMessage(`Language ${document.languageId} is not supported by CodeGreen`);
            return null;
        }

        try {
            return await this.runCodeGreenMeasurement(document.fileName, document.languageId);
        } catch (error: any) {
            vscode.window.showErrorMessage(`CodeGreen Measurement Failed: ${error.message}`);
            return null;
        }
    }

    private async runCodeGreenMeasurement(filePath: string, language: string): Promise<EnergyAnalysisResult> {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const codegreenPath = this.getCodeGreenPath();
            
            // Build CodeGreen command with JSON output
            // We use 'measure' to get actual energy data
            const args = [
                'measure',
                language,
                filePath,
                '--json'
            ];

            const childProcess = child_process.spawn(codegreenPath, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                env: { ...process.env, PYTHONPATH: path.join(path.dirname(path.dirname(path.dirname(codegreenPath))), 'src') }
            });

            let stdout = '';
            let stderr = '';

            childProcess.stdout.on('data', (data) => stdout += data.toString());
            childProcess.stderr.on('data', (data) => stderr += data.toString());

            childProcess.on('close', (code) => {
                const analysisTime = Date.now() - startTime;

                if (code !== 0 && !stdout.includes('codegreen_results')) {
                    reject(new Error(`Process exited with code ${code}. Stderr: ${stderr}`));
                    return;
                }

                try {
                    const result = this.parseJsonOutput(stdout, filePath, analysisTime);
                    resolve(result);
                } catch (error) {
                    reject(new Error(`Failed to parse CLI JSON output: ${error}\nRaw output: ${stdout}`));
                }
            });

            childProcess.on('error', (error) => {
                reject(new Error(`Failed to start CodeGreen CLI: ${error.message}`));
            });

            // 60 second timeout for actual execution
            setTimeout(() => {
                childProcess.kill();
                reject(new Error('CodeGreen measurement timed out after 60s'));
            }, 60000);
        });
    }

    private parseJsonOutput(stdout: string, filePath: string, analysisTime: number): EnergyAnalysisResult {
        // Find the JSON block in stdout (CLI might have some logs before/after)
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error("No JSON found in CLI output");
        }

        const data = JSON.parse(jsonMatch[0]);
        const hotspots: EnergyHotspot[] = [];
        
        let totalJ = 0;
        let avgW = 0;

        // Extract measurement data from CLI JSON
        if (data.measurement && data.measurement.checkpoints) {
            const checkpoints = data.measurement.checkpoints;
            
            checkpoints.forEach((cp: any) => {
                const energy = cp.joules || 0;
                const power = cp.watts || 0;
                
                totalJ += energy;
                avgW += power;

                // Severity logic
                let severity: 'low' | 'medium' | 'high' | 'critical' = 'low';
                if (energy > 1.0) severity = 'critical';
                else if (energy > 0.5) severity = 'high';
                else if (energy > 0.1) severity = 'medium';

                // We try to match runtime checkpoint ID with line numbers if possible
                // checkpoint_id usually looks like "type_name_line_col"
                const idParts = cp.checkpoint_id.split('_');
                const line = parseInt(idParts[idParts.length - 2]) || 1;

                hotspots.push({
                    line: line,
                    column: 0,
                    energy: energy,
                    power: power,
                    function: idParts.slice(2, -2).join('_') || 'unknown',
                    description: `Energy: ${energy.toFixed(3)}J, Power: ${power.toFixed(3)}W`,
                    severity: severity
                });
            });

            if (checkpoints.length > 0) {
                avgW /= checkpoints.length;
            }
        }

        return {
            filePath: filePath,
            totalEnergy: totalJ,
            averagePower: avgW,
            hotspots: hotspots,
            analysisTime: analysisTime,
            timestamp: new Date()
        };
    }

    private isSupportedLanguage(languageId: string): boolean {
        return ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'].includes(languageId);
    }

    dispose() {}
}