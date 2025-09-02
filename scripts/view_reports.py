#!/usr/bin/env python3
"""
CodeGreen Report Viewer
Opens enhanced energy analysis reports in browser
"""

import os
import sys
import webbrowser
import http.server
import socketserver
from pathlib import Path
import threading
import time

def serve_reports(report_dir, port=8000):
    """Serve reports via HTTP server"""
    os.chdir(report_dir)
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress HTTP request logs
            pass
    
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"📊 Serving reports at http://localhost:{port}")
        httpd.serve_forever()

def main():
    base_dir = Path(__file__).parent.parent
    report_dirs = [
        base_dir / "reports_enhanced",
        base_dir / "reports_demo",
        base_dir / "reports"
    ]
    
    # Find the most recent report directory
    report_dir = None
    for dir_path in report_dirs:
        if dir_path.exists() and (dir_path / "energy_report.html").exists():
            report_dir = dir_path
            break
    
    if not report_dir:
        print("❌ No energy reports found!")
        print("Generate reports first using: python3 scripts/generate_energy_report.py")
        return
    
    print(f"🔍 Found reports in: {report_dir}")
    
    # List available reports
    html_files = list(report_dir.glob("*.html"))
    png_files = list(report_dir.glob("*.png"))
    
    print(f"📄 HTML Reports: {len(html_files)}")
    print(f"📊 Visualizations: {len(png_files)}")
    
    # Show available visualizations
    if png_files:
        print("\\n🎨 Available Energy Visualizations:")
        for png_file in png_files:
            name = png_file.stem
            if "timeline" in name:
                print(f"   • {png_file.name} - Energy consumption over time")
            elif "function_analysis" in name:
                print(f"   • {png_file.name} - Function-level energy breakdown")
            elif "heatmap" in name:
                print(f"   • {png_file.name} - Energy distribution heatmap")
            elif "code_energy_analysis" in name:
                print(f"   • {png_file.name} - 🔥 CODE-LINE ENERGY ANALYSIS WITH PEAKS!")
            else:
                print(f"   • {png_file.name}")
    
    # Start HTTP server in background
    port = 8000
    server_thread = threading.Thread(target=serve_reports, args=(str(report_dir), port))
    server_thread.daemon = True
    server_thread.start()
    
    # Give server time to start
    time.sleep(1)
    
    # Open main report in browser
    main_report = report_dir / "energy_report.html"
    if main_report.exists():
        url = f"http://localhost:{port}/energy_report.html"
        print(f"\\n🌐 Opening main report in browser: {url}")
        webbrowser.open(url)
        
        print("\\n📋 Report Contents:")
        print("   ✅ Session energy statistics")
        print("   📈 Timeline visualization") 
        print("   🔧 Function analysis")
        print("   🗺️  Energy distribution heatmap")
        print("   🔥 CODE-LINE PEAK ANALYSIS - Shows which lines cause energy spikes!")
        
        # Check if we have the enhanced code analysis
        code_analysis_files = [f for f in png_files if "code_energy_analysis" in f.name]
        if code_analysis_files:
            print("\\n🎯 Enhanced Code Analysis Available:")
            print("   • Peak detection algorithm identifies energy hotspots")
            print("   • Separates computational peaks from measurement noise")
            print("   • Shows exact source lines causing high energy consumption")
            print("   • Function-level peak contribution analysis")
        
        print("\\n💡 Tip: Keep this terminal open to keep the web server running")
        print("Press Ctrl+C to stop")
        
        try:
            # Keep server running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\\n🛑 Stopping report server...")
            
    else:
        print(f"❌ Main report not found: {main_report}")

if __name__ == "__main__":
    main()