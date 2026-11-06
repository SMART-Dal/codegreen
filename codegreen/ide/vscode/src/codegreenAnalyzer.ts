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

export interface MeasurementValidity {
    status: string;
    reasons: string[];
    detail: { [code: string]: string };
    warnings: { [code: string]: string };
}

export interface EnergyAnalysisResult {
    filePath: string;
    totalEnergy: number;
    averagePower: number;
    hotspots: EnergyHotspot[];
    analysisTime: number;
    timestamp: Date;
    validity: MeasurementValidity | null;
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
            const result = await this.runCodeGreenMeasurement(document.fileName, document.languageId);
            this.reportValidity(result.validity);
            return result;
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

            const timer = setTimeout(() => {
                childProcess.kill();
                reject(new Error('CodeGreen measurement timed out after 60s'));
            }, 60000);

            // Exit 3 (invalid measurement) and other failures still print the JSON result, so stdout is
            // parsed whatever the exit code; only output without a usable result is an error.
            childProcess.on('close', (code) => {
                clearTimeout(timer);
                try {
                    resolve(this.parseJsonOutput(stdout, filePath, Date.now() - startTime));
                } catch (error: any) {
                    reject(new Error(`codegreen measure exited with code ${code}: ${error.message}\n${stderr.slice(-2000)}`));
                }
            });

            childProcess.on('error', (error) => {
                clearTimeout(timer);
                reject(new Error(`Failed to start CodeGreen CLI: ${error.message}`));
            });
        });
    }

    private parseJsonOutput(stdout: string, filePath: string, analysisTime: number): EnergyAnalysisResult {
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error('no JSON result in the CLI output');
        }
        const data = JSON.parse(jsonMatch[0]);
        const validity: MeasurementValidity | null = data.validity || null;
        if (!data.summary || (data.success === false && !validity)) {
            throw new Error(data.error || 'the JSON result has no summary');
        }
        const total: number = data.summary.total_energy_j;
        const lines: { [name: string]: number } = {};
        for (const p of Object.values<any>(data.instrumentation_points || {})) {
            if (!(p.name in lines) || p.line < lines[p.name]) lines[p.name] = p.line;
        }
        const invalid = validity && validity.status !== 'valid' ? ` [invalid: ${validity.reasons.join(', ')}]` : '';
        // per_function_energy values are per-function totals (inclusive_j covers callees); they are never summed.
        const hotspots: EnergyHotspot[] = Object.entries<any>(data.per_function_energy || {}).map(([name, f]): EnergyHotspot => {
            const share = total > 0 ? f.inclusive_j / total : 0;
            return {
                line: lines[name] || 1,
                column: 0,
                energy: f.inclusive_j,
                power: f.avg_power_w,
                function: name,
                description: `${f.inclusive_j.toFixed(3)} J inclusive, ${f.exclusive_j.toFixed(3)} J exclusive, `
                    + `${f.calls} calls, ${f.avg_power_w} W (${f.quality})${invalid}`,
                severity: share >= 0.5 ? 'critical' : share >= 0.25 ? 'high' : share >= 0.1 ? 'medium' : 'low'
            };
        });
        return {
            filePath: filePath,
            totalEnergy: total,
            averagePower: data.summary.avg_power_w,
            hotspots: hotspots,
            analysisTime: analysisTime,
            timestamp: new Date(),
            validity: validity
        };
    }

    private reportValidity(validity: MeasurementValidity | null) {
        if (!validity) {
            vscode.window.showWarningMessage('CodeGreen: the result carries no validity verdict; treat its numbers as unverified.');
            return;
        }
        const fmt = (m: { [code: string]: string }) => Object.entries(m).map(([c, t]) => `${c}: ${t}`).join('; ');
        if (validity.status !== 'valid') {
            vscode.window.showWarningMessage(`CodeGreen: invalid measurement. ${fmt(validity.detail)}`);
        }
        if (Object.keys(validity.warnings || {}).length) {
            vscode.window.showInformationMessage(`CodeGreen warnings: ${fmt(validity.warnings)}`);
        }
    }

    private isSupportedLanguage(languageId: string): boolean {
        return ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'].includes(languageId);
    }

    dispose() {}
}