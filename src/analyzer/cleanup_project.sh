#!/bin/bash

# CodeGreen Project Cleanup Script
# Removes redundant files and optimizes the project structure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🧹 CodeGreen Project Cleanup"
echo "============================"
echo "Project directory: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

# 1. Clean build artifacts (keep the binary)
echo "1. Cleaning build artifacts..."
if [ -d "build" ]; then
    # Keep the binary but clean intermediate files
    find build/ -name "*.o" -delete 2>/dev/null || true
    find build/ -name "*.cmake" -delete 2>/dev/null || true
    find build/ -name "CMakeCache.txt" -delete 2>/dev/null || true
    find build/ -name "CMakeFiles" -type d -exec rm -rf {} + 2>/dev/null || true
    echo "✅ Build artifacts cleaned (binary preserved)"
else
    echo "ℹ️  No build directory found"
fi

# 2. Remove redundant report directories  
echo ""
echo "2. Cleaning report directories..."
if [ -d "reports_demo" ]; then
    rm -rf reports_demo/
    echo "✅ Removed reports_demo/ (demo data only)"
fi

if [ -d "reports" ] && [ -z "$(ls -A reports 2>/dev/null)" ]; then
    rm -rf reports/
    echo "✅ Removed empty reports/ directory"
fi

# Keep reports_enhanced/ - has the advanced code analysis
echo "✅ Keeping reports_enhanced/ (enhanced analysis)"

# 3. Optimize SQLite database
echo ""
echo "3. Optimizing SQLite database..."
if [ -f "energy_data.db" ]; then
    ORIGINAL_SIZE=$(ls -lh energy_data.db | awk '{print $5}')
    sqlite3 energy_data.db "VACUUM;" 2>/dev/null || true
    NEW_SIZE=$(ls -lh energy_data.db | awk '{print $5}')
    echo "✅ Database optimized: $ORIGINAL_SIZE → $NEW_SIZE"
else
    echo "ℹ️  No database file found"
fi

# 4. Clean temporary files
echo ""
echo "4. Cleaning temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true  
find . -name "*.log" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean old instrumented files in /tmp
find /tmp -name "codegreen_*" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true

echo "✅ Temporary files cleaned"

# 5. Show project structure summary
echo ""
echo "📊 Project Structure Summary:"
echo "=============================="

echo ""
echo "🔧 Core Components:"
ls -la bin/ 2>/dev/null | head -3 || echo "   No bin/ directory"
ls -la core/ | head -3
ls -la packages/ | head -3

echo ""
echo "📊 Visualization:"
echo "   • Grafana dashboard: grafana/codegreen-dashboard.json"
echo "   • Enhanced reports: reports_enhanced/"
echo "   • Monitoring scripts: scripts/{start,stop}_monitoring.sh"

echo ""
echo "💾 Data Storage:"
if [ -f "energy_data.db" ]; then
    echo "   • SQLite database: energy_data.db ($(ls -lh energy_data.db | awk '{print $5}'))"
    sqlite3 energy_data.db "SELECT COUNT(*) FROM sessions;" 2>/dev/null | xargs -I {} echo "   • Sessions stored: {}" || true
else
    echo "   • No database found"
fi

echo ""
echo "🎯 Usage Summary:"
echo "=================="
echo "• Generate reports:  python3 scripts/generate_energy_report.py"
echo "• View HTML reports: python3 scripts/view_reports.py"  
echo "• Start monitoring:  ./scripts/start_monitoring.sh"
echo "• Run CodeGreen:     ./bin/codegreen python3 script.py"

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📋 Architecture Summary:"
echo "  SQLite (primary storage) → HTML Reports (detailed analysis)"  
echo "  SQLite (primary storage) → Prometheus → Grafana (real-time monitoring)"
echo "  No redundancy - each component serves unique purposes"