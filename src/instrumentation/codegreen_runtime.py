"""
CodeGreen Runtime Module for Python
Provides runtime energy measurement functionality for instrumented Python code.
Designed for minimal overhead and high accuracy energy measurements.
"""

import time
import threading
import json
import os
import sys
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass, asdict

@dataclass
class EnergyMeasurement:
    """Lightweight energy measurement data structure"""
    checkpoint_id: str
    timestamp: float
    joules: float = 0.0
    watts: float = 0.0
    source: str = "pmt"

class MeasurementCollector:
    """High-performance measurement collector with minimal overhead"""
    
    def __init__(self):
        self.measurements: List[EnergyMeasurement] = []
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def record_checkpoint(self, checkpoint_id: str, checkpoint_type: str, name: str, 
                         line_number: int, context: str) -> None:
        """Record a checkpoint with minimal overhead"""
        # Use high-precision timer for accuracy
        timestamp = time.perf_counter()
        
        # Create measurement with placeholder values
        # In production, these would be filled by the C++ PMT integration
        measurement = EnergyMeasurement(
            checkpoint_id=checkpoint_id,
            timestamp=timestamp,
            joules=0.0,  # Will be filled by PMT
            watts=0.0,   # Will be filled by PMT
            source="pmt"
        )
        
        # Thread-safe append with minimal locking
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