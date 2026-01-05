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

try:
    from .language_configs import get_language_config_manager, LanguageConfig
except ImportError:
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
    node_end_byte: Optional[int] = None # End of the node for wrapping/replacing
    node_end_byte: Optional[int] = None # End of the node for wrapping/replacing

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
    
    def _find_target_with_query(self, node: Node, rule: Dict[str, Any]) -> Optional[int]:
        """Find insertion point by executing a configured query on the node."""
        query_name = rule.get("query")
        queries = self.config.ast_config.get("insertion_queries", {})
        query_str = queries.get(query_name)

        if not query_str:
            logger.warning(f"Insertion query '{query_name}' not found in config")
            return None

        try:
            from tree_sitter import Query, QueryCursor
            from tree_sitter_language_pack import get_language
            ts_lang = get_language(self.config.tree_sitter_name)
            query = Query(ts_lang, query_str)
            cursor = QueryCursor(query)

            # Execute query on the specific node
            captures_dict = cursor.captures(node)

            # captures_dict is a dict: {capture_name: [nodes]}
            target_nodes = captures_dict.get("target", [])
            if target_nodes:
                # Filter out docstrings if we have multiple matches
                non_docstring_nodes = []
                for captured_node in target_nodes:
                    # Check if this is a docstring (expression_statement containing only a string)
                    if captured_node.type == 'expression_statement' and len(captured_node.children) > 0:
                        is_docstring = any(child.type == 'string' for child in captured_node.children)
                        if is_docstring:
                            logger.debug(f"   Skipping docstring node at {captured_node.start_byte}")
                            continue
                    non_docstring_nodes.append(captured_node)

                # Use first non-docstring node, or fallback to first node if all are docstrings
                captured_node = non_docstring_nodes[0] if non_docstring_nodes else target_nodes[0]
                placement = rule.get("placement", "before")

                logger.debug(f"   Query matched target: {captured_node.type} at {captured_node.start_byte}")

                if placement == "before":
                    # For "before" placement, return the start of the LINE, not the node
                    line_start = self.source_code.rfind('\n', 0, captured_node.start_byte) + 1
                    logger.debug(f"   Placement 'before': node at {captured_node.start_byte}, returning line start {line_start}")
                    return line_start
                elif placement == "after":
                    return captured_node.end_byte

            logger.debug(f"   Query '{query_name}' executed but @target not found")
            return None

        except Exception as e:
            logger.error(f"Error executing insertion query '{query_name}': {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def find_body_node(self, node: Node) -> Optional[Node]:
        """Find the body/block node for a given node using language configuration."""
        ast_config = self.config.ast_config
        
        # Check if the node itself is a body/block
        body_types = self.config.node_types.get("body_types", ["block"])
        if node.type in body_types or node.type in ["compound_statement", "block", "body", "class_body"]:
            logger.debug(f"   Node is already a body/block: {node.type}")
            return node
        
        # If this is an identifier (function name, class name, etc.), look for parent definition
        if node.type in ["identifier", "type_identifier", "field_identifier"]:
            logger.debug(f"🔍 Finding body for identifier node: {node.type} at {node.start_point}-{node.end_point}")
            current = node.parent
            level = 0
            # Get configurable parent search levels
            limits = self.config_manager.get_processing_limits(self.language)
            max_levels = limits.get('max_parent_search_levels', 10)
            while current and level < max_levels:  # Prevent infinite loops
                logger.debug(f"   Parent level {level}: {current.type} at {current.start_point}-{current.end_point}")
                if current.type in ["function_definition", "method_definition", "async_function_definition", "class_definition", "class_specifier", "class_declaration", "constructor_definition"]:
                    logger.debug(f"   Found parent definition: {current.type}")
                    # Found the parent function/method/class, now find its body
                    body = self._find_body_in_node(current, ast_config)
                    logger.debug(f"   Body found: {body.type if body else None}")
                    return body
                current = current.parent
                level += 1
            logger.debug(f"   No parent definition found after {level} levels")
        
        # For other node types, try to find body directly
        return self._find_body_in_node(node, ast_config)
    
    def _find_body_in_node(self, node: Node, ast_config: Dict[str, Any]) -> Optional[Node]:
        """Helper method to find body within a specific node."""
        # First, try field name
        body_field = ast_config.get("body_field", "body")
        body = node.child_by_field_name(body_field)
        if body:
            return body
        
        # Fallback: check all possible body types from config
        body_types = self.config.node_types.get("body_types", ["block"])
        for child in node.named_children:
            if child.type in body_types:
                return child
        
        # Super fallback: look for any child that looks like a block
        for child in node.named_children:
            if child.type in ["compound_statement", "block", "body", "class_body"]:
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
        if node.type in ['class_definition', 'class_declaration', 'class_specifier', 'struct_specifier']:
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
                'immediately_before': 'function_return',
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
        logger.debug(f"   Language: {self.language}")
        logger.debug(f"   Rule mode: {rule.get('mode')}")
        
        if rule.get("mode") == "query_target":
            logger.debug(f"   Processing query_target mode with query '{rule.get('query')}'")
            insertion_byte = self._find_target_with_query(node, rule)
            if insertion_byte is not None:
                logger.debug(f"   Query found target at: {insertion_byte}")
                return insertion_byte
            
            # Fallback if query fails
            fallback_mode = rule.get("fallback_mode", "inside_start")
            logger.debug(f"   Query failed, falling back to mode '{fallback_mode}'")
            # Create a temporary rule for fallback to avoid recursion
            fallback_rule = rule.copy()
            fallback_rule["mode"] = fallback_mode
            # We need to manually dispatch to the correct logic block, or recursively call but with modified rule
            # Recursion is risky if we don't change the mode.
            # Let's just fall through to the manual logic blocks by temporarily modifying local variables
            # or better, just copy the logic blocks here or refactor.
            # Refactoring to avoid huge method:
            return self._find_insertion_point_manual(node, fallback_mode, fallback_rule)

        return self._find_insertion_point_manual(node, rule.get("mode"), rule)

    def _find_insertion_point_manual(self, node: Node, mode: str, rule: Dict[str, Any]) -> Optional[int]:
        """Manual AST walking logic (fallback)."""
        if mode == "inside_start":
            logger.debug(f"   Processing inside_start mode for {node.type}")
            # Get the internal body/block node
            body_node = self.find_body_node(node)

            if not body_node:
                logger.debug(f"   No body node found for inside_start mode, using node start: {node.start_byte}")
                return node.start_byte

            if rule.get("find_first_statement", False):
                insertion_byte = self._find_first_statement_line_start(body_node, rule)
                logger.debug(f"   Found first statement position: {insertion_byte}")
                return insertion_byte
            else:
                # For inside_start, we want to insert at the beginning of the body content
                body_start = body_node.start_byte
                
                # Language-specific logic for finding the insertion point
                if self.language == 'python':
                    # For Python, find the first non-docstring statement
                    logger.debug(f"   Calling _find_python_function_start for Python")
                    insertion_byte = self._find_python_function_start(body_node, rule)
                    if insertion_byte is not None:
                        return insertion_byte
                else:
                    # For C/C++/Java, look for opening brace
                    # Get configurable text preview length
                    limits = self.config_manager.get_processing_limits(self.language)
                    text_preview_length = limits.get('debug_text_preview_length', 100)
                    body_text = self.source_code[body_start:body_start + text_preview_length]
                    
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
                
                logger.debug(f"   Using body start: {body_node.start_byte}")
                return body_node.start_byte
        
        elif mode == "inside_end":
            logger.debug(f"   Processing inside_end mode for {node.type}")
            # Get the internal body/block node
            body_node = self.find_body_node(node)

            if not body_node:
                logger.debug(f"   No body node found for inside_end mode, using node end: {node.end_byte}")
                return node.end_byte

            # For brace-based languages, we want to insert BEFORE the closing brace '}'
            # but only if the body actually uses braces.
            if self.language in ['c', 'cpp', 'java', 'javascript', 'typescript']:
                 # Find the LAST closing brace in the body node
                 body_text = self.source_code[body_node.start_byte:body_node.end_byte]
                 last_brace_idx = body_text.rfind('}')
                 if last_brace_idx != -1:
                     insertion_pos = body_node.start_byte + last_brace_idx
                     
                     # We want to be at the end of the line BEFORE the closing brace
                     # so find the newline preceding the brace
                     search_start = max(0, last_brace_idx - 1)
                     prev_newline = body_text.rfind('\n', 0, last_brace_idx)
                     
                     if prev_newline != -1:
                         # Insert after the last statement's newline but before the brace's line
                         insertion_pos = body_node.start_byte + prev_newline + 1
                     else:
                         # No newline, just move slightly before the brace
                         while insertion_pos > body_node.start_byte and self.source_code[insertion_pos-1] in ' \t':
                             insertion_pos -= 1
                         
                     logger.debug(f"   Found closing brace at {body_node.start_byte + last_brace_idx}, inserting at {insertion_pos}")
                     return insertion_pos
            
            # Fallback to node end
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
        logger.warning(f"⚠️  FALLBACK: Unknown rule mode '{rule.get('mode')}' for insertion mode '{mode}'")
        if mode == 'before':
            fallback_byte = node.start_byte
            logger.debug(f"   Using default before position: {fallback_byte}")
            return fallback_byte
        elif mode == 'after':
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
    
    def _find_python_function_start(self, body_node: Node, rule: Dict) -> Optional[int]:
        """Find the insertion point before the first non-docstring statement in a Python function body."""
        logger.debug(f"   Finding Python function start for body node {body_node.type}")
        
        # Use tree-sitter to find the first non-comment/docstring statement
        for child in body_node.children:
            # Skip comments
            if child.type == 'comment':
                logger.debug(f"   Skipping comment: {self.source_code[child.start_byte:child.end_byte]}")
                continue
            
            # Skip docstrings (expression_statement with string)
            if child.type == 'expression_statement':
                # Check if this is a docstring by looking for string children
                for grandchild in child.children:
                    if grandchild.type == 'string':
                        logger.debug(f"   Skipping docstring: {self.source_code[child.start_byte:child.end_byte]}")
                        break
                else:
                    # This is a real statement, not a docstring
                    # Return the beginning of the line containing this statement
                    line_start = self.source_code.rfind('\n', 0, child.start_byte) + 1
                    logger.debug(f"   Found first statement: {self.source_code[child.start_byte:child.end_byte]}")
                    return line_start
                continue
            
            # Skip empty lines (whitespace)
            if child.type in ['pass_statement', 'expression_statement'] and not child.children:
                continue
            
            # Found the first real statement
            # Return the beginning of the line containing this statement
            line_start = self.source_code.rfind('\n', 0, child.start_byte) + 1
            logger.debug(f"   Found first statement: {self.source_code[child.start_byte:child.end_byte]}")
            return line_start
        
        # Fallback to body start if no statements found
        logger.debug(f"   No statement found, using body start")
        return body_node.start_byte
    
    def _find_first_statement_line_start(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the start of the line containing the first statement in a body node."""
        skip_docstrings = rule.get("skip_docstrings", False)
        skip_comments = rule.get("skip_comments", False)
        
        for i, child in enumerate(body_node.children):
            child_text = self._get_node_text(child)
            
            # Skip docstrings if configured
            if skip_docstrings and self._is_docstring(child, child_text):
                continue
            
            # Skip comments if configured
            if skip_comments and self._is_comment(child):
                continue
            
            # Found first real statement - return the start of the line containing this statement
            line_start = self.source_code.rfind('\n', 0, child.start_byte) + 1
            logger.debug(f"   Found first statement '{child.type}' at byte {child.start_byte}")
            logger.debug(f"   Returning line start: {line_start}")
            return line_start
        
        # Fallback to body start
        return body_node.start_byte
    
    def _find_last_statement_line_end(self, body_node: Node, rule: Dict[str, Any]) -> int:
        """Find the position to insert AFTER the last statement in a body node for implicit exits."""
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

            # Found last real statement - for implicit exits, insert AFTER it (after line ends)
            # Find the end of the line containing this statement
            line_end = self.source_code.find('\n', child.end_byte)
            if line_end == -1:
                # Last line in file, use end of file
                line_end = len(self.source_code)
            else:
                # Position after the newline (start of next line)
                line_end = line_end + 1

            logger.debug(f"   Found last statement ending at byte {child.end_byte}, inserting after line at byte {line_end}")
            return line_end

        # Fallback: if no statements found, insert at body start
        logger.debug(f"   No statements found in body, using body start {body_node.start_byte}")
        return body_node.start_byte
    
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
            # Get configurable indent size
            limits = self.config_manager.get_processing_limits(self.language)
            default_indent_size = limits.get('default_indent_size', 4)
            indent_level = base_indent // default_indent_size
        
        # Get configurable indent size
        limits = self.config_manager.get_processing_limits(self.language)
        default_indent_size = limits.get('default_indent_size', 4)
        indent_string = indent_char * (indent_level * (1 if indent_char == '\t' else default_indent_size))
        
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
        
        # Get global configuration for common values
        global_config = self._get_global_config()
        self.default_indent_size = global_config.get('default_indent_size', 4)
        self.supported_languages = set(global_config.get('supported_languages', ['python', 'c', 'cpp', 'java', 'javascript']))
        
        logger.info(f"🔧 TreeSitterIndentationEngine initialized with nvim-treesitter at: {self.nvim_treesitter_path}")
    
    def _get_global_config(self) -> Dict[str, Any]:
        """Get global configuration values."""
        config_manager = get_language_config_manager()
        return config_manager.get_global_config()
    
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
            # Get configurable encoding
            global_config = self._get_global_config()
            encoding = global_config.get('default_encoding', 'utf-8')
            
            # Read the query file
            query_content = query_file.read_text(encoding=encoding)
            
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
                        inherited_content = inherited_file.read_text(encoding=encoding)
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
            if point.insertion_mode == "query_target":
                # query_target finds the specific node to insert relative to.
                # Currently we only support placement="before" in the query logic which returns start_byte.
                # So we treat this as insert_before.
                edit_type = "insert_before"
                
            logger.debug(f"   Edit type: {edit_type}")
            
            edit = ASTEdit(
                byte_offset=byte_offset,
                insertion_text=instrumentation_code,
                edit_type=edit_type,
                node_info=f"{point.type}:{point.name}",
                node_end_byte=point.node.end_byte if hasattr(point, 'node') and point.node else None
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
        
        # If we have a node and an insertion mode, let the AST processor find the best point.
        # This is more accurate than a fixed byte offset because it handles block boundaries,
        # braces, and indentation based on the actual tree structure.
        if node and point.insertion_mode:
            insertion_offset = self.ast_processor.find_insertion_point(node, point.insertion_mode)
            if insertion_offset is not None:
                logger.debug(f"   AST processor found insertion offset: {insertion_offset}")
                return insertion_offset

        if point.byte_offset is not None:
            logger.debug(f"   Using provided byte offset: {point.byte_offset}")
            return point.byte_offset
            
        # Fallback to line/column conversion
        fallback_offset = self._line_column_to_byte_offset(point.line, point.column)
        logger.debug(f"   Using fallback line/column offset: {fallback_offset}")
        return fallback_offset
    
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
            # Get configurable text preview length
            limits = self.config_manager.get_processing_limits(self.language)
            text_preview_length = limits.get('debug_text_preview_length', 100)
            logger.debug(f"      Insertion text preview: {edit.insertion_text[:text_preview_length]}{'...' if len(edit.insertion_text) > text_preview_length else ''}")
        
        sorted_edits = sorted(self.edits, key=lambda e: e.byte_offset, reverse=True)
        result_code = self.current_code
        current_tree = self.tree.copy()
        
        # Check if the tree already has errors to be more lenient during validation
        had_errors_initially = self.tree.root_node.has_error
        if had_errors_initially:
            logger.info("⚠️  Original tree has syntax errors (possibly due to macros). Validation will be more lenient.")
        
        successful_edits = 0
        failed_edits = 0
        
        for i, edit in enumerate(sorted_edits):
            logger.debug(f"🔧 Processing edit {i+1}/{len(sorted_edits)}: {edit.edit_type} at offset {edit.byte_offset}")
            
            # Log context around the edit location
            limits = self.config_manager.get_processing_limits(self.language)
            context_window = limits.get('max_search_window', 50)
            context_start = max(0, edit.byte_offset - context_window)
            context_end = min(len(result_code), edit.byte_offset + context_window)
            context = result_code[context_start:context_end]
            logger.debug(f"   Context around edit: '{context}'")
            
            old_code = result_code
            try:
                result_code, current_tree = self._apply_edit_with_tree_parsing(result_code, current_tree, edit)
                
                # Validate the edit didn't break syntax
                # If it had errors initially, we only fail if it causes a crash or major failure
                # (since we can't easily detect if NEW errors were added vs old ones remaining)
                if current_tree and current_tree.root_node.has_error and not had_errors_initially:
                    logger.error(f"❌ Edit {i+1} caused syntax error: {edit.node_info}")
                    logger.error(f"   Edit type: {edit.edit_type}")
                    logger.error(f"   Byte offset: {edit.byte_offset}")
                    # Get configurable error text length
                    limits = self.config_manager.get_processing_limits(self.language)
                    error_text_length = limits.get('debug_error_text_length', 200)
                    logger.error(f"   Insertion text: {edit.insertion_text[:error_text_length]}{'...' if len(edit.insertion_text) > error_text_length else ''}")
                    
                    # Log the specific error details
                    if hasattr(current_tree.root_node, 'has_error') and current_tree.root_node.has_error:
                        logger.error(f"   Tree has syntax errors after edit")
                    
                    # Revert to previous state
                    result_code = old_code
                    # Get configurable encoding
                    global_config = self.config_manager.get_global_config()
                    encoding = global_config.get('default_encoding', 'utf-8')
                    current_tree = self.parser.parse(old_code.encode(encoding))
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
                # Get configurable encoding
                global_config = self.config_manager.get_global_config()
                encoding = global_config.get('default_encoding', 'utf-8')
                current_tree = self.parser.parse(old_code.encode(encoding))
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
            
            # Calculate the actual inserted text length
            inserted_length = len(new_code) - len(code)
            logger.debug(f"   Actual inserted length: {inserted_length}")
            
            # Calculate edit parameters for tree-sitter
            # For insertions: start_byte = old_end_byte = insertion point
            # new_end_byte = insertion point + actual inserted length
            start_byte = offset
            old_end_byte = offset  # For insertions, old and start are the same
            new_end_byte = offset + inserted_length  # Use actual inserted length
            
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
            
            # Get configurable encoding
            global_config = self.config_manager.get_global_config()
            encoding = global_config.get('default_encoding', 'utf-8')
            
            # Incrementally reparse with the old tree
            new_tree = self.parser.parse(new_code.encode(encoding), old_tree=tree)
            
            if new_tree is None:
                logger.warning("Tree parsing failed, using original tree")
                return new_code, tree
            
            logger.debug(f"   New tree has errors: {new_tree.root_node.has_error}")
            if new_tree.root_node.has_error:
                # Get configurable error text length
                limits = self.config_manager.get_processing_limits(self.language)
                error_text_length = limits.get('debug_error_text_length', 200)
                logger.debug(f"   Tree error details: {new_tree.root_node.text.decode()[:error_text_length]}...")
                # If tree has errors, try to parse from scratch
                fresh_tree = self.parser.parse(new_code.encode(encoding))
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
            
            result = src[:pos] + prepend_nl + content + append_nl + src[pos:]
            logger.debug(f"   wrap_as_own_line: pos={pos}, prepend_nl='{repr(prepend_nl)}', append_nl='{repr(append_nl)}'")
            logger.debug(f"   Final wrapped result length: {len(result)} (was {len(src)})")
            return result

        if edit.edit_type == 'insert_before':
            # For insert_before, ensure we insert at the beginning of the line to preserve indentation
            line_start = code.rfind('\n', 0, offset) + 1
            if line_start != offset:
                logger.debug(f"   Adjusting insert_before offset from {offset} to line start {line_start}")
                offset = line_start
            # Insert checkpoint on its own line before the target statement
            logger.debug(f"   Using insert_before mode - inserting at line start {offset}")
            result = code[:offset] + indented_text + '\n' + code[offset:]
            logger.debug(f"   insert_before: inserted at offset {offset}, result length: {len(result)} (was {len(code)})")
        elif edit.edit_type == 'insert_after':
            # Insert after the node; keep it on its own line to avoid token merging
            logger.debug(f"   Using insert_after mode")
            result = wrap_as_own_line(code, offset, indented_text)
        elif edit.edit_type == 'insert_inside_start':
            # For insert_inside_start, insert checkpoint on its own line before the target statement
            # This preserves the target statement's position and indentation
            logger.debug(f"   Using insert_inside_start mode - inserting before target statement")
            result = code[:offset] + indented_text + '\n' + code[offset:]
            logger.debug(f"   insert_inside_start: inserted at offset {offset}, result length: {len(result)} (was {len(code)})")
        elif edit.edit_type == 'insert_inside_end':
            # Insert before the last statement in the body (for implicit function exits)
            logger.debug(f"   Using insert_inside_end mode - inserting on new line before target")
            prefix = '\n' if offset > 0 and code[offset-1] != '\n' else ''
            result = code[:offset] + prefix + indented_text + '\n' + code[offset:]
            logger.debug(f"   insert_inside_end: inserted at offset {offset}, result length: {len(result)} (was {len(code)})")
        elif edit.edit_type == 'insert_immediately_before':
            # Insert directly before the node, without adding newlines or matching line indentation
            # This is used for return statements to handle one-liner if blocks
            logger.debug(f"   Using insert_immediately_before mode")
            
            # For C-like languages, if we have the node end byte, wrap in braces to handle one-liners
            if edit.node_end_byte is not None and self.language in ['c', 'cpp', 'java', 'javascript']:
                stmt_text = code[offset:edit.node_end_byte]
                result = code[:offset] + "{ " + edit.insertion_text + " " + stmt_text + " }" + code[edit.node_end_byte:]
                logger.debug(f"   insert_immediately_before: wrapped in braces, result length: {len(result)}")
            else:
                result = code[:offset] + edit.insertion_text + code[offset:]
                logger.debug(f"   insert_immediately_before: inserted at offset {offset}, result length: {len(result)} (was {len(code)})")
        else:
            logger.warning(f"Unknown edit type: {edit.edit_type}")
            return code
        
        # Log the result for debugging
        logger.debug(f"   Edit result length: {len(result)} (was {len(code)})")
        # Get configurable significant change threshold
        limits = self.config_manager.get_processing_limits(self.language)
        significant_change_threshold = limits.get('debug_significant_change_threshold', 100)
        if len(result) > len(code) + significant_change_threshold:  # Only log if significant change
            text_preview_length = limits.get('debug_text_preview_length', 100)
            logger.debug(f"   Result preview: {result[offset:offset+text_preview_length]}...")
        
        return result
    
    def _add_proper_indentation(self, text: str, code: str, offset: int, edit_type: str = None) -> str:
        """
        Professional indentation using TreeSitter indentation engine.
        
        This replaces hardcoded indentation logic with the comprehensive
        nvim-treesitter indentation system.
        """
        logger.debug(f"🔧 Calculating indentation for edit_type='{edit_type}' at offset={offset}")
        
        # For Python, we need to be very careful about indentation
        if self.language == 'python':
            return self._calculate_python_indentation(text, code, offset, edit_type)
        
        # Try to use TreeSitter indentation engine first for other languages
        if self.tree and self.indent_engine:
            try:
                logger.debug(f"   Using TreeSitter indentation engine for {self.language}")
                indent_info = self.indent_engine.calculate_indentation_at_position(
                    self.tree, code, offset, self.language
                )
                logger.debug(f"   TreeSitter indent_info: level={indent_info.indent_level}, char='{indent_info.indent_char}', size={indent_info.indent_size}")
                
                # Apply indentation to each line
                lines = text.split('\n')
                indented_lines = []
                for i, line in enumerate(lines):
                    if line.strip():  # Non-empty line
                        indented_line = indent_info.indent_string + line.strip()
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
    
    def _calculate_python_indentation(self, text: str, code: str, offset: int, edit_type: str = None) -> str:
        """
        Calculate proper Python indentation based on the target location and edit type.

        Strategy:
        - If offset is at line start (column 0): Query-based insertion → match that line's indent
        - If offset is mid-line: Manual insertion → calculate indent from context
        """
        logger.debug(f"🔧 Calculating Python indentation for edit_type='{edit_type}' at offset={offset}")

        # Find the line containing the offset
        line_start = code.rfind('\n', 0, offset) + 1
        line_end = code.find('\n', offset)
        if line_end == -1:
            line_end = len(code)

        current_line = code[line_start:line_end]
        column = offset - line_start
        logger.debug(f"   Current line: '{current_line}'")
        logger.debug(f"   Offset column: {column} (line_start={line_start})")

        # Detect indentation style from the file
        indent_char, indent_size = self._detect_python_indent_style(code)
        logger.debug(f"   Detected indent: char='{indent_char}', size={indent_size}")

        # GENERAL RULE: If offset is at column 0 (line start), use that line's existing indentation
        # This handles query-based insertion where we return line_start of the target statement
        if column == 0:
            # Special case for insert_inside_end: offset is at start of line AFTER function body
            # We need to look at the PREVIOUS line to get function body indentation
            if edit_type == 'insert_inside_end':
                # offset is at start of line (after the \n), so offset-1 is the \n itself
                # We need to find the line BEFORE that \n
                if offset > 0:
                    # Find the \n before the current position
                    newline_pos = offset - 1
                    # Find the \n before that (end of previous line)
                    prev_newline_pos = code.rfind('\n', 0, newline_pos)
                    # Extract the previous line content (between prev_newline and newline_pos)
                    if prev_newline_pos >= 0:
                        prev_line = code[prev_newline_pos + 1:newline_pos]
                    else:
                        # First line in file
                        prev_line = code[:newline_pos]

                    if prev_line.strip():  # Non-empty previous line
                        target_indent = len(prev_line) - len(prev_line.lstrip())
                        indent_string = indent_char * target_indent
                        logger.debug(f"   insert_inside_end: using previous line indent={target_indent}")
                        logger.debug(f"   Previous line: '{prev_line}'")

                        # Apply indentation
                        lines = text.split('\n')
                        indented_lines = []
                        for i, line in enumerate(lines):
                            if line.strip():
                                indented_line = indent_string + line.strip()
                                indented_lines.append(indented_line)
                            else:
                                indented_lines.append('')

                        result = '\n'.join(indented_lines)
                        logger.debug(f"   Final indented text: '{result}'")
                        return result

            # For other cases, use current line's indentation
            if current_line.strip():
                target_indent = len(current_line) - len(current_line.lstrip())
                indent_string = indent_char * target_indent
                logger.debug(f"   Query-based insertion detected (column=0): using target line indent={target_indent}")

                # Apply indentation to each line of the text
                lines = text.split('\n')
                indented_lines = []
                for i, line in enumerate(lines):
                    if line.strip():
                        indented_line = indent_string + line.strip()
                        indented_lines.append(indented_line)
                    else:
                        indented_lines.append('')

                result = '\n'.join(indented_lines)
                logger.debug(f"   Final indented text: '{result}'")
                return result
        
        if edit_type == 'insert_inside_start':
            # For function enter checkpoints, find the first real statement and match its indentation
            # This ensures we insert at the same indentation level as the function body statements
            first_statement_indent = self._find_first_statement_indentation(offset, code)
            if first_statement_indent is not None:
                indent_string = indent_char * first_statement_indent
                logger.debug(f"   insert_inside_start: matched first statement indentation={first_statement_indent}, indent_string='{indent_string}'")
            else:
                # Fallback: use function definition + 1 level
                function_node = self._find_containing_function(offset)
                if function_node:
                    func_line_start = code.rfind('\n', 0, function_node.start_byte) + 1
                    func_line_end = code.find('\n', function_node.start_byte)
                    if func_line_end == -1:
                        func_line_end = len(code)
                    func_line = code[func_line_start:func_line_end]
                    func_indent = len(func_line) - len(func_line.lstrip())
                    body_indent = func_indent + indent_size
                    indent_string = indent_char * body_indent
                    logger.debug(f"   insert_inside_start fallback: func_indent={func_indent}, body_indent={body_indent}, indent_string='{indent_string}'")
                else:
                    # Final fallback
                    current_indent = len(current_line) - len(current_line.lstrip())
                    indent_string = indent_char * (current_indent + indent_size)
                    logger.debug(f"   insert_inside_start final fallback: current_indent={current_indent}, final='{indent_string}'")
                
        elif edit_type == 'insert_before':
            # For insert_before, match the target line's exact indentation
            target_indent = len(current_line) - len(current_line.lstrip())
            indent_string = indent_char * target_indent
            logger.debug(f"   insert_before: target_indent={target_indent}, indent_string='{indent_string}'")
            
        elif edit_type == 'insert_after' or edit_type == 'insert_inside_end':
            # For insert_after and insert_inside_end, match the current context indentation
            current_indent = len(current_line) - len(current_line.lstrip())
            indent_string = indent_char * current_indent
            logger.debug(f"   {edit_type}: current_indent={current_indent}, indent_string='{indent_string}'")
            
        else:
            # Default: match current line indentation
            current_indent = len(current_line) - len(current_line.lstrip())
            indent_string = indent_char * current_indent
            logger.debug(f"   default: current_indent={current_indent}, indent_string='{indent_string}'")
        
        # Apply indentation to each line of the text
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
        logger.debug(f"   Final Python indented text: '{result}'")
        return result
    
    def _detect_python_indent_style(self, code: str) -> Tuple[str, int]:
        """
        Detect Python indentation style from the source code.
        
        Returns:
            Tuple of (indent_char, indent_size)
        """
        lines = code.split('\n')
        indent_sizes = []
        uses_tabs = False
        
        for line in lines:
            if not line.strip():  # Skip empty lines
                continue
            
            # Count leading whitespace
            indent = 0
            for char in line:
                if char == ' ':
                    indent += 1
                elif char == '\t':
                    uses_tabs = True
                    indent += 4  # Count tabs as 4 spaces for analysis
                else:
                    break
            
            if indent > 0:
                indent_sizes.append(indent)
        
        if uses_tabs:
            return '\t', 1
        
        # Find the most common indentation size
        if indent_sizes:
            # Find the GCD of all indentation sizes to get the base unit
            import math
            size = indent_sizes[0]
            for s in indent_sizes[1:]:
                size = math.gcd(size, s)
            
            # Common Python indentation is 4 spaces, but respect the code's style
            if size in [2, 4, 8]:
                return ' ', size
            else:
                return ' ', 4  # Default to 4 spaces
        
        return ' ', 4  # Default fallback
    
    def _find_containing_function(self, offset: int) -> Optional[Node]:
        """
        Find the function definition node that contains the given byte offset.
        """
        if not self.tree:
            return None
        
        # Find the node at the offset
        target_node = self.tree.root_node.descendant_for_byte_range(offset, offset + 1)
        if not target_node:
            return None
        
        # Walk up the AST to find the function definition
        current = target_node
        while current:
            if current.type in ['function_definition', 'method_definition', 'async_function_definition']:
                return current
            current = current.parent
        
        return None
    
    def _find_first_statement_indentation(self, offset: int, code: str) -> Optional[int]:
        """
        Find the indentation of the first real statement in the function containing the given offset.
        
        This is used for insert_inside_start to ensure checkpoints are indented at the same
        level as the function body statements.
        """
        if not self.tree:
            return None
        
        # Find the function containing this offset
        function_node = self._find_containing_function(offset)
        if not function_node:
            logger.debug(f"   No function found containing offset {offset}")
            return None
        
        logger.debug(f"   Found function '{function_node.type}' containing offset {offset}")
        
        # For Python, traverse all children of the function to find the first real statement
        # We don't need to find a specific body node - just iterate through all children
        for child in function_node.children:
            # Skip comments
            if child.type == 'comment':
                logger.debug(f"   Skipping comment: {child.type}")
                continue
            
            # Skip the function signature parts (def, name, parameters, colon)
            if child.type in ['def', 'identifier', 'parameters', ':', 'type_annotation']:
                logger.debug(f"   Skipping function signature part: {child.type}")
                continue
            
            # Skip docstrings (expression_statement with string)
            if child.type == 'expression_statement':
                # Check if this is a docstring
                for grandchild in child.children:
                    if grandchild.type == 'string':
                        logger.debug(f"   Skipping docstring: {child.type}")
                        break  # This is a docstring, skip it
                else:
                    # This is a real statement, get its indentation
                    line_start = code.rfind('\n', 0, child.start_byte) + 1
                    line_text = code[line_start:child.start_byte]
                    indentation = len(line_text) - len(line_text.lstrip())
                    logger.debug(f"   Found first real statement (expression_statement) with {indentation} spaces indentation")
                    return indentation
                continue
            
            # Skip whitespace and empty nodes
            if not child.type or child.type in ['pass_statement'] and not child.children:
                logger.debug(f"   Skipping empty/pass statement: {child.type}")
                continue
            
            # Check if this node has any text content (not just syntax)
            child_text = code[child.start_byte:child.end_byte].strip()
            if not child_text:
                logger.debug(f"   Skipping empty node: {child.type}")
                continue
            
            # Found the first real statement
            line_start = code.rfind('\n', 0, child.start_byte) + 1
            line_text = code[line_start:child.start_byte]
            indentation = len(line_text) - len(line_text.lstrip())
            logger.debug(f"   Found first real statement '{child.type}' with {indentation} spaces indentation")
            logger.debug(f"   Statement text preview: '{child_text[:50]}...'")
            return indentation
        
        logger.debug(f"   No real statements found in function")
        return None
    
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
                                # Get configurable indent size
                                limits = self.config_manager.get_processing_limits(self.language)
                                default_indent_size = limits.get('default_indent_size', 4)
                                indent_string = '\t' * (base_indent // default_indent_size)  # Convert spaces to tabs
                            else:
                                indent_string = ' ' * base_indent
                            
                            # Get configurable text preview length
                            limits = self.config_manager.get_processing_limits(self.language)
                            text_preview_length = limits.get('debug_text_preview_length', 100)
                            logger.debug(f"🔧 AST-based inside_start: found first statement '{self._get_node_text(first_statement)[:text_preview_length]}...', indentation '{indent_string}' (len={len(indent_string)})")
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
        # Get configurable indent size
        limits = self.config_manager.get_processing_limits(self.language)
        default_indent_size = limits.get('default_indent_size', 4)
        return ' ' * max(default_indent_size, indent_info.indent_size if hasattr(indent_info, 'indent_size') else default_indent_size)
    
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
