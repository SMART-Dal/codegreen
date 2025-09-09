"""
Python Language Adapter for CodeGreen

Provides comprehensive Python code analysis using tree-sitter queries
with regex-based fallback support.
"""

import re
from typing import List, Dict
from ..base import LanguageAdapter, InstrumentationPoint


class PythonAdapter(LanguageAdapter):
    """Enhanced Python language adapter with query-based instrumentation"""
    
    @property
    def language_id(self) -> str:
        return "python"
    
    def get_file_extensions(self) -> List[str]:
        return [".py", ".pyw"]
    
    def get_query_definitions(self) -> Dict[str, str]:
        """Tree-sitter queries for Python instrumentation points"""
        return {
            # Function definitions
            'functions': '''
                (function_definition
                  name: (identifier) @function.name
                  body: (block) @function.body) @function.def
            ''',
            
            # Class definitions  
            'classes': '''
                (class_definition
                  name: (identifier) @class.name
                  body: (block) @class.body) @class.def
            ''',
            
            # Loop constructs
            'loops': '''
                (for_statement
                  left: (_) @loop.var
                  right: (_) @loop.iter
                  body: (block) @loop.body) @loop.for
                  
                (while_statement
                  condition: (_) @loop.condition
                  body: (block) @loop.body) @loop.while
            ''',
            
            # Conditional statements
            'conditionals': '''
                (if_statement
                  condition: (_) @condition
                  consequence: (block) @if.body) @conditional.if
            ''',
            
            # Comprehensions (high energy consumers)
            'comprehensions': '''
                (list_comprehension) @comprehension.list
                (dictionary_comprehension) @comprehension.dict
                (set_comprehension) @comprehension.set
                (generator_expression) @comprehension.generator
            ''',
            
            # Function calls (potential energy hotspots)
            'calls': '''
                (call
                  function: (identifier) @call.name) @call.simple
                  
                (call
                  function: (attribute
                    object: (_) @call.object
                    attribute: (identifier) @call.method)) @call.method
            ''',
            
            # With statements (context managers)
            'context_managers': '''
                (with_statement
                  (with_clause
                    (with_item
                      value: (_) @context.value)) @context.clause
                  body: (block) @context.body) @context.with
            '''
        }
    
    def _create_instrumentation_point_from_capture(
        self, 
        query_name: str, 
        capture_name: str, 
        node, 
        source_code: str
    ) -> InstrumentationPoint:
        """Create Python-specific instrumentation points"""
        
        line = node.start_point.row + 1
        column = node.start_point.column + 1
        
        if query_name == 'functions':
            if capture_name == 'function.name':
                name = self._extract_name_from_node(node, source_code)
                return InstrumentationPoint(
                    type='function_enter',
                    subtype='entry',
                    name=name,
                    line=line,
                    column=column,
                    context=f"Function entry: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
            elif capture_name == 'function.body':
                # Extract function name from parent
                parent = node.parent
                if parent:
                    func_name = self._find_function_name(parent, source_code)
                    return InstrumentationPoint(
                        type='function_exit',
                        subtype='exit',
                        name=func_name,
                        line=node.end_point.row + 1,
                        column=node.end_point.column + 1,
                        context=f"Function exit: {func_name}",
                        metadata={'query': query_name, 'capture': capture_name}
                    )
        
        elif query_name == 'loops':
            loop_type = capture_name.split('.')[1] if '.' in capture_name else 'loop'
            return InstrumentationPoint(
                type='loop_start',
                subtype=loop_type,
                name=f"{loop_type}_loop",
                line=line,
                column=column,
                context=f"{loop_type.title()} loop at line {line}",
                metadata={'query': query_name, 'capture': capture_name}
            )
        
        elif query_name == 'comprehensions':
            comp_type = capture_name.split('.')[1] if '.' in capture_name else 'comprehension'
            return InstrumentationPoint(
                type='comprehension',
                subtype=comp_type,
                name=f"{comp_type}_comp",
                line=line,
                column=column,
                context=f"{comp_type.title()} comprehension at line {line}",
                metadata={'query': query_name, 'capture': capture_name, 'energy_intensive': True}
            )
        
        # Default instrumentation point
        return InstrumentationPoint(
            type=query_name,
            subtype=capture_name,
            name=self._extract_name_from_node(node, source_code) or f"{query_name}_{line}",
            line=line,
            column=column,
            context=f"{query_name} at line {line}",
            metadata={'query': query_name, 'capture': capture_name}
        )
    
    def _find_function_name(self, node, source_code: str) -> str:
        """Extract function name from function definition node"""
        if node.type == 'function_definition':
            for child in node.children:
                if child.type == 'identifier':
                    return self._extract_name_from_node(child, source_code)
        return 'unknown'
    
    def _generate_instrumentation_points_fallback(self, source_code: str) -> List[InstrumentationPoint]:
        """Regex-based fallback analysis for Python"""
        points = []
        lines = source_code.split('\n')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Function definitions
            func_match = re.match(r'^\s*def\s+(\w+)', line)
            if func_match:
                func_name = func_match.group(1)
                points.append(InstrumentationPoint(
                    type='function_enter',
                    subtype='entry',
                    name=func_name,
                    line=line_num,
                    column=func_match.start(1),
                    context=f"Function entry: {func_name}"
                ))
            
            # Class definitions
            class_match = re.match(r'^\s*class\s+(\w+)', line)
            if class_match:
                class_name = class_match.group(1)
                points.append(InstrumentationPoint(
                    type='class_enter',
                    subtype='entry',
                    name=class_name,
                    line=line_num,
                    column=class_match.start(1),
                    context=f"Class definition: {class_name}"
                ))
            
            # For loops
            for_match = re.match(r'^\s*for\s+', line)
            if for_match:
                points.append(InstrumentationPoint(
                    type='loop_start',
                    subtype='for',
                    name='for_loop',
                    line=line_num,
                    column=for_match.start(),
                    context=f"For loop at line {line_num}"
                ))
            
            # While loops  
            while_match = re.match(r'^\s*while\s+', line)
            if while_match:
                points.append(InstrumentationPoint(
                    type='loop_start',
                    subtype='while', 
                    name='while_loop',
                    line=line_num,
                    column=while_match.start(),
                    context=f"While loop at line {line_num}"
                ))
            
            # List comprehensions (energy intensive)
            if '[' in line and 'for' in line and 'in' in line:
                comp_match = re.search(r'\[.*for.*in.*\]', line)
                if comp_match:
                    points.append(InstrumentationPoint(
                        type='comprehension',
                        subtype='list',
                        name='list_comp',
                        line=line_num,
                        column=comp_match.start(),
                        context=f"List comprehension at line {line_num}",
                        metadata={'energy_intensive': True}
                    ))
        
        return points
    
    def _generate_instrumentation_call(self, checkpoint) -> str:
        """Generate Python instrumentation call"""
        return (
            f"    import time; "
            f"print(f'CODEGREEN_CHECKPOINT: {checkpoint.id}|{checkpoint.type}|"
            f"{checkpoint.name}|{checkpoint.line_number}|{checkpoint.context}|"
            f"{{time.time_ns() // 1000000}}')"
        )
    
    def analyze_code(self, source_code: str) -> List[str]:
        """Analyze Python code for optimization opportunities"""
        suggestions = []
        
        # Check for common performance anti-patterns
        if re.search(r'\+.*=.*in\s+for', source_code):
            suggestions.append("Consider using str.join() instead of string concatenation in loops")
        
        if 'import *' in source_code:
            suggestions.append("Avoid wildcard imports - use specific imports for better performance")
        
        if re.search(r'list\(.*\)', source_code) and '[' in source_code:
            suggestions.append("Consider list comprehensions instead of list() constructor where applicable")
        
        # Check for nested loops (O(n²) patterns)  
        nested_loops = len(re.findall(r'^\s*for.*:\s*\n.*for', source_code, re.MULTILINE))
        if nested_loops > 0:
            suggestions.append(f"Found {nested_loops} nested loop patterns - consider algorithmic optimizations")
        
        return suggestions