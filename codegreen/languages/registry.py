"""
Language Registry for CodeGreen

Central registry for all supported languages following plugin architecture
pattern from tree-climber and nvim-treesitter.
"""

import logging
from typing import Dict, List, Optional, Type
from .base import LanguageAdapter

logger = logging.getLogger(__name__)


class LanguageRegistry:
    """
    Central registry for all language adapters.
    
    Provides plugin-style registration and discovery of language support,
    following the extensible pattern from tree-sitter tooling ecosystem.
    """
    
    def __init__(self):
        self._adapters: Dict[str, Type[LanguageAdapter]] = {}
        self._extension_map: Dict[str, str] = {}  # .py -> python
        
    def register_adapter(self, adapter_class: Type[LanguageAdapter]):
        """
        Register a language adapter class.
        
        Args:
            adapter_class: Class that implements LanguageAdapter interface
        """
        # Create instance to get language info
        temp_instance = adapter_class()
        language_id = temp_instance.language_id
        
        self._adapters[language_id] = adapter_class
        
        # Register file extensions
        for ext in temp_instance.get_file_extensions():
            self._extension_map[ext] = language_id
            
        logger.info(f"✅ Registered language adapter: {language_id}")
    
    def get_adapter(self, language_id: str, **kwargs) -> Optional[LanguageAdapter]:
        """
        Get adapter instance for specified language.
        
        Args:
            language_id: Language identifier (e.g., 'python', 'c')
            **kwargs: Additional arguments passed to adapter constructor
            
        Returns:
            LanguageAdapter instance or None if not found
        """
        if language_id not in self._adapters:
            logger.warning(f"❌ No adapter found for language: {language_id}")
            return None
            
        try:
            return self._adapters[language_id](**kwargs)
        except Exception as e:
            logger.error(f"❌ Failed to create adapter for {language_id}: {e}")
            return None
    
    def get_adapter_for_file(self, filename: str, **kwargs) -> Optional[LanguageAdapter]:
        """
        Get adapter for file based on its extension.
        
        Args:
            filename: Filename or path
            **kwargs: Additional arguments passed to adapter constructor
            
        Returns:
            LanguageAdapter instance or None if no matching adapter
        """
        # Extract extension
        if '.' not in filename:
            return None
            
        ext = '.' + filename.split('.')[-1]
        
        if ext not in self._extension_map:
            logger.warning(f"❌ No adapter found for extension: {ext}")
            return None
            
        language_id = self._extension_map[ext]
        return self.get_adapter(language_id, **kwargs)
    
    def list_supported_languages(self) -> List[str]:
        """Get list of all supported language IDs"""
        return list(self._adapters.keys())
    
    def list_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions"""
        return list(self._extension_map.keys())
    
    def is_supported(self, language_id: str) -> bool:
        """Check if language is supported"""
        return language_id in self._adapters


# Global registry instance
_global_registry = LanguageRegistry()


def get_language_adapter(language_id: str, **kwargs) -> Optional[LanguageAdapter]:
    """
    Convenience function to get adapter from global registry.
    
    Args:
        language_id: Language identifier
        **kwargs: Additional arguments passed to adapter constructor
        
    Returns:
        LanguageAdapter instance or None
    """
    return _global_registry.get_adapter(language_id, **kwargs)


def get_adapter_for_file(filename: str, **kwargs) -> Optional[LanguageAdapter]:
    """
    Convenience function to get adapter for file from global registry.
    
    Args:
        filename: Filename or path
        **kwargs: Additional arguments passed to adapter constructor
        
    Returns:
        LanguageAdapter instance or None
    """
    return _global_registry.get_adapter_for_file(filename, **kwargs)


def register_adapter(adapter_class: Type[LanguageAdapter]):
    """
    Convenience function to register adapter in global registry.
    
    Args:
        adapter_class: Class that implements LanguageAdapter interface
    """
    _global_registry.register_adapter(adapter_class)


def list_supported_languages() -> List[str]:
    """Get list of all supported languages from global registry"""
    return _global_registry.list_supported_languages()