#!/usr/bin/env python3
"""
CodeGreen Energy Report Generator
Creates comprehensive energy analysis reports with visualizations
"""

import sys
import os
import sqlite3
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import pandas as pd
import seaborn as sns
import numpy as np
from pathlib import Path
import argparse

# Set style for better-looking plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

class EnergyReportGenerator:
    def __init__(self, db_path="energy_data.db", output_dir="reports"):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def connect_database(self):
        """Connect to SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
    
    def get_session_data(self, session_id=None):
        """Retrieve session data from database"""
        conn = self.connect_database()
        if not conn:
            return None
            
        try:
            if session_id:
                cursor = conn.execute("""
                    SELECT * FROM sessions WHERE session_id = ?
                """, (session_id,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10
                """)
                
            sessions = [dict(row) for row in cursor.fetchall()]
            
            # Get checkpoint data for each session
            for session in sessions:
                cursor = conn.execute("""
                    SELECT * FROM checkpoints 
                    WHERE session_id = ? 
                    ORDER BY timestamp
                """, (session['session_id'],))
                session['checkpoints'] = [dict(row) for row in cursor.fetchall()]
                
            return sessions
            
        except sqlite3.Error as e:
            print(f"Query error: {e}")
            return None
        finally:
            conn.close()
    
    def generate_session_timeline(self, session):
        """Generate timeline visualization for a session"""
        if not session['checkpoints']:
            return None
            
        # Prepare data
        timestamps = []
        energy_values = []
        checkpoint_types = []
        
        for checkpoint in session['checkpoints']:
            if checkpoint['energy_consumed']:
                timestamps.append(datetime.fromisoformat(checkpoint['timestamp']))
                energy_values.append(float(checkpoint['energy_consumed']))
                checkpoint_types.append(checkpoint['checkpoint_type'])
        
        if not timestamps:
            return None
            
        # Create plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Timeline plot
        ax1.plot(timestamps, energy_values, marker='o', linewidth=2, markersize=4)
        ax1.set_title(f'Energy Consumption Timeline - Session {session["session_id"]}', 
                     fontsize=16, fontweight='bold')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Energy (Joules)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Cumulative energy plot
        cumulative_energy = [sum(energy_values[:i+1]) for i in range(len(energy_values))]
        ax2.plot(timestamps, cumulative_energy, color='red', linewidth=2)
        ax2.fill_between(timestamps, cumulative_energy, alpha=0.3, color='red')
        ax2.set_title('Cumulative Energy Consumption', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Cumulative Energy (Joules)')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_dir / f"timeline_{session['session_id']}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def generate_function_analysis(self, session):
        """Generate function-level energy analysis"""
        if not session['checkpoints']:
            return None
            
        # Group by function
        function_energy = {}
        for checkpoint in session['checkpoints']:
            if checkpoint['energy_consumed'] and checkpoint['function_name']:
                func_name = checkpoint['function_name']
                energy = float(checkpoint['energy_consumed'])
                
                if func_name not in function_energy:
                    function_energy[func_name] = []
                function_energy[func_name].append(energy)
        
        if not function_energy:
            return None
            
        # Calculate statistics
        func_stats = {}
        for func, energies in function_energy.items():
            func_stats[func] = {
                'total': sum(energies),
                'avg': sum(energies) / len(energies),
                'count': len(energies),
                'max': max(energies),
                'min': min(energies)
            }
        
        # Create visualizations
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # Total energy by function (bar chart)
        functions = list(func_stats.keys())
        total_energies = [func_stats[f]['total'] for f in functions]
        
        bars = ax1.bar(functions, total_energies)
        ax1.set_title('Total Energy by Function', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Total Energy (Joules)')
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, total_energies):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{value:.3f}', ha='center', va='bottom', fontsize=8)
        
        # Average energy by function (horizontal bar)
        avg_energies = [func_stats[f]['avg'] for f in functions]
        ax2.barh(functions, avg_energies)
        ax2.set_title('Average Energy per Call', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Average Energy (Joules)')
        
        # Function call count
        call_counts = [func_stats[f]['count'] for f in functions]
        ax3.bar(functions, call_counts, color='orange')
        ax3.set_title('Function Call Frequency', fontsize=14, fontweight='bold')
        ax3.set_ylabel('Number of Calls')
        ax3.tick_params(axis='x', rotation=45)
        
        # Energy distribution pie chart
        ax4.pie(total_energies, labels=functions, autopct='%1.1f%%', startangle=90)
        ax4.set_title('Energy Distribution by Function', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_dir / f"function_analysis_{session['session_id']}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path), func_stats
    
    def generate_code_energy_analysis(self, session):
        """Generate detailed code-line energy analysis with peak detection"""
        if not session['checkpoints']:
            return None
            
        # Build line-to-energy mapping
        line_energy_map = {}
        peak_threshold_percentile = 90  # Top 10% are considered peaks
        
        # Collect energy by line number
        energy_values = []
        for checkpoint in session['checkpoints']:
            if checkpoint['energy_consumed'] and checkpoint['line_number']:
                line_num = checkpoint['line_number']
                energy = float(checkpoint['energy_consumed'])
                energy_values.append(energy)
                
                if line_num not in line_energy_map:
                    line_energy_map[line_num] = {
                        'total_energy': 0,
                        'count': 0,
                        'checkpoints': [],
                        'function_name': checkpoint.get('function_name', 'unknown')
                    }
                
                line_energy_map[line_num]['total_energy'] += energy
                line_energy_map[line_num]['count'] += 1
                line_energy_map[line_num]['checkpoints'].append({
                    'type': checkpoint['checkpoint_type'],
                    'energy': energy
                })
        
        if not energy_values:
            return None
            
        # Calculate peak threshold
        peak_threshold = np.percentile(energy_values, peak_threshold_percentile)
        noise_threshold = np.percentile(energy_values, 25)  # Bottom 25% likely noise
        
        # Identify peaks and noise
        peak_lines = []
        noise_lines = []
        significant_lines = []
        
        for line_num, data in line_energy_map.items():
            avg_energy = data['total_energy'] / data['count']
            
            if avg_energy >= peak_threshold:
                peak_lines.append((line_num, avg_energy, data))
            elif avg_energy <= noise_threshold:
                noise_lines.append((line_num, avg_energy, data))
            else:
                significant_lines.append((line_num, avg_energy, data))
        
        # Sort by energy
        peak_lines.sort(key=lambda x: x[1], reverse=True)
        significant_lines.sort(key=lambda x: x[1], reverse=True)
        
        # Create detailed analysis plot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # 1. Line-level energy distribution
        lines = list(line_energy_map.keys())
        energies = [line_energy_map[line]['total_energy'] for line in lines]
        
        colors = ['red' if energy >= peak_threshold else 'orange' if energy > noise_threshold else 'lightblue' 
                 for energy in energies]
        
        bars = ax1.bar(lines, energies, color=colors)
        ax1.set_title('Energy Consumption by Source Line\n(Red=Peaks, Orange=Significant, Blue=Low)', 
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Source Line Number')
        ax1.set_ylabel('Total Energy (Joules)')
        ax1.axhline(y=peak_threshold, color='red', linestyle='--', alpha=0.7, label=f'Peak Threshold ({peak_threshold:.6f}J)')
        ax1.axhline(y=noise_threshold, color='blue', linestyle='--', alpha=0.7, label=f'Noise Threshold ({noise_threshold:.6f}J)')
        ax1.legend()
        
        # 2. Peak analysis - top energy consuming lines
        if peak_lines:
            top_peaks = peak_lines[:10]  # Top 10 peaks
            peak_line_nums = [str(x[0]) for x in top_peaks]
            peak_energies = [x[1] for x in top_peaks]
            
            bars = ax2.bar(peak_line_nums, peak_energies, color='red', alpha=0.7)
            ax2.set_title('Top 10 Energy Peak Lines\n(Likely Computational Hotspots)', 
                         fontsize=14, fontweight='bold')
            ax2.set_xlabel('Source Line Number')
            ax2.set_ylabel('Average Energy per Execution (Joules)')
            ax2.tick_params(axis='x', rotation=45)
            
            # Add function names as labels
            for i, (bar, (line_num, energy, data)) in enumerate(zip(bars, top_peaks)):
                func_name = data['function_name'][:15] + ('...' if len(data['function_name']) > 15 else '')
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(peak_energies)*0.02,
                        func_name, ha='center', va='bottom', fontsize=8, rotation=45)
        
        # 3. Noise vs Signal classification
        categories = ['Peaks\n(Hotspots)', 'Significant\n(Normal)', 'Noise\n(Low Impact)']
        counts = [len(peak_lines), len(significant_lines), len(noise_lines)]
        colors = ['red', 'orange', 'lightblue']
        
        wedges, texts, autotexts = ax3.pie(counts, labels=categories, colors=colors, autopct='%1.1f%%', 
                                          startangle=90)
        ax3.set_title('Energy Distribution Classification\n(Peak Detection Analysis)', 
                     fontsize=14, fontweight='bold')
        
        # 4. Function-wise peak contribution
        func_peak_energy = {}
        for line_num, energy, data in peak_lines:
            func_name = data['function_name']
            if func_name not in func_peak_energy:
                func_peak_energy[func_name] = 0
            func_peak_energy[func_name] += energy
        
        if func_peak_energy:
            sorted_funcs = sorted(func_peak_energy.items(), key=lambda x: x[1], reverse=True)[:8]
            func_names = [f[0] for f in sorted_funcs]
            func_energies = [f[1] for f in sorted_funcs]
            
            ax4.barh(func_names, func_energies, color='darkred', alpha=0.7)
            ax4.set_title('Functions Contributing Most to Energy Peaks', fontsize=14, fontweight='bold')
            ax4.set_xlabel('Total Peak Energy (Joules)')
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_dir / f"code_energy_analysis_{session['session_id']}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Generate analysis summary
        analysis_summary = {
            'peak_threshold': peak_threshold,
            'noise_threshold': noise_threshold,
            'peak_lines': [(int(line), float(energy), data['function_name']) for line, energy, data in peak_lines[:10]],
            'noise_lines_count': len(noise_lines),
            'significant_lines_count': len(significant_lines),
            'peak_functions': dict(sorted_funcs[:5]) if func_peak_energy else {}
        }
        
        return str(plot_path), analysis_summary
    
    def generate_checkpoint_heatmap(self, session):
        """Generate heatmap of energy consumption by checkpoint type and location"""
        if not session['checkpoints']:
            return None
            
        # Prepare data for heatmap
        checkpoint_data = []
        for checkpoint in session['checkpoints']:
            if checkpoint['energy_consumed']:
                checkpoint_data.append({
                    'type': checkpoint['checkpoint_type'],
                    'line': checkpoint['line_number'] if checkpoint['line_number'] else 0,
                    'energy': float(checkpoint['energy_consumed'])
                })
        
        if not checkpoint_data:
            return None
            
        # Create DataFrame
        df = pd.DataFrame(checkpoint_data)
        
        # Create pivot table for heatmap
        pivot_table = df.pivot_table(
            values='energy', 
            index='type', 
            columns='line',
            aggfunc='sum',
            fill_value=0
        )
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(14, 8))
        sns.heatmap(pivot_table, annot=True, fmt='.3f', cmap='YlOrRd', ax=ax)
        ax.set_title(f'Energy Consumption Heatmap by Checkpoint Type and Line - Session {session["session_id"]}',
                    fontsize=14, fontweight='bold')
        ax.set_xlabel('Line Number')
        ax.set_ylabel('Checkpoint Type')
        
        plt.tight_layout()
        
        # Save plot
        plot_path = self.output_dir / f"heatmap_{session['session_id']}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(plot_path)
    
    def generate_comprehensive_report(self, session_id=None):
        """Generate comprehensive energy report"""
        sessions = self.get_session_data(session_id)
        if not sessions:
            print("No session data found")
            return
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'sessions': [],
            'visualizations': []
        }
        
        for session in sessions:
            print(f"Processing session: {session['session_id']}")
            
            session_report = {
                'session_id': session['session_id'],
                'language': session.get('language', 'unknown'),
                'total_energy': session.get('total_energy', 0),
                'duration': session.get('duration', 0),
                'checkpoints_count': len(session['checkpoints']),
                'created_at': session['created_at'],
                'plots': []
            }
            
            # Generate timeline
            timeline_plot = self.generate_session_timeline(session)
            if timeline_plot:
                session_report['plots'].append({
                    'type': 'timeline',
                    'path': timeline_plot
                })
                report['visualizations'].append(timeline_plot)
            
            # Generate function analysis
            func_result = self.generate_function_analysis(session)
            if func_result:
                func_plot, func_stats = func_result
                session_report['plots'].append({
                    'type': 'function_analysis',
                    'path': func_plot
                })
                session_report['function_stats'] = func_stats
                report['visualizations'].append(func_plot)
            
            # Generate heatmap
            heatmap_plot = self.generate_checkpoint_heatmap(session)
            if heatmap_plot:
                session_report['plots'].append({
                    'type': 'heatmap',
                    'path': heatmap_plot
                })
                report['visualizations'].append(heatmap_plot)
            
            # Generate code energy analysis with peak detection
            code_analysis_result = self.generate_code_energy_analysis(session)
            if code_analysis_result:
                analysis_plot, analysis_summary = code_analysis_result
                session_report['plots'].append({
                    'type': 'code_energy_analysis',
                    'path': analysis_plot
                })
                session_report['code_analysis'] = analysis_summary
                report['visualizations'].append(analysis_plot)
            
            report['sessions'].append(session_report)
        
        # Save comprehensive report
        report_path = self.output_dir / "energy_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Generate HTML report
        html_report = self.generate_html_report(report)
        html_path = self.output_dir / "energy_report.html"
        with open(html_path, 'w') as f:
            f.write(html_report)
        
        print(f"Report generated successfully!")
        print(f"JSON report: {report_path}")
        print(f"HTML report: {html_path}")
        print(f"Visualizations: {len(report['visualizations'])} plots generated")
        
        return report
    
    def generate_html_report(self, report_data):
        """Generate HTML report with embedded visualizations"""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CodeGreen Energy Analysis Report</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 0 20px rgba(0,0,0,0.1);
                }
                h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; }
                h2 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
                h3 { color: #7f8c8d; }
                .session {
                    margin: 30px 0;
                    padding: 20px;
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    background-color: #fdfdfd;
                }
                .stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 20px 0;
                }
                .stat-card {
                    background: #3498db;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    text-align: center;
                }
                .stat-value { font-size: 24px; font-weight: bold; }
                .stat-label { font-size: 14px; opacity: 0.9; }
                .plot-container {
                    margin: 20px 0;
                    text-align: center;
                }
                .plot-container img {
                    max-width: 100%;
                    height: auto;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
                .function-stats {
                    overflow-x: auto;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }
                th, td {
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                th {
                    background-color: #f8f9fa;
                    font-weight: bold;
                }
                .timestamp {
                    color: #7f8c8d;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔋 CodeGreen Energy Analysis Report</h1>
                <p class="timestamp">Generated on: """ + report_data['generated_at'] + """</p>
        """
        
        for session in report_data['sessions']:
            html += f"""
                <div class="session">
                    <h2>Session: {session['session_id']}</h2>
                    
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-value">{session.get('total_energy', 0):.3f}</div>
                            <div class="stat-label">Total Energy (J)</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{session.get('duration', 0):.2f}</div>
                            <div class="stat-label">Duration (s)</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{session['checkpoints_count']}</div>
                            <div class="stat-label">Checkpoints</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{session.get('language', 'unknown').upper()}</div>
                            <div class="stat-label">Language</div>
                        </div>
                    </div>
            """
            
            # Add plots
            for plot in session['plots']:
                plot_name = os.path.basename(plot['path'])
                html += f"""
                    <div class="plot-container">
                        <h3>{plot['type'].replace('_', ' ').title()}</h3>
                        <img src="{plot_name}" alt="{plot['type']} visualization">
                    </div>
                """
            
            # Add function statistics table if available
            if 'function_stats' in session:
                html += """
                    <div class="function-stats">
                        <h3>Function Energy Statistics</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Function</th>
                                    <th>Total Energy (J)</th>
                                    <th>Average Energy (J)</th>
                                    <th>Call Count</th>
                                    <th>Max Energy (J)</th>
                                    <th>Min Energy (J)</th>
                                </tr>
                            </thead>
                            <tbody>
                """
                
                for func_name, stats in session['function_stats'].items():
                    html += f"""
                        <tr>
                            <td>{func_name}</td>
                            <td>{stats['total']:.6f}</td>
                            <td>{stats['avg']:.6f}</td>
                            <td>{stats['count']}</td>
                            <td>{stats['max']:.6f}</td>
                            <td>{stats['min']:.6f}</td>
                        </tr>
                    """
                
                html += """
                            </tbody>
                        </table>
                    </div>
                """
            
            # Add code energy analysis if available
            if 'code_analysis' in session:
                analysis = session['code_analysis']
                html += f"""
                    <div class="code-analysis">
                        <h3>🔥 Code Energy Analysis & Peak Detection</h3>
                        <div class="analysis-summary">
                            <p><strong>Peak Energy Threshold:</strong> {analysis.get('peak_threshold', 0):.6f} J</p>
                            <p><strong>Noise Threshold:</strong> {analysis.get('noise_threshold', 0):.6f} J</p>
                            <p><strong>Significant Lines:</strong> {analysis.get('significant_lines_count', 0)} | 
                               <strong>Noise Lines:</strong> {analysis.get('noise_lines_count', 0)}</p>
                        </div>
                        
                        <h4>Top Energy Hotspot Lines:</h4>
                        <table>
                            <thead>
                                <tr>
                                    <th>Line #</th>
                                    <th>Energy (µJ)</th>
                                    <th>Function</th>
                                    <th>Classification</th>
                                </tr>
                            </thead>
                            <tbody>
                """
                
                for line_num, energy, func_name in analysis.get('peak_lines', [])[:10]:
                    classification = "🔥 PEAK" if energy >= analysis.get('peak_threshold', 0) else "⚡ Significant"
                    html += f"""
                        <tr>
                            <td>Line {line_num}</td>
                            <td>{energy * 1e6:.2f}</td>
                            <td>{func_name}</td>
                            <td>{classification}</td>
                        </tr>
                    """
                
                html += """
                            </tbody>
                        </table>
                        
                        <h4>Peak-Contributing Functions:</h4>
                        <ul>
                """
                
                for func_name, energy in analysis.get('peak_functions', {}).items():
                    html += f"<li><strong>{func_name}:</strong> {energy * 1e6:.2f} µJ peak contribution</li>"
                
                html += """
                        </ul>
                        
                        <div class="interpretation">
                            <h4>📊 Interpretation Guide:</h4>
                            <ul>
                                <li><strong>🔥 PEAK lines:</strong> Computational hotspots - optimize these first</li>
                                <li><strong>⚡ Significant lines:</strong> Normal energy consumption</li>
                                <li><strong>🔵 Noise lines:</strong> Low impact - measurement noise or trivial operations</li>
                            </ul>
                        </div>
                    </div>
                """
            
            html += "</div>"  # Close session div
        
        html += """
            </div>
        </body>
        </html>
        """
        
        return html

def main():
    parser = argparse.ArgumentParser(description='Generate CodeGreen energy analysis report')
    parser.add_argument('--db', default='energy_data.db', help='Database file path')
    parser.add_argument('--session', help='Specific session ID to analyze')
    parser.add_argument('--output', default='reports', help='Output directory')
    
    args = parser.parse_args()
    
    # Check if database exists
    if not os.path.exists(args.db):
        print(f"Database file not found: {args.db}")
        print("Creating sample database for demonstration...")
        create_sample_database(args.db)
    
    generator = EnergyReportGenerator(args.db, args.output)
    generator.generate_comprehensive_report(args.session)

def create_sample_database(db_path):
    """Create sample database for demonstration"""
    conn = sqlite3.connect(db_path)
    
    # Create tables
    conn.execute('''
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            language TEXT,
            total_energy REAL,
            duration REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            checkpoint_type TEXT,
            function_name TEXT,
            file_path TEXT,
            line_number INTEGER,
            column_number INTEGER,
            energy_consumed REAL,
            timestamp DATETIME,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
    ''')
    
    # Insert sample data
    import random
    from datetime import datetime, timedelta
    
    session_id = "session_demo_1"
    base_time = datetime.now()
    
    conn.execute('''
        INSERT INTO sessions (session_id, language, total_energy, duration)
        VALUES (?, ?, ?, ?)
    ''', (session_id, "python", 2.456, 0.125))
    
    # Sample checkpoints
    functions = ["main", "process_data", "fibonacci_recursive", "fibonacci_iterative", "get_statistics"]
    checkpoint_types = ["function_enter", "function_exit", "loop_start", "function_call"]
    
    for i in range(50):
        checkpoint_data = (
            session_id,
            random.choice(checkpoint_types),
            random.choice(functions),
            "sample_code.py",
            random.randint(10, 100),
            random.randint(1, 80),
            random.uniform(0.001, 0.1),
            (base_time + timedelta(milliseconds=i*10)).isoformat()
        )
        
        conn.execute('''
            INSERT INTO checkpoints (session_id, checkpoint_type, function_name, file_path, 
                                   line_number, column_number, energy_consumed, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', checkpoint_data)
    
    conn.commit()
    conn.close()
    print(f"Sample database created: {db_path}")

if __name__ == "__main__":
    main()