# CodeGreen VSCode Extension

A Visual Studio Code extension that integrates with CodeGreen to visualize energy consumption hotspots directly in your code editor.

## Features

- 🔥 **Energy Hotspot Visualization**: See energy consumption hotspots directly in the gutter
- ⚡ **Real-time Analysis**: Analyze energy consumption with a single command
- 📊 **Detailed Reports**: View comprehensive energy analysis reports
- 🎯 **Multi-language Support**: Works with Python, JavaScript, TypeScript, Java, C++, and C
- 🔧 **Configurable**: Customize energy thresholds, icons, and display options
- 🚀 **Auto-analysis**: Optional automatic analysis on file save

## Installation

### From Source

1. Clone the CodeGreen repository
2. Navigate to the extension directory:
   ```bash
   cd packages/ide/include/vscode
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Compile the extension:
   ```bash
   npm run compile
   ```
5. Press F5 to launch a new VSCode window with the extension loaded

### From VSIX Package

1. Package the extension:
   ```bash
   npm install -g vsce
   vsce package
   ```
2. Install the generated `.vsix` file in VSCode

## Usage

### Basic Analysis

1. Open a supported code file (Python, JavaScript, TypeScript, Java, C++, or C)
2. Use one of these methods to run energy analysis:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) and type "Analyze Energy Consumption"
   - Click the energy analysis button in the editor title bar
   - Right-click in the editor and select "Analyze Energy Consumption"

### Viewing Results

- **Gutter Markers**: Energy hotspots are displayed as icons in the gutter
- **Hover Information**: Hover over hotspots to see detailed energy information
- **Side Panel**: View a tree of all hotspots in the "Energy Analysis" panel
- **Detailed Report**: Click "Show Energy Report" for a comprehensive HTML report

### Configuration

The extension can be configured through VSCode settings:

- `codegreen.autoAnalysis`: Enable/disable automatic analysis on file save
- `codegreen.energyThreshold`: Set the energy threshold for highlighting hotspots
- `codegreen.hotspotIcon`: Choose the icon style for hotspots
- `codegreen.showTooltips`: Enable/disable hover tooltips
- `codegreen.codegreenPath`: Specify the path to the CodeGreen executable

## Commands

- `codegreen.analyzeEnergy`: Run energy analysis on the current file
- `codegreen.clearHotspots`: Clear all energy hotspot markers
- `codegreen.showReport`: Display detailed energy report
- `codegreen.toggleAutoAnalysis`: Toggle automatic analysis on/off

## Requirements

- CodeGreen CLI tool must be installed and accessible
- Supported languages: Python, JavaScript, TypeScript, Java, C++, C
- VSCode 1.74.0 or later

## Troubleshooting

### CodeGreen Not Found

If you get an error that CodeGreen is not found:

1. Ensure CodeGreen is installed: `pip install codegreen`
2. Check that `codegreen` command is in your PATH
3. Configure the path in settings: `codegreen.codegreenPath`

### No Hotspots Displayed

1. Check that your file is in a supported language
2. Verify that CodeGreen analysis completed successfully
3. Adjust the energy threshold in settings
4. Check the output panel for error messages

### Performance Issues

1. Disable auto-analysis if not needed
2. Increase the energy threshold to show only high-energy hotspots
3. Close the detailed report panel when not needed

## Development

### Building

```bash
npm install
npm run compile
```

### Watching for Changes

```bash
npm run watch
```

### Testing

```bash
npm test
```

### Linting

```bash
npm run lint
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This extension is part of the CodeGreen project and follows the same licensing terms.

## Support

For issues and questions:
- Check the [CodeGreen documentation](../../../README.md)
- Open an issue on the GitHub repository
- Check the VSCode output panel for error messages
