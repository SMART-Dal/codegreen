"""
Comprehensive AST processor for CodeGreen.

This module consolidates all AST processing operations including:
- Language-agnostic AST node processing
- Professional indentation using nvim-treesitter queries
- AST-based code rewriting and editing
- Tree-sitter query execution and capture processing

This replaces the need for separate treesitter_indent.py and AST operations
scattered throughout language_engine.py.
"""

import logging
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, NamedTuple
from dataclasses import dataclass
from tree_sitter import Language, Parser, Tree, Node, Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

from language_configs import get_language_config_manager, LanguageConfig

logger = logging.getLogger(__name__)

@dataclass
class IndentationInfo:
    """Information about indentation at a specific position."""
    indent_level: int  # Number of indentation units
    indent_char: str   # ' ' or '\t'
    indent_size: int   # Size of one indentation unit (e.g., 4 for 4 spaces)
    indent_string: str # Final indentation string to use

@dataclass
class ASTEdit:
    """Represents an AST-based edit operation"""
    byte_offset: int
    insertion_text: str
    edit_type: str  # 'insert_before', 'insert_after', 'insert_inside_start', 'insert_inside_end'
    node_info: Optional[str] = None  # Debug info about the node

class ASTProcessor:
    """Language-agnostic AST processor using configuration-driven approach."""
    
    def __init__(self, language: str, source_code: str = "", tree: Optional[Tree] = None):
        self.language = language
        self.source_code = source_code
        self.tree = tree  # Tree-sitter AST tree for advanced indentation
        self.config_manager = get_language_config_manager()
        self.config = self.config_manager.get_config(language)
        self.indent_engine = get_indentation_engine()  # TreeSitter indentation engine
        
        if not self.config:
            logger.warning(f"⚠️  FALLBACK: No configuration found for language: {language}, using default behavior")
            raise ValueError(f"No configuration found for language: {language}")
    
    def find_body_node(self, node: Node) -> Optional[Node]:
        """Find the body/block node for a given node using language configuration."""
        ast_config = self.config.ast_config
        
        # If this is an identifier (function name, class name, etc.), look for parent definition
        if node.type in ["identifier", "type_identifier", "field_identifier"]:
            current = node.parent
            while current:
                if current.type in ["function_definition", "method_definition", "class_definition", "constructor_definition"]:
                    # Found the parent function/method/class, now find its body
                    return self._find_body_in_node(current, ast_config)
                current = current.parent
        
        # For other node types, try to find body directly
        return self._find_body_in_node(node, ast_config)
    
    def _find_body_in_node(self, node: Node, ast_config: Dict[str, Any]) -> Optional[Node]:
        """Helper method to find body within a specific node."""
        # First, try field name
        body_field = ast_config.get("body_field", "body")
        body = node.child_by_field_name(body_field)
        if body:
            return body
        
        # Fallback: Search named children for block type
        block_type = ast_config.get("block_type", "block")
        for child in node.named_children:
            if child.type == block_type:
                return child
        
        return None
    
    def find_insertion_point(self, node: Node, insertion_mode: str) -> Optional[int]:
        """Find the insertion point for a node using language configuration."""
        logger.debug(f"🔍 Finding insertion point for node {node.type} with mode '{insertion_mode}'")
        logger.debug(f"   Node position: {node.start_point}-{node.end_point}")
        logger.debug(f"   Node bytes: {node.start_byte}-{node.end_byte}")
        
        ast_config = self.config.ast_config
        insertion_rules = ast_config.get("insertion_rules", {})
        logger.debug(f"   Available insertion rules: {list(insertion_rules.keys())}")
        
        # Map insertion modes to rule keys based on node type
        if node.type in ['class_definition', 'class_declaration']:
            # For class definitions, use different mapping
            mode_mapping = {
                'inside_start': 'class_enter',
                'inside_end': 'class_exit',
                'before': 'before',
                'after': 'after'
            }
        else:
            # For function definitions and other nodes
            mode_mapping = {
                'inside_start': 'function_enter',
                'inside_end': 'function_exit',
                'before': 'before',
                'after': 'after'
            }
        
        rule_key = mode_mapping.get(insertion_mode, insertion_mode)
        logger.debug(f"   Mapped mode '{insertion_mode}' to rule key '{rule_key}' for node type '{node.type}'")
        
        if rule_key not in insertion_rules:
            # Default behavior with enhanced logging
            logger.warning(f"⚠️  FALLBACK: No insertion rule found for '{rule_key}', using default behavior")
            logger.warning(f"   Available rules: {list(insertion_rules.keys())}")
            logger.warning(f"   This indicates missing configuration for insertion mode '{insertion_mode}'")
            
            if insertion_mode == 'before':
                fallback_byte = node.start_byte
                logger.debug(f"   Using fallback 'before' position: {fallback_byte}")
                return fallback_byte
            elif insertion_mode == 'after':
                fallback_byte = node.end_byte
                logger.debug(f"   Using fallback 'after' position: {fallback_byte}")
                return fallback_byte
            else:
                fallback_byte = node.start_byte
                logger.debug(f"   Using fallback default position: {fallback_byte}")
                return fallback_byte
        
        rule = insertion_rules[rule_key]
        logger.debug(f"   Using rule: {rule}")
        
        if rule.get("mode") == "inside_start":
            logger.debug(f"   Processing inside_start mode")
            body_node = self.find_body_node(node)
            if not body_node:
                logger.debug(f"   No body node found, using node start: {node.start_byte}")
                return node.start_byte
            
            if rule.get("find_first_statement", False):
                insertion_byte = self._find_first_statement_line_start(body_node, rule)
                logger.debug(f"   Found first statement position: {insertion_byte}")
                return insertion_byte
            else:
                # For inside_start, we want to insert at the beginning of the body content
                # Skip the opening brace if it's on the same line
                body_start = body_node.start_byte
                body_text = self.source_code[body_start:body_start + 100]  # First 100 chars
                
                # Find the opening brace
                brace_pos = body_text.find('{')
                if brace_pos != -1:
                    # Insert after the opening brace and any whitespace
                    insertion_pos = body_start + brace_pos + 1
                    # Skip whitespace after the brace
                    while insertion_pos < len(self.source_code) and self.source_code[insertion_pos] in ' \t':
                        insertion_pos += 1
                    # Skip newline if present
                    if insertion_pos < len(self.source_code) and self.source_code[insertion_pos] == '\n':
                        insertion_pos += 1
                    logger.debug(f"   Using body start after brace: {insertion_pos}")
                    return insertion_pos
                else:
                    logger.debug(f"   Using body start: {body_node.start_byte}")
                    return body_node.start_byte
        
        elif rule.get("mode") == "inside_end":
            logger.debug(f"   Processing inside_end mode")
            body_node = self.find_body_node(node)
            if not body_node:
                logger.debug(f"   No body node found, using node end: {node.end_byte}")
                return node.end_byte
            
            if rule.get("find_last_statement", False):
                insertion_byte = self._find_last_statement_line_end(body_node, rule)
                # Ensure we don't cross the block's closing dedent/brace
                bounded = min(insertion_byte, body_node.end_byte)
                logger.debug(f"   Found last statement position (bounded): {bounded}")
                return bounded
            else:
                logger.debug(f"   Using body end: {body_node.end_byte}")
                return body_node.end_byte
                
        elif rule.get("mode") == "before":
            logger.debug(f"   Processing before mode - inserting before node")
            # For 'before' mode, we want to insert at the beginning of the line containing the node
            # not at the node itself
            line_start = self.source_code.rfind('\n', 0, node.start_byte) + 1
            insertion_byte = line_start
            logger.debug(f"   Before insertion position: {insertion_byte} (line start, not node start)")
            return insertion_byte
            
        elif rule.get("mode") == "after":
            logger.debug(f"   Processing after mode - inserting after node")
            insertion_byte = node.end_byte
            logger.debug(f"   After insertion position: {insertion_byte}")
            return insertion_byte
        
        # Default fallback
        logger.warning(f"⚠️  FALLBACK: Unknown rule mode '{rule.get('mode')}' for insertion mode '{insertion_mode}'")
        if insertion_mode == 'before':
            fallback_byte = node.start_byte
            logger.debug(f"   Using default before position: {fallback_byte}")
            return fallback_byte
        elif insertion_mode == 'after':
            fallback_byte = node.end_byte
            logger.debug(f"   Using default after position: {fallback_byte}")
            return fallback_byte
        else:
            fallback_byte = node.start_byte
            logger.debug(f"   Using default position: {fallback_byte}")
            return fallback_byte
    
    def _find_first_statement(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the first statement in a body node."""
        skip_docstrings = rule.get("skip_docstrings", False)
        skip_comments = rule.get("skip_comments", False)
        
        for child in body_node.children:
            child_text = self._get_node_text(child)
            
            # Skip docstrings if configured
            if skip_docstrings and self._is_docstring(child, child_text):
                continue
            
            # Skip comments if configured
            if skip_comments and self._is_comment(child):
                continue
            
            # Found first real statement
            return child.start_byte
        
        # Fallback to body start
        return body_node.start_byte
    
    def _find_first_statement_line_start(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the start of the line containing the first statement in a body node."""
        skip_docstrings = rule.get("skip_docstrings", False)
        skip_comments = rule.get("skip_comments", False)
        
        for child in body_node.children:
            child_text = self._get_node_text(child)
            
            # Skip docstrings if configured
            if skip_docstrings and self._is_docstring(child, child_text):
                continue
            
            # Skip comments if configured
            if skip_comments and self._is_comment(child):
                continue
            
            # Found first real statement - return start of its line for 'inside_start' insertion
            line_start = self.source_code.rfind('\n', 0, child.start_byte) + 1
            return line_start
        
        # Fallback to body start
        return body_node.start_byte
    
    def _find_last_statement_line_end(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the end of the line containing the last statement in a body node."""
        skip_docstrings = rule.get("skip_docstrings", False)
        skip_comments = rule.get("skip_comments", False)
        
        # Search from the end
        for child in reversed(body_node.children):
            child_text = self._get_node_text(child)
            
            # Skip docstrings if configured
            if skip_docstrings and self._is_docstring(child, child_text):
                continue
            
            # Skip comments if configured
            if skip_comments and self._is_comment(child):
                continue
            
            # Found last real statement - return end of its line
            line_end = self.source_code.find('\n', child.end_byte)
            if line_end == -1:
                line_end = len(self.source_code)
            # Bound insertion to within the body range
            return min(line_end, body_node.end_byte)
        
        # Fallback to body end
        return body_node.end_byte
    
    def _find_last_statement(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the last statement in a body node."""
        skip_docstrings = rule.get("skip_docstrings", False)
        skip_comments = rule.get("skip_comments", False)
        
        # Search from the end
        for child in reversed(body_node.children):
            child_text = self._get_node_text(child)
            
            # Skip docstrings if configured
            if skip_docstrings and self._is_docstring(child, child_text):
                continue
            
            # Skip comments if configured
            if skip_comments and self._is_comment(child):
                continue
            
            # Found last real statement
            return child.end_byte
        
        # Fallback to body end
        return body_node.end_byte
    
    def _is_docstring(self, node: Node, text: str) -> bool:
        """Check if a node is a docstring."""
        if not text:
            return False
        
        text = text.strip()
        return (text.startswith('"""') and text.endswith('"""')) or \
               (text.startswith("'''") and text.endswith("'''"))
    
    def _is_comment(self, node: Node) -> bool:
        """Check if a node is a comment."""
        ast_config = self.config.ast_config
        comment_types = ast_config.get("comment_types", ["comment"])
        return node.type in comment_types
    
    def _get_node_text(self, node: Node) -> str:
        """Get text content from a node."""
        if not self.source_code:
            return ""
        return self.source_code[node.start_byte:node.end_byte]
    
    def get_capture_mapping(self) -> Dict[str, str]:
        """Get capture mapping for this language."""
        query_config = self.config.query_config
        return query_config.get("capture_mapping", {})
    
    def get_priority_order(self) -> List[str]:
        """Get priority order for captures."""
        query_config = self.config.query_config
        return query_config.get("priority_order", [])
    
    def get_instrumentation_template(self, point_type: str) -> Optional[str]:
        """Get instrumentation template for a point type."""
        instrumentation_config = self.config.instrumentation_config
        templates = instrumentation_config.get("templates", {})
        return templates.get(point_type)
    
    def get_import_statement(self) -> Optional[str]:
        """Get import statement for this language."""
        instrumentation_config = self.config.instrumentation_config
        return instrumentation_config.get("import_statement")
    
    def get_formatting_config(self) -> Dict[str, Any]:
        """Get formatting configuration for this language."""
        return self.config.formatting_config
    
    def get_rules(self) -> Dict[str, Any]:
        """Get language-specific rules."""
        return self.config.rules
    
    def should_skip_node(self, node: Node, text: str) -> bool:
        """Check if a node should be skipped based on language rules."""
        rules = self.get_rules()
        
        # Skip docstrings if configured
        if rules.get("skip_docstrings", False) and self._is_docstring(node, text):
            return True
        
        # Skip comments if configured
        if rules.get("skip_comments", False) and self._is_comment(node):
            return True
        
        return False
    
    def calculate_indentation_for_insertion(self, body_node: Node, insertion_offset: int) -> Tuple[int, str]:
        """
        Calculate proper indentation for insertion using TreeSitter indentation engine.
        
        This replaces the hardcoded indentation logic with professional-grade
        indentation calculation using nvim-treesitter indentation queries.
        
        Returns:
            Tuple of (total_indent, indent_string)
        """
        if not self.source_code:
            return 0, ""
        
        # Use TreeSitter indentation engine if available
        if self.tree and self.indent_engine:
            try:
                indent_info = self.indent_engine.calculate_indentation_at_position(
                    self.tree, self.source_code, insertion_offset, self.language
                )
                logger.debug(f"🔧 TreeSitter indentation: level={indent_info.indent_level}, "
                           f"string='{indent_info.indent_string}' (len={len(indent_info.indent_string)})")
                return indent_info.indent_level, indent_info.indent_string
            except Exception as e:
                logger.warning(f"⚠️  TreeSitter indentation failed, falling back to legacy method: {e}")
        
        # Fallback to legacy line-based indentation
        logger.debug("🔧 Using fallback line-based indentation")
        return self._legacy_calculate_indentation(body_node, insertion_offset)
    
    def _legacy_calculate_indentation(self, body_node: Node, insertion_offset: int) -> Tuple[int, str]:
        """
        Legacy indentation calculation for fallback when TreeSitter engine fails.
        """
        if not body_node or not self.source_code:
            return 0, ""
        
        # Find the current line
        line_start = self.source_code.rfind('\n', 0, insertion_offset) + 1
        line_end = self.source_code.find('\n', insertion_offset)
        if line_end == -1:
            line_end = len(self.source_code)
        
        current_line = self.source_code[line_start:line_end]
        base_indent = len(current_line) - len(current_line.lstrip())
        
        # Detect indent character from context
        indent_char = self._detect_indent_character(body_node)
        
        # Convert to indent levels
        if indent_char == '\t':
            indent_level = base_indent  # Each tab is one level
        else:
            indent_level = base_indent // 4  # Assume 4-space indentation
        
        indent_string = indent_char * (indent_level * (1 if indent_char == '\t' else 4))
        
        return indent_level, indent_string
    
    def _detect_indent_character(self, body_node: Node) -> str:
        """Detect whether the code uses tabs or spaces for indentation."""
        if not body_node or not self.source_code:
            return " "
        
        # Check the first few lines of the body for indentation
        body_start = body_node.start_byte
        limits = self.config_manager.get_processing_limits(self.language)
        max_body_text_check = limits.get('max_body_text_check', 200)
        body_end = min(body_node.start_byte + max_body_text_check, body_node.end_byte)  # Check first N chars
        body_text = self.source_code[body_start:body_end]
        
        lines = body_text.split('\n')
        for line in lines:
            if line.strip():  # Non-empty line
                if line.startswith('\t'):
                    return '\t'
                elif line.startswith(' '):
                    return ' '
        
        # Default to spaces
        return " "


class TreeSitterIndentationEngine:
    """
    Professional indentation engine using nvim-treesitter queries.
    
    This engine provides language-agnostic indentation by leveraging the
    comprehensive indentation rules maintained by the nvim-treesitter community.
    """
    
    def __init__(self, nvim_treesitter_path: Optional[str] = None):
        """
        Initialize the indentation engine.
        
        Args:
            nvim_treesitter_path: Path to nvim-treesitter directory. If None, will auto-detect.
        """
        self.nvim_treesitter_path = nvim_treesitter_path or self._find_nvim_treesitter_path()
        self.language_parsers: Dict[str, Parser] = {}
        self.indentation_queries: Dict[str, Query] = {}
        self.indent_cache: Dict[str, IndentationInfo] = {}
        
        # Common indentation patterns
        self.default_indent_size = 4
        self.supported_languages = {'python', 'c', 'cpp', 'java', 'javascript'}
        
        logger.info(f"🔧 TreeSitterIndentationEngine initialized with nvim-treesitter at: {self.nvim_treesitter_path}")
    
    def _find_nvim_treesitter_path(self) -> Optional[str]:
        """Auto-detect nvim-treesitter path."""
        potential_paths = [
            "third_party/nvim-treesitter",
            "../third_party/nvim-treesitter",
            "../../third_party/nvim-treesitter"
        ]
        
        for path_str in potential_paths:
            path = Path(path_str)
            if path.exists() and (path / "queries").exists():
                logger.debug(f"🔍 Found nvim-treesitter at: {path.absolute()}")
                return str(path.absolute())
        
        logger.warning("⚠️  Could not auto-detect nvim-treesitter path")
        return None
    
    def get_parser(self, language: str) -> Optional[Parser]:
        """Get or create a parser for the specified language."""
        if language not in self.language_parsers:
            try:
                parser = get_parser(language)
                self.language_parsers[language] = parser
                logger.debug(f"✅ Created parser for {language}")
            except Exception as e:
                logger.warning(f"❌ Failed to create parser for {language}: {e}")
                return None
        
        return self.language_parsers.get(language)
    
    def load_indentation_queries(self, language: str) -> Optional[Query]:
        """Load indentation queries for a language from nvim-treesitter."""
        if language in self.indentation_queries:
            return self.indentation_queries[language]
        
        if not self.nvim_treesitter_path:
            logger.warning(f"⚠️  No nvim-treesitter path available for loading {language} indentation queries")
            return None
        
        query_file = Path(self.nvim_treesitter_path) / "queries" / language / "indents.scm"
        
        if not query_file.exists():
            logger.warning(f"⚠️  No indentation queries found for {language} at {query_file}")
            return None
        
        try:
            # Read the query file
            query_content = query_file.read_text(encoding='utf-8')
            
            # Handle inheritance (e.g., "javascript" inherits from "ecma")
            if query_content.strip().startswith("; inherits:"):
                inherit_line = query_content.split('\n')[0]
                inherited_languages = inherit_line.replace("; inherits:", "").strip().split(',')
                
                # Load inherited queries first
                combined_content = []
                for inherited_lang in inherited_languages:
                    inherited_lang = inherited_lang.strip()
                    inherited_file = Path(self.nvim_treesitter_path) / "queries" / inherited_lang / "indents.scm"
                    if inherited_file.exists():
                        inherited_content = inherited_file.read_text(encoding='utf-8')
                        combined_content.append(f";; Inherited from {inherited_lang}\n{inherited_content}")
                        logger.debug(f"📖 Loaded inherited indentation from {inherited_lang} for {language}")
                
                # Add the current language's content (excluding the inherit line)
                current_content = '\n'.join(query_content.split('\n')[1:]).strip()
                if current_content:
                    combined_content.append(f";; From {language}\n{current_content}")
                
                query_content = '\n\n'.join(combined_content)
            
            # Create the query
            language_obj = get_language(language)
            query = Query(language_obj, query_content)
            
            self.indentation_queries[language] = query
            logger.info(f"✅ Loaded indentation queries for {language} ({query.capture_count} captures)")
            
            return query
            
        except Exception as e:
            logger.error(f"❌ Failed to load indentation queries for {language}: {e}")
            return None
    
    def detect_indent_style(self, source_code: str) -> Tuple[str, int]:
        """
        Detect indentation style (tabs vs spaces) and size from source code.
        
        Returns:
            Tuple of (indent_char, indent_size)
        """
        lines = source_code.split('\n')
        indent_chars = []
        indent_sizes = []
        
        for line in lines:
            if not line.strip():  # Skip empty lines
                continue
                
            # Count leading whitespace
            indent_match = ""
            for char in line:
                if char in [' ', '\t']:
                    indent_match += char
                else:
                    break
            
            if indent_match:
                if '\t' in indent_match:
                    indent_chars.append('\t')
                    indent_sizes.append(1)  # Tab is always size 1
                elif ' ' in indent_match:
                    indent_chars.append(' ')
                    indent_sizes.append(len(indent_match))
        
        # Determine most common indent character
        if not indent_chars:
            return ' ', self.default_indent_size
        
        tab_count = indent_chars.count('\t')
        space_count = indent_chars.count(' ')
        
        if tab_count > space_count:
            indent_char = '\t'
            indent_size = 1
        else:
            indent_char = ' '
            # Determine most common indent size for spaces
            if indent_sizes:
                # Find the most common non-zero indent size
                valid_sizes = [s for s in indent_sizes if s > 0]
                if valid_sizes:
                    indent_size = max(set(valid_sizes), key=valid_sizes.count)
                else:
                    indent_size = self.default_indent_size
            else:
                indent_size = self.default_indent_size
        
        logger.debug(f"🔧 Detected indent style: '{indent_char}' (size: {indent_size})")
        return indent_char, indent_size
    
    def calculate_indentation_at_position(self, tree: Tree, source_code: str, byte_offset: int, language: str) -> IndentationInfo:
        """
        Calculate proper indentation at a specific byte position using tree-sitter indentation queries.
        
        Args:
            tree: Parsed tree-sitter tree
            source_code: Original source code
            byte_offset: Byte position where we want to insert
            language: Programming language
            
        Returns:
            IndentationInfo with calculated indentation
        """
        # Detect base indentation style
        indent_char, indent_size = self.detect_indent_style(source_code)
        
        # Load indentation queries for the language
        query = self.load_indentation_queries(language)
        
        if not query:
            # Fallback to line-based indentation
            return self._fallback_line_based_indentation(source_code, byte_offset, indent_char, indent_size)
        
        # Find the node at the insertion position
        root_node = tree.root_node
        target_node = root_node.descendant_for_byte_range(byte_offset, byte_offset + 1)
        
        if not target_node:
            return IndentationInfo(0, indent_char, indent_size, "")
        
        # Calculate indentation based on tree-sitter queries
        indent_level = self._calculate_indent_level_from_queries(
            query, root_node, target_node, byte_offset, source_code
        )
        
        # Generate indent string
        if indent_char == '\t':
            indent_string = '\t' * indent_level
        else:
            indent_string = ' ' * (indent_level * indent_size)
        
        return IndentationInfo(indent_level, indent_char, indent_size, indent_string)
    
    def _calculate_indent_level_from_queries(self, query: Query, root_node: Node, 
                                           target_node: Node, byte_offset: int, source_code: str) -> int:
        """
        Calculate indentation level using tree-sitter indentation queries.
        
        This is a simplified implementation. The full nvim-treesitter indentation
        engine is much more sophisticated, but this provides the core functionality.
        """
        # Find the line we're inserting on
        line_start = source_code.rfind('\n', 0, byte_offset) + 1
        current_line = source_code[line_start:source_code.find('\n', byte_offset)] if source_code.find('\n', byte_offset) != -1 else source_code[line_start:]
        base_indent = len(current_line) - len(current_line.lstrip())
        
        # Convert to indent levels
        indent_char, indent_size = self.detect_indent_style(source_code)
        if indent_char == '\t':
            base_level = base_indent  # Each tab is one level
        else:
            base_level = base_indent // indent_size  # Convert spaces to levels
        
        # Execute indentation queries to find modifiers
        cursor = QueryCursor(query)
        captures = cursor.captures(root_node)
        indent_modifiers = 0
        
        # Process captures to find indentation-affecting nodes
        # Track which nodes we've already processed to avoid double-counting
        processed_nodes = set()
        
        # Walk up the AST to find indentation-affecting nodes
        current_node = target_node
        while current_node:
            # Check all capture types
            for capture_name, node_list in captures.items():
                for node in node_list:
                    # Only count each node once, and only if it contains our target
                    if (node.id not in processed_nodes and 
                        (node == current_node or (node.start_byte <= current_node.start_byte <= node.end_byte))):
                        
                        processed_nodes.add(node.id)
                        
                        if capture_name == "indent.begin":
                            indent_modifiers += 1
                            logger.debug(f"🔧 Found @indent.begin at {node.type} (id={node.id}): +1 level")
                        elif capture_name == "indent.dedent":
                            indent_modifiers -= 1
                            logger.debug(f"🔧 Found @indent.dedent at {node.type} (id={node.id}): -1 level")
            
            current_node = current_node.parent
        
        final_level = max(0, base_level + indent_modifiers)
        logger.debug(f"🔧 Calculated indent: base={base_level} + modifiers={indent_modifiers} = {final_level}")
        
        return final_level
    
    def _fallback_line_based_indentation(self, source_code: str, byte_offset: int, 
                                       indent_char: str, indent_size: int) -> IndentationInfo:
        """Fallback indentation calculation when queries are not available."""
        logger.debug("🔧 Using fallback line-based indentation")
        
        # Find the current line
        line_start = source_code.rfind('\n', 0, byte_offset) + 1
        line_end = source_code.find('\n', byte_offset)
        if line_end == -1:
            line_end = len(source_code)
        
        current_line = source_code[line_start:line_end]
        base_indent = len(current_line) - len(current_line.lstrip())
        
        # Convert to indent levels
        if indent_char == '\t':
            indent_level = base_indent
        else:
            indent_level = base_indent // indent_size
        
        indent_string = indent_char * (indent_level * (1 if indent_char == '\t' else indent_size))
        
        return IndentationInfo(indent_level, indent_char, indent_size, indent_string)


class ASTRewriter:
    """
    Improved AST-based code rewriter using tree-sitter's incremental parsing for syntactically correct instrumentation.
    
    Improvements:
    - Node-based offset calculation: Traverses AST to find body/block nodes accurately
    - Dynamic indentation: Derived from actual body child's start column
    - No hardcoded search windows or string finds—uses tree structure
    - Post-edit validation: Checks if new_tree.has_error to detect syntax breaks
    - Language config: For body_field (e.g., 'body', 'block'), extra_indent
    - Better insert handling: No forced leading '\n'; checks context
    """
    
    def __init__(self, source_code: str, language: str, parser: Optional[Parser] = None, tree: Optional[Tree] = None):
        self.source_code = source_code
        self.language = language
        self.parser = parser
        self.tree = tree
        self.edits: List[ASTEdit] = []
        self.current_code = source_code  # Track code changes for incremental updates
        self.indent_engine = get_indentation_engine()  # TreeSitter indentation engine
        
        # Use configuration-driven approach with TreeSitter indentation engine
        self.ast_processor = ASTProcessor(language, source_code, tree)
        self.config_manager = get_language_config_manager()
        self.lang_config = self.config_manager.get_config(language)
        if not self.lang_config:
            raise ValueError(f"No configuration found for language: {language}")
        
    def add_instrumentation(self, point, instrumentation_code: str) -> bool:
        """
        Add instrumentation using node-based offsets or byte-based fallback.
        Supports both AST-based insertion (with 'node' attribute) and byte-based insertion.
        """
        try:
            logger.debug(f"🔧 Adding instrumentation for point '{point.id}'")
            logger.debug(f"   Point type: {point.type}, mode: {point.insertion_mode}")
            logger.debug(f"   Has node: {hasattr(point, 'node') and point.node is not None}")
            logger.debug(f"   Has byte_offset: {hasattr(point, 'byte_offset') and point.byte_offset is not None}")
            
            # Check if this point has a node for AST-based insertion
            if hasattr(point, 'node') and point.node:
                logger.debug(f"   Using AST-based insertion for point '{point.id}' with node")
                byte_offset = self._calculate_insertion_offset(point)
                if byte_offset is None:
                    logger.warning(f"⚠️  Failed to calculate AST-based offset for point '{point.id}'")
                    return False
                logger.debug(f"   Calculated byte offset: {byte_offset}")
            else:
                # Fallback to byte-based insertion for points without nodes (like imports)
                logger.debug(f"   Using byte-based insertion for point '{point.id}' (no node attribute)")
                if hasattr(point, 'byte_offset') and point.byte_offset is not None:
                    byte_offset = point.byte_offset
                    logger.debug(f"   Using provided byte offset: {byte_offset}")
                else:
                    logger.error(f"❌ Point '{point.id}' has no node and no byte_offset - cannot insert")
                    return False
                
            edit_type = f"insert_{point.insertion_mode}"
            logger.debug(f"   Edit type: {edit_type}")
            
            edit = ASTEdit(
                byte_offset=byte_offset,
                insertion_text=instrumentation_code,
                edit_type=edit_type,
                node_info=f"{point.type}:{point.name}"
            )
            
            self.edits.append(edit)
            logger.debug(f"   ✅ Successfully added edit to queue (total edits: {len(self.edits)})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add instrumentation for {point.id}: {e}")
            import traceback
            logger.debug(f"   Error traceback: {traceback.format_exc()}")
            return False
    
    def _calculate_insertion_offset(self, point) -> Optional[int]:
        """Configuration-driven offset calculation using AST processor."""
        node: Node = point.node  # Assume added to dataclass
        
        if point.byte_offset is not None:
            return point.byte_offset
            
        # Use the AST processor to find insertion point
        insertion_offset = self.ast_processor.find_insertion_point(node, point.insertion_mode)
        
        if insertion_offset is not None:
            return insertion_offset
        
        # Fallback to line/column conversion
        return self._line_column_to_byte_offset(point.line, point.column)
    
    def _find_body_node(self, node: Node) -> Optional[Node]:
        """Use AST processor to find body/block node."""
        return self.ast_processor.find_body_node(node)
    
    def _line_column_to_byte_offset(self, line: int, column: int) -> int:
        """Convert line/column position to byte offset (fallback method)"""
        lines = self.source_code.split('\n')
        if line <= 0 or line > len(lines):
            return 0
            
        # Convert to 0-based indexing
        line_idx = line - 1
        
        # Calculate byte offset
        byte_offset = 0
        for i in range(line_idx):
            byte_offset += len(lines[i]) + 1  # +1 for newline
        
        # Add column offset (clamped to line length)
        line_text = lines[line_idx] if line_idx < len(lines) else ""
        column_offset = min(column, len(line_text))
        byte_offset += column_offset
        
        return min(byte_offset, len(self.source_code))
    
    def apply_edits(self) -> str:
        """Apply edits with validation and verbose diagnostics."""
        if not self.edits:
            logger.debug("🔧 No edits to apply")
            return self.source_code
        
        if not self.parser or not self.tree:
            logger.warning("⚠️  FALLBACK: No parser/tree available, using string-based editing instead of AST-based editing")
            return self._apply_edits_string_based()
        
        logger.info(f"🔧 Applying {len(self.edits)} edits using AST-based approach")
        
        # Try AST-based approach first, but fall back to string-based if it fails
        try:
            return self._apply_edits_ast_based()
        except Exception as e:
            logger.warning(f"⚠️  FALLBACK: AST-based editing failed: {e}, using string-based editing instead")
            return self._apply_edits_string_based()
    
    def _apply_edits_ast_based(self) -> str:
        """Apply edits using AST-based approach with tree-sitter incremental parsing."""
        
        # Log all edits before processing
        for i, edit in enumerate(self.edits):
            logger.debug(f"   Edit {i+1}/{len(self.edits)}: {edit.edit_type} at offset {edit.byte_offset}")
            logger.debug(f"      Node info: {edit.node_info}")
            logger.debug(f"      Insertion text preview: {edit.insertion_text[:100]}{'...' if len(edit.insertion_text) > 100 else ''}")
        
        sorted_edits = sorted(self.edits, key=lambda e: e.byte_offset, reverse=True)
        result_code = self.current_code
        current_tree = self.tree.copy()
        
        successful_edits = 0
        failed_edits = 0
        
        for i, edit in enumerate(sorted_edits):
            logger.debug(f"🔧 Processing edit {i+1}/{len(sorted_edits)}: {edit.edit_type} at offset {edit.byte_offset}")
            
            # Log context around the edit location
            context_start = max(0, edit.byte_offset - 50)
            context_end = min(len(result_code), edit.byte_offset + 50)
            context = result_code[context_start:context_end]
            logger.debug(f"   Context around edit: '{context}'")
            
            old_code = result_code
            try:
                result_code, current_tree = self._apply_edit_with_tree_parsing(result_code, current_tree, edit)
                
                # Validate the edit didn't break syntax
                if current_tree and current_tree.root_node.has_error:
                    logger.error(f"❌ Edit {i+1} caused syntax error: {edit.node_info}")
                    logger.error(f"   Edit type: {edit.edit_type}")
                    logger.error(f"   Byte offset: {edit.byte_offset}")
                    logger.error(f"   Insertion text: {edit.insertion_text[:200]}{'...' if len(edit.insertion_text) > 200 else ''}")
                    
                    # Log the specific error details
                    if hasattr(current_tree.root_node, 'has_error') and current_tree.root_node.has_error:
                        logger.error(f"   Tree has syntax errors after edit")
                    
                    # Revert to previous state
                    result_code = old_code
                    current_tree = self.parser.parse(old_code.encode('utf-8'))
                    failed_edits += 1
                    logger.warning(f"   ⚠️  Reverted edit {i+1} due to syntax error")
                else:
                    successful_edits += 1
                    logger.debug(f"   ✅ Edit {i+1} applied successfully")
                    
            except Exception as e:
                logger.error(f"❌ Edit {i+1} failed with exception: {e}")
                logger.error(f"   Edit type: {edit.edit_type}")
                logger.error(f"   Byte offset: {edit.byte_offset}")
                logger.error(f"   Exception type: {type(e).__name__}")
                
                # Revert to previous state
                result_code = old_code
                current_tree = self.parser.parse(old_code.encode('utf-8'))
                failed_edits += 1
                logger.warning(f"   ⚠️  Reverted edit {i+1} due to exception")
        
        logger.info(f"📊 Edit application summary: {successful_edits} successful, {failed_edits} failed")
        
        if failed_edits > 0:
            logger.warning(f"⚠️  {failed_edits} edits failed, some instrumentation may be missing")
        
        return result_code
    
    def _apply_edits_string_based(self) -> str:
        """Fallback string-based edit application when tree-sitter is unavailable"""
        # Sort edits by byte offset (descending) to avoid offset corruption
        sorted_edits = sorted(self.edits, key=lambda e: e.byte_offset, reverse=True)
        
        # Apply edits from end to beginning
        result = self.source_code
        for edit in sorted_edits:
            result = self._apply_single_edit(result, edit)
        
        return result
    
    def _apply_edit_with_tree_parsing(self, code: str, tree: Tree, edit: ASTEdit) -> Tuple[str, Tree]:
        """
        Apply a single edit using tree-sitter's proper editing workflow.
        
        Returns tuple of (updated_code, updated_tree)
        """
        try:
            # Calculate the insertion
            offset = max(0, min(edit.byte_offset, len(code)))
            new_code = self._apply_single_edit(code, edit)
            
            logger.debug(f"   _apply_edit_with_tree_parsing: offset={offset}")
            logger.debug(f"   Original code length: {len(code)}")
            logger.debug(f"   New code length: {len(new_code)}")
            logger.debug(f"   Insertion text length: {len(edit.insertion_text)}")
            
            # Calculate edit parameters for tree-sitter
            # For insertions: start_byte = old_end_byte = insertion point
            # new_end_byte = insertion point + length of inserted text
            start_byte = offset
            old_end_byte = offset  # For insertions, old and start are the same
            new_end_byte = offset + len(edit.insertion_text)  # For insertions, new_end is start + inserted length
            
            # Convert byte offsets to points (row/column)
            start_point = self._byte_to_point(code, start_byte)
            old_end_point = start_point  # For insertions
            new_end_point = self._byte_to_point(new_code, new_end_byte)  # For insertions, new_end is after insertion
            
            logger.debug(f"   Edit parameters: start_byte={start_byte}, old_end_byte={old_end_byte}, new_end_byte={new_end_byte}")
            logger.debug(f"   Edit points: start={start_point}, old_end={old_end_point}, new_end={new_end_point}")
            
            # Inform tree-sitter about the edit
            tree.edit(
                start_byte=start_byte,
                old_end_byte=old_end_byte, 
                new_end_byte=new_end_byte,
                start_point=start_point,
                old_end_point=old_end_point,
                new_end_point=new_end_point
            )
            
            # Incrementally reparse with the old tree
            new_tree = self.parser.parse(new_code.encode('utf-8'), old_tree=tree)
            
            if new_tree is None:
                logger.warning("Tree parsing failed, using original tree")
                return new_code, tree
            
            logger.debug(f"   New tree has errors: {new_tree.root_node.has_error}")
            if new_tree.root_node.has_error:
                logger.debug(f"   Tree error details: {new_tree.root_node.text.decode()[:200]}...")
                # If tree has errors, try to parse from scratch
                fresh_tree = self.parser.parse(new_code.encode('utf-8'))
                if fresh_tree and not fresh_tree.root_node.has_error:
                    logger.debug("   Fresh parse succeeded, using fresh tree")
                    return new_code, fresh_tree
                else:
                    logger.warning("   Both incremental and fresh parsing failed, using original tree")
                    return new_code, tree
                
            return new_code, new_tree
            
        except Exception as e:
            logger.warning(f"⚠️  FALLBACK: Tree-sitter edit failed: {e}, using string-based editing instead of AST-based editing")
            import traceback
            logger.debug(f"   Edit error traceback: {traceback.format_exc()}")
            return self._apply_single_edit(code, edit), tree
    
    def _byte_to_point(self, code: str, byte_offset: int) -> Tuple[int, int]:
        """Convert byte offset to (row, column) point"""
        if byte_offset >= len(code):
            byte_offset = len(code)
        
        # Count lines and calculate column
        lines = code[:byte_offset].split('\n')
        row = len(lines) - 1
        column = len(lines[-1]) if lines else 0
        
        return (row, column)
    
    def _apply_single_edit(self, code: str, edit: ASTEdit) -> str:
        """Improved: Respect modes fully with verbose diagnostics."""
        offset = max(0, min(edit.byte_offset, len(code)))
        
        logger.debug(f"🔧 Applying single edit: {edit.edit_type} at offset {offset}")
        logger.debug(f"   Original insertion text: '{edit.insertion_text}'")
        
        indented_text = self._add_proper_indentation(edit.insertion_text, code, offset, edit.edit_type)
        logger.debug(f"   Indented text: '{indented_text}'")
        
        def wrap_as_own_line(src: str, pos: int, content: str) -> str:
            # Ensure the inserted statement stands alone on its own line
            # For insert_before: insert before the current line, don't add extra newlines
            # For insert_after: insert after the current line, don't add extra newlines  
            # For insert_inside_*: insert at the position, add newline after if needed
            
            if edit.edit_type == 'insert_before':
                # Insert before the current line - add newline before content, add newline after to separate from next statement
                prepend_nl = '\n' if pos > 0 and src[pos - 1] != '\n' else ''
                append_nl = '\n'  # Always add newline after for insert_before to separate from the target statement
            elif edit.edit_type == 'insert_after':
                # Insert after the current line - add newline after content
                prepend_nl = ''
                append_nl = '\n' if pos < len(src) and src[pos] != '\n' else ''
            else:  # insert_inside_start, insert_inside_end
                # Insert at the position - add newline after content
                prepend_nl = ''
                append_nl = '\n' if pos < len(src) and src[pos] != '\n' else ''
            
            logger.debug(f"   wrap_as_own_line: pos={pos}, prepend_nl='{repr(prepend_nl)}', append_nl='{repr(append_nl)}'")
            result = src[:pos] + prepend_nl + content + append_nl + src[pos:]
            logger.debug(f"   Final wrapped result length: {len(result)} (was {len(src)})")
            return result

        if edit.edit_type == 'insert_before':
            # Insert the statement on its own line before the target line
            logger.debug(f"   Using insert_before mode")
            result = wrap_as_own_line(code, offset, indented_text)
        elif edit.edit_type == 'insert_after':
            # Insert after the node; keep it on its own line to avoid token merging
            logger.debug(f"   Using insert_after mode")
            result = wrap_as_own_line(code, offset, indented_text)
        elif edit.edit_type == 'insert_inside_start':
            # First line of the body: keep statement on its own line
            logger.debug(f"   Using insert_inside_start mode")
            result = wrap_as_own_line(code, offset, indented_text)
        elif edit.edit_type == 'insert_inside_end':
            # End of the body: ensure newline separation from dedent/next token
            logger.debug(f"   Using insert_inside_end mode")
            result = wrap_as_own_line(code, offset, indented_text)
        else:
            logger.warning(f"Unknown edit type: {edit.edit_type}")
            return code
        
        # Log the result for debugging
        logger.debug(f"   Edit result length: {len(result)} (was {len(code)})")
        if len(result) > len(code) + 100:  # Only log if significant change
            logger.debug(f"   Result preview: {result[offset:offset+100]}...")
        
        return result
    
    def _add_proper_indentation(self, text: str, code: str, offset: int, edit_type: str = None) -> str:
        """
        Professional indentation using TreeSitter indentation engine.
        
        This replaces hardcoded indentation logic with the comprehensive
        nvim-treesitter indentation system.
        """
        logger.debug(f"🔧 Calculating indentation for edit_type='{edit_type}' at offset={offset}")
        
        # Try to use TreeSitter indentation engine first
        if self.tree and self.indent_engine:
            try:
                logger.debug(f"   Using TreeSitter indentation engine for {self.language}")
                indent_info = self.indent_engine.calculate_indentation_at_position(
                    self.tree, code, offset, self.language
                )
                logger.debug(f"   TreeSitter indent_info: level={indent_info.indent_level}, char='{indent_info.indent_char}', size={indent_info.indent_size}")
                
                # Special handling for different edit types
                if edit_type == 'insert_before':
                    # For insert_before, prefer the target line's indentation, but if the
                    # target token is part of an inline suite like "if x: return y",
                    # split onto a new line and indent one level deeper than the header.
                    line_start = code.rfind('\n', 0, offset) + 1
                    line_end = code.find('\n', offset)
                    if line_end == -1:
                        line_end = len(code)
                    current_line = code[line_start:line_end]
                    base_indent = len(current_line) - len(current_line.lstrip())
                    is_inline_suite = (':' in current_line and current_line.find(':') < (offset - line_start))
                    extra = indent_info.indent_size if (indent_info.indent_char == ' ' and is_inline_suite) else (1 if (indent_info.indent_char == '\t' and is_inline_suite) else 0)
                    effective_indent = base_indent + extra
                    if indent_info.indent_char == '\t':
                        indent_string = '\t' * effective_indent
                    else:
                        indent_string = ' ' * effective_indent
                    logger.debug(f"   insert_before: current_line='{current_line}', base_indent={base_indent}, is_inline_suite={is_inline_suite}, effective_indent={effective_indent}")
                    logger.debug(f"   Final indent_string: '{indent_string}' (len={len(indent_string)})")
                
                elif edit_type == 'insert_inside_start':
                    # For insert_inside_start, use AST-based reasoning to find proper indentation
                    # This replaces hardcoded string searching with proper AST analysis
                    logger.debug(f"   Using AST-based inside_start indentation calculation")
                    indent_string = self._calculate_inside_start_indentation(indent_info, code, offset)
                elif edit_type == 'insert_inside_end':
                    # Match the last real statement's indentation within the body
                    logger.debug(f"   Using AST-based inside_end indentation calculation")
                    indent_string = self._calculate_inside_end_indentation(indent_info, code, offset)
                
                else:
                    indent_string = indent_info.indent_string
                    logger.debug(f"   Using default TreeSitter indentation: '{indent_string}' (len={len(indent_string)})")
                
                # Apply indentation to each line
                lines = text.split('\n')
                indented_lines = []
                for i, line in enumerate(lines):
                    if line.strip():  # Non-empty line
                        indented_line = indent_string + line.strip()
                        indented_lines.append(indented_line)
                        logger.debug(f"   Line {i+1}: '{line.strip()}' -> '{indented_line}'")
                    else:  # Empty line
                        indented_lines.append('')
                        logger.debug(f"   Line {i+1}: (empty line)")
                
                result = '\n'.join(indented_lines)
                logger.debug(f"   Final indented text: '{result}'")
                return result
                
            except Exception as e:
                logger.warning(f"⚠️  TreeSitter indentation failed, using legacy fallback: {e}")
                import traceback
                logger.debug(f"   TreeSitter indentation error traceback: {traceback.format_exc()}")
        
        # Fallback to simplified line-based indentation
        logger.debug("🔧 Using legacy line-based indentation fallback")
        return self._legacy_add_proper_indentation(text, code, offset, edit_type)
    
    def _calculate_inside_start_indentation(self, indent_info, code: str, offset: int) -> str:
        """
        Calculate proper indentation for insert_inside_start using AST-based reasoning.
        
        This replaces hardcoded string searching with proper AST analysis to find
        the correct indentation level for function body content.
        """
        try:
            # Use AST processor to find the function body and calculate proper indentation
            if hasattr(self, 'ast_processor') and self.ast_processor:
                # Find the function or class node containing this offset
                function_node = self._find_function_or_class_node_at_offset(offset)
                if function_node:
                    # Use AST processor to calculate proper indentation
                    body_node = self.ast_processor.find_body_node(function_node)
                    if body_node:
                        # Calculate indentation based on the first statement in the body
                        first_statement = self._find_first_real_statement(body_node)
                        if first_statement:
                            # Get the indentation of the first real statement
                            line_start = code.rfind('\n', 0, first_statement.start_byte) + 1
                            line_text = code[line_start:first_statement.start_byte]
                            base_indent = len(line_text) - len(line_text.lstrip())
                            
                            # Use the same indent character as detected
                            if indent_info.indent_char == '\t':
                                indent_string = '\t' * (base_indent // 4)  # Convert spaces to tabs
                            else:
                                indent_string = ' ' * base_indent
                            
                            logger.debug(f"🔧 AST-based inside_start: found first statement '{self._get_node_text(first_statement)[:30]}...', indentation '{indent_string}' (len={len(indent_string)})")
                            return indent_string
            
            # Fallback: Use TreeSitter indentation engine
            if self.tree and self.indent_engine:
                try:
                    indent_info_ts = self.indent_engine.calculate_indentation_at_position(
                        self.tree, code, offset, self.language
                    )
                    logger.debug(f"🔧 TreeSitter fallback inside_start: '{indent_info_ts.indent_string}' (len={len(indent_info_ts.indent_string)})")
                    return indent_info_ts.indent_string
                except Exception as e:
                    logger.warning(f"⚠️  TreeSitter indentation fallback failed: {e}")
            
            # Final fallback: Use standard indentation
            indent_string = '    ' if indent_info.indent_char == ' ' else '\t'
            logger.debug(f"🔧 Final fallback inside_start: '{indent_string}' (len={len(indent_string)})")
            return indent_string
            
        except Exception as e:
            logger.warning(f"⚠️  AST-based indentation calculation failed: {e}")
            # Fallback to standard indentation
            indent_string = '    ' if indent_info.indent_char == ' ' else '\t'
            return indent_string

    def _calculate_inside_end_indentation(self, indent_info, code: str, offset: int) -> str:
        """
        Calculate proper indentation for insert_inside_end by matching the last
        real statement's indentation inside the target body block.
        """
        try:
            if hasattr(self, 'ast_processor') and self.ast_processor and self.tree:
                # Find the enclosing function/method/class node
                function_node = self._find_function_node_at_offset(offset)
                if function_node:
                    body_node = self.ast_processor.find_body_node(function_node)
                    if body_node:
                        # Find the last real statement in the body
                        last_stmt = None
                        for child in reversed(body_node.children):
                            text = self._get_node_text(child)
                            if text.strip() and not self._is_docstring_or_comment(child, text):
                                last_stmt = child
                                break
                        # If found, match its line indentation
                        if last_stmt:
                            line_start = code.rfind('\n', 0, last_stmt.start_byte) + 1
                            line_text = code[line_start:last_stmt.start_byte]
                            base_indent = len(line_text) - len(line_text.lstrip())
                            if indent_info.indent_char == '\t':
                                # Tabs: assume one tab per logical level; count leading tabs
                                leading = 0
                                for ch in line_text:
                                    if ch == '\t':
                                        leading += 1
                                    elif ch == ' ':
                                        # spaces before tabs shouldn't normally occur; ignore
                                        continue
                                    else:
                                        break
                                indent_string = '\t' * leading
                            else:
                                indent_string = ' ' * base_indent
                            logger.debug(f"🔧 AST-based inside_end: matched indent '{indent_string}' (len={len(indent_string)})")
                            return indent_string
        except Exception as e:
            logger.warning(f"⚠️  AST-based inside_end indentation failed: {e}")
        # Fallbacks
        if indent_info.indent_char == '\t':
            return '\t'
        return ' ' * max(4, indent_info.indent_size if hasattr(indent_info, 'indent_size') else 4)
    
    def _find_function_or_class_node_at_offset(self, offset: int) -> Optional['Node']:
        """Find the function or class node containing the given byte offset."""
        if not self.tree:
            return None
        
        # Find the node at the offset
        target_node = self.tree.root_node.descendant_for_byte_range(offset, offset + 1)
        if not target_node:
            return None
        
        # Walk up the AST to find the function or class definition
        current = target_node
        while current:
            if current.type in ['function_definition', 'method_definition', 'constructor_definition', 'class_definition']:
                return current
            current = current.parent
        
        return None
    
    def _find_first_real_statement(self, body_node: 'Node') -> Optional['Node']:
        """Find the first real statement in a body node, skipping docstrings and comments."""
        if not body_node:
            return None
        
        for child in body_node.children:
            child_text = self._get_node_text(child)
            if child_text.strip():  # Non-empty child
                # Skip docstrings and comments
                if not self._is_docstring_or_comment(child, child_text):
                    return child
        
        return None
    
    def _is_docstring_or_comment(self, node: 'Node', text: str) -> bool:
        """Check if a node is a docstring or comment."""
        if not text:
            return False
        
        text = text.strip()
        
        # Check for docstrings
        if (text.startswith('"""') and text.endswith('"""')) or \
           (text.startswith("'''") and text.endswith("'''")):
            return True
        
        # Check for comments
        if node.type == 'comment' or text.startswith('#'):
            return True
        
        return False
    
    def _get_node_text(self, node: 'Node') -> str:
        """Get text content from a node."""
        if not self.source_code or not node:
            return ""
        return self.source_code[node.start_byte:node.end_byte]
    
    def _legacy_add_proper_indentation(self, text: str, code: str, offset: int, edit_type: str = None) -> str:
        """Legacy indentation fallback when TreeSitter engine is unavailable."""
        # Find the line where we're inserting
        line_start = code.rfind('\n', 0, offset) + 1
        line_end = code.find('\n', offset)
        if line_end == -1:
            line_end = len(code)
        
        current_line = code[line_start:line_end]
        current_indent = len(current_line) - len(current_line.lstrip())
        
        # For 'insert_before', match the indentation of the target line
        target_indent = current_indent
        
        # Detect indent character from context
        indent_char = ' '  # Default to spaces
        if current_line.startswith('\t'):
            indent_char = '\t'
        
        indent_str = indent_char * target_indent
        logger.debug(f"🔧 Legacy indentation: '{indent_str}' (len={len(indent_str)})")
        
        lines = text.split('\n')
        indented_lines = []
        for line in lines:
            if line.strip():  # Non-empty line
                indented_lines.append(indent_str + line.strip())
            else:  # Empty line
                indented_lines.append('')
        
        return '\n'.join(indented_lines)


# Global instance for use throughout the codebase
_global_indentation_engine: Optional[TreeSitterIndentationEngine] = None

def get_indentation_engine() -> TreeSitterIndentationEngine:
    """Get the global indentation engine instance."""
    global _global_indentation_engine
    if _global_indentation_engine is None:
        _global_indentation_engine = TreeSitterIndentationEngine()
    return _global_indentation_engine
