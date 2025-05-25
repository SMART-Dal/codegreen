# Codegreen Installation Guide

Codegreen is a comprehensive energy measurement tool that provides insights across multiple programming languages and hardware architectures. This guide will help you set up and run the tool.

## Prerequisites

### System Requirements
- Linux operating system (tested on Ubuntu 20.04+)
- Rust toolchain (latest stable)
- Docker and Docker Compose
- Python 3.8+ (for Python bindings)
- CMake 3.10+
- Build essentials (gcc, make, etc.)

### Required Hardware Support
- Intel CPU with RAPL support (for CPU energy measurements)
- NVIDIA GPU (optional, for GPU energy measurements)
- ARM CPU (optional, for ARM-specific measurements)

## Quick Start

### 1. Install Dependencies

#### Ubuntu/Debian
```bash
# System dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    python3-dev \
    python3-pip \
    docker.io \
    docker-compose

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install Python dependencies
pip3 install maturin
```

#### CentOS/RHEL
```bash
# System dependencies
sudo yum groupinstall "Development Tools"
sudo yum install cmake openssl-devel python3-devel python3-pip docker docker-compose

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install Python dependencies
pip3 install maturin
```

### 2. Clone and Build

```bash
# Clone the repository
git clone ...
cd codegreen

# Build all packages
./scripts/build.sh
```

### 3. Start Services

```bash
# Start required services (InfluxDB, Prometheus, Grafana)
./scripts/start-services.sh
```

### 4. Install Python Package (Optional)

```bash
# Install Python package
cd packages/energy-instrumentation
maturin develop
```

## Project Structure

```
codegreen/
├── packages/
│   ├── energy-core/           # Core measurement engine
│   ├── energy-instrumentation/ # Code instrumentation
│   ├── energy-language-adapters/ # Language-specific adapters
│   ├── energy-hardware-plugins/  # Hardware measurement plugins
│   ├── energy-visualization/     # Visualization and dashboards
│   └── energy-optimizer/         # Energy optimization tools
├── scripts/
│   ├── build.sh              # Build script
│   ├── start-services.sh     # Service startup script
│   └── install-deps.sh       # Dependency installation
├── docker/
│   ├── influxdb/            # InfluxDB configuration
│   ├── prometheus/          # Prometheus configuration
│   └── grafana/             # Grafana configuration
└── docs/                    # Documentation
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
INFLUXDB_URL=http://localhost:8086
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
```

### Hardware Configuration

#### Intel RAPL
```bash
# Enable RAPL access
sudo modprobe msr
sudo chmod 666 /dev/cpu/*/msr
```

#### NVIDIA GPU
```bash
# Install NVIDIA drivers and CUDA toolkit
sudo apt-get install nvidia-driver-xxx cuda-toolkit
```

## Usage Examples

### Basic Usage

```python
from codegreen import EnergyInstrumentation

# Initialize the instrumentation engine
engine = EnergyInstrumentation()

# Instrument Python code
instrumented_code = engine.instrument("""
def calculate_sum(a, b):
    return a + b
""", "python")
```

### Command Line Usage

```bash
# Run energy measurement
codegreen measure --file example.py --language python

# View energy consumption dashboard
codegreen dashboard
```

## Troubleshooting

### Common Issues

1. **Permission Denied for RAPL**
   ```bash
   sudo chmod 666 /dev/cpu/*/msr
   ```

2. **Docker Service Issues**
   ```bash
   sudo systemctl restart docker
   ```

3. **Build Failures**
   ```bash
   # Clean and rebuild
   ./scripts/clean.sh
   ./scripts/build.sh
   ```

## Support

For issues and feature requests, please visit our [GitHub repository](https://github.com/yourusername/codegreen).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 