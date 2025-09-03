# CodeGreen Installation Scripts

This directory contains installation and setup scripts for CodeGreen.

## 🔧 Permission Setup

### Problem
CodeGreen needs to read energy monitoring files (RAPL) that are typically restricted to root access:
- `/sys/class/powercap/intel-rapl:*/energy_uj`
- `/sys/class/powercap/intel-rapl:*/power_uw`

### Solution
The `setup_permissions.sh` script creates a secure, user-level access solution:

1. **Creates `powercap` group** - Dedicated group for energy monitoring
2. **Adds user to group** - Gives your user access to energy files
3. **Creates udev rules** - Automatically sets permissions for new devices
4. **Sets current permissions** - Fixes existing files immediately

### Usage

#### Option 1: Run Setup Script Directly
```bash
sudo install/setup_permissions.sh
```

#### Option 2: Use CodeGreen Init Command
```bash
sudo codegreen init --setup-permissions
```

#### Option 3: Full Installation
```bash
sudo install/install.sh
```

### After Setup
1. **Log out and log back in** (or restart) for group membership to take effect
2. **Test with**: `codegreen benchmark cpu_stress --duration 5`
3. **Verify groups**: `groups` (should show `powercap`)

## 🔒 Security

This setup is secure because:
- ✅ **Read-only access** - Only allows reading energy data
- ✅ **No sudo required** - After setup, no root access needed
- ✅ **User-specific** - Only affects users added to the group
- ✅ **Minimal permissions** - Only grants access to energy monitoring files

## 🐛 Troubleshooting

### Still Getting Permission Denied?
1. **Check groups**: `groups` - should include `powercap`
2. **Check file permissions**: `ls -la /sys/class/powercap/intel-rapl:0/energy_uj`
3. **Restart udev**: `sudo udevadm control --reload-rules && sudo udevadm trigger`
4. **Logout/login**: Group membership requires a new session

### Files Still Root-Only?
```bash
# Manual fix (temporary)
sudo chmod 644 /sys/class/powercap/intel-rapl:*/energy_uj

# Permanent fix (re-run setup)
sudo install/setup_permissions.sh
```

## 📋 What the Scripts Do

### `setup_permissions.sh`
- Creates `powercap` group
- Adds current user to group
- Creates udev rules for automatic permissions
- Sets permissions on existing files
- Provides setup verification

### `install.sh`
- Runs permission setup
- Installs Python dependencies
- Installs CodeGreen package
- Verifies installation
- Provides next steps

## 🔄 Environment-Specific Setup

### Container Environments
- May need `--privileged` flag
- Consider using `--cap-add=SYS_ADMIN`
- See `docker-setup.sh` for container-specific configuration

### HPC Environments
- Contact system administrator
- May need module installation
- See `hpc-module.lua` for Lmod integration

### CI/CD Environments
- Usually run with elevated privileges
- May need different permission strategies
- Consider using `--setup-permissions` in CI scripts

