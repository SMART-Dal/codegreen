"""
Base classes for CodeGreen language support system.

Provides abstract interfaces and data structures for extensible language adapters
following industry best practices from tree-sitter tooling ecosystem.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from tree_sitter import Tree, Parser, Query


@dataclass
class InstrumentationPoint:
    """Represents a point in code where energy measurements should be taken"""
    type: str  # e.g., 'function', 'loop', 'conditional'
    subtype: str  # e.g., 'entry', 'exit', 'start', 'end'
    name: str  # Function name, variable name, etc.
    line: int
    column: int
    context: str  # Human readable description
    metadata: Dict[str, Any] = None  # Additional language-specific data
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass  
class CodeCheckpoint:
    """Legacy checkpoint structure for backward compatibility"""
    id: str
    type: str
    name: str
    line_number: int
    column_number: int
    context: str
    
    @classmethod
    def from_instrumentation_point(cls, point: InstrumentationPoint) -> 'CodeCheckpoint':
        """Convert InstrumentationPoint to legacy CodeCheckpoint format"""
        checkpoint_id = f"{point.type}_{point.name}_{point.line}"
        return cls(
            id=checkpoint_id,
            type=point.type,
            name=point.name,
            line_number=point.line,
            column_number=point.column,
            context=point.context
        )


class LanguageAdapter(ABC):
    """
    Base class for all language adapters in CodeGreen.
    
    Follows the extensible architecture pattern from tree-climber and nvim-treesitter,
    providing both tree-sitter based analysis and fallback regex-based analysis.
    """
    
    def __init__(self, parser: Optional[Parser] = None):
        """
        Initialize language adapter.
        
        Args:
            parser: Optional tree-sitter parser. If None, fallback analysis will be used.
        """
        self.parser = parser
        self._queries: Dict[str, Query] = {}
        if parser:
            self._load_queries()
    
    @property
    @abstractmethod
    def language_id(self) -> str:
        """Unique identifier for this language (e.g., 'python', 'c', 'java')"""
        pass
    
    @abstractmethod
    def get_file_extensions(self) -> List[str]:
        """List of file extensions supported by this language"""
        pass
    
    def _load_queries(self):
        """Load tree-sitter queries for instrumentation point detection"""
        queries = self.get_query_definitions()
        
        if self.parser and queries:
            language = self.parser.language
            for query_name, query_text in queries.items():
                try:
                    self._queries[query_name] = language.query(query_text)
                except Exception as e:
                    # Log warning but continue - some queries may be optional
                    print(f"Warning: Failed to load query '{query_name}' for {self.language_id}: {e}")
    
    def get_query_definitions(self) -> Dict[str, str]:
        """
        Define tree-sitter queries for instrumentation points.
        
        Override in subclasses to provide language-specific queries.
        
        Returns:
            Dictionary mapping query names to query text
        """
        return {}
    
    def generate_checkpoints(self, source_code: str) -> List[CodeCheckpoint]:
        """
        Generate instrumentation checkpoints for the given source code.
        
        Uses tree-sitter analysis if parser is available, otherwise falls back
        to regex-based analysis.
        """
        if self.parser and self._queries:
            points = self._generate_instrumentation_points_treesitter(source_code)
        else:
            points = self._generate_instrumentation_points_fallback(source_code)
            
        # Convert to legacy checkpoint format for backward compatibility
        return [CodeCheckpoint.from_instrumentation_point(point) for point in points]
    
    def _generate_instrumentation_points_treesitter(self, source_code: str) -> List[InstrumentationPoint]:
        """Generate instrumentation points using tree-sitter analysis"""
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        points = []
        
        for query_name, query in self._queries.items():
            captures = query.captures(tree.root_node)
            
            for node, capture_name in captures:
                point = self._create_instrumentation_point_from_capture(
                    query_name, capture_name, node, source_code
                )
                if point:
                    points.append(point)
                    
        return points
    
    def _create_instrumentation_point_from_capture(
        self, 
        query_name: str, 
        capture_name: str, 
        node, 
        source_code: str
    ) -> Optional[InstrumentationPoint]:
        """
        Create instrumentation point from tree-sitter capture.
        
        Override in subclasses for language-specific logic.
        """
        return InstrumentationPoint(
            type=query_name,
            subtype=capture_name,
            name=self._extract_name_from_node(node, source_code),
            line=node.start_point.row + 1,
            column=node.start_point.column + 1,
            context=f"{query_name} at line {node.start_point.row + 1}"
        )
    
    def _extract_name_from_node(self, node, source_code: str) -> str:
        """Extract meaningful name from tree-sitter node"""
        # Default implementation - extract text from node
        start_byte = node.start_byte
        end_byte = node.end_byte
        return source_code[start_byte:end_byte].strip()
    
    @abstractmethod
    def _generate_instrumentation_points_fallback(self, source_code: str) -> List[InstrumentationPoint]:
        """
        Generate instrumentation points using regex-based fallback analysis.
        
        This method should be implemented by each language adapter to provide
        basic functionality when tree-sitter is not available.
        """
        pass
    
    def instrument_code(self, source_code: str, checkpoints: List[CodeCheckpoint]) -> str:
        """
        Instrument source code with measurement calls.
        
        Override in subclasses for language-specific instrumentation strategies.
        """
        return self._basic_instrumentation(source_code, checkpoints)
    
    def _basic_instrumentation(self, source_code: str, checkpoints: List[CodeCheckpoint]) -> str:
        """Basic line-based instrumentation as fallback"""
        lines = source_code.split('\n')
        
        # Sort checkpoints by line number in reverse order to avoid offset issues
        sorted_checkpoints = sorted(checkpoints, key=lambda c: c.line_number, reverse=True)
        
        for checkpoint in sorted_checkpoints:
            if 1 <= checkpoint.line_number <= len(lines):
                instrumentation_call = self._generate_instrumentation_call(checkpoint)
                # Insert instrumentation call before the target line
                insert_index = checkpoint.line_number - 1
                lines.insert(insert_index, instrumentation_call)
                
        return '\n'.join(lines)
    
    def _generate_instrumentation_call(self, checkpoint: CodeCheckpoint) -> str:
        """Generate language-specific instrumentation call"""
        # Default implementation - override in subclasses
        return f"    // CodeGreen checkpoint: {checkpoint.id}"
    
    def analyze_code(self, source_code: str) -> List[str]:
        """
        Analyze code for optimization opportunities.
        
        Returns list of optimization suggestions.
        """
        return []  # Default: no analysis