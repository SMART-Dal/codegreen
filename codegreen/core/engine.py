"""
Measurement Engine - Python wrapper for C++ measurement engine

This module provides a Python interface to the CodeGreen measurement engine,
allowing for programmatic access to energy measurement capabilities.
"""

import os
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
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
                cmd.extend(['--output', str(output_file)])
            
            if sensors:
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