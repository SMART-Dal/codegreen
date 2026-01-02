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
        lib_path = _find_nemb_library()
        if not lib_path:
            self.lib = None
            return

        try:
            self.lib = ctypes.CDLL(lib_path)
            self.lib.nemb_initialize.argtypes = []
            self.lib.nemb_initialize.restype = c_int
            
            # Instantaneous reading API
            self.lib.nemb_read_current.argtypes = [ctypes.POINTER(c_double), ctypes.POINTER(c_double)]
            self.lib.nemb_read_current.restype = c_int
            
            # High-accuracy "Signal Generator" API
            self.lib.nemb_mark_checkpoint.argtypes = [c_char_p]
            self.lib.nemb_mark_checkpoint.restype = None
            
            self.lib.nemb_get_checkpoints_json.argtypes = [c_char_p, c_int]
            self.lib.nemb_get_checkpoints_json.restype = c_int

            if not self.lib.nemb_initialize():
                self.lib = None
        except Exception:
            self.lib = None

    def mark_checkpoint(self, name: str):
        """Send a lightweight signal to the C++ backend"""
        if self.lib:
            self.lib.nemb_mark_checkpoint(name.encode('utf-8'))

    def get_final_measurements(self) -> List[Dict]:
        """Retrieve correlated time-series measurements from C++ backend"""
        if not self.lib:
            return []
            
        # Use a large buffer for JSON data (1MB)
        buf_size = 1024 * 1024
        buf = ctypes.create_string_buffer(buf_size)
        
        ret = self.lib.nemb_get_checkpoints_json(buf, buf_size)
        if ret > 0:
            try:
                data = json.loads(buf.value.decode('utf-8'))
                return data.get("checkpoints", [])
            except Exception:
                return []
        return []

    def read_energy(self) -> tuple:
        """Returns (joules, watts) - kept for compatibility"""
        if not self.lib:
            return (0.0, 0.0)

        energy = c_double()
        power = c_double()
        if self.lib.nemb_read_current(byref(energy), byref(power)):
            return (energy.value, power.value)
        return (0.0, 0.0)

# --- Runtime Implementation ---

_nemb_client: Optional[NEMBClient] = None
_client_lock = threading.Lock()

def _get_nemb_client() -> NEMBClient:
    """Get or create global NEMB client"""
    global _nemb_client
    if _nemb_client is None:
        with _client_lock:
            if _nemb_client is None:
                _nemb_client = NEMBClient()
    return _nemb_client

def _report_at_exit():
    """Report measurements to stdout in a way that CLI can parse"""
    client = _get_nemb_client()
    measurements = client.get_final_measurements()
    
    if not measurements:
        return
    
    # Wrap in clear markers for CLI tool parsing
    print("\n--- CODEGREEN_RESULT_START ---")
    results = {
        "measurements": measurements
    }
    print(json.dumps(results))
    print("--- CODEGREEN_RESULT_END ---")

import atexit
atexit.register(_report_at_exit)

def measure_checkpoint(checkpoint_id: str, checkpoint_type: str, 
                      name: str, line_number: int, context: str):
    """Record a checkpoint marker with ultra-low overhead."""
    client = _get_nemb_client()
    # Signal name contains ID and metadata for later correlation
    signal_name = f"{checkpoint_type}:{name}:{checkpoint_id}"
    client.mark_checkpoint(signal_name)


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