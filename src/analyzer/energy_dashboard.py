#!/usr/bin/env python3
"""
CodeGreen Energy Dashboard
Visualizes energy consumption data stored in SQLite database
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import argparse
import os

class EnergyDashboard:
    def __init__(self, db_path="energy_data.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database: {self.db_path}")
            return True
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return False
    
    def get_sessions_summary(self):
        """Get summary of all measurement sessions"""
        query = """
        SELECT session_id, code_version, file_path, start_time, end_time,
               total_joules, average_watts, peak_watts, checkpoint_count, duration_seconds
        FROM measurement_sessions
        ORDER BY start_time DESC
        """
        
        df = pd.read_sql_query(query, self.conn)
        
        # Convert timestamps
        df['start_time'] = pd.to_datetime(df['start_time'], unit='s')
        df['end_time'] = pd.to_datetime(df['end_time'], unit='s')
        
        return df
    
    def get_session_measurements(self, session_id):
        """Get detailed measurements for a specific session"""
        query = """
        SELECT source, joules, watts, temperature, timestamp, checkpoint_id, 
               checkpoint_type, name, line_number, context
        FROM measurements
        WHERE session_id = ?
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, self.conn, params=(session_id,))
        
        # Convert timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        return df
    
    def plot_energy_trends(self, output_dir="energy_plots"):
        """Generate energy consumption trend plots"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Get sessions summary
        sessions_df = self.get_sessions_summary()
        
        if sessions_df.empty:
            print("No energy data found in database")
            return
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 1. Energy consumption over time
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        plt.plot(sessions_df['start_time'], sessions_df['total_joules'], 'o-', linewidth=2, markersize=8)
        plt.title('Total Energy Consumption Over Time', fontsize=14, fontweight='bold')
        plt.xlabel('Session Start Time')
        plt.ylabel('Total Energy (Joules)')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        
        # 2. Power consumption comparison
        plt.subplot(2, 2, 2)
        plt.bar(range(len(sessions_df)), sessions_df['average_watts'], 
                color=sns.color_palette("husl", len(sessions_df)))
        plt.title('Average Power Consumption by Session', fontsize=14, fontweight='bold')
        plt.xlabel('Session Index')
        plt.ylabel('Average Power (Watts)')
        plt.xticks(range(len(sessions_df)), [f"Session {i+1}" for i in range(len(sessions_df))], rotation=45)
        plt.grid(True, alpha=0.3)
        
        # 3. Duration vs Energy scatter
        plt.subplot(2, 2, 3)
        plt.scatter(sessions_df['duration_seconds'], sessions_df['total_joules'], 
                   s=100, alpha=0.7, c=sessions_df['average_watts'], cmap='viridis')
        plt.colorbar(label='Average Power (W)')
        plt.title('Duration vs Energy Consumption', fontsize=14, fontweight='bold')
        plt.xlabel('Duration (seconds)')
        plt.ylabel('Total Energy (Joules)')
        plt.grid(True, alpha=0.3)
        
        # 4. Checkpoint count vs Energy
        plt.subplot(2, 2, 4)
        plt.scatter(sessions_df['checkpoint_count'], sessions_df['total_joules'], 
                   s=100, alpha=0.7, c=sessions_df['peak_watts'], cmap='plasma')
        plt.colorbar(label='Peak Power (W)')
        plt.title('Checkpoint Count vs Energy Consumption', fontsize=14, fontweight='bold')
        plt.xlabel('Number of Checkpoints')
        plt.ylabel('Total Energy (Joules)')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/energy_trends.png", dpi=300, bbox_inches='tight')
        plt.show()
        
        # Save summary to CSV
        sessions_df.to_csv(f"{output_dir}/sessions_summary.csv", index=False)
        print(f"Plots saved to: {output_dir}")
    
    def plot_session_details(self, session_id, output_dir="energy_plots"):
        """Generate detailed plots for a specific session"""
        os.makedirs(output_dir, exist_ok=True)
        
        measurements_df = self.get_session_measurements(session_id)
        
        if measurements_df.empty:
            print(f"No measurements found for session: {session_id}")
            return
        
        # Set style
        plt.style.use('seaborn-v0_8')
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. Energy consumption over time
        axes[0, 0].plot(measurements_df['timestamp'], measurements_df['joules'], 'o-', linewidth=2)
        axes[0, 0].set_title(f'Energy Consumption Over Time\nSession: {session_id}', fontweight='bold')
        axes[0, 0].set_xlabel('Time')
        axes[0, 0].set_ylabel('Energy (Joules)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Power consumption over time
        axes[0, 1].plot(measurements_df['timestamp'], measurements_df['watts'], 's-', linewidth=2, color='orange')
        axes[0, 1].set_title('Power Consumption Over Time', fontweight='bold')
        axes[0, 1].set_xlabel('Time')
        axes[0, 1].set_ylabel('Power (Watts)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Energy distribution histogram
        axes[1, 0].hist(measurements_df['joules'], bins=20, alpha=0.7, color='green', edgecolor='black')
        axes[1, 0].set_title('Energy Consumption Distribution', fontweight='bold')
        axes[1, 0].set_xlabel('Energy (Joules)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Power distribution histogram
        axes[1, 1].hist(measurements_df['watts'], bins=20, alpha=0.7, color='red', edgecolor='black')
        axes[1, 1].set_title('Power Consumption Distribution', fontweight='bold')
        axes[1, 1].set_xlabel('Power (Watts)')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/session_{session_id}_details.png", dpi=300, bbox_inches='tight')
        plt.show()
        
        # Save measurements to CSV
        measurements_df.to_csv(f"{output_dir}/session_{session_id}_measurements.csv", index=False)
        print(f"Session details saved to: {output_dir}")
    
    def compare_sessions(self, session1_id, session2_id):
        """Compare two sessions and generate comparison report"""
        session1_df = self.get_session_measurements(session1_id)
        session2_df = self.get_session_measurements(session2_id)
        
        if session1_df.empty or session2_df.empty:
            print("One or both sessions not found")
            return
        
        # Calculate statistics
        stats1 = {
            'total_energy': session1_df['joules'].sum(),
            'avg_power': session1_df['watts'].mean(),
            'peak_power': session1_df['watts'].max(),
            'duration': (session1_df['timestamp'].max() - session1_df['timestamp'].min()).total_seconds(),
            'checkpoint_count': len(session1_df)
        }
        
        stats2 = {
            'total_energy': session2_df['joules'].sum(),
            'avg_power': session2_df['watts'].mean(),
            'peak_power': session2_df['watts'].max(),
            'duration': (session2_df['timestamp'].max() - session2_df['timestamp'].min()).total_seconds(),
            'checkpoint_count': len(session2_df)
        }
        
        # Print comparison
        print(f"\n{'='*60}")
        print(f"SESSION COMPARISON REPORT")
        print(f"{'='*60}")
        print(f"Session 1: {session1_id}")
        print(f"Session 2: {session2_id}")
        print(f"{'='*60}")
        
        print(f"{'Metric':<20} {'Session 1':<15} {'Session 2':<15} {'Difference':<15}")
        print(f"{'-'*65}")
        
        for metric in ['total_energy', 'avg_power', 'peak_power', 'duration', 'checkpoint_count']:
            val1 = stats1[metric]
            val2 = stats2[metric]
            diff = val2 - val1
            
            if metric in ['total_energy', 'avg_power', 'peak_power']:
                print(f"{metric:<20} {val1:<15.2f} {val2:<15.2f} {diff:<15.2f}")
            else:
                print(f"{metric:<20} {val1:<15.2f} {val2:<15.2f} {diff:<15.2f}")
        
        # Calculate efficiency improvement
        if stats1['total_energy'] > 0:
            efficiency_improvement = ((stats1['total_energy'] - stats2['total_energy']) / stats1['total_energy']) * 100
            print(f"\nEfficiency Improvement: {efficiency_improvement:.2f}%")
            
            if efficiency_improvement > 0:
                print("✅ Session 2 is more energy efficient!")
            else:
                print("⚠️  Session 1 is more energy efficient")
        
        print(f"{'='*60}")
    
    def export_for_grafana(self, output_dir="grafana_data"):
        """Export data in formats suitable for Grafana"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export all measurements as CSV for Grafana
        query = """
        SELECT m.session_id, m.timestamp, m.joules, m.watts, m.temperature,
               s.code_version, s.file_path
        FROM measurements m
        JOIN measurement_sessions s ON m.session_id = s.session_id
        ORDER BY m.timestamp
        """
        
        df = pd.read_sql_query(query, self.conn)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Save as CSV
        csv_path = f"{output_dir}/energy_data.csv"
        df.to_csv(csv_path, index=False)
        
        # Create InfluxDB line protocol format
        influx_path = f"{output_dir}/energy_data_influx.txt"
        with open(influx_path, 'w') as f:
            for _, row in df.iterrows():
                # InfluxDB line protocol: measurement,tag1=value1,tag2=value2 field1=value1,field2=value2 timestamp
                line = f"energy_consumption,session_id={row['session_id']},source=pmt,code_version={row['code_version']} "
                line += f"joules={row['joules']},watts={row['watts']},temperature={row['temperature']} "
                line += f"{int(row['timestamp'].timestamp() * 1e9)}\n"
                f.write(line)
        
        print(f"Grafana-ready data exported to: {output_dir}")
        print(f"  - CSV: {csv_path}")
        print(f"  - InfluxDB: {influx_path}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

def main():
    parser = argparse.ArgumentParser(description='CodeGreen Energy Dashboard')
    parser.add_argument('--db', default='energy_data.db', help='Path to SQLite database')
    parser.add_argument('--output', default='energy_plots', help='Output directory for plots')
    parser.add_argument('--compare', nargs=2, metavar=('SESSION1', 'SESSION2'), 
                       help='Compare two sessions')
    parser.add_argument('--session', help='Show details for specific session')
    parser.add_argument('--grafana', action='store_true', help='Export data for Grafana')
    
    args = parser.parse_args()
    
    dashboard = EnergyDashboard(args.db)
    
    if not dashboard.connect():
        return
    
    try:
        if args.compare:
            dashboard.compare_sessions(args.compare[0], args.compare[1])
        elif args.session:
            dashboard.plot_session_details(args.session, args.output)
        elif args.grafana:
            dashboard.export_for_grafana(args.output)
        else:
            # Default: show trends
            dashboard.plot_energy_trends(args.output)
            
    finally:
        dashboard.close()

if __name__ == "__main__":
    main()
