# CodeGreen VSCode Extension

A Visual Studio Code extension that integrates with CodeGreen to visualize energy consumption hotspots directly in your code editor.

## Features

- 🔥 **Energy Hotspot Visualization**: Fire icons appear directly in the gutter for energy-intensive code.
- ⚡ **Interactive Optimization**: Click on hotspots to get AI-powered energy-saving recommendations.
- 📊 **Detailed Reports**: Comprehensive energy analysis reports in Markdown and HTML.
- 🎯 **Real-time Metrics**: Status bar energy tracking for the latest execution.

## Installation

### From Source

1. Clone the CodeGreen repository
2. Navigate to the extension directory:
   ```bash
   cd src/ide/vscode
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Compile the extension:
   ```bash
   npm run compile
   ```
5. Press **F5** to launch a new VSCode window with the extension loaded.

## Commands

- `CodeGreen: Analyze Energy Consumption`: Measure energy for the current file.
- `CodeGreen: Clear Energy Hotspots`: Remove markers from the editor.
- `CodeGreen: Show Energy Report`: View the full measurement summary.

## Requirements

- **CodeGreen CLI**: Must be installed and accessible in your PATH.
- **Linux**: Primary platform for hardware energy sensors (RAPL).

## License

MIT License - see [LICENSE](../../LICENSE) for details.