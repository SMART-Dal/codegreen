#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print status
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_warning "Please do not run this script as root"
    exit 1
fi

# Check for required tools
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is required but not installed"
        exit 1
    fi
}

print_status "Checking dependencies..."
check_dependency docker
check_dependency docker-compose

# Create docker network if it doesn't exist
print_status "Creating docker network..."
docker network create codegreen-network 2>/dev/null || true

# Start InfluxDB
print_status "Starting InfluxDB..."
docker-compose -f docker/influxdb/docker-compose.yml up -d

# Start Prometheus
print_status "Starting Prometheus..."
docker-compose -f docker/prometheus/docker-compose.yml up -d

# Start Grafana
print_status "Starting Grafana..."
docker-compose -f docker/grafana/docker-compose.yml up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if services are running
check_service() {
    if ! curl -s "$1" > /dev/null; then
        print_error "Service at $1 is not responding"
        exit 1
    fi
}

print_status "Checking service health..."
check_service "http://localhost:8086/health"  # InfluxDB
check_service "http://localhost:9090/-/healthy"  # Prometheus
check_service "http://localhost:3000/api/health"  # Grafana

print_status "All services are running!"
print_status "InfluxDB: http://localhost:8086"
print_status "Prometheus: http://localhost:9090"
print_status "Grafana: http://localhost:3000" 