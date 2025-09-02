#!/usr/bin/env python3
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
        
        return "\n".join(metrics) + "\n"
    
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
