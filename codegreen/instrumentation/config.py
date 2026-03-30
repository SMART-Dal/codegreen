"""
Configuration Management for CodeGreen Python Package
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

class Config:
    """CodeGreen configuration management."""
    
    def __init__(self, config_file: Optional[Path] = None):
        self._config: Dict[str, Any] = {}
        self._config_file: Optional[Path] = config_file
        self._load_config()
    
    def _find_config_file(self) -> Optional[Path]:
        """Find configuration file from various locations."""
        
        if self._config_file and self._config_file.exists():
            return self._config_file
        
        # Environment variable
        env_config = os.environ.get('CODEGREEN_CONFIG')
        if env_config and Path(env_config).exists():
            return Path(env_config)
        
        # Package-distributed config
        package_configs = [
            Path(__file__).parents[1] / "bin" / "config" / "codegreen.json",
            Path(__file__).parents[2] / "config" / "codegreen.json",
        ]
        
        for config_path in package_configs:
            if config_path.exists():
                return config_path
        
        return None
    
    def _load_config(self):
        """Load configuration from file or use defaults."""
        config_file = self._find_config_file()
        
        if config_file:
            try:
                with open(config_file, 'r') as f:
                    self._config = json.load(f)
                return
            except (json.JSONDecodeError, IOError):
                pass
        
        # Use defaults
        self._config = {
            "measurement": {
                "pmt": {
                    "preferred_sensors": ["rapl", "nvml", "dummy"]
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation."""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default