"""
Language Plugin Manager for CodeGreen

Automatic discovery and registration of language plugins with graceful fallbacks.
Follows the extensible pattern from tree-sitter-languages and nvim-treesitter.
"""

import logging
from typing import Optional, Dict, Any
from .registry import register_adapter, _global_registry
from .base import LanguageAdapter

logger = logging.getLogger(__name__)


class LanguagePluginManager:
    """
    Manages automatic discovery and registration of language plugins.
    
    Provides multiple strategies for language support:
    1. tree-sitter-languages package (preferred)
    2. Built-in adapters with fallback analysis
    3. External plugin discovery
    """
    
    def __init__(self):
        self.registry = _global_registry
        self._treesitter_available = False
        self._discover_plugins()
    
    def _discover_plugins(self):
        """Automatically discover and register all available language plugins"""
        logger.info("🔍 Discovering language plugins...")
        
        # 1. Check tree-sitter-languages availability
        self._check_treesitter_languages()
        
        # 2. Register built-in languages
        self._register_builtin_languages()
        
        # 3. Register tree-sitter enhanced languages
        if self._treesitter_available:
            self._register_treesitter_languages()
        
        logger.info(f"✅ Language discovery complete. {len(self.registry.list_supported_languages())} languages available")
    
    def _check_treesitter_languages(self):
        """Check if tree-sitter-languages package is available"""
        try:
            import tree_sitter_language_pack
            self._treesitter_available = True
            logger.info("✅ tree-sitter-languages package available")
        except ImportError:
            self._treesitter_available = False
            logger.info("⚠️ tree-sitter-languages not available, using fallback analysis")
    
    def _register_builtin_languages(self):
        """Register built-in language adapters with fallback support"""
        
        # Import built-in adapters
        from .adapters.python import PythonAdapter
        from .adapters.c import CAdapter  
        from .adapters.cpp import CppAdapter
        from .adapters.java import JavaAdapter
        
        builtin_adapters = [PythonAdapter, CAdapter, CppAdapter, JavaAdapter]
        
        for adapter_class in builtin_adapters:
            try:
                register_adapter(adapter_class)
                logger.info(f"✅ Registered built-in adapter: {adapter_class.__name__}")
            except Exception as e:
                logger.error(f"❌ Failed to register {adapter_class.__name__}: {e}")
    
    def _register_treesitter_languages(self):
        """Register enhanced adapters using tree-sitter-languages"""
        if not self._treesitter_available:
            return
            
        from tree_sitter_language_pack import get_parser
        
        # Languages to enhance with tree-sitter parsing
        enhanced_languages = {
            'python': 'python',
            'c': 'c', 
            'cpp': 'cpp',
            'java': 'java',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'rust': 'rust',
            'go': 'go',
            'bash': 'bash'
        }
        
        for lang_id, parser_name in enhanced_languages.items():
            try:
                parser = get_parser(parser_name)
                
                # Get existing adapter or create generic one
                existing_adapter = self.registry.get_adapter(lang_id)
                
                if existing_adapter:
                    # Enhance existing adapter with tree-sitter parser
                    enhanced = self._enhance_adapter_with_parser(existing_adapter, parser)
                    if enhanced:
                        logger.info(f"🚀 Enhanced {lang_id} with tree-sitter parser")
                else:
                    # Create generic tree-sitter adapter
                    generic_adapter = self._create_generic_adapter(lang_id, parser)
                    if generic_adapter:
                        register_adapter(generic_adapter)
                        logger.info(f"🆕 Added generic tree-sitter support for {lang_id}")
                        
            except Exception as e:
                logger.debug(f"⚠️ Could not enhance {lang_id}: {e}")
    
    def _enhance_adapter_with_parser(self, adapter: LanguageAdapter, parser) -> bool:
        """Enhance existing adapter with tree-sitter parser"""
        try:
            # Replace parser in existing adapter instance
            adapter.parser = parser
            adapter._load_queries()  # Reload queries with new parser
            return True
        except Exception as e:
            logger.error(f"❌ Failed to enhance adapter: {e}")
            return False
    
    def _create_generic_adapter(self, language_id: str, parser) -> Optional[type]:
        """Create generic adapter class for tree-sitter parser"""
        
        # Common file extensions mapping
        extension_map = {
            'python': ['.py', '.pyw'],
            'c': ['.c', '.h'],
            'cpp': ['.cpp', '.cxx', '.cc', '.hpp', '.hxx', '.h++'],
            'java': ['.java'],
            'javascript': ['.js', '.jsx'],
            'typescript': ['.ts', '.tsx'],
            'rust': ['.rs'],
            'go': ['.go'],
            'bash': ['.sh', '.bash']
        }
        
        extensions = extension_map.get(language_id, [f'.{language_id}'])
        
        class GenericTreeSitterAdapter(LanguageAdapter):
            """Generic adapter using tree-sitter parser"""
            
            def __init__(self, parser_instance=None):
                super().__init__(parser_instance or parser)
            
            @property
            def language_id(self) -> str:
                return language_id
            
            def get_file_extensions(self) -> list:
                return extensions
            
            def get_query_definitions(self) -> Dict[str, str]:
                """Basic queries that work for most languages"""
                return {
                    'functions': """
                        (function_definition) @function.def
                        (method_definition) @function.def  
                        (function_declaration) @function.def
                    """,
                    'loops': """
                        [(for_statement) (while_statement) (do_statement)] @loop
                    """,
                    'conditionals': """
                        [(if_statement) (switch_statement)] @conditional
                    """
                }
            
            def _generate_instrumentation_points_fallback(self, source_code: str):
                """Basic regex fallback for generic languages"""
                import re
                points = []
                
                # Basic function detection
                func_pattern = r'^\s*(def|function|func|fn)\s+(\w+)'
                for i, line in enumerate(source_code.split('\n')):
                    match = re.match(func_pattern, line)
                    if match:
                        from .base import InstrumentationPoint
                        points.append(InstrumentationPoint(
                            type='function',
                            subtype='definition',
                            name=match.group(2),
                            line=i + 1,
                            column=match.start(2),
                            context=f"Function {match.group(2)} at line {i + 1}"
                        ))
                
                return points
        
        return GenericTreeSitterAdapter


# Global manager instance
_plugin_manager = None


def get_plugin_manager() -> LanguagePluginManager:
    """Get global plugin manager instance"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = LanguagePluginManager()
    return _plugin_manager


def ensure_plugins_loaded():
    """Ensure language plugins are loaded"""
    get_plugin_manager()  # This will trigger plugin discovery if not done