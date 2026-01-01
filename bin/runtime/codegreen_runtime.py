"""
CodeGreen Runtime Module for Python
Provides runtime energy measurement functionality for instrumented Python code.
Designed for minimal overhead and high accuracy energy measurements using the NEMB C++ backend.
"""

import time
import threading
import json
import os
import sys
import ctypes
from ctypes import c_double, c_char_p, c_uint64, c_int, byref
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass, asdict
from pathlib import Path

# --- C++ Backend Interface ---

def _find_nemb_library() -> Optional[str]:
    """Find the path to the shared NEMB library."""
    possible_names = ["libcodegreen-nemb.so", "libcodegreen-nemb.dylib", "codegreen-nemb.dll"]
    
    # Paths to search
    search_paths = [
        # 1. Relative to this file (if installed in site-packages/codegreen/instrumentation)
        Path(__file__).parent.parent.parent / "lib",
        Path(__file__).parent.parent.parent / "build" / "lib",
        # 2. Standard library paths
        Path("/usr/local/lib"),
        Path("/usr/lib"),
        # 3. Environment variable
        Path(os.environ.get("CODEGREEN_LIB_PATH", ""))
    ]
    
    for path in search_paths:
        if not path.exists():
            continue
        for name in possible_names:
            lib_path = path / name
            if lib_path.exists():
                return str(lib_path)
    
    return None

class NEMBClient:
    """Interface to the Native Energy Measurement Backend (C++)"""
    
    def __init__(self):
        self.lib = None
        self.available = False
        
        lib_path = _find_nemb_library()
        if lib_path:
            try:
                self.lib = ctypes.CDLL(lib_path)
                
                # Setup function signatures
                self.lib.nemb_initialize.argtypes = []
                self.lib.nemb_initialize.restype = c_int
                
                self.lib.nemb_read_current.argtypes = [ctypes.POINTER(c_double), ctypes.POINTER(c_double)]
                self.lib.nemb_read_current.restype = c_int
                
                # Initialize backend
                if self.lib.nemb_initialize():
                    self.available = True
            except Exception as e:
                print(f"CodeGreen Runtime Warning: Failed to load NEMB library: {e}", file=sys.stderr)
        else:
            # Fallback for development where library might not be built yet
            pass

    def read_energy(self) -> tuple:
        """Returns (joules, watts)"""
        if not self.available:
            return (0.0, 0.0)
            
        energy = c_double()
        power = c_double()
        
        if self.lib.nemb_read_current(byref(energy), byref(power)):
            return (energy.value, power.value)
            
        return (0.0, 0.0)

# --- Runtime Implementation ---

class EnergyReader:
    """Reads energy from hardware sensors via NEMB or fallback"""

    def __init__(self):
        self.client = NEMBClient()
        self.available = self.client.available
        
        # Fallback for legacy RAPL if C++ backend unavailable
        if not self.available:
            self.rapl_path = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
            self.fallback_available = self.rapl_path.exists()
            self.last_energy = 0
            self.last_timestamp = 0
            if self.fallback_available:
                try:
                    self.last_energy = self._read_rapl_fallback()
                    self.last_timestamp = time.perf_counter()
                except:
                    self.fallback_available = False
        else:
            self.fallback_available = False

    def _read_rapl_fallback(self) -> int:
        """Read RAPL energy counter in microjoules (Fallback)"""
        try:
            with open(self.rapl_path, 'r') as f:
                return int(f.read().strip())
        except:
            return 0

    def read_energy(self) -> tuple:
        """Returns (joules, watts) since last read"""
        if self.available:
            return self.client.read_energy()
            
        if not self.fallback_available:
            return (0.0, 0.0)

        # Legacy fallback logic
        try:
            current_energy = self._read_rapl_fallback()
            current_timestamp = time.perf_counter()

            delta_uj = current_energy - self.last_energy
            delta_time = current_timestamp - self.last_timestamp

            if delta_uj < 0:
                delta_uj += (1 << 32)

            joules = delta_uj / 1_000_000.0
            watts = joules / delta_time if delta_time > 0 else 0.0

            self.last_energy = current_energy
            self.last_timestamp = current_timestamp

            return (joules, watts)
        except:
            return (0.0, 0.0)

_energy_reader: Optional[EnergyReader] = None
_energy_lock = threading.Lock()

def _get_energy_reader() -> EnergyReader:
    """Get or create global energy reader"""
    global _energy_reader
    if _energy_reader is None:
        with _energy_lock:
            if _energy_reader is None:
                _energy_reader = EnergyReader()
    return _energy_reader

@dataclass
class EnergyMeasurement:
    """Lightweight energy measurement data structure"""
    checkpoint_id: str
    timestamp: float
    joules: float = 0.0
    watts: float = 0.0
    source: str = "nemb"

class MeasurementCollector:
    """High-performance measurement collector with minimal overhead"""
    
    def __init__(self):
        self.measurements: List[EnergyMeasurement] = []
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def record_checkpoint(self, checkpoint_id: str, checkpoint_type: str, name: str,
                         line_number: int, context: str) -> None:
        """Record a checkpoint with minimal overhead"""
        timestamp = time.perf_counter()

        energy_reader = _get_energy_reader()
        joules, watts = energy_reader.read_energy()

        measurement = EnergyMeasurement(
            checkpoint_id=checkpoint_id,
            timestamp=timestamp,
            joules=joules,
            watts=watts,
            source="nemb" if energy_reader.available else "rapl_fallback"
        )

        with self.lock:
            self.measurements.append(measurement)
    
    def get_measurements(self) -> List[EnergyMeasurement]:
        """Get all measurements"""
        with self.lock:
            return self.measurements.copy()
    
    def clear(self) -> None:
        """Clear all measurements"""
        with self.lock:
            self.measurements.clear()

# Global measurement collector
_measurement_collector: Optional[MeasurementCollector] = None
_collector_lock = threading.Lock()

# Global session management
_measurement_session: Optional['MeasurementSession'] = None
_session_lock = threading.Lock()


@dataclass
class CheckpointMeasurement:
    """Represents a single checkpoint measurement."""
    id: str
    type: str
    name: str
    line_number: int
    context: str
    timestamp: float
    process_id: int
    thread_id: int


class MeasurementSession:
    """Manages energy measurement session for a single execution."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.measurements: List[CheckpointMeasurement] = []
        self.start_time = time.time()
        self.process_id = os.getpid()
        self._lock = threading.Lock()
    
    def add_measurement(self, checkpoint_id: str, checkpoint_type: str, 
                       name: str, line_number: int, context: str):
        """Add a checkpoint measurement to the session."""
        measurement = CheckpointMeasurement(
            id=checkpoint_id,
            type=checkpoint_type,
            name=name,
            line_number=line_number,
            context=context,
            timestamp=time.perf_counter(),
            process_id=self.process_id,
            thread_id=threading.get_ident()
        )
        
        with self._lock:
            self.measurements.append(measurement)
    
    def save_to_file(self, filepath: str):
        """Save measurement session to JSON file."""
        session_data = {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': time.time(),
            'process_id': self.process_id,
            'measurements': [asdict(m) for m in self.measurements]
        }
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)


def initialize_session(session_id: Optional[str] = None) -> str:
    """Initialize a new measurement session."""
    global _measurement_session
    
    if session_id is None:
        session_id = f"codegreen_{int(time.time())}_{os.getpid()}"
    
    with _session_lock:
        _measurement_session = MeasurementSession(session_id)
    
    return session_id


def finalize_session(output_file: Optional[str] = None) -> Dict:
    """Finalize the measurement session and optionally save to file."""
    global _measurement_session
    
    with _session_lock:
        if _measurement_session is None:
            return {}
        
        if output_file:
            _measurement_session.save_to_file(output_file)
        
        # Create summary data
        summary = {
            'session_id': _measurement_session.session_id,
            'total_checkpoints': len(_measurement_session.measurements),
            'duration': time.time() - _measurement_session.start_time,
            'measurements': [asdict(m) for m in _measurement_session.measurements]
        }
        
        _measurement_session = None
        return summary


def measure_checkpoint(checkpoint_id: str, checkpoint_type: str, 
                      name: str, line_number: int, context: str):
    """Record a checkpoint measurement with minimal overhead for energy accuracy."""
    global _measurement_collector
    
    # Initialize collector on first use (lazy initialization)
    if _measurement_collector is None:
        with _collector_lock:
            if _measurement_collector is None:
                _measurement_collector = MeasurementCollector()
    
    # Record checkpoint with minimal overhead
    _measurement_collector.record_checkpoint(checkpoint_id, checkpoint_type, name, line_number, context)


def checkpoint(checkpoint_id: str, name: str, checkpoint_type: str):
    """Simplified checkpoint function for compatibility with instrumented code."""
    measure_checkpoint(checkpoint_id, checkpoint_type, name, 0, "")


def get_session_info() -> Dict:
    """Get information about the current measurement session."""
    global _measurement_session
    
    with _session_lock:
        if _measurement_session is None:
            return {'active': False}
        
        return {
            'active': True,
            'session_id': _measurement_session.session_id,
            'start_time': _measurement_session.start_time,
            'checkpoint_count': len(_measurement_session.measurements),
            'process_id': _measurement_session.process_id
        }


# Export key functions for instrumented code
__all__ = [
    'measure_checkpoint',
    'checkpoint',
    'initialize_session', 
    'finalize_session',
    'get_session_info'
]