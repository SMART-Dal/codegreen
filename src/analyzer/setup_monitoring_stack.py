#!/usr/bin/env python3
"""
CodeGreen Monitoring Stack Setup
Sets up Prometheus + Grafana for energy monitoring visualization
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

class MonitoringStackManager:
    def __init__(self, base_dir="/home/srajput/codegreen"):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "monitoring"
        self.data_dir = self.base_dir / "monitoring" / "data"
        
        # Create directories
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        (self.data_dir / "prometheus").mkdir(exist_ok=True)
        (self.data_dir / "grafana").mkdir(exist_ok=True)
    
    def create_prometheus_config(self):
        """Create Prometheus configuration"""
        config = {
            "global": {
                "scrape_interval": "5s",
                "evaluation_interval": "5s"
            },
            "scrape_configs": [
                {
                    "job_name": "codegreen",
                    "static_configs": [
                        {"targets": ["localhost:8080"]}
                    ],
                    "scrape_interval": "2s",
                    "metrics_path": "/metrics"
                }
            ]
        }
        
        config_file = self.config_dir / "prometheus.yml"
        with open(config_file, 'w') as f:
            import yaml
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"✅ Prometheus config created: {config_file}")
        return config_file
    
    def create_docker_compose(self):
        """Create Docker Compose for Prometheus + Grafana"""
        compose_config = {
            "version": "3.8",
            "services": {
                "prometheus": {
                    "image": "prom/prometheus:latest",
                    "container_name": "codegreen-prometheus",
                    "ports": ["9090:9090"],
                    "volumes": [
                        f"{self.config_dir}/prometheus.yml:/etc/prometheus/prometheus.yml",
                        f"{self.data_dir}/prometheus:/prometheus"
                    ],
                    "command": [
                        "--config.file=/etc/prometheus/prometheus.yml",
                        "--storage.tsdb.path=/prometheus",
                        "--web.console.libraries=/etc/prometheus/console_libraries",
                        "--web.console.templates=/etc/prometheus/consoles",
                        "--storage.tsdb.retention.time=15d",
                        "--web.enable-lifecycle"
                    ]
                },
                "grafana": {
                    "image": "grafana/grafana:latest",
                    "container_name": "codegreen-grafana",
                    "ports": ["3000:3000"],
                    "volumes": [
                        f"{self.data_dir}/grafana:/var/lib/grafana"
                    ],
                    "environment": [
                        "GF_SECURITY_ADMIN_PASSWORD=codegreen123",
                        "GF_USERS_ALLOW_SIGN_UP=false"
                    ]
                }
            }
        }
        
        compose_file = self.config_dir / "docker-compose.yml"
        with open(compose_file, 'w') as f:
            import yaml
            yaml.dump(compose_config, f, default_flow_style=False)
        
        print(f"✅ Docker Compose created: {compose_file}")
        return compose_file
    
    def setup_prometheus_exporter(self):
        """Create a simple Prometheus metrics exporter for CodeGreen"""
        exporter_code = '''#!/usr/bin/env python3
"""
CodeGreen Prometheus Metrics Exporter
Serves energy metrics on :8080/metrics for Prometheus scraping
"""

import time
import random
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            metrics = self.generate_metrics()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(metrics.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def generate_metrics(self):
        """Generate Prometheus metrics from CodeGreen data"""
        metrics = []
        
        # Try to read from actual database
        db_path = "/home/srajput/codegreen/energy_data.db"
        if Path(db_path).exists():
            metrics.extend(self.read_database_metrics(db_path))
        else:
            # Generate sample metrics for demonstration
            metrics.extend(self.generate_sample_metrics())
        
        return "\\n".join(metrics) + "\\n"
    
    def read_database_metrics(self, db_path):
        """Read actual metrics from CodeGreen database"""
        metrics = []
        try:
            conn = sqlite3.connect(db_path)
            
            # Session metrics
            cursor = conn.execute("SELECT session_id, total_energy, duration FROM sessions ORDER BY created_at DESC LIMIT 10")
            for session_id, energy, duration in cursor.fetchall():
                if energy and duration:
                    metrics.append(f'codegreen_session_total_energy_joules{{session_id="{session_id}"}} {energy}')
                    metrics.append(f'codegreen_session_duration_seconds{{session_id="{session_id}"}} {duration}')
            
            # Checkpoint metrics
            cursor = conn.execute("""
                SELECT session_id, checkpoint_type, function_name, energy_consumed, line_number 
                FROM checkpoints WHERE energy_consumed > 0 ORDER BY timestamp DESC LIMIT 50
            """)
            for session_id, checkpoint_type, func_name, energy, line_num in cursor.fetchall():
                if energy:
                    labels = f'session_id="{session_id}",type="{checkpoint_type}",function="{func_name}",line="{line_num}"'
                    metrics.append(f'codegreen_checkpoint_energy_joules{{{labels}}} {energy}')
            
            conn.close()
        except Exception as e:
            print(f"Database error: {e}")
            metrics.extend(self.generate_sample_metrics())
        
        return metrics
    
    def generate_sample_metrics(self):
        """Generate sample metrics for testing"""
        timestamp = int(time.time() * 1000)
        metrics = [
            f'codegreen_session_total_energy_joules{{session_id="demo_session",language="python"}} {random.uniform(1.0, 5.0)}',
            f'codegreen_session_duration_seconds{{session_id="demo_session",language="python"}} {random.uniform(0.1, 1.0)}',
            f'codegreen_checkpoint_energy_joules{{session_id="demo_session",type="function_enter",function="main",line="60"}} {random.uniform(0.001, 0.1)}',
            f'codegreen_checkpoint_energy_joules{{session_id="demo_session",type="loop_start",function="process_data",line="23"}} {random.uniform(0.01, 0.5)}',
            f'codegreen_checkpoint_energy_joules{{session_id="demo_session",type="function_call",function="fibonacci_recursive",line="48"}} {random.uniform(0.005, 0.2)}'
        ]
        return metrics
    
    def log_message(self, format, *args):
        # Suppress HTTP request logs
        pass

def run_exporter(port=8080):
    """Run the Prometheus metrics exporter"""
    server = HTTPServer(('localhost', port), MetricsHandler)
    print(f"🚀 CodeGreen Prometheus Exporter running on http://localhost:{port}/metrics")
    server.serve_forever()

if __name__ == "__main__":
    run_exporter()
'''
        
        exporter_file = self.config_dir / "prometheus_exporter.py"
        with open(exporter_file, 'w') as f:
            f.write(exporter_code)
        
        # Make executable
        os.chmod(exporter_file, 0o755)
        print(f"✅ Prometheus exporter created: {exporter_file}")
        return exporter_file
    
    def start_monitoring_stack(self):
        """Start the monitoring stack"""
        try:
            # Create required YAML library
            try:
                import yaml
            except ImportError:
                print("Installing PyYAML...")
                subprocess.run([sys.executable, "-m", "pip", "install", "PyYAML"], check=True)
                import yaml
            
            # Create configurations
            self.create_prometheus_config()
            compose_file = self.create_docker_compose()
            exporter_file = self.setup_prometheus_exporter()
            
            print("\n🔧 Starting monitoring stack...")
            
            # Start Prometheus exporter in background
            print("1. Starting CodeGreen Prometheus exporter...")
            exporter_process = subprocess.Popen([
                sys.executable, str(exporter_file)
            ])
            
            # Give exporter time to start
            time.sleep(2)
            
            # Start Docker services
            print("2. Starting Prometheus and Grafana with Docker...")
            result = subprocess.run([
                "docker-compose", "-f", str(compose_file), "up", "-d"
            ], cwd=self.config_dir, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Monitoring stack started successfully!")
                print("\n📊 Access URLs:")
                print("   • Prometheus: http://localhost:9090")
                print("   • Grafana: http://localhost:3000")
                print("   • CodeGreen Metrics: http://localhost:8080/metrics")
                print("\n🔑 Grafana Login:")
                print("   • Username: admin")
                print("   • Password: codegreen123")
                print("\n📋 Next steps:")
                print("   1. Open Grafana at http://localhost:3000")
                print("   2. Add Prometheus data source: http://localhost:9090") 
                print("   3. Import dashboard from grafana/codegreen-dashboard.json")
                
                return True
            else:
                print(f"❌ Failed to start Docker services: {result.stderr}")
                exporter_process.terminate()
                return False
                
        except Exception as e:
            print(f"❌ Error starting monitoring stack: {e}")
            return False
    
    def stop_monitoring_stack(self):
        """Stop the monitoring stack"""
        try:
            compose_file = self.config_dir / "docker-compose.yml"
            subprocess.run([
                "docker-compose", "-f", str(compose_file), "down"
            ], cwd=self.config_dir)
            
            # Kill prometheus exporter
            subprocess.run(["pkill", "-f", "prometheus_exporter.py"])
            
            print("✅ Monitoring stack stopped")
            
        except Exception as e:
            print(f"❌ Error stopping monitoring stack: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='CodeGreen Monitoring Stack Manager')
    parser.add_argument('action', choices=['start', 'stop'], help='Action to perform')
    
    args = parser.parse_args()
    
    manager = MonitoringStackManager()
    
    if args.action == 'start':
        success = manager.start_monitoring_stack()
        if success:
            print("\\n⚡ Run CodeGreen measurements to see live metrics in Grafana!")
        sys.exit(0 if success else 1)
    elif args.action == 'stop':
        manager.stop_monitoring_stack()

if __name__ == "__main__":
    main()