#!/bin/bash

# Stop CodeGreen Monitoring Stack

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
MONITORING_DIR="$BASE_DIR/monitoring"

echo "🛑 Stopping CodeGreen Monitoring Stack"
echo "======================================"

# Stop Prometheus exporter
if [ -f "$MONITORING_DIR/exporter.pid" ]; then
    EXPORTER_PID=$(cat "$MONITORING_DIR/exporter.pid")
    if kill -0 "$EXPORTER_PID" 2>/dev/null; then
        kill "$EXPORTER_PID"
        echo "✅ Stopped Prometheus exporter (PID: $EXPORTER_PID)"
    fi
    rm -f "$MONITORING_DIR/exporter.pid"
fi

# Stop Docker containers
if [ -f "$MONITORING_DIR/prometheus.container" ]; then
    CONTAINER=$(cat "$MONITORING_DIR/prometheus.container")
    if docker ps -q -f name="$CONTAINER" | grep -q .; then
        docker stop "$CONTAINER" > /dev/null 2>&1
        docker rm "$CONTAINER" > /dev/null 2>&1
        echo "✅ Stopped Prometheus container"
    fi
    rm -f "$MONITORING_DIR/prometheus.container"
fi

if [ -f "$MONITORING_DIR/grafana.container" ]; then
    CONTAINER=$(cat "$MONITORING_DIR/grafana.container")
    if docker ps -q -f name="$CONTAINER" | grep -q .; then
        docker stop "$CONTAINER" > /dev/null 2>&1
        docker rm "$CONTAINER" > /dev/null 2>&1
        echo "✅ Stopped Grafana container"
    fi
    rm -f "$MONITORING_DIR/grafana.container"
fi

echo ""
echo "✅ All monitoring services stopped"