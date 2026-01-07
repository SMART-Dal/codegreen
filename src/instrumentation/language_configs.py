"""
Centralized language configuration system for CodeGreen.

This module provides a clean, extensible way to configure language-specific
behavior by loading configurations from external JSON files.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class LanguageConfig:
    """Configuration for a specific programming language."""
    
    # Basic language info
    name: str
    extensions: List[str]
    tree_sitter_name: str
    
    # AST structure configuration
    ast_config: Dict[str, Any]
    
    # Query configuration
    query_config: Dict[str, Any]
    
    # Instrumentation configuration
    instrumentation_config: Dict[str, Any]
    
    # Indentation and formatting
    formatting_config: Dict[str, Any]
    
    # Language-specific rules
    rules: Dict[str, Any]
    
    # Analysis patterns for fallback
    analysis_patterns: Dict[str, Any]
    
    # Language detection patterns
    detection_patterns: Dict[str, Any]
    
    # Processing limits and thresholds
    processing_limits: Dict[str, Any]
    
    # AST node type mappings
    node_types: Dict[str, Any]
    
    # Custom queries
    custom_queries: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LanguageConfig':
        """Create a LanguageConfig from a dictionary, filtering out comment keys."""
        # Filter out keys starting with underscore (used for comments)
        filtered_data = {k: v for k, v in data.items() if not k.startswith('_')}
        return cls(**filtered_data)

class LanguageConfigManager:
    """Manages language configurations in a centralized way."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        # Default to the configs directory relative to this file
        self.config_dir = config_dir or Path(__file__).parent / "configs"
        self._configs: Dict[str, LanguageConfig] = {}
        self._load_configs()
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration values that apply across all languages."""
        return {
            "supported_languages": list(self._configs.keys()),
            "strict_mode": False,
            "default_encoding": "utf-8",
            "default_timeout_ms": 30000,
            "default_file_size_mb": 100,
            "default_indent_size": 4,
            "default_indent_char": " ",
            "debug_text_preview_length": 100,
            "debug_error_text_length": 200,
            "debug_significant_change_threshold": 100,
            "max_parent_search_levels": 10,
            "max_inheritance_depth": 5,
            "capture_priority_high": 1,
            "capture_priority_medium": 2,
            "capture_priority_low": 3,
            "line_offset": 1,
            "common_node_types": {
                "function_types": ["function_definition", "method_definition", "constructor_definition", "async_function_definition"],
                "class_types": ["class_definition", "class_specifier", "class_declaration", "struct_specifier"],
                "body_types": ["body", "block", "compound_statement", "constructor_body"],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": ["expression_statement"]
            }
        }
    
    def _load_configs(self):
        """Load all language configurations from the config directory."""
        if not self.config_dir.exists():
            logger.warning(f"⚠️  Config directory not found: {self.config_dir}")
            return

        for config_file in self.config_dir.glob("*.json"):
            if config_file.name == "TEMPLATE.json":
                continue
            try:
                lang_id = config_file.stem
                with open(config_file, "r") as f:
                    data = json.load(f)
                    self._configs[lang_id] = LanguageConfig.from_dict(data)
                logger.debug(f"✅ Loaded configuration for {lang_id}")
            except Exception as e:
                logger.error(f"❌ Failed to load configuration from {config_file}: {e}")
    
    def get_config(self, language: str) -> Optional[LanguageConfig]:
        """Get configuration for a specific language."""
        return self._configs.get(language)
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self._configs.keys())
    
    def get_ast_config(self, language: str) -> Dict[str, Any]:
        """Get AST configuration for a language."""
        config = self.get_config(language)
        return config.ast_config if config else {}
    
    def get_query_config(self, language: str) -> Dict[str, Any]:
        """Get query configuration for a language."""
        config = self.get_config(language)
        return config.query_config if config else {}
    
    def get_instrumentation_config(self, language: str) -> Dict[str, Any]:
        """Get instrumentation configuration for a language."""
        config = self.get_config(language)
        return config.instrumentation_config if config else {}
    
    def get_formatting_config(self, language: str) -> Dict[str, Any]:
        """Get formatting configuration for a language."""
        config = self.get_config(language)
        return config.formatting_config if config else {}
    
    def get_rules(self, language: str) -> Dict[str, Any]:
        """Get language-specific rules."""
        config = self.get_config(language)
        return config.rules if config else {}
    
    def get_analysis_patterns(self, language: str) -> Dict[str, Any]:
        """Get analysis patterns for fallback regex analysis."""
        config = self.get_config(language)
        return config.analysis_patterns if config else {}
    
    def get_detection_patterns(self, language: str) -> Dict[str, Any]:
        """Get language detection patterns."""
        config = self.get_config(language)
        return config.detection_patterns if config else {}
    
    def get_processing_limits(self, language: str) -> Dict[str, Any]:
        """Get processing limits and thresholds for a language."""
        config = self.get_config(language)
        return config.processing_limits if config else {}
    
    def get_node_types(self, language: str) -> Dict[str, Any]:
        """Get AST node type mappings for a language."""
        config = self.get_config(language)
        return config.node_types if config else {}
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions across all languages."""
        extensions = []
        for config in self._configs.values():
            extensions.extend(config.extensions)
        return list(set(extensions))  # Remove duplicates
    
    def detect_language_from_filename(self, filename: str) -> Optional[str]:
        """Detect language from filename using configuration."""
        ext = Path(filename).suffix.lower()
        for language, config in self._configs.items():
            if ext in config.extensions:
                return language
        return None
    
    def detect_language_from_content(self, content: str) -> Optional[str]:
        """Detect language from content using detection patterns."""
        for language, config in self._configs.items():
            detection_patterns = config.detection_patterns
            if not detection_patterns:
                continue
            
            # Check for language-specific patterns
            for pattern_name, pattern in detection_patterns.items():
                if isinstance(pattern, str) and pattern in content:
                    return language
                elif isinstance(pattern, dict) and 'regex' in pattern:
                    import re
                    if re.search(pattern['regex'], content):
                        return language
        
        return None

# Global instance
_config_manager = None

def get_language_config_manager() -> LanguageConfigManager:
    """Get the global language configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = LanguageConfigManager()
    return _config_manager