"""
C Language Adapter for CodeGreen

Provides comprehensive C code analysis using tree-sitter queries
with regex-based fallback support.
"""

import re
from typing import List, Dict
from ..base import LanguageAdapter, InstrumentationPoint


class CAdapter(LanguageAdapter):
    """Enhanced C language adapter with query-based instrumentation"""
    
    @property
    def language_id(self) -> str:
        return "c"
    
    def get_file_extensions(self) -> List[str]:
        return [".c", ".h"]
    
    def get_query_definitions(self) -> Dict[str, str]:
        """Tree-sitter queries for C instrumentation points"""
        return {
            # Function definitions
            'functions': '''
                (function_definition
                  declarator: (function_declarator
                    declarator: (identifier) @function.name
                    parameters: (_) @function.params) @function.declarator
                  body: (compound_statement) @function.body) @function.def
            ''',
            
            # Loop constructs
            'loops': '''
                (for_statement
                  initializer: (_) @loop.init
                  condition: (_) @loop.condition  
                  update: (_) @loop.update
                  body: (_) @loop.body) @loop.for
                  
                (while_statement
                  condition: (_) @loop.condition
                  body: (_) @loop.body) @loop.while
                  
                (do_statement
                  body: (_) @loop.body
                  condition: (_) @loop.condition) @loop.do
            ''',
            
            # Conditional statements
            'conditionals': '''
                (if_statement
                  condition: (_) @condition
                  consequence: (_) @if.body
                  alternative: (_)? @if.else) @conditional.if
                  
                (switch_statement
                  condition: (_) @switch.condition
                  body: (_) @switch.body) @conditional.switch
            ''',
            
            # Function calls
            'calls': '''
                (call_expression
                  function: (identifier) @call.name
                  arguments: (_) @call.args) @call.simple
                  
                (call_expression
                  function: (field_expression
                    object: (_) @call.object
                    field: (field_identifier) @call.method)
                  arguments: (_) @call.args) @call.method
            ''',
            
            # Memory operations (malloc, free, etc.)
            'memory_ops': '''
                (call_expression
                  function: (identifier) @memory.op
                  arguments: (_) @memory.args) @memory.call
                  (#match? @memory.op "^(malloc|calloc|realloc|free)$")
            ''',
            
            # Pointer operations (energy intensive)
            'pointers': '''
                (pointer_expression) @pointer.deref
                (assignment_expression
                  left: (pointer_expression) @pointer.assign_left
                  right: (_) @pointer.assign_right) @pointer.assign
            '''
        }
    
    def _create_instrumentation_point_from_capture(
        self, 
        query_name: str, 
        capture_name: str, 
        node, 
        source_code: str
    ) -> InstrumentationPoint:
        """Create C-specific instrumentation points"""
        
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
                # Find function name from parent
                func_name = self._find_function_name_from_body(node, source_code)
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
            if capture_name in ['loop.for', 'loop.while', 'loop.do']:
                return InstrumentationPoint(
                    type='loop_start',
                    subtype=loop_type,
                    name=f"{loop_type}_loop",
                    line=line,
                    column=column,
                    context=f"{loop_type.title()} loop at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'memory_ops':
            if capture_name == 'memory.op':
                op_name = self._extract_name_from_node(node, source_code)
                return InstrumentationPoint(
                    type='memory_operation',
                    subtype=op_name,
                    name=op_name,
                    line=line,
                    column=column,
                    context=f"Memory operation: {op_name} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'energy_intensive': True}
                )
        
        elif query_name == 'calls':
            if capture_name == 'call.name':
                func_name = self._extract_name_from_node(node, source_code)
                return InstrumentationPoint(
                    type='function_call',
                    subtype='simple',
                    name=func_name,
                    line=line,
                    column=column,
                    context=f"Function call: {func_name} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
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
    
    def _find_function_name_from_body(self, body_node, source_code: str) -> str:
        """Extract function name from function body by looking at parent"""
        current = body_node.parent
        while current:
            if current.type == 'function_definition':
                for child in current.children:
                    if child.type == 'function_declarator':
                        for grandchild in child.children:
                            if grandchild.type == 'identifier':
                                return self._extract_name_from_node(grandchild, source_code)
            current = current.parent
        return 'unknown'
    
    def _generate_instrumentation_points_fallback(self, source_code: str) -> List[InstrumentationPoint]:
        """Regex-based fallback analysis for C"""
        points = []
        lines = source_code.split('\n')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Function definitions (simplified pattern)
            func_match = re.match(r'^\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*\{?\s*$', line)
            if func_match and not any(keyword in line for keyword in ['if', 'while', 'for', 'switch']):
                func_name = func_match.group(1)
                # Skip common keywords
                if func_name not in ['if', 'else', 'while', 'for', 'do', 'switch', 'case', 'return']:
                    points.append(InstrumentationPoint(
                        type='function_enter',
                        subtype='entry',
                        name=func_name,
                        line=line_num,
                        column=func_match.start(1),
                        context=f"Function entry: {func_name}"
                    ))
            
            # For loops
            for_match = re.match(r'^\s*for\s*\(', line)
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
            while_match = re.match(r'^\s*while\s*\(', line)
            if while_match:
                points.append(InstrumentationPoint(
                    type='loop_start',
                    subtype='while',
                    name='while_loop',
                    line=line_num,
                    column=while_match.start(),
                    context=f"While loop at line {line_num}"
                ))
            
            # Do-while loops
            do_match = re.match(r'^\s*do\s*\{', line)
            if do_match:
                points.append(InstrumentationPoint(
                    type='loop_start',
                    subtype='do',
                    name='do_loop',
                    line=line_num,
                    column=do_match.start(),
                    context=f"Do-while loop at line {line_num}"
                ))
            
            # Memory operations
            memory_match = re.search(r'\b(malloc|calloc|realloc|free)\s*\(', line)
            if memory_match:
                op_name = memory_match.group(1)
                points.append(InstrumentationPoint(
                    type='memory_operation',
                    subtype=op_name,
                    name=op_name,
                    line=line_num,
                    column=memory_match.start(),
                    context=f"Memory operation: {op_name} at line {line_num}",
                    metadata={'energy_intensive': True}
                ))
        
        return points
    
    def _generate_instrumentation_call(self, checkpoint) -> str:
        """Generate C instrumentation call"""
        return (
            f"    codegreen_measure_checkpoint(\"{checkpoint.id}\", \"{checkpoint.type}\", "
            f"\"{checkpoint.name}\", {checkpoint.line_number}, \"{checkpoint.context}\");"
        )
    
    def instrument_code(self, source_code: str, checkpoints: List) -> str:
        """Instrument C code with measurement calls"""
        lines = source_code.split('\n')
        
        # Add instrumentation include at the top
        instrumented_include = (
            "#include <stdio.h>\n"
            "#include <sys/time.h>\n"
            "void codegreen_measure_checkpoint(const char* id, const char* type, const char* name, int line, const char* context) {\n"
            "    struct timeval tv; gettimeofday(&tv, NULL);\n"
            "    printf(\"CODEGREEN_CHECKPOINT: %s|%s|%s|%d|%s|%ld.%06ld\\n\", id, type, name, line, context, tv.tv_sec, tv.tv_usec);\n"
            "}\n"
        )
        
        # Find insertion point after existing includes
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('#include') or line.startswith('#define') or line.startswith('#pragma'):
                insert_pos = i + 1
            elif line.strip() and not line.startswith('/*') and not line.startswith('//'):
                break
        
        lines.insert(insert_pos, instrumented_include)
        
        # Apply basic instrumentation
        return self._basic_instrumentation('\n'.join(lines), checkpoints)
    
    def analyze_code(self, source_code: str) -> List[str]:
        """Analyze C code for optimization opportunities"""
        suggestions = []
        
        # Check for strlen in loop conditions
        if re.search(r'for\s*\([^;]*strlen', source_code):
            suggestions.append("Avoid calling strlen() in loop conditions; cache the length in a variable")
        
        # Check for malloc without free
        malloc_count = len(re.findall(r'\bmalloc\s*\(', source_code))
        free_count = len(re.findall(r'\bfree\s*\(', source_code))
        if malloc_count > free_count:
            suggestions.append(f"Found {malloc_count} malloc calls but only {free_count} free calls - potential memory leak")
        
        # Check for malloc in loops
        if re.search(r'for.*{[^}]*malloc', source_code, re.DOTALL):
            suggestions.append("Consider pre-allocating memory outside loops to reduce allocation overhead")
        
        # Check for I/O in loops
        if re.search(r'(for|while).*{[^}]*printf', source_code, re.DOTALL):
            suggestions.append("Consider buffering output or reducing I/O operations inside loops")
        
        return suggestions