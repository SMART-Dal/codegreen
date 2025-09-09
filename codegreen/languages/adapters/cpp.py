"""
C++ Language Adapter for CodeGreen

Provides comprehensive C++ code analysis using tree-sitter queries
with regex-based fallback support.
"""

import re
from typing import List, Dict
from ..base import LanguageAdapter, InstrumentationPoint


class CppAdapter(LanguageAdapter):
    """Enhanced C++ language adapter with query-based instrumentation"""
    
    @property
    def language_id(self) -> str:
        return "cpp"
    
    def get_file_extensions(self) -> List[str]:
        return [".cpp", ".cxx", ".cc", ".hpp", ".h", ".hxx", ".h++"]
    
    def get_query_definitions(self) -> Dict[str, str]:
        """Tree-sitter queries for C++ instrumentation points"""
        return {
            # Function definitions (including methods)
            'functions': '''
                (function_definition
                  declarator: (function_declarator
                    declarator: (identifier) @function.name) @function.declarator
                  body: (compound_statement) @function.body) @function.def
                  
                (method_definition
                  declarator: (function_declarator
                    declarator: (identifier) @method.name) @method.declarator
                  body: (compound_statement) @method.body) @method.def
            ''',
            
            # Class and struct definitions
            'classes': '''
                (class_specifier
                  name: (type_identifier) @class.name
                  body: (field_declaration_list) @class.body) @class.def
                  
                (struct_specifier
                  name: (type_identifier) @struct.name
                  body: (field_declaration_list) @struct.body) @struct.def
            ''',
            
            # Constructor and destructor
            'constructors': '''
                (constructor_definition
                  name: (identifier) @constructor.name
                  body: (compound_statement) @constructor.body) @constructor.def
                  
                (destructor_definition
                  name: (identifier) @destructor.name
                  body: (compound_statement) @destructor.body) @destructor.def
            ''',
            
            # Loop constructs (including range-based for)
            'loops': '''
                (for_statement
                  initializer: (_) @loop.init
                  condition: (_) @loop.condition
                  update: (_) @loop.update
                  body: (_) @loop.body) @loop.for
                  
                (range_for_statement
                  declarator: (_) @loop.var
                  right: (_) @loop.range
                  body: (_) @loop.body) @loop.range_for
                  
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
            
            # Function and method calls
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
            
            # Memory operations (new, delete, smart pointers)
            'memory_ops': '''
                (new_expression
                  type: (_) @memory.type) @memory.new
                  
                (delete_expression
                  argument: (_) @memory.target) @memory.delete
                  
                (call_expression
                  function: (identifier) @memory.smart_ptr
                  arguments: (_) @memory.args) @memory.smart_call
                  (#match? @memory.smart_ptr "^(make_unique|make_shared|unique_ptr|shared_ptr)$")
            ''',
            
            # Templates (potentially complex)
            'templates': '''
                (template_declaration
                  parameters: (_) @template.params
                  (function_definition) @template.function) @template.func_def
                  
                (template_declaration
                  parameters: (_) @template.params
                  (class_specifier) @template.class) @template.class_def
            ''',
            
            # Exception handling
            'exceptions': '''
                (try_statement
                  body: (_) @try.body
                  handler: (catch_clause) @try.catch) @exception.try
                  
                (throw_statement
                  (expression_statement)? @throw.expr) @exception.throw
            '''
        }
    
    def _create_instrumentation_point_from_capture(
        self, 
        query_name: str, 
        capture_name: str, 
        node, 
        source_code: str
    ) -> InstrumentationPoint:
        """Create C++-specific instrumentation points"""
        
        line = node.start_point.row + 1
        column = node.start_point.column + 1
        
        if query_name == 'functions':
            if capture_name in ['function.name', 'method.name']:
                name = self._extract_name_from_node(node, source_code)
                func_type = 'method' if capture_name.startswith('method') else 'function'
                return InstrumentationPoint(
                    type='function_enter',
                    subtype=func_type,
                    name=name,
                    line=line,
                    column=column,
                    context=f"{func_type.title()} entry: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
            elif capture_name in ['function.body', 'method.body']:
                func_name = self._find_function_name_from_body(node, source_code)
                func_type = 'method' if capture_name.startswith('method') else 'function'
                return InstrumentationPoint(
                    type='function_exit',
                    subtype=func_type,
                    name=func_name,
                    line=node.end_point.row + 1,
                    column=node.end_point.column + 1,
                    context=f"{func_type.title()} exit: {func_name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'classes':
            if capture_name in ['class.name', 'struct.name']:
                name = self._extract_name_from_node(node, source_code)
                class_type = capture_name.split('.')[0]  # 'class' or 'struct'
                return InstrumentationPoint(
                    type='class_enter',
                    subtype=class_type,
                    name=name,
                    line=line,
                    column=column,
                    context=f"{class_type.title()} definition: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'constructors':
            if capture_name in ['constructor.name', 'destructor.name']:
                name = self._extract_name_from_node(node, source_code)
                ctor_type = capture_name.split('.')[0]  # 'constructor' or 'destructor'
                return InstrumentationPoint(
                    type='constructor_enter' if ctor_type == 'constructor' else 'destructor_enter',
                    subtype=ctor_type,
                    name=name,
                    line=line,
                    column=column,
                    context=f"{ctor_type.title()}: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'loops':
            loop_type = capture_name.split('.')[1] if '.' in capture_name else 'loop'
            if capture_name in ['loop.for', 'loop.range_for', 'loop.while', 'loop.do']:
                return InstrumentationPoint(
                    type='loop_start',
                    subtype=loop_type,
                    name=f"{loop_type}_loop",
                    line=line,
                    column=column,
                    context=f"{loop_type.replace('_', '-').title()} loop at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'memory_ops':
            if capture_name == 'memory.new':
                return InstrumentationPoint(
                    type='memory_operation',
                    subtype='new',
                    name='new_allocation',
                    line=line,
                    column=column,
                    context=f"Memory allocation (new) at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'energy_intensive': True}
                )
            elif capture_name == 'memory.delete':
                return InstrumentationPoint(
                    type='memory_operation',
                    subtype='delete',
                    name='delete_deallocation',
                    line=line,
                    column=column,
                    context=f"Memory deallocation (delete) at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
            elif capture_name == 'memory.smart_ptr':
                smart_ptr_name = self._extract_name_from_node(node, source_code)
                return InstrumentationPoint(
                    type='smart_pointer',
                    subtype='creation',
                    name=smart_ptr_name,
                    line=line,
                    column=column,
                    context=f"Smart pointer creation: {smart_ptr_name} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'templates':
            if capture_name in ['template.function', 'template.class']:
                template_type = capture_name.split('.')[1]  # 'function' or 'class'
                return InstrumentationPoint(
                    type='template_instantiation',
                    subtype=template_type,
                    name=f"template_{template_type}",
                    line=line,
                    column=column,
                    context=f"Template {template_type} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'complex': True}
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
            if current.type in ['function_definition', 'method_definition', 'constructor_definition', 'destructor_definition']:
                for child in current.children:
                    if child.type == 'function_declarator':
                        for grandchild in child.children:
                            if grandchild.type == 'identifier':
                                return self._extract_name_from_node(grandchild, source_code)
            current = current.parent
        return 'unknown'
    
    def _generate_instrumentation_points_fallback(self, source_code: str) -> List[InstrumentationPoint]:
        """Regex-based fallback analysis for C++"""
        points = []
        lines = source_code.split('\n')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Function definitions (more flexible pattern for C++)
            func_match = re.match(r'^\s*(?:(?:virtual|static|inline|explicit)\s+)*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:final\s*)?\{?\s*$', line)
            if func_match and not any(keyword in line for keyword in ['if', 'while', 'for', 'switch', 'namespace']):
                func_name = func_match.group(1)
                if func_name not in ['if', 'else', 'while', 'for', 'do', 'switch', 'case', 'return', 'namespace']:
                    points.append(InstrumentationPoint(
                        type='function_enter',
                        subtype='function',
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
                    subtype='class',
                    name=class_name,
                    line=line_num,
                    column=class_match.start(1),
                    context=f"Class definition: {class_name}"
                ))
            
            # Struct definitions
            struct_match = re.match(r'^\s*struct\s+(\w+)', line)
            if struct_match:
                struct_name = struct_match.group(1)
                points.append(InstrumentationPoint(
                    type='class_enter',
                    subtype='struct',
                    name=struct_name,
                    line=line_num,
                    column=struct_match.start(1),
                    context=f"Struct definition: {struct_name}"
                ))
            
            # For loops (including range-based)
            for_match = re.match(r'^\s*for\s*\(', line)
            if for_match:
                loop_type = 'range_for' if ':' in line else 'for'
                points.append(InstrumentationPoint(
                    type='loop_start',
                    subtype=loop_type,
                    name=f'{loop_type}_loop',
                    line=line_num,
                    column=for_match.start(),
                    context=f"{loop_type.replace('_', '-').title()} loop at line {line_num}"
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
            
            # Memory operations
            new_match = re.search(r'\bnew\s+', line)
            if new_match:
                points.append(InstrumentationPoint(
                    type='memory_operation',
                    subtype='new',
                    name='new_allocation',
                    line=line_num,
                    column=new_match.start(),
                    context=f"Memory allocation (new) at line {line_num}",
                    metadata={'energy_intensive': True}
                ))
            
            delete_match = re.search(r'\bdelete\s+', line)
            if delete_match:
                points.append(InstrumentationPoint(
                    type='memory_operation',
                    subtype='delete',
                    name='delete_deallocation',
                    line=line_num,
                    column=delete_match.start(),
                    context=f"Memory deallocation (delete) at line {line_num}"
                ))
            
            # Smart pointer creation
            smart_ptr_match = re.search(r'\b(make_unique|make_shared|unique_ptr|shared_ptr)\s*[<(]', line)
            if smart_ptr_match:
                smart_ptr_name = smart_ptr_match.group(1)
                points.append(InstrumentationPoint(
                    type='smart_pointer',
                    subtype='creation',
                    name=smart_ptr_name,
                    line=line_num,
                    column=smart_ptr_match.start(),
                    context=f"Smart pointer creation: {smart_ptr_name} at line {line_num}"
                ))
        
        return points
    
    def _generate_instrumentation_call(self, checkpoint) -> str:
        """Generate C++ instrumentation call"""
        return (
            f"    codegreen_measure_checkpoint(\"{checkpoint.id}\", \"{checkpoint.type}\", "
            f"\"{checkpoint.name}\", {checkpoint.line_number}, \"{checkpoint.context}\");"
        )
    
    def instrument_code(self, source_code: str, checkpoints: List) -> str:
        """Instrument C++ code with measurement calls"""
        lines = source_code.split('\n')
        
        # Add instrumentation include at the top
        instrumented_include = (
            "#include <codegreen_runtime.h>\n"
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
        """Analyze C++ code for optimization opportunities"""
        suggestions = []
        
        # Check for raw pointer usage
        if re.search(r'\bnew\s+', source_code) and 'delete' not in source_code:
            suggestions.append("Consider using smart pointers (std::unique_ptr, std::shared_ptr) instead of raw pointers")
        
        # Check for inefficient loop patterns
        if re.search(r'for.*\.size\(\)', source_code):
            suggestions.append("Consider using range-based for loops or caching container size in loops")
        
        # Check for vector reallocations
        if 'std::vector' in source_code and 'reserve' not in source_code:
            suggestions.append("Consider reserving capacity for std::vector if you know the approximate size")
        
        # Check for template usage without concepts
        if 'template' in source_code and 'concept' not in source_code:
            suggestions.append("Consider using concepts (C++20) to constrain template parameters")
        
        # Check for exception handling performance
        exception_count = len(re.findall(r'\bthrow\b', source_code))
        if exception_count > 0:
            suggestions.append(f"Found {exception_count} throw statements - ensure exceptions are used for exceptional cases only")
        
        return suggestions