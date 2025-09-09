"""
Binary location and validation utilities
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional

def get_binary_name() -> str:
    """Get the binary name for the current platform."""
    if platform.system() == "Windows":
        return "codegreen.exe"
    return "codegreen"

def find_binary() -> Optional[Path]:
    """
    Find the CodeGreen binary in various locations.
    
    Returns:
        Path to binary if found, None otherwise
    """
    binary_name = get_binary_name()
    
    # Search locations in priority order
    search_paths = [
        # 1. Package installation directory
        Path(__file__).parents[1] / "bin" / binary_name,
        
        # 2. Platform-specific package directory
        Path(__file__).parents[1] / "bin" / f"{platform.system().lower()}-{platform.machine().lower()}" / binary_name,
        
        # 3. Development build directory
        Path(__file__).parents[2] / "build" / "bin" / binary_name,
        
        # 4. System PATH
        shutil.which("codegreen"),
    ]
    
    for path in search_paths:
        if path and Path(path).exists() and os.access(path, os.X_OK):
            return Path(path)
    
    return None

def ensure_binary_available() -> Path:
    """
    Ensure binary is available and return its path.
    
    Raises:
        RuntimeError: If binary cannot be found
        
    Returns:
        Path to the binary
    """
    binary_path = find_binary()
    
    if not binary_path:
        raise RuntimeError(
            "CodeGreen binary not found. Please ensure CodeGreen is properly installed.\n"
            "Try: pip install --force-reinstall codegreen"
        )
    
    return binary_path