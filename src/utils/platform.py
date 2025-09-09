"""
Platform detection utilities
"""

import platform
from typing import Dict, Any

def get_platform_info() -> Dict[str, Any]:
    """
    Get comprehensive platform information.
    
    Returns:
        Dictionary with platform details
    """
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture(),
    }

def get_platform_tag() -> str:
    """
    Get a platform tag for binary selection.
    
    Returns:
        Platform tag like 'linux-x86_64' or 'windows-amd64'
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize machine names
    machine_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64', 
        'aarch64': 'aarch64',
        'arm64': 'aarch64',
    }
    
    normalized_machine = machine_map.get(machine, machine)
    return f"{system}-{normalized_machine}"