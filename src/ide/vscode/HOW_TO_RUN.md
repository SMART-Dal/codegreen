# How to Run CodeGreen VSCode Extension

## Prerequisites

1. **VSCode or Cursor installed**
2. **CodeGreen CLI installed** (should be in `~/.local/bin/codegreen`)
3. **Node.js** (for extension development)

## Step-by-Step Instructions

### 1. Open the Extension in VSCode

```bash
cd <project-root>/src/ide/vscode
code .
```

Or if using Cursor:
```bash
cursor .
```

### 2. Install Dependencies (if not already done)

```bash
npm install
```

### 3. Launch Extension Development Host

**Option A: Using Keyboard Shortcut**
- Press `F5` in VSCode/Cursor
- This will open a new "Extension Development Host" window

**Option B: Using Command Palette**
- Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
- Type "Debug: Start Debugging"
- Select "Launch Extension"

**Option C: Using Menu**
- Go to `Run` → `Start Debugging`

### 4. Test the Extension

Once the Extension Development Host window opens:

1. **Open a test file:**
   - In the new window, go to `File` → `Open File...`
   - Navigate to: `<project-root>/src/ide/vscode/test_files/example.py`
   - Or open `example.js` for JavaScript testing

2. **Run Energy Analysis:**
   - **Method 1: Command Palette**
     - Press `Ctrl+Shift+P` (or `Cmd+Shift+P`)
     - Type "CodeGreen: Analyze Energy Consumption"
     - Press Enter
   
   - **Method 2: Right-click Context Menu**
     - Right-click in the editor
     - Select "Analyze Energy Consumption"
   
   - **Method 3: Editor Title Bar**
     - Look for the CodeGreen icon in the editor title bar
     - Click it to run analysis

3. **View Results:**
   - **Gutter Icons**: Energy hotspots will appear as icons in the left gutter
   - **Status Bar**: Energy metrics will show in the bottom-right status bar
   - **Hover Tooltips**: Hover over hotspots to see detailed energy information
   - **Energy Panel**: Click the status bar item to open the energy dashboard

### 5. Interactive Features

- **Click on Hotspots**: Click the fire icon (🔥) in the gutter to see optimization options
- **AI Optimization**: Run "CodeGreen: AI Optimize Energy" from Command Palette
- **Predictive Modeling**: Run "CodeGreen: Predict Energy Impact" to see forecasts
- **Energy Panel**: Click the status bar energy indicator to open the dashboard

## Testing with Different Files

### Python File
```bash
# Open in Extension Development Host
<project-root>/src/ide/vscode/test_files/example.py
```

### JavaScript File
```bash
# Open in Extension Development Host
<project-root>/src/ide/vscode/test_files/example.js
```

### Your Own Files
You can analyze any Python, JavaScript, TypeScript, Java, C, or C++ file:
1. Open the file in the Extension Development Host
2. Run "CodeGreen: Analyze Energy Consumption"
3. View the energy hotspots

## Troubleshooting

### Extension Not Activating
- Check the Debug Console (View → Debug Console) for errors
- Ensure CodeGreen CLI is installed: `which codegreen`
- Verify PATH includes `~/.local/bin`

### No Hotspots Showing
- Make sure the file has been saved
- Check that CodeGreen CLI can analyze the file: `codegreen measure python test_files/example.py`
- Look for errors in the Debug Console

### Command Not Found
- Ensure the extension is properly activated
- Check `package.json` for command definitions
- Restart the Extension Development Host

## Configuration

You can customize the extension behavior:

1. Open Settings (`Ctrl+,` or `Cmd+,`)
2. Search for "CodeGreen"
3. Adjust:
   - `codegreen.autoAnalysis`: Auto-analyze on save
   - `codegreen.energyThreshold`: Energy threshold for hotspots
   - `codegreen.uiStyle`: Visual style (subtle/prominent/minimal)
   - `codegreen.showStatusBar`: Show energy in status bar
   - `codegreen.enableAIOptimization`: Enable AI features
   - `codegreen.enablePredictiveModeling`: Enable predictive features

## Quick Test Commands

```bash
# Test CodeGreen CLI directly
cd <project-root>/src/ide/vscode
export PATH="$HOME/.local/bin:$PATH"
codegreen measure python test_files/example.py

# Verify extension files
ls -la extension.js package.json

# Check Node.js version (should be 10+)
node --version
```

## Next Steps

1. **Customize UI**: Adjust settings in VSCode preferences
2. **Add More Test Files**: Create additional test cases
3. **Integrate with CI/CD**: Use CodeGreen in your build pipeline
4. **Explore AI Features**: Try the AI optimization suggestions
5. **Use Predictive Modeling**: Forecast energy impact of changes

## Support

If you encounter issues:
1. Check the Debug Console for error messages
2. Verify CodeGreen CLI is working: `codegreen --help`
3. Check extension logs in the Output panel (View → Output → CodeGreen)
