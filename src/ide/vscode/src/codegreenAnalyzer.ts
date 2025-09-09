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
    private codegreenPath: string;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.codegreenPath = this.getCodeGreenPath();
    }

    private getCodeGreenPath(): string {
        const config = vscode.workspace.getConfiguration('codegreen');
        return config.get('codegreenPath', 'codegreen');
    }

    async analyzeFile(document: vscode.TextDocument): Promise<EnergyAnalysisResult | null> {
        if (!this.isSupportedLanguage(document.languageId)) {
            throw new Error(`Language ${document.languageId} is not supported by CodeGreen`);
        }

        // Create temporary file for analysis
        const tempDir = path.join(this.context.extensionPath, 'temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFile = path.join(tempDir, `temp_${Date.now()}.${this.getFileExtension(document.languageId)}`);
        
        try {
            // Write document content to temp file
            fs.writeFileSync(tempFile, document.getText());

            // Run CodeGreen analysis
            const results = await this.runCodeGreenAnalysis(tempFile, document.languageId);
            
            // Clean up temp file
            fs.unlinkSync(tempFile);

            return results;
        } catch (error) {
            // Clean up temp file on error
            if (fs.existsSync(tempFile)) {
                fs.unlinkSync(tempFile);
            }
            throw error;
        }
    }

    private async runCodeGreenAnalysis(filePath: string, language: string): Promise<EnergyAnalysisResult> {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            
            // Build CodeGreen command
            const args = [
                'measure',
                language,
                filePath,
                '--output-format', 'json',
                '--quiet'
            ];

            const process = child_process.spawn(this.codegreenPath, args, {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

            process.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            process.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            process.on('close', (code) => {
                const analysisTime = Date.now() - startTime;

                if (code !== 0) {
                    reject(new Error(`CodeGreen analysis failed: ${stderr}`));
                    return;
                }

                try {
                    const results = this.parseCodeGreenOutput(stdout, filePath, analysisTime);
                    resolve(results);
                } catch (error) {
                    reject(new Error(`Failed to parse CodeGreen output: ${error}`));
                }
            });

            process.on('error', (error) => {
                reject(new Error(`Failed to start CodeGreen: ${error.message}`));
            });

            // Set timeout
            setTimeout(() => {
                process.kill();
                reject(new Error('CodeGreen analysis timed out'));
            }, 30000); // 30 second timeout
        });
    }

    private parseCodeGreenOutput(output: string, filePath: string, analysisTime: number): EnergyAnalysisResult {
        try {
            // Try to parse as JSON first
            const data = JSON.parse(output);
            
            const hotspots: EnergyHotspot[] = [];
            let totalEnergy = 0;
            let averagePower = 0;

            if (data.checkpoints && Array.isArray(data.checkpoints)) {
                data.checkpoints.forEach((checkpoint: any, index: number) => {
                    const energy = parseFloat(checkpoint.energy_consumed || '0');
                    const power = parseFloat(checkpoint.power_watts || '0');
                    
                    totalEnergy += energy;
                    averagePower += power;

                    // Determine severity based on energy consumption
                    let severity: 'low' | 'medium' | 'high' | 'critical' = 'low';
                    if (energy > 1.0) severity = 'critical';
                    else if (energy > 0.5) severity = 'high';
                    else if (energy > 0.1) severity = 'medium';

                    hotspots.push({
                        line: parseInt(checkpoint.line_number || '1'),
                        column: parseInt(checkpoint.column_number || '0'),
                        energy: energy,
                        power: power,
                        function: checkpoint.function_name,
                        description: `Energy: ${energy.toFixed(3)}J, Power: ${power.toFixed(3)}W`,
                        severity: severity
                    });
                });

                averagePower = hotspots.length > 0 ? averagePower / hotspots.length : 0;
            }

            return {
                filePath: filePath,
                totalEnergy: totalEnergy,
                averagePower: averagePower,
                hotspots: hotspots,
                analysisTime: analysisTime,
                timestamp: new Date()
            };
        } catch (error) {
            // Fallback parsing for non-JSON output
            return this.parseTextOutput(output, filePath, analysisTime);
        }
    }

    private parseTextOutput(output: string, filePath: string, analysisTime: number): EnergyAnalysisResult {
        const lines = output.split('\n');
        const hotspots: EnergyHotspot[] = [];
        let totalEnergy = 0;
        let averagePower = 0;

        // Look for energy consumption patterns in the output
        const energyRegex = /Energy consumed:\s*([0-9.]+)\s*J/i;
        const powerRegex = /Power:\s*([0-9.]+)\s*W/i;
        const lineRegex = /line\s*(\d+)/i;

        lines.forEach((line, index) => {
            const energyMatch = line.match(energyRegex);
            const powerMatch = line.match(powerRegex);
            const lineMatch = line.match(lineRegex);

            if (energyMatch) {
                const energy = parseFloat(energyMatch[1]);
                const power = powerMatch ? parseFloat(powerMatch[1]) : 0;
                const lineNumber = lineMatch ? parseInt(lineMatch[1]) : index + 1;

                totalEnergy += energy;
                averagePower += power;

                let severity: 'low' | 'medium' | 'high' | 'critical' = 'low';
                if (energy > 1.0) severity = 'critical';
                else if (energy > 0.5) severity = 'high';
                else if (energy > 0.1) severity = 'medium';

                hotspots.push({
                    line: lineNumber,
                    column: 0,
                    energy: energy,
                    power: power,
                    description: `Energy: ${energy.toFixed(3)}J, Power: ${power.toFixed(3)}W`,
                    severity: severity
                });
            }
        });

        averagePower = hotspots.length > 0 ? averagePower / hotspots.length : 0;

        return {
            filePath: filePath,
            totalEnergy: totalEnergy,
            averagePower: averagePower,
            hotspots: hotspots,
            analysisTime: analysisTime,
            timestamp: new Date()
        };
    }

    private isSupportedLanguage(languageId: string): boolean {
        const supportedLanguages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'];
        return supportedLanguages.includes(languageId);
    }

    private getFileExtension(languageId: string): string {
        const extensions: { [key: string]: string } = {
            'python': 'py',
            'javascript': 'js',
            'typescript': 'ts',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c'
        };
        return extensions[languageId] || 'txt';
    }

    dispose() {
        // Clean up any resources
    }
}
