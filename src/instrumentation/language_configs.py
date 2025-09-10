"""
Centralized language configuration system for CodeGreen.

This module provides a clean, extensible way to configure language-specific
behavior without hardcoding if/else blocks throughout the codebase.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
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

class LanguageConfigManager:
    """Manages language configurations in a centralized way."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent / "language_configs"
        self._configs: Dict[str, LanguageConfig] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all language configurations from files."""
        if not self.config_dir.exists():
            logger.warning(f"Config directory {self.config_dir} does not exist, using defaults")
            self._load_default_configs()
            return
        
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    language_name = config_file.stem
                    config = LanguageConfig(**config_data)
                    self._configs[language_name] = config
                    logger.info(f"Loaded configuration for {language_name}")
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")
    
    def _load_default_configs(self):
        """Load default configurations if no config files exist."""
        self._configs = {
            'python': self._get_default_python_config(),
            'c': self._get_default_c_config(),
            'cpp': self._get_default_cpp_config(),
            'java': self._get_default_java_config(),
            'javascript': self._get_default_javascript_config(),
        }
    
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
    
    def _get_default_python_config(self) -> LanguageConfig:
        """Default Python configuration."""
        return LanguageConfig(
            name="python",
            extensions=[".py", ".pyw"],
            tree_sitter_name="python",
            ast_config={
                "body_field": "body",
                "block_type": "block",
                "function_types": ["function_definition"],
                "class_types": ["class_definition"],
                "loop_types": ["for_statement", "while_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": ["expression_statement"],
                "insertion_rules": {
                    "function_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": True,
                        "skip_comments": True
                    },
                    "function_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "class_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": True,
                        "skip_comments": True
                    },
                    "class_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "before": {
                        "mode": "before"
                    },
                    "after": {
                        "mode": "after"
                    }
                }
            },
            query_config={
                "capture_mapping": {
                    "function.definition": "function_enter",
                    "function.name": "function_enter",
                    "class.definition": "class_enter",
                    "class.name": "class_enter",
                    "return.statement": "function_exit",
                    "loop.for": "loop_start",
                    "loop.while": "loop_start"
                },
                "priority_order": [
                    "function.definition",
                    "class.definition", 
                    "return.statement",
                    "loop.for",
                    "loop.while"
                ]
            },
            instrumentation_config={
                "import_statement": "import codegreen_runtime as _codegreen_rt",
                "templates": {
                    "function_enter": "_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'enter')",
                    "function_exit": "_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'exit')",
                    "class_enter": "_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'class_enter')",
                    "loop_start": "_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'loop_start')",
                    "loop_exit": "_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'loop_exit')"
                },
                "statement_terminator": "",
                "comment_prefix": "#"
            },
            formatting_config={
                "indent_size": 4,
                "indent_char": " ",
                "line_ending": "\n",
                "extra_indent_for_inside": 4
            },
            rules={
                "skip_docstrings": True,
                "skip_comments": True,
                "handle_async": True,
                "handle_decorators": True,
                "handle_generators": True,
                "special_exit_functions": ["__init__", "__enter__", "__exit__", "__call__", "__iter__", "__next__"]
            },
            analysis_patterns={
                "function_def": r'^\s*def\s+(\w+)',
                "class_def": r'^\s*class\s+(\w+)',
                "for_loop": r'^\s*for\s+',
                "while_loop": r'^\s*while\s+',
                "list_comp": r'\[.*for.*in.*\]',
                "lambda_expr": r'lambda\s+',
                "import_star": r'from\s+\w+\s+import\s+\*',
                "nested_loops": r'^\s*for.*:\s*\n.*for'
            },
            detection_patterns={
                "shebang": "#!/usr/bin/env python",
                "import_keywords": ["import", "from"],
                "syntax_keywords": ["def ", "class ", "if __name__"],
                "regex": r'^\s*(def|class|import|from)\s+'
            },
            processing_limits={
                "max_captures_per_query": 10000,
                "max_lines_for_processing": 50000,
                "max_function_name_length": 100,
                "max_identifier_length": 50,
                "max_safety_counter": 10,
                "max_search_window": 50,
                "max_body_text_check": 200,
                "max_function_body_search_lines": 10
            },
            node_types={
                "function_types": ["function_definition", "method_definition", "constructor_definition"],
                "body_types": ["block", "compound_statement", "constructor_body"],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "class_types": ["class_definition", "class_specifier", "struct_specifier"],
                "comment_types": ["comment"],
                "return_types": ["return_statement"]
            }
        )
    
    def _get_default_c_config(self) -> LanguageConfig:
        """Default C configuration."""
        return LanguageConfig(
            name="c",
            extensions=[".c", ".h"],
            tree_sitter_name="c",
            ast_config={
                "body_field": "body",
                "block_type": "compound_statement",
                "function_types": ["function_definition"],
                "class_types": [],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": [],
                "insertion_rules": {
                    "function_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "function_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "class_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "class_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "before": {
                        "mode": "before"
                    },
                    "after": {
                        "mode": "after"
                    }
                }
            },
            query_config={
                "capture_mapping": {
                    "function.definition": "function_enter",
                    "function.name": "function_enter",
                    "return.statement": "function_exit",
                    "loop.for": "loop_start",
                    "loop.while": "loop_start",
                    "loop.do": "loop_start"
                },
                "priority_order": [
                    "function.definition",
                    "return.statement",
                    "loop.for",
                    "loop.while",
                    "loop.do"
                ]
            },
            instrumentation_config={
                "import_statement": '#include "codegreen_runtime.h"',
                "templates": {
                    "function_enter": "codegreen_checkpoint(\"{checkpoint_id}\", \"{name}\", \"enter\");",
                    "function_exit": "codegreen_checkpoint(\"{checkpoint_id}\", \"{name}\", \"exit\");",
                    "loop_start": "codegreen_checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_start\");",
                    "loop_exit": "codegreen_checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_exit\");"
                },
                "statement_terminator": ";",
                "comment_prefix": "//"
            },
            formatting_config={
                "indent_size": 2,
                "indent_char": " ",
                "line_ending": "\n",
                "extra_indent_for_inside": 2
            },
            rules={
                "skip_docstrings": False,
                "skip_comments": True,
                "handle_async": False,
                "handle_decorators": False,
                "handle_generators": False,
                "special_exit_functions": []
            },
            analysis_patterns={
                "function_def": r'^\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*\{?\s*$',
                "for_loop": r'^\s*for\s*\(',
                "while_loop": r'^\s*while\s*\(',
                "do_loop": r'^\s*do\s*\{',
                "memory_op": r'\b(malloc|calloc|realloc|free)\s*\(',
                "strlen_in_loop": r'for\s*\([^;]*strlen',
                "printf_in_loop": r'(for|while).*{[^}]*printf'
            },
            detection_patterns={
                "include_directives": ["#include", "#define"],
                "syntax_keywords": ["int main", "void ", "char ", "return "],
                "regex": r'^\s*(#include|int\s+\w+\s*\(|void\s+\w+\s*\()'
            },
            processing_limits={
                "max_captures_per_query": 10000,
                "max_lines_for_processing": 50000,
                "max_function_name_length": 100,
                "max_identifier_length": 50,
                "max_safety_counter": 10,
                "max_search_window": 50,
                "max_body_text_check": 200,
                "max_function_body_search_lines": 10
            },
            node_types={
                "function_types": ["function_definition"],
                "body_types": ["compound_statement"],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "class_types": [],
                "comment_types": ["comment"],
                "return_types": ["return_statement"]
            }
        )
    
    def _get_default_cpp_config(self) -> LanguageConfig:
        """Default C++ configuration."""
        return LanguageConfig(
            name="cpp",
            extensions=[".cpp", ".cxx", ".cc", ".hpp", ".h", ".hxx", ".h++"],
            tree_sitter_name="cpp",
            ast_config={
                "body_field": "body",
                "block_type": "compound_statement",
                "function_types": ["function_definition"],
                "class_types": ["class_specifier", "struct_specifier"],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": [],
                "insertion_rules": {
                    "function_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "function_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "class_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "class_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "before": {
                        "mode": "before"
                    },
                    "after": {
                        "mode": "after"
                    }
                }
            },
            query_config={
                "capture_mapping": {
                    "function.definition": "function_enter",
                    "function.name": "function_enter",
                    "class.definition": "class_enter",
                    "class.name": "class_enter",
                    "return.statement": "function_exit",
                    "loop.for": "loop_start",
                    "loop.while": "loop_start",
                    "loop.do": "loop_start"
                },
                "priority_order": [
                    "function.definition",
                    "class.definition",
                    "return.statement",
                    "loop.for",
                    "loop.while",
                    "loop.do"
                ]
            },
            instrumentation_config={
                "import_statement": '#include <codegreen/runtime.hpp>',
                "templates": {
                    "function_enter": "CodeGreen::checkpoint(\"{checkpoint_id}\", \"{name}\", \"enter\");",
                    "function_exit": "CodeGreen::checkpoint(\"{checkpoint_id}\", \"{name}\", \"exit\");",
                    "class_enter": "CodeGreen::checkpoint(\"{checkpoint_id}\", \"{name}\", \"class_enter\");",
                    "loop_start": "CodeGreen::checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_start\");",
                    "loop_exit": "CodeGreen::checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_exit\");"
                },
                "statement_terminator": ";",
                "comment_prefix": "//"
            },
            formatting_config={
                "indent_size": 2,
                "indent_char": " ",
                "line_ending": "\n",
                "extra_indent_for_inside": 2
            },
            rules={
                "skip_docstrings": False,
                "skip_comments": True,
                "handle_async": False,
                "handle_decorators": False,
                "handle_generators": False,
                "special_exit_functions": []
            },
            analysis_patterns={
                "function_def": r'^\s*(?:(?:virtual|static|inline|explicit)\s+)*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:final\s*)?\{?\s*$',
                "class_def": r'^\s*class\s+(\w+)',
                "struct_def": r'^\s*struct\s+(\w+)',
                "for_loop": r'^\s*for\s*\(',
                "while_loop": r'^\s*while\s*\(',
                "new_op": r'\bnew\s+',
                "delete_op": r'\bdelete\s+'
            },
            detection_patterns={
                "include_directives": ["#include", "#define", "using namespace"],
                "syntax_keywords": ["int main", "void ", "class ", "namespace "],
                "regex": r'^\s*(#include|class\s+\w+|namespace\s+\w+)'
            },
            processing_limits={
                "max_captures_per_query": 10000,
                "max_lines_for_processing": 50000,
                "max_function_name_length": 100,
                "max_identifier_length": 50,
                "max_safety_counter": 10,
                "max_search_window": 50,
                "max_body_text_check": 200,
                "max_function_body_search_lines": 10
            },
            node_types={
                "function_types": ["function_definition"],
                "body_types": ["compound_statement"],
                "loop_types": ["for_statement", "while_statement", "do_statement"],
                "class_types": ["class_specifier", "struct_specifier"],
                "comment_types": ["comment"],
                "return_types": ["return_statement"]
            }
        )
    
    def _get_default_java_config(self) -> LanguageConfig:
        """Default Java configuration."""
        return LanguageConfig(
            name="java",
            extensions=[".java"],
            tree_sitter_name="java",
            ast_config={
                "body_field": "body",
                "block_type": "block",
                "function_types": ["method_declaration", "constructor_declaration"],
                "class_types": ["class_declaration", "interface_declaration", "enum_declaration"],
                "loop_types": ["for_statement", "while_statement", "do_statement", "enhanced_for_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": [],
                "insertion_rules": {
                    "function_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "function_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "class_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "class_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "before": {
                        "mode": "before"
                    },
                    "after": {
                        "mode": "after"
                    }
                }
            },
            query_config={
                "capture_mapping": {
                    "method.definition": "function_enter",
                    "method.name": "function_enter",
                    "constructor.definition": "function_enter",
                    "constructor.name": "function_enter",
                    "class.definition": "class_enter",
                    "class.name": "class_enter",
                    "return.statement": "function_exit",
                    "loop.for": "loop_start",
                    "loop.while": "loop_start",
                    "loop.do": "loop_start",
                    "loop.enhanced_for": "loop_start"
                },
                "priority_order": [
                    "method.definition",
                    "constructor.definition",
                    "class.definition",
                    "return.statement",
                    "loop.for",
                    "loop.while",
                    "loop.do",
                    "loop.enhanced_for"
                ]
            },
            instrumentation_config={
                "import_statement": "import codegreen.runtime.CodeGreenRuntime;",
                "templates": {
                    "function_enter": "CodeGreenRuntime.checkpoint(\"{checkpoint_id}\", \"{name}\", \"enter\");",
                    "function_exit": "CodeGreenRuntime.checkpoint(\"{checkpoint_id}\", \"{name}\", \"exit\");",
                    "class_enter": "CodeGreenRuntime.checkpoint(\"{checkpoint_id}\", \"{name}\", \"class_enter\");",
                    "loop_start": "CodeGreenRuntime.checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_start\");",
                    "loop_exit": "CodeGreenRuntime.checkpoint(\"{checkpoint_id}\", \"{name}\", \"loop_exit\");"
                },
                "statement_terminator": ";",
                "comment_prefix": "//"
            },
            formatting_config={
                "indent_size": 4,
                "indent_char": " ",
                "line_ending": "\n",
                "extra_indent_for_inside": 4
            },
            rules={
                "skip_docstrings": False,
                "skip_comments": True,
                "handle_async": False,
                "handle_decorators": False,
                "handle_generators": False,
                "special_exit_functions": []
            },
            analysis_patterns={
                "method_def": r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:,\s*\w+)*)?\s*\{?\s*$',
                "class_def": r'^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*class\s+(\w+)',
                "interface_def": r'^\s*(?:(?:public|private|protected)\s+)*interface\s+(\w+)',
                "for_loop": r'^\s*for\s*\(',
                "while_loop": r'^\s*while\s*\(',
                "lambda_expr": r'\([^)]*\)\s*->',
                "stream_op": r'\.(stream|map|filter|reduce|collect|forEach|parallel)\s*\('
            },
            detection_patterns={
                "package_declaration": ["package ", "import "],
                "syntax_keywords": ["public class", "private ", "public static void main"],
                "regex": r'^\s*(package\s+\w+|import\s+\w+|public\s+class\s+\w+)'
            },
            processing_limits={
                "max_captures_per_query": 10000,
                "max_lines_for_processing": 50000,
                "max_function_name_length": 100,
                "max_identifier_length": 50,
                "max_safety_counter": 10,
                "max_search_window": 50,
                "max_body_text_check": 200,
                "max_function_body_search_lines": 10
            },
            node_types={
                "function_types": ["method_declaration", "constructor_declaration"],
                "body_types": ["block"],
                "loop_types": ["for_statement", "while_statement", "do_statement", "enhanced_for_statement"],
                "class_types": ["class_declaration", "interface_declaration", "enum_declaration"],
                "comment_types": ["comment"],
                "return_types": ["return_statement"]
            }
        )
    
    def _get_default_javascript_config(self) -> LanguageConfig:
        """Default JavaScript configuration."""
        return LanguageConfig(
            name="javascript",
            extensions=[".js", ".jsx", ".mjs", ".ts", ".tsx"],
            tree_sitter_name="javascript",
            ast_config={
                "body_field": "body",
                "block_type": "statement_block",
                "function_types": ["function_declaration", "arrow_function", "function_expression"],
                "class_types": ["class_declaration"],
                "loop_types": ["for_statement", "while_statement", "for_in_statement", "for_of_statement"],
                "return_types": ["return_statement"],
                "comment_types": ["comment"],
                "docstring_types": [],
                "insertion_rules": {
                    "function_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "function_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "class_enter": {
                        "mode": "inside_start",
                        "find_first_statement": True,
                        "skip_docstrings": False,
                        "skip_comments": True
                    },
                    "class_exit": {
                        "mode": "inside_end",
                        "find_last_statement": True
                    },
                    "before": {
                        "mode": "before"
                    },
                    "after": {
                        "mode": "after"
                    }
                }
            },
            query_config={
                "capture_mapping": {
                    "function.definition": "function_enter",
                    "function.name": "function_enter",
                    "class.definition": "class_enter",
                    "class.name": "class_enter",
                    "return.statement": "function_exit",
                    "loop.for": "loop_start",
                    "loop.while": "loop_start",
                    "loop.for_in": "loop_start",
                    "loop.for_of": "loop_start"
                },
                "priority_order": [
                    "function.definition",
                    "class.definition",
                    "return.statement",
                    "loop.for",
                    "loop.while",
                    "loop.for_in",
                    "loop.for_of"
                ]
            },
            instrumentation_config={
                "import_statement": "import { CodeGreen } from 'codegreen-runtime';",
                "templates": {
                    "function_enter": "CodeGreen.checkpoint('{checkpoint_id}', '{name}', 'enter');",
                    "function_exit": "CodeGreen.checkpoint('{checkpoint_id}', '{name}', 'exit');",
                    "class_enter": "CodeGreen.checkpoint('{checkpoint_id}', '{name}', 'class_enter');",
                    "loop_start": "CodeGreen.checkpoint('{checkpoint_id}', '{name}', 'loop_start');",
                    "loop_exit": "CodeGreen.checkpoint('{checkpoint_id}', '{name}', 'loop_exit');"
                },
                "statement_terminator": ";",
                "comment_prefix": "//"
            },
            formatting_config={
                "indent_size": 2,
                "indent_char": " ",
                "line_ending": "\n",
                "extra_indent_for_inside": 2
            },
            rules={
                "skip_docstrings": False,
                "skip_comments": True,
                "handle_async": True,
                "handle_decorators": False,
                "handle_generators": True
            },
            analysis_patterns={
                "function_def": r'^\s*(?:async\s+)?(?:function\s+(\w+)|(\w+)\s*[:=]\s*(?:async\s+)?(?:function|=>))',
                "class_def": r'^\s*class\s+(\w+)',
                "arrow_function": r'^\s*(\w+)\s*=>',
                "for_loop": r'^\s*for\s*\(',
                "while_loop": r'^\s*while\s*\(',
                "for_in_loop": r'^\s*for\s*\(\s*\w+\s+in\s+',
                "for_of_loop": r'^\s*for\s*\(\s*\w+\s+of\s+',
                "async_function": r'^\s*async\s+function',
                "promise_chain": r'\.then\s*\(',
                "async_await": r'await\s+'
            },
            detection_patterns={
                "import_keywords": ["import ", "export ", "require("],
                "syntax_keywords": ["function ", "const ", "let ", "var ", "class "],
                "regex": r'^\s*(import\s+|export\s+|function\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+)'
            },
            processing_limits={
                "max_captures_per_query": 10000,
                "max_lines_for_processing": 50000,
                "max_function_name_length": 100,
                "max_identifier_length": 50,
                "max_safety_counter": 10,
                "max_search_window": 50,
                "max_body_text_check": 200,
                "max_function_body_search_lines": 10
            },
            node_types={
                "function_types": ["function_declaration", "arrow_function", "function_expression"],
                "body_types": ["statement_block"],
                "loop_types": ["for_statement", "while_statement", "for_in_statement", "for_of_statement"],
                "class_types": ["class_declaration"],
                "comment_types": ["comment"],
                "return_types": ["return_statement"]
            }
        )

# Global instance
_config_manager = None

def get_language_config_manager() -> LanguageConfigManager:
    """Get the global language configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = LanguageConfigManager()
    return _config_manager
