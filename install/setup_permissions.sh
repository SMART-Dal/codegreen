#!/bin/bash

# CodeGreen Permission Setup Script
# This script sets up secure user-level access to energy monitoring files
# without requiring sudo for normal operation.

set -e

echo "🔧 Setting up CodeGreen permissions..."

# Check if we have sudo access (running with sudo or as root)
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script requires sudo access to set up permissions."
    echo "   Please run: sudo $0"
    exit 1
fi

# Get the actual user (not root when using sudo)
if [[ -n "$SUDO_USER" ]]; then
    ACTUAL_USER="$SUDO_USER"
else
    echo "❌ Please run this script with sudo, not as root directly."
    echo "   Use: sudo $0"
    exit 1
fi

echo "✅ Running with sudo access"

# Environment detection for appropriate setup method
detect_environment() {
    local env_type="personal"
    
    # Check for containerized environment
    if [[ -f /.dockerenv ]] || [[ -n "${CONTAINER}" ]] || [[ -n "${CI}" ]]; then
        env_type="container"
    # Check for HPC environment
    elif [[ -d /opt/slurm ]] || [[ -n "$SLURM_JOB_ID" ]] || [[ -d /usr/local/hpc ]] || [[ -f /etc/modules ]] && grep -q "module" /etc/profile.d/* 2>/dev/null; then
        env_type="hpc"
    # Check for shared server (multiple users, shared home directories)
    elif [[ $(who | wc -l 2>/dev/null || echo 0) -gt 5 ]] && [[ -d /home ]] && [[ $(ls /home | wc -l) -gt 10 ]]; then
        env_type="shared_server"
    # Check for CI/CD environment
    elif [[ -n "$CI" ]] || [[ -n "$GITHUB_ACTIONS" ]] || [[ -n "$GITLAB_CI" ]] || [[ -n "$JENKINS_URL" ]] || [[ -n "$TRAVIS" ]]; then
        env_type="cicd"
    fi
    
    echo "$env_type"
}

ENVIRONMENT=$(detect_environment)
echo "🔍 Detected environment: $ENVIRONMENT"

case "$ENVIRONMENT" in
    "container")
        echo "🐳 Container environment detected"
        echo "   Using simplified setup for containerized deployment"
        ;;
    "hpc")
        echo "🏢 HPC cluster environment detected"
        echo "   Using HPC-compatible setup with centralized access"
        ;;
    "shared_server")
        echo "🖥️  Shared server environment detected"
        echo "   Using secure group-based setup with user isolation"
        ;;
    "cicd")
        echo "⚙️  CI/CD pipeline environment detected"
        echo "   Using automated testing setup"
        ;;
    *)
        echo "💻 Personal/development environment detected"
        echo "   Using standard group-based setup"
        ;;
esac

# Create powercap group if it doesn't exist (skip in containers and CI/CD)
if [[ "$ENVIRONMENT" != "container" ]] && [[ "$ENVIRONMENT" != "cicd" ]]; then
    if ! getent group powercap >/dev/null 2>&1; then
        echo "📦 Creating powercap group..."
        groupadd powercap
        echo "✅ Created powercap group"
    else
        echo "✅ powercap group already exists"
    fi

    # Add current user to powercap group
    echo "👤 Adding user $ACTUAL_USER to powercap group..."
    usermod -a -G powercap $ACTUAL_USER
    echo "✅ Added $ACTUAL_USER to powercap group"
else
    echo "⏭️  Skipping group creation for $ENVIRONMENT environment"
fi

# Setup method based on environment
case "$ENVIRONMENT" in
    "container"|"cicd")
        echo "📋 Container/CI setup: Using direct permissions (no udev rules needed)"
        # In containers, we often have direct access or need to use capabilities
        ;;
    "hpc")
        echo "📋 HPC setup: Creating module-compatible udev rules"
        # Create udev rules but also provide module loading instructions
        tee /etc/udev/rules.d/99-codegreen-rapl-hpc.rules > /dev/null << 'EOF'
# CodeGreen RAPL Energy Monitoring Rules - HPC Compatible
# Allows both powercap group and specific HPC user patterns

# Intel RAPL energy files - broader access for HPC
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:energy_uj", GROUP="powercap", MODE="0644" 
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:power_uw", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:max_energy_range_uj", GROUP="powercap", MODE="0644"

# AMD RAPL energy files 
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*:energy_uj", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*:power_uw", GROUP="powercap", MODE="0644"

# HPC-specific: Allow compute node access patterns
SUBSYSTEM=="powercap", KERNEL=="*rapl*", MODE="0644"
EOF
        ;;
    *)
        echo "📋 Standard setup: Creating udev rules for RAPL energy monitoring"
        tee /etc/udev/rules.d/99-codegreen-rapl.rules > /dev/null << 'EOF'
# CodeGreen RAPL Energy Monitoring Rules
# Allows powercap group to read RAPL energy files

# Intel RAPL energy files
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:energy_uj", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:power_uw", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*:max_energy_range_uj", GROUP="powercap", MODE="0644"

# AMD RAPL energy files (if available)
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*:energy_uj", GROUP="powercap", MODE="0644"
SUBSYSTEM=="powercap", KERNEL=="amd_rapl:*:power_uw", GROUP="powercap", MODE="0644"
EOF
        ;;
esac

if [[ "$ENVIRONMENT" != "container" ]] && [[ "$ENVIRONMENT" != "cicd" ]]; then
    echo "✅ Created udev rules for $ENVIRONMENT environment"
fi

# Reload udev rules
echo "🔄 Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger --subsystem-match=powercap

echo "✅ Reloaded udev rules"

# Set current permissions and group ownership on existing files
echo "🔧 Setting permissions on existing RAPL files..."
if [ -d "/sys/class/powercap" ]; then
    # Set group ownership and permissions for energy files
    find /sys/class/powercap -name "energy_uj" -exec chgrp powercap {} \; -exec chmod 644 {} \;
    find /sys/class/powercap -name "power_uw" -exec chgrp powercap {} \; -exec chmod 644 {} \;
    find /sys/class/powercap -name "max_energy_range_uj" -exec chgrp powercap {} \; -exec chmod 644 {} \;
    
    # Set directory permissions
    find /sys/class/powercap -name "*rapl*" -type d -exec chgrp powercap {} \; -exec chmod 755 {} \;
    
    echo "✅ Set permissions and group ownership on existing files"
else
    echo "⚠️  No RAPL files found (may not be available on this system)"
fi

# Create environment configuration file
echo "📝 Creating environment configuration..."
mkdir -p "/etc/codegreen"
cat > "/etc/codegreen/environment.conf" << EOF
# CodeGreen Environment Configuration
ENVIRONMENT_TYPE=$ENVIRONMENT
SETUP_DATE=$(date -I)
SETUP_USER=$ACTUAL_USER
PERMISSION_METHOD=group_based
EOF

# Environment-specific final instructions
echo ""
echo "🎉 Permission setup completed for $ENVIRONMENT environment!"
echo ""

case "$ENVIRONMENT" in
    "container")
        echo "🐳 Container Environment Instructions:"
        echo "   • No additional steps required in containers"
        echo "   • Energy monitoring may require --privileged or specific capabilities"
        echo "   • Test with: python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
        echo ""
        echo "📋 Docker example:"
        echo "   docker run --privileged -v /sys/class/powercap:/sys/class/powercap:ro your-image"
        ;;
    "hpc")
        echo "🏢 HPC Environment Instructions:"
        echo "   • Module file may be needed: module load codegreen"
        echo "   • Check with your HPC admin about energy monitoring policies"
        echo "   • Test with: python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
        echo ""
        echo "📋 For HPC admins:"
        echo "   • Consider creating a module file in /usr/local/modules/codegreen"
        echo "   • May require compute node configuration for full functionality"
        ;;
    "shared_server")
        echo "🖥️  Shared Server Instructions:"
        echo "   • Group changes require logout/login or: newgrp powercap"
        echo "   • Other users will need to be added to powercap group individually"
        echo "   • Test with: python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
        echo ""
        echo "🔒 For server admins:"
        echo "   • Monitor usage with: journalctl -f | grep codegreen"
        echo "   • Consider usage quotas if needed"
        ;;
    "cicd")
        echo "⚙️  CI/CD Pipeline Instructions:"
        echo "   • No user group changes needed in CI environment"
        echo "   • May need elevated container privileges for energy access"
        echo "   • Test with: python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
        echo ""
        echo "📋 CI/CD Example:"
        echo "   - Use privileged: true in docker-compose or --privileged in docker run"
        echo "   - Mount: -v /sys/class/powercap:/sys/class/powercap:ro"
        ;;
    *)
        echo "💻 Personal/Development Environment Instructions:"
        echo "   1. Log out and log back in (or run: newgrp powercap) for group changes to take effect"
        echo "   2. Test with: python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
        echo ""
        echo "🔍 To verify setup:"
        echo "   - Check groups: groups"
        echo "   - Check RAPL files: ls -la /sys/class/powercap/intel-rapl:0/energy_uj"
        echo ""
        echo "💡 Quick test without logout: newgrp powercap"
        ;;
esac

echo ""
echo "🔧 Common troubleshooting:"
echo "   • If 'Permission denied': ensure you're in powercap group (groups command)"
echo "   • If no energy readings: check hardware support (ls /sys/class/powercap/)"
echo "   • For containers: may need --privileged or specific capabilities"
echo "   • For VMs: ensure energy counters are exposed to guest"
echo ""
echo "📚 Documentation: https://github.com/SMART-Dal/codegreen/docs/setup"
