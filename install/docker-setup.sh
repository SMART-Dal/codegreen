#!/bin/bash

# CodeGreen Docker/Container Setup Helper
# Provides container-specific setup instructions and validation

echo "🐳 CodeGreen Container Setup"
echo "================================"

# Check if running in container
if [[ -f /.dockerenv ]] || [[ -n "${CONTAINER}" ]]; then
    echo "✅ Running inside container"
    
    # Check for required mount points
    if [[ -d "/sys/class/powercap" ]] && [[ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]]; then
        echo "✅ RAPL energy files accessible"
    else
        echo "❌ RAPL energy files not accessible"
        echo "   Container needs: -v /sys/class/powercap:/sys/class/powercap:ro"
    fi
    
    # Check for capabilities
    if [[ $(cat /proc/self/status | grep "CapEff" | cut -f2) != "0000000000000000" ]]; then
        echo "✅ Container has some capabilities"
    else
        echo "⚠️  Container may need --privileged or specific capabilities"
    fi
    
else
    echo "📋 Docker run examples for CodeGreen:"
    echo ""
    echo "🔸 Basic energy monitoring:"
    echo "   docker run --rm -v /sys/class/powercap:/sys/class/powercap:ro \\"
    echo "              -v \$(pwd):/workspace your-image \\"
    echo "              python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
    echo ""
    echo "🔸 Full privileged mode (for all hardware access):"
    echo "   docker run --privileged --rm -v \$(pwd):/workspace your-image \\"
    echo "              python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"
    echo ""
    echo "🔸 Docker Compose example:"
    echo "   version: '3.8'"
    echo "   services:"
    echo "     codegreen:"
    echo "       image: your-image"
    echo "       privileged: true"
    echo "       volumes:"
    echo "         - /sys/class/powercap:/sys/class/powercap:ro"
    echo "         - ./:/workspace"
fi

echo ""
echo "🧪 Testing container energy access:"
echo "   python codegreen/cli.py info"
echo "   python codegreen/cli.py run --repeat 3 -- python3 -c 'sum(range(10**7))'"