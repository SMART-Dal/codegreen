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
exports.CodeGreenAnalyzer = void 0;
const vscode = __importStar(require("vscode"));
const child_process = __importStar(require("child_process"));
const path = __importStar(require("path"));
class CodeGreenAnalyzer {
    constructor(context) {
        this.context = context;
    }
    getCodeGreenPath() {
        const config = vscode.workspace.getConfiguration('codegreen');
        return config.get('codegreenPath', 'codegreen');
    }
    async analyzeFile(document) {
        if (!this.isSupportedLanguage(document.languageId)) {
            vscode.window.showErrorMessage(`Language ${document.languageId} is not supported by CodeGreen`);
            return null;
        }
        try {
            return await this.runCodeGreenMeasurement(document.fileName, document.languageId);
        }
        catch (error) {
            vscode.window.showErrorMessage(`CodeGreen Measurement Failed: ${error.message}`);
            return null;
        }
    }
    async runCodeGreenMeasurement(filePath, language) {
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
                env: Object.assign(Object.assign({}, process.env), { PYTHONPATH: path.join(path.dirname(path.dirname(path.dirname(codegreenPath))), 'src') })
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
                }
                catch (error) {
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
    parseJsonOutput(stdout, filePath, analysisTime) {
        // Find the JSON block in stdout (CLI might have some logs before/after)
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error("No JSON found in CLI output");
        }
        const data = JSON.parse(jsonMatch[0]);
        const hotspots = [];
        let totalJ = 0;
        let avgW = 0;
        // Extract measurement data from CLI JSON
        if (data.measurement && data.measurement.checkpoints) {
            const checkpoints = data.measurement.checkpoints;
            checkpoints.forEach((cp) => {
                const energy = cp.joules || 0;
                const power = cp.watts || 0;
                totalJ += energy;
                avgW += power;
                // Severity logic
                let severity = 'low';
                if (energy > 1.0)
                    severity = 'critical';
                else if (energy > 0.5)
                    severity = 'high';
                else if (energy > 0.1)
                    severity = 'medium';
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
    isSupportedLanguage(languageId) {
        return ['python', 'javascript', 'typescript', 'java', 'cpp', 'c'].includes(languageId);
    }
    dispose() { }
}
exports.CodeGreenAnalyzer = CodeGreenAnalyzer;
//# sourceMappingURL=codegreenAnalyzer.js.map