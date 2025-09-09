"""
Language-agnostic AST processor for CodeGreen.

This module provides a clean, extensible way to process AST nodes
without hardcoding language-specific logic.
"""

from typing import Dict, Any, List, Optional, Tuple
from tree_sitter import Node
from .language_configs import get_language_config_manager, LanguageConfig

class ASTProcessor:
    """Language-agnostic AST processor using configuration-driven approach."""
    
    def __init__(self, language: str, source_code: str = ""):
        self.language = language
        self.source_code = source_code
        self.config_manager = get_language_config_manager()
        self.config = self.config_manager.get_config(language)
        if not self.config:
            raise ValueError(f"No configuration found for language: {language}")
    
    def find_body_node(self, node: Node) -> Optional[Node]:
        """Find the body/block node for a given node using language configuration."""
        ast_config = self.config.ast_config
        
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
        ast_config = self.config.ast_config
        insertion_rules = ast_config.get("insertion_rules", {})
        
        # Map insertion modes to rule keys
        mode_mapping = {
            'inside_start': 'function_enter',
            'inside_end': 'function_exit',
            'before': 'before',
            'after': 'after'
        }
        
        rule_key = mode_mapping.get(insertion_mode, insertion_mode)
        
        if rule_key not in insertion_rules:
            # Default behavior
            if insertion_mode == 'before':
                return node.start_byte
            elif insertion_mode == 'after':
                return node.end_byte
            else:
                return node.start_byte
        
        rule = insertion_rules[rule_key]
        
        if rule.get("mode") == "inside_start":
            body_node = self.find_body_node(node)
            if not body_node:
                return node.start_byte
            
            if rule.get("find_first_statement", False):
                return self._find_first_statement_line_start(body_node, rule)
            else:
                return body_node.start_byte
        
        elif rule.get("mode") == "inside_end":
            body_node = self.find_body_node(node)
            if not body_node:
                return node.end_byte
            
            if rule.get("find_last_statement", False):
                return self._find_last_statement_line_end(body_node, rule)
            else:
                return body_node.end_byte
        
        # Default fallback
        if insertion_mode == 'before':
            return node.start_byte
        elif insertion_mode == 'after':
            return node.end_byte
        else:
            return node.start_byte
    
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
            
            # Found first real statement - return start of its line
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
            return line_end
        
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
        Calculate proper indentation for insertion based on AST node information.
        
        Returns:
            Tuple of (total_indent, indent_string)
        """
        if not body_node or not self.source_code:
            return 0, ""
        
        # Find the first non-whitespace child in the body
        first_statement = None
        for child in body_node.children:
            child_text = self._get_node_text(child)
            if child_text.strip():  # Non-empty child
                first_statement = child
                break
        
        if first_statement:
            # Use the first statement's indentation as base
            line_start = self.source_code.rfind('\n', 0, first_statement.start_byte) + 1
            line_text = self.source_code[line_start:first_statement.start_byte]
            base_indent = len(line_text)
        else:
            # Empty body - use parent's indentation + extra
            parent_line_start = self.source_code.rfind('\n', 0, body_node.start_byte) + 1
            parent_line_text = self.source_code[parent_line_start:body_node.start_byte]
            base_indent = len(parent_line_text)
        
        # Get extra indentation from config
        formatting_config = self.get_formatting_config()
        extra_indent = formatting_config.get("extra_indent_for_inside", 4)
        
        # Check if we're inserting at the beginning of a line
        insertion_line_start = self.source_code.rfind('\n', 0, insertion_offset) + 1
        if insertion_offset == insertion_line_start:
            # Inserting at line start - use base indent
            total_indent = base_indent
        else:
            # Inserting in middle of line - use base + extra
            total_indent = base_indent + extra_indent
        
        # Detect tabs vs spaces from the context
        indent_char = self._detect_indent_character(body_node)
        indent_string = indent_char * total_indent
        
        return total_indent, indent_string
    
    def _detect_indent_character(self, body_node: Node) -> str:
        """Detect whether the code uses tabs or spaces for indentation."""
        if not body_node or not self.source_code:
            return " "
        
        # Check the first few lines of the body for indentation
        body_start = body_node.start_byte
        body_end = min(body_node.start_byte + 200, body_node.end_byte)  # Check first 200 chars
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
