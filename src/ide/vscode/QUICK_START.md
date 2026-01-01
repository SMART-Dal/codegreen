# 🚀 Quick Start Guide - CodeGreen Extension

## ⚡ Fast Setup (2 Steps)

### Step 1: Open Extension Directory
```bash
cd <project-root>/src/ide/vscode
code .  # or 'cursor .'
```

### Step 2: Launch Extension
- **Press `F5`** (or `Ctrl+F5` to skip debugging)
- A new "Extension Development Host" window will open

## 📁 Finding Test Files

Once the Extension Development Host opens:

### Option 1: File Explorer
1. Look at the left sidebar (File Explorer)
2. Expand the folder structure
3. Navigate to: `test_files/` folder
4. Open: `example.py` or `example.js`

### Option 2: Quick Open
1. Press `Ctrl+P` (or `Cmd+P` on Mac)
2. Type: `test_files/example.py`
3. Press Enter

### Option 3: Command Line
1. In the Extension Development Host terminal:
   ```bash
   code test_files/example.py
   ```

## 🎯 Running Energy Analysis

1. **Open a test file** (see above)
2. **Run Analysis:**
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P`)
   - Type: `CodeGreen: Analyze Energy Consumption`
   - Press Enter

## 🔧 Troubleshooting

### Issue: "Select the build task" error
**Fixed!** The launch configuration now has two options:
- **"Launch Extension"** - No build task (use this one)
- **"Launch Extension (No Build)"** - With dummy build task

**Solution:** Select "Launch Extension" when prompted, or press `F5` directly.

### Issue: Test files not visible
**Solution:** 
1. Check File Explorer sidebar is open (View → Explorer)
2. Use Quick Open: `Ctrl+P` → type `test_files/example.py`
3. Or manually navigate: File → Open File → browse to `test_files/example.py`

### Issue: Extension doesn't activate
**Solution:**
1. Check Debug Console (View → Debug Console) for errors
2. Verify `extension.js` exists in the root directory
3. Check `package.json` has correct `main` entry: `"./extension.js"`

## 📝 Test Files Location

```
<project-root>/src/ide/vscode/
├── test_files/
│   ├── example.py    ← Python test file
│   └── example.js    ← JavaScript test file
├── extension.js       ← Main extension file
└── package.json      ← Extension manifest
```

## ✅ Verification Checklist

Before running:
- [ ] `extension.js` exists in root directory
- [ ] `test_files/example.py` exists
- [ ] CodeGreen CLI is installed: `which codegreen`
- [ ] Node.js is available: `node --version`

## 🎨 What to Expect

After running analysis:
- **🔥 Icons** in the left gutter (energy hotspots)
- **Status bar** showing energy metrics (bottom-right)
- **Hover tooltips** with energy details
- **Clickable hotspots** for optimization options

## 💡 Pro Tips

1. **Use F5** for quick launch (no build task needed)
2. **Quick Open** (`Ctrl+P`) is fastest way to open files
3. **Command Palette** (`Ctrl+Shift+P`) for all commands
4. **Debug Console** shows extension logs

## 🆘 Still Having Issues?

1. **Check the Debug Console** (View → Debug Console)
2. **Verify CodeGreen CLI:**
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   codegreen --help
   ```
3. **Check extension logs:** View → Output → Select "CodeGreen"

---

**Ready?** Press `F5` and start analyzing! 🚀
