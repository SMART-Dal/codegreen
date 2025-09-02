# CodeGreen Visualization & Monitoring Guide

This guide shows you how to visualize CodeGreen energy measurements using both **Grafana dashboards** and **enhanced HTML reports** with code-line energy analysis.

## 🎯 Quick Setup Summary

1. **Clean Grafana Setup**: Removed redundant old dashboard, kept optimized Prometheus-based version
2. **Enhanced Reports**: Added code-line energy mapping with peak detection algorithm  
3. **Easy Monitoring**: Simple scripts to start/stop Prometheus + Grafana stack

---

## 📊 Option 1: Grafana Dashboard (Real-time)

### Setup Grafana + Prometheus Monitoring

```bash
# Start monitoring stack
./scripts/start_monitoring.sh

# Access Grafana
# URL: http://localhost:3000
# Username: admin
# Password: codegreen123
```

### Import Dashboard
1. Open Grafana: http://localhost:3000
2. Login with admin/codegreen123  
3. Add Prometheus data source: `http://host.docker.internal:9090`
4. Import dashboard: `grafana/codegreen-dashboard.json`

### Dashboard Features
- **Real-time energy consumption** timeline
- **Session duration** tracking
- **Function-level** energy breakdown  
- **Programming language** comparison
- **Top energy-consuming files** analysis

### Stop Monitoring
```bash
./scripts/stop_monitoring.sh
```

---

## 📈 Option 2: Enhanced HTML Reports (Detailed Analysis)

### Generate Reports with Code Analysis
```bash
# Generate enhanced reports
python3 scripts/generate_energy_report.py --output reports_enhanced

# View in browser
python3 scripts/view_reports.py
```

### 🔥 NEW: Code-Line Energy Analysis

The enhanced reports now include **advanced peak detection** that shows:

#### ✨ Peak Detection Algorithm
- **Peak Threshold**: Top 10% energy consumers (computational hotspots)
- **Noise Threshold**: Bottom 25% energy consumers (measurement noise)
- **Significant Operations**: Normal energy consumption (25-90th percentile)

#### 📊 Visualizations Include:
1. **Energy by Source Line** - Color-coded bar chart:
   - 🔴 **Red**: Energy peaks (optimize these first!)
   - 🟠 **Orange**: Significant operations  
   - 🔵 **Blue**: Low impact/noise

2. **Top 10 Energy Peak Lines** - Exact line numbers causing energy spikes
   - Shows function names and line numbers
   - Identifies computational hotspots

3. **Peak vs Noise Classification** - Pie chart showing:
   - How many lines are real peaks vs noise
   - Helps distinguish actual issues from measurement artifacts

4. **Function Peak Contribution** - Which functions contribute most to energy peaks

#### 🎯 Interpretation Guide:
- **🔥 PEAK lines**: Computational hotspots - **optimize these first**
- **⚡ Significant lines**: Normal energy consumption  
- **🔵 Noise lines**: Low impact - measurement noise or trivial operations

---

## 📋 Report Contents Comparison

| Feature | Grafana Dashboard | Enhanced HTML Reports |
|---------|------------------|----------------------|
| Real-time monitoring | ✅ | ❌ |
| Historical analysis | ✅ | ✅ |
| Code-line mapping | ❌ | ✅ |
| Peak detection | ❌ | ✅ |
| Function breakdown | ✅ | ✅ |
| Noise filtering | ❌ | ✅ |
| Source line context | ❌ | ✅ |

---

## 🛠️ Troubleshooting

### Docker Issues
If Docker is not available:
- Use HTML reports instead: `python3 scripts/view_reports.py`
- Reports provide more detailed analysis than Grafana

### No Data in Grafana
1. Check Prometheus exporter: http://localhost:8080/metrics
2. Verify Prometheus config: `monitoring/prometheus.yml`
3. Run CodeGreen measurements to generate data

### Missing Reports
```bash
# Generate fresh reports with sample data
python3 scripts/generate_energy_report.py --output reports_new
```

---

## 🎨 File Locations

```
codegreen/
├── grafana/
│   ├── codegreen-dashboard.json    # ✅ Prometheus-based dashboard (KEEP)
│   └── README.md                   # Setup instructions
├── scripts/
│   ├── start_monitoring.sh         # Start Grafana + Prometheus
│   ├── stop_monitoring.sh          # Stop monitoring stack
│   ├── view_reports.py             # View HTML reports in browser
│   └── generate_energy_report.py   # Generate enhanced reports
├── reports_enhanced/
│   ├── energy_report.html          # 🔥 Main report with code analysis
│   ├── timeline_*.png              # Energy over time
│   ├── function_analysis_*.png     # Function-level analysis  
│   ├── heatmap_*.png               # Energy distribution heatmap
│   └── code_energy_analysis_*.png  # 🔥 Code-line peak analysis
└── monitoring/
    ├── prometheus.yml              # Prometheus configuration
    └── docker-compose.yml          # Container orchestration
```

---

## 🚀 Next Steps

1. **Try both approaches**: Start with HTML reports for detailed analysis, then use Grafana for real-time monitoring
2. **Run CodeGreen on your code**: `./bin/codegreen python3 your_script.py`
3. **Analyze peaks**: Look for 🔥 red lines in code analysis - these are your optimization targets
4. **Optimize code**: Focus on peak lines first for maximum energy savings

The enhanced visualization now gives you **exact source line attribution** and **distinguishes real energy peaks from measurement noise** - making CodeGreen much more actionable for code optimization!