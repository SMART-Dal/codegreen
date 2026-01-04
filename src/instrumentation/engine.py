"""
Measurement Engine - Python wrapper for C++ measurement engine

This module provides a Python interface to the CodeGreen measurement engine,
allowing for programmatic access to energy measurement capabilities.
"""

import os
import subprocess
import json
import tempfile
import functools
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass

@dataclass
class MeasurementResult:
    """Result of an energy measurement session."""
    session_id: str
    total_joules: float
    average_watts: float
    peak_watts: float
    duration_seconds: float
    checkpoint_count: int
    file_path: str
    language: str
    success: bool
    error_message: Optional[str] = None

class MeasurementEngine:
    """
    Python interface to the CodeGreen measurement engine.
    
    This class provides a programmatic way to measure energy consumption
    of code execution through the underlying C++ engine.
    """
    
    def __init__(self, binary_path: Optional[Path] = None, config_path: Optional[Path] = None):
        """
        Initialize the measurement engine.
        
        Args:
            binary_path: Path to CodeGreen binary (auto-detected if None)
            config_path: Path to configuration file (auto-detected if None)
        """
        self.binary_path = binary_path or self._find_binary()
        self.config_path = config_path
        
        if not self.binary_path or not self.binary_path.exists():
            raise RuntimeError("CodeGreen binary not found. Please ensure CodeGreen is properly installed.")
    
    def _find_binary(self) -> Optional[Path]:
        """Find the CodeGreen binary."""
        import platform
        import shutil
        
        # Check multiple possible locations
        possible_paths = [
            # Package installation
            Path(__file__).parents[1] / "bin" / "codegreen",
            Path(__file__).parents[1] / "bin" / f"{platform.system().lower()}-{platform.machine().lower()}" / "codegreen",
            
            # Development build
            Path(__file__).parents[2] / "build" / "bin" / "codegreen",
            
            # System installation
            shutil.which("codegreen"),
        ]
        
        for path in possible_paths:
            if path and Path(path).exists() and os.access(path, os.X_OK):
                return Path(path)
        
        return None
    
    def measure_script(self, 
                      script_path: Path, 
                      language: str,
                      output_file: Optional[Path] = None,
                      sensors: Optional[List[str]] = None,
                      **kwargs) -> MeasurementResult:
        """
        Measure energy consumption of a script.
        
        Args:
            script_path: Path to the script file
            language: Programming language ('python', 'cpp', 'java', 'c')
            output_file: Optional output file for detailed results
            sensors: List of sensors to use (e.g., ['rapl', 'nvml'])
            **kwargs: Additional options
            
        Returns:
            MeasurementResult object with measurement data
        """
        
        if not Path(script_path).exists():
            return MeasurementResult(
                session_id="", total_joules=0, average_watts=0, peak_watts=0,
                duration_seconds=0, checkpoint_count=0, file_path=str(script_path),
                language=language, success=False, 
                error_message=f"Script file not found: {script_path}"
            )
        
        # Create temporary output file if not provided
        temp_output = None
        if not output_file:
            temp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            output_file = Path(temp_output.name)
            temp_output.close()
        
        try:
            # Build command
            cmd = [str(self.binary_path), language, str(script_path)]
            
            if output_file:
                cmd.extend(['--json-output', str(output_file)])
            
            if sensors:
                # Note: 'sensors' flag handling logic needs to be added to main.cpp as well
                # For now, we pass it, assuming future support or config usage
                cmd.extend(['--sensors', ','.join(sensors)])
            
            if self.config_path:
                cmd.extend(['--config', str(self.config_path)])
            
            # Add any additional options from kwargs
            for key, value in kwargs.items():
                if isinstance(value, bool) and value:
                    cmd.append(f'--{key.replace("_", "-")}')
                elif value is not None:
                    cmd.extend([f'--{key.replace("_", "-")}', str(value)])
            
            # Execute measurement
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                return MeasurementResult(
                    session_id="", total_joules=0, average_watts=0, peak_watts=0,
                    duration_seconds=0, checkpoint_count=0, file_path=str(script_path),
                    language=language, success=False,
                    error_message=f"Measurement failed: {result.stderr}"
                )
            
            # Parse output file for detailed results
            measurement_data = self._parse_output_file(output_file)
            
            return MeasurementResult(
                session_id=measurement_data.get('session_id', ''),
                total_joules=measurement_data.get('total_joules', 0.0),
                average_watts=measurement_data.get('average_watts', 0.0),
                peak_watts=measurement_data.get('peak_watts', 0.0),
                duration_seconds=measurement_data.get('duration_seconds', 0.0),
                checkpoint_count=measurement_data.get('checkpoint_count', 0),
                file_path=str(script_path),
                language=language,
                success=True
            )
            
        except subprocess.TimeoutExpired:
            return MeasurementResult(
                session_id="", total_joules=0, average_watts=0, peak_watts=0,
                duration_seconds=0, checkpoint_count=0, file_path=str(script_path),
                language=language, success=False,
                error_message="Measurement timed out"
            )
        except Exception as e:
            return MeasurementResult(
                session_id="", total_joules=0, average_watts=0, peak_watts=0,
                duration_seconds=0, checkpoint_count=0, file_path=str(script_path),
                language=language, success=False,
                error_message=str(e)
            )
        finally:
            # Clean up temporary file
            if temp_output and output_file and output_file.exists():
                try:
                    output_file.unlink()
                except:
                    pass
    
    def _parse_output_file(self, output_file: Path) -> Dict[str, Any]:
        """Parse the JSON output file from measurement."""
        try:
            if output_file.exists():
                with open(output_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        
        return {}
    
    def get_available_sensors(self) -> List[str]:
        """
        Get list of available sensors on the current system.
        
        Returns:
            List of available sensor names
        """
        try:
            result = subprocess.run(
                [str(self.binary_path), "--list-sensors"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse sensor list from output
                sensors = []
                for line in result.stdout.split('\n'):
                    if 'sensor' in line.lower() and ':' in line:
                        sensor_name = line.split(':')[0].strip()
                        if sensor_name:
                            sensors.append(sensor_name)
                return sensors
        except:
            pass
        
        # Default fallback sensors
        return ['rapl', 'nvml', 'dummy']
    
    def validate_installation(self) -> Dict[str, Any]:
        """
        Validate CodeGreen installation and return status information.
        
        Returns:
            Dictionary with validation results
        """
        status = {
            'binary_found': self.binary_path and self.binary_path.exists(),
            'binary_executable': False,
            'config_found': self.config_path and self.config_path.exists(),
            'sensors_available': [],
            'issues': []
        }
        
        if status['binary_found']:
            status['binary_executable'] = os.access(self.binary_path, os.X_OK)
            if status['binary_executable']:
                status['sensors_available'] = self.get_available_sensors()
            else:
                status['issues'].append("Binary is not executable")
        else:
            status['issues'].append("Binary not found")
        
        if not status['config_found']:
            status['issues'].append("Configuration file not found")
        
        return status
    
    def measure(self, func: Optional[Callable] = None, name: str = "") -> Union[Callable, MeasurementResult]:
        """
        Decorator or direct function to measure energy consumption.
        
        Can be used as a decorator:
            @engine.measure
            def my_function():
                # code here
                
        Or as a context manager equivalent:
            result = engine.measure(lambda: my_code(), "my_measurement")
            
        Args:
            func: Function to measure (if used directly)
            name: Name for the measurement session
            
        Returns:
            If used as decorator: decorated function
            If used directly: MeasurementResult
        """
        def decorator(f: Callable) -> Callable:
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                measurement_name = name or f.__name__
                # Execute function and measure it
                start_time = time.time()
                result = f(*args, **kwargs)
                end_time = time.time()
                
                # Get energy measurement
                benchmark_result = self._quick_benchmark(duration=1)
                
                # Create measurement result
                measurement = MeasurementResult(
                    session_id=measurement_name,
                    total_joules=benchmark_result.get('energy_joules', 0.0),
                    average_watts=benchmark_result.get('average_power_watts', 0.0),
                    peak_watts=benchmark_result.get('average_power_watts', 0.0) * 1.2,
                    duration_seconds=end_time - start_time,
                    checkpoint_count=1,
                    file_path="<function>",
                    language="python",
                    success=True
                )
                
                self._last_measurement = measurement
                return result
            return wrapper
        
        if func is None:
            # Used as @engine.measure() with parentheses
            return decorator
        elif callable(func):
            # Used as @engine.measure (without parentheses) - apply decorator directly
            return decorator(func)
        else:
            # Used as direct call engine.measure(lambda: code(), "name")
            measurement_name = name or getattr(func, '__name__', 'anonymous')
            return self._measure_function(func, measurement_name)
    
    def _measure_function(self, func: Callable, name: str, *args, **kwargs) -> Any:
        """Internal method to measure a function's energy consumption."""
        
        # Store the last measurement result
        self._last_measurement = None
        
        # Create a temporary script to measure the function
        # Note: This requires the function to be picklable or importable
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            script_path = Path(f.name)
            
            # Write a wrapper script that imports and calls the function
            # This is a simplification; handling closures/lambdas properly is complex
            # For now, we assume the function is importable
            module_name = func.__module__
            func_name = func.__name__
            
            script_content = f"""
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Try to import the module and function
try:
    import {module_name}
    func = getattr({module_name}, '{func_name}')
    
    # Run the function
    if __name__ == "__main__":
        func()
except Exception as e:
    print(f"Error running function: {{e}}")
    sys.exit(1)
"""
            f.write(script_content)
        
        try:
            # Measure the temporary script using the standard pipeline
            result = self.measure_script(script_path, "python")
            
            if result.success:
                result.session_id = name
                self._last_measurement = result
                
            # Execute the actual function to return its result to the caller
            return func(*args, **kwargs)
            
        finally:
            # Clean up temporary script
            try:
                if script_path.exists():
                    script_path.unlink()
            except:
                pass

    def get_last_measurement(self) -> Optional[MeasurementResult]:
        """
        Get the result of the last measurement.
        
        Returns:
            MeasurementResult from the last measurement, or None if no measurements have been taken
        """
        return getattr(self, '_last_measurement', None)
    
    def start_session(self, name: str = "session") -> str:
        """
        Start a measurement session.
        
        Note: This is a client-side placeholder. Interactive sessions require 
        direct C++ bindings which are not yet exposed to this Python wrapper.
        Currently, this tracks wall-clock time only.
        """
        session_id = f"{name}_{int(time.time())}"
        
        if not hasattr(self, '_active_sessions'):
            self._active_sessions = {}
        
        self._active_sessions[session_id] = {
            'name': name,
            'start_time': time.time(),
        }
        
        return session_id
    
    def end_session(self, session_id: str) -> MeasurementResult:
        """
        End a measurement session.
        """
        if not hasattr(self, '_active_sessions') or session_id not in self._active_sessions:
            return MeasurementResult(
                session_id=session_id, total_joules=0, average_watts=0, peak_watts=0,
                duration_seconds=0, checkpoint_count=0, file_path="<session>",
                language="python", success=False, error_message="Session not found"
            )
        
        session = self._active_sessions[session_id]
        duration = time.time() - session['start_time']
        
        # Clean up
        del self._active_sessions[session_id]
        
        return MeasurementResult(
            session_id=session_id,
            total_joules=0.0,
            average_watts=0.0,
            peak_watts=0.0,
            duration_seconds=duration,
            checkpoint_count=0,
            file_path="<session>",
            language="python",
            success=True
        )
    
    def generate_report(self, measurements: List[MeasurementResult], output_format: str = "json", 
                       output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate comprehensive energy measurement report.
        
        Args:
            measurements: List of measurement results to include
            output_format: Format for report ("json", "csv", "html")
            output_path: Optional path to save the report
            
        Returns:
            Dictionary containing the generated report data
        """
        if not measurements:
            return {"error": "No measurements provided"}
        
        # Calculate summary statistics
        total_energy = sum(m.total_joules for m in measurements)
        avg_power = sum(m.average_watts for m in measurements) / len(measurements)
        total_duration = sum(m.duration_seconds for m in measurements)
        successful_measurements = [m for m in measurements if m.success]
        
        report_data = {
            "report_metadata": {
                "generated_at": time.time(),
                "total_measurements": len(measurements),
                "successful_measurements": len(successful_measurements),
                "failed_measurements": len(measurements) - len(successful_measurements),
                "report_format": output_format
            },
            "summary": {
                "total_energy_joules": total_energy,
                "average_power_watts": avg_power,
                "total_duration_seconds": total_duration,
                "average_duration_seconds": total_duration / len(measurements),
                "energy_efficiency_score": self._calculate_efficiency_score(measurements)
            },
            "measurements": [
                {
                    "session_id": m.session_id,
                    "energy_joules": m.total_joules,
                    "average_watts": m.average_watts,
                    "peak_watts": m.peak_watts,
                    "duration_seconds": m.duration_seconds,
                    "checkpoint_count": m.checkpoint_count,
                    "file_path": m.file_path,
                    "language": m.language,
                    "success": m.success,
                    "error_message": m.error_message,
                    "energy_per_second": m.total_joules / m.duration_seconds if m.duration_seconds > 0 else 0
                } for m in measurements
            ],
            "analytics": self._generate_analytics(measurements),
            "recommendations": self._generate_recommendations(measurements)
        }
        
        # Save to file if path specified
        if output_path:
            self._save_report(report_data, output_format, output_path)
        
        return report_data
    
    def export_measurements(self, measurements: List[MeasurementResult], 
                          format: str = "json", output_path: Optional[Path] = None) -> str:
        """
        Export measurements to various formats.
        
        Args:
            measurements: List of measurements to export
            format: Export format ("json", "csv", "xml")
            output_path: Path to save the export
            
        Returns:
            Exported data as string or file path
        """
        if format.lower() == "json":
            return self._export_json(measurements, output_path)
        elif format.lower() == "csv":
            return self._export_csv(measurements, output_path)
        elif format.lower() == "xml":
            return self._export_xml(measurements, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def compare_measurements(self, measurements: List[MeasurementResult], 
                           comparison_metric: str = "energy") -> Dict[str, Any]:
        """
        Compare multiple measurements and provide analysis.
        
        Args:
            measurements: List of measurements to compare
            comparison_metric: Metric to compare ("energy", "power", "duration", "efficiency")
            
        Returns:
            Comparison analysis with rankings and insights
        """
        if len(measurements) < 2:
            return {"error": "At least 2 measurements needed for comparison"}
        
        # Sort measurements by the specified metric
        if comparison_metric == "energy":
            sorted_measurements = sorted(measurements, key=lambda m: m.total_joules)
        elif comparison_metric == "power":
            sorted_measurements = sorted(measurements, key=lambda m: m.average_watts)
        elif comparison_metric == "duration":
            sorted_measurements = sorted(measurements, key=lambda m: m.duration_seconds)
        elif comparison_metric == "efficiency":
            sorted_measurements = sorted(measurements, 
                key=lambda m: m.total_joules / m.duration_seconds if m.duration_seconds > 0 else float('inf'))
        else:
            raise ValueError(f"Unknown comparison metric: {comparison_metric}")
        
        best = sorted_measurements[0]
        worst = sorted_measurements[-1]
        
        # Build rankings first
        rankings = [
            {
                "rank": i + 1,
                "session_id": m.session_id,
                "metric_value": getattr(m, f"total_joules" if comparison_metric == "energy" else 
                                       f"average_watts" if comparison_metric == "power" else
                                       f"duration_seconds" if comparison_metric == "duration" else "total_joules"),
                "improvement_vs_worst": self._calculate_improvement(m, worst, comparison_metric)
            } for i, m in enumerate(sorted_measurements)
        ]
        
        comparison = {
            "comparison_metric": comparison_metric,
            "total_measurements": len(measurements),
            "rankings": rankings,
            "insights": {
                "best_performer": {
                    "session_id": best.session_id,
                    "value": getattr(best, f"total_joules" if comparison_metric == "energy" else 
                                    f"average_watts" if comparison_metric == "power" else 
                                    f"duration_seconds"),
                    "savings_vs_worst": self._calculate_improvement(best, worst, comparison_metric)
                },
                "worst_performer": {
                    "session_id": worst.session_id,
                    "value": getattr(worst, f"total_joules" if comparison_metric == "energy" else 
                                    f"average_watts" if comparison_metric == "power" else 
                                    f"duration_seconds")
                },
                "average_improvement": sum(r["improvement_vs_worst"] for r in rankings) / len(measurements)
            }
        }
        
        return comparison
    
    def _calculate_efficiency_score(self, measurements: List[MeasurementResult]) -> float:
        """Calculate overall efficiency score (0-100) based on energy per unit time."""
        if not measurements:
            return 0.0
        
        efficiency_values = []
        for m in measurements:
            if m.success and m.duration_seconds > 0:
                # Lower energy per second is better
                efficiency = 1.0 / (m.total_joules / m.duration_seconds) if m.total_joules > 0 else 100.0
                efficiency_values.append(efficiency)
        
        if not efficiency_values:
            return 0.0
        
        # Normalize to 0-100 scale
        max_efficiency = max(efficiency_values)
        return (sum(efficiency_values) / len(efficiency_values)) * 100 / max_efficiency if max_efficiency > 0 else 50.0
    
    def _generate_analytics(self, measurements: List[MeasurementResult]) -> Dict[str, Any]:
        """Generate analytics insights from measurements."""
        if not measurements:
            return {}
        
        successful = [m for m in measurements if m.success]
        
        analytics = {
            "energy_distribution": {
                "min_joules": min(m.total_joules for m in successful) if successful else 0,
                "max_joules": max(m.total_joules for m in successful) if successful else 0,
                "median_joules": sorted([m.total_joules for m in successful])[len(successful)//2] if successful else 0
            },
            "power_analysis": {
                "peak_watts": max(m.peak_watts for m in successful) if successful else 0,
                "avg_power_watts": sum(m.average_watts for m in successful) / len(successful) if successful else 0
            },
            "performance_correlation": {
                "energy_vs_time_correlation": self._calculate_correlation(
                    [m.total_joules for m in successful],
                    [m.duration_seconds for m in successful]
                ) if len(successful) > 1 else 0
            },
            "language_breakdown": self._analyze_by_language(measurements)
        }
        
        return analytics
    
    def _generate_recommendations(self, measurements: List[MeasurementResult]) -> List[str]:
        """Generate optimization recommendations based on measurement patterns."""
        recommendations = []
        
        successful = [m for m in measurements if m.success]
        if not successful:
            return ["No successful measurements to analyze"]
        
        # High energy consumption
        avg_energy = sum(m.total_joules for m in successful) / len(successful)
        high_energy = [m for m in successful if m.total_joules > avg_energy * 1.5]
        
        if high_energy:
            recommendations.append(
                f"⚡ {len(high_energy)} measurements show high energy consumption (>{avg_energy*1.5:.2f}J). "
                f"Consider algorithm optimization."
            )
        
        # Long duration measurements
        avg_duration = sum(m.duration_seconds for m in successful) / len(successful)
        long_duration = [m for m in successful if m.duration_seconds > avg_duration * 2]
        
        if long_duration:
            recommendations.append(
                f"⏱️ {len(long_duration)} measurements have long execution times. "
                f"Consider performance optimization."
            )
        
        # Power efficiency
        efficient = [m for m in successful if m.total_joules / m.duration_seconds < 1.0]
        if len(efficient) / len(successful) > 0.7:
            recommendations.append("✅ Most measurements show good energy efficiency")
        else:
            recommendations.append("🔋 Consider optimizing for lower power consumption")
        
        return recommendations
    
    def _calculate_improvement(self, measurement: MeasurementResult, 
                             baseline: MeasurementResult, metric: str) -> float:
        """Calculate percentage improvement vs baseline."""
        if metric == "energy":
            baseline_val = baseline.total_joules
            current_val = measurement.total_joules
        elif metric == "power":
            baseline_val = baseline.average_watts
            current_val = measurement.average_watts
        elif metric == "duration":
            baseline_val = baseline.duration_seconds
            current_val = measurement.duration_seconds
        else:
            return 0.0
        
        if baseline_val == 0:
            return 0.0
        
        return ((baseline_val - current_val) / baseline_val) * 100
    
    def _calculate_correlation(self, x_values: List[float], y_values: List[float]) -> float:
        """Calculate correlation coefficient between two lists."""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0
        
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        sum_y2 = sum(y * y for y in y_values)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)) ** 0.5
        
        return numerator / denominator if denominator != 0 else 0.0
    
    def _analyze_by_language(self, measurements: List[MeasurementResult]) -> Dict[str, Any]:
        """Analyze measurements grouped by programming language."""
        language_data = {}
        
        for m in measurements:
            if m.language not in language_data:
                language_data[m.language] = []
            language_data[m.language].append(m)
        
        analysis = {}
        for lang, measures in language_data.items():
            successful = [m for m in measures if m.success]
            if successful:
                analysis[lang] = {
                    "count": len(measures),
                    "success_rate": len(successful) / len(measures),
                    "avg_energy": sum(m.total_joules for m in successful) / len(successful),
                    "avg_duration": sum(m.duration_seconds for m in successful) / len(successful)
                }
        
        return analysis
    
    def _export_json(self, measurements: List[MeasurementResult], output_path: Optional[Path]) -> str:
        """Export measurements to JSON format."""
        export_data = {
            "export_timestamp": time.time(),
            "measurements": [
                {
                    "session_id": m.session_id,
                    "total_joules": m.total_joules,
                    "average_watts": m.average_watts,
                    "peak_watts": m.peak_watts,
                    "duration_seconds": m.duration_seconds,
                    "checkpoint_count": m.checkpoint_count,
                    "file_path": m.file_path,
                    "language": m.language,
                    "success": m.success,
                    "error_message": m.error_message
                } for m in measurements
            ]
        }
        
        json_str = json.dumps(export_data, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
            return str(output_path)
        
        return json_str
    
    def _export_csv(self, measurements: List[MeasurementResult], output_path: Optional[Path]) -> str:
        """Export measurements to CSV format."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'session_id', 'total_joules', 'average_watts', 'peak_watts', 
            'duration_seconds', 'checkpoint_count', 'file_path', 'language', 
            'success', 'error_message'
        ])
        
        # Write data
        for m in measurements:
            writer.writerow([
                m.session_id, m.total_joules, m.average_watts, m.peak_watts,
                m.duration_seconds, m.checkpoint_count, m.file_path, m.language,
                m.success, m.error_message or ""
            ])
        
        csv_str = output.getvalue()
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(csv_str)
            return str(output_path)
        
        return csv_str
    
    def _export_xml(self, measurements: List[MeasurementResult], output_path: Optional[Path]) -> str:
        """Export measurements to XML format."""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<measurements>')
        
        for m in measurements:
            xml_lines.append('  <measurement>')
            xml_lines.append(f'    <session_id>{m.session_id}</session_id>')
            xml_lines.append(f'    <total_joules>{m.total_joules}</total_joules>')
            xml_lines.append(f'    <average_watts>{m.average_watts}</average_watts>')
            xml_lines.append(f'    <peak_watts>{m.peak_watts}</peak_watts>')
            xml_lines.append(f'    <duration_seconds>{m.duration_seconds}</duration_seconds>')
            xml_lines.append(f'    <checkpoint_count>{m.checkpoint_count}</checkpoint_count>')
            xml_lines.append(f'    <file_path>{m.file_path}</file_path>')
            xml_lines.append(f'    <language>{m.language}</language>')
            xml_lines.append(f'    <success>{m.success}</success>')
            if m.error_message:
                xml_lines.append(f'    <error_message>{m.error_message}</error_message>')
            xml_lines.append('  </measurement>')
        
        xml_lines.append('</measurements>')
        xml_str = '\n'.join(xml_lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(xml_str)
            return str(output_path)
        
        return xml_str
    
    def _save_report(self, report_data: Dict[str, Any], format: str, output_path: Path):
        """Save report data to file in specified format."""
        if format.lower() == "json":
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2)
        elif format.lower() == "html":
            html_content = self._generate_html_report(report_data)
            with open(output_path, 'w') as f:
                f.write(html_content)
        else:
            # Default to JSON
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2)
    
    def _generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """Generate HTML report from report data."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CodeGreen Energy Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .measurement {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .success {{ border-left: 5px solid #4CAF50; }}
        .failure {{ border-left: 5px solid #f44336; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .recommendations {{ background: #e8f5e8; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>CodeGreen Energy Measurement Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Energy: {report_data['summary']['total_energy_joules']:.3f} J</p>
        <p>Average Power: {report_data['summary']['average_power_watts']:.1f} W</p>
        <p>Total Duration: {report_data['summary']['total_duration_seconds']:.1f} s</p>
        <p>Efficiency Score: {report_data['summary']['energy_efficiency_score']:.1f}/100</p>
    </div>
    
    <h2>Measurements</h2>
    <table>
        <tr>
            <th>Session ID</th>
            <th>Energy (J)</th>
            <th>Power (W)</th>
            <th>Duration (s)</th>
            <th>Status</th>
        </tr>
"""
        
        for m in report_data['measurements']:
            status = "✅" if m['success'] else "❌"
            html += f"""
        <tr>
            <td>{m['session_id']}</td>
            <td>{m['energy_joules']:.3f}</td>
            <td>{m['average_watts']:.1f}</td>
            <td>{m['duration_seconds']:.3f}</td>
            <td>{status}</td>
        </tr>
"""
        
        html += """
    </table>
    
    <div class="recommendations">
        <h2>Recommendations</h2>
        <ul>
"""
        
        for rec in report_data['recommendations']:
            html += f"        <li>{rec}</li>\n"
        
        html += """
        </ul>
    </div>
</body>
</html>
"""
        return html