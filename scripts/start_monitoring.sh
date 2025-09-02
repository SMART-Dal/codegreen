#!/bin/bash

# CodeGreen Monitoring Stack - Simple Docker Setup
# Sets up Prometheus and Grafana without docker-compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
MONITORING_DIR="$BASE_DIR/monitoring"

echo "🚀 CodeGreen Monitoring Stack Setup"
echo "===================================="

# Create directories
mkdir -p "$MONITORING_DIR"/{data/prometheus,data/grafana}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker to use Grafana visualization"
    echo ""
    echo "🔧 Alternative: View HTML reports directly"
    echo "   File location: $BASE_DIR/reports_enhanced/energy_report.html"
    echo "   Open in browser to see code energy analysis with peak detection"
    exit 1
fi

# Create Prometheus config
cat > "$MONITORING_DIR/prometheus.yml" << EOF
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: 'codegreen'
    static_configs:
      - targets: ['host.docker.internal:8080']
    scrape_interval: 2s
    metrics_path: '/metrics'
EOF

echo "✅ Created Prometheus config"

# Start Prometheus exporter in background
echo "🔄 Starting CodeGreen Prometheus exporter..."
python3 "$MONITORING_DIR/prometheus_exporter.py" &
EXPORTER_PID=$!
sleep 2

# Start Prometheus
echo "🔄 Starting Prometheus..."
docker run -d \
  --name codegreen-prometheus \
  -p 9090:9090 \
  -v "$MONITORING_DIR/prometheus.yml:/etc/prometheus/prometheus.yml" \
  -v "$MONITORING_DIR/data/prometheus:/prometheus" \
  --add-host=host.docker.internal:host-gateway \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.enable-lifecycle

# Start Grafana
echo "🔄 Starting Grafana..."
docker run -d \
  --name codegreen-grafana \
  -p 3000:3000 \
  -v "$MONITORING_DIR/data/grafana:/var/lib/grafana" \
  -e "GF_SECURITY_ADMIN_PASSWORD=codegreen123" \
  -e "GF_USERS_ALLOW_SIGN_UP=false" \
  grafana/grafana:latest

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if curl -s http://localhost:9090 > /dev/null; then
    echo "✅ Prometheus started successfully"
else
    echo "⚠️  Prometheus may not be ready yet"
fi

if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Grafana started successfully"
else
    echo "⚠️  Grafana may not be ready yet"
fi

echo ""
echo "📊 CodeGreen Monitoring Stack Ready!"
echo "===================================="
echo ""
echo "🌐 Access URLs:"
echo "   • Prometheus: http://localhost:9090"
echo "   • Grafana: http://localhost:3000"
echo "   • CodeGreen Metrics: http://localhost:8080/metrics"
echo ""
echo "🔑 Grafana Login:"
echo "   • Username: admin"
echo "   • Password: codegreen123"
echo ""
echo "📋 Next Steps:"
echo "   1. Open Grafana: http://localhost:3000"
echo "   2. Add Prometheus data source: http://host.docker.internal:9090"
echo "   3. Import dashboard: $BASE_DIR/grafana/codegreen-dashboard.json"
echo ""
echo "📈 Enhanced Reports Available:"
echo "   • HTML Report: $BASE_DIR/reports_enhanced/energy_report.html"
echo "   • Code Analysis: $BASE_DIR/reports_enhanced/code_energy_analysis_session_demo_1.png"
echo ""
echo "🛑 To stop: ./stop_monitoring.sh"

# Save PIDs for cleanup
echo "$EXPORTER_PID" > "$MONITORING_DIR/exporter.pid"
echo "codegreen-prometheus" > "$MONITORING_DIR/prometheus.container"
echo "codegreen-grafana" > "$MONITORING_DIR/grafana.container"