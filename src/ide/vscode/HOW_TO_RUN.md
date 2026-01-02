# How to Run CodeGreen VSCode Extension

## Prerequisites

1. **VSCode or Cursor installed**
2. **CodeGreen CLI installed** (run `./install.sh` in project root)
3. **Node.js 16+** (for extension development)

## Step-by-Step Instructions

### 1. Open the Extension in VSCode

```bash
cd <project-root>/src/ide/vscode
code .
```

### 2. Install Dependencies and Build

```bash
npm install
npm run compile
```

### 3. Launch Extension Development Host

- Press `F5` in VSCode
- This will open a new "Extension Development Host" window

### 4. Test the Extension

1. **Open a test file:** `test_files/example.py`
2. **Run Energy Measurement:**
   - Press `Ctrl+Shift+P`
   - Type "CodeGreen: Analyze Energy Consumption"
   - Press Enter
3. **View Results:**
   - **🔥 Gutter Icons**: Fire icons appear next to energy-intensive functions.
   - **Interactive Menu**: Click the 🔥 icon or hover over it and select **Optimize** to see energy-saving recommendations.
   - **Status Bar**: Real-time Joule metrics in the bottom-right.

## Troubleshooting

- **No Hotspots**: Ensure the CodeGreen CLI is functional by running `codegreen info` in your terminal.
- **Activation Error**: Check `Help > Toggle Developer Tools` in VSCode for detailed error logs.