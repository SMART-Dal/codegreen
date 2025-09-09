"""
Java Language Adapter for CodeGreen

Provides comprehensive Java code analysis using tree-sitter queries
with regex-based fallback support.
"""

import re
from typing import List, Dict
from ..base import LanguageAdapter, InstrumentationPoint


class JavaAdapter(LanguageAdapter):
    """Enhanced Java language adapter with query-based instrumentation"""
    
    @property
    def language_id(self) -> str:
        return "java"
    
    def get_file_extensions(self) -> List[str]:
        return [".java"]
    
    def get_query_definitions(self) -> Dict[str, str]:
        """Tree-sitter queries for Java instrumentation points"""
        return {
            # Method definitions
            'methods': '''
                (method_declaration
                  name: (identifier) @method.name
                  parameters: (_) @method.params
                  body: (block) @method.body) @method.def
                  
                (constructor_declaration
                  name: (identifier) @constructor.name
                  parameters: (_) @constructor.params
                  body: (constructor_body) @constructor.body) @constructor.def
            ''',
            
            # Class and interface definitions
            'classes': '''
                (class_declaration
                  name: (identifier) @class.name
                  body: (class_body) @class.body) @class.def
                  
                (interface_declaration
                  name: (identifier) @interface.name
                  body: (interface_body) @interface.body) @interface.def
                  
                (enum_declaration
                  name: (identifier) @enum.name
                  body: (enum_body) @enum.body) @enum.def
            ''',
            
            # Loop constructs
            'loops': '''
                (for_statement
                  init: (_) @loop.init
                  condition: (_) @loop.condition
                  update: (_) @loop.update
                  body: (_) @loop.body) @loop.for
                  
                (enhanced_for_statement
                  type: (_) @loop.type
                  name: (identifier) @loop.var
                  value: (_) @loop.iterable
                  body: (_) @loop.body) @loop.enhanced_for
                  
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
            
            # Method calls and invocations
            'calls': '''
                (method_invocation
                  object: (_) @call.object
                  name: (identifier) @call.method
                  arguments: (_) @call.args) @call.method_invocation
                  
                (method_invocation
                  name: (identifier) @call.name
                  arguments: (_) @call.args) @call.simple_invocation
            ''',
            
            # Exception handling
            'exceptions': '''
                (try_statement
                  body: (block) @try.body
                  handler: (catch_clause)* @try.catch
                  finalizer: (finally_clause)? @try.finally) @exception.try
                  
                (throw_statement
                  (expression) @throw.expr) @exception.throw
            ''',
            
            # Lambda expressions and streams (energy intensive)
            'lambdas': '''
                (lambda_expression
                  parameters: (_) @lambda.params
                  body: (_) @lambda.body) @lambda.def
            ''',
            
            # Collections and streams operations
            'collections': '''
                (method_invocation
                  object: (_) @stream.object
                  name: (identifier) @stream.operation
                  arguments: (_) @stream.args) @stream.call
                  (#match? @stream.operation "^(stream|map|filter|reduce|collect|forEach|parallel)$")
            ''',
            
            # Synchronization constructs
            'synchronization': '''
                (synchronized_statement
                  lock: (_) @sync.lock
                  body: (block) @sync.body) @sync.statement
            '''
        }
    
    def _create_instrumentation_point_from_capture(
        self, 
        query_name: str, 
        capture_name: str, 
        node, 
        source_code: str
    ) -> InstrumentationPoint:
        """Create Java-specific instrumentation points"""
        
        line = node.start_point.row + 1
        column = node.start_point.column + 1
        
        if query_name == 'methods':
            if capture_name in ['method.name', 'constructor.name']:
                name = self._extract_name_from_node(node, source_code)
                method_type = 'constructor' if capture_name.startswith('constructor') else 'method'
                return InstrumentationPoint(
                    type='method_enter',
                    subtype=method_type,
                    name=name,
                    line=line,
                    column=column,
                    context=f"{method_type.title()} entry: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
            elif capture_name in ['method.body', 'constructor.body']:
                method_name = self._find_method_name_from_body(node, source_code)
                method_type = 'constructor' if capture_name.startswith('constructor') else 'method'
                return InstrumentationPoint(
                    type='method_exit',
                    subtype=method_type,
                    name=method_name,
                    line=node.end_point.row + 1,
                    column=node.end_point.column + 1,
                    context=f"{method_type.title()} exit: {method_name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'classes':
            if capture_name in ['class.name', 'interface.name', 'enum.name']:
                name = self._extract_name_from_node(node, source_code)
                class_type = capture_name.split('.')[0]  # 'class', 'interface', or 'enum'
                return InstrumentationPoint(
                    type='class_enter',
                    subtype=class_type,
                    name=name,
                    line=line,
                    column=column,
                    context=f"{class_type.title()} definition: {name}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'loops':
            loop_type = capture_name.split('.')[1] if '.' in capture_name else 'loop'
            if capture_name in ['loop.for', 'loop.enhanced_for', 'loop.while', 'loop.do']:
                display_type = loop_type.replace('_', '-')
                return InstrumentationPoint(
                    type='loop_start',
                    subtype=loop_type,
                    name=f"{loop_type}_loop",
                    line=line,
                    column=column,
                    context=f"{display_type.title()} loop at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'calls':
            if capture_name in ['call.method', 'call.name']:
                method_name = self._extract_name_from_node(node, source_code)
                call_type = 'method_call' if capture_name == 'call.method' else 'simple_call'
                return InstrumentationPoint(
                    type='method_call',
                    subtype=call_type,
                    name=method_name,
                    line=line,
                    column=column,
                    context=f"Method call: {method_name} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name}
                )
        
        elif query_name == 'lambdas':
            if capture_name == 'lambda.def':
                return InstrumentationPoint(
                    type='lambda_expression',
                    subtype='definition',
                    name='lambda',
                    line=line,
                    column=column,
                    context=f"Lambda expression at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'energy_intensive': True}
                )
        
        elif query_name == 'collections':
            if capture_name == 'stream.operation':
                operation_name = self._extract_name_from_node(node, source_code)
                return InstrumentationPoint(
                    type='stream_operation',
                    subtype='operation',
                    name=operation_name,
                    line=line,
                    column=column,
                    context=f"Stream operation: {operation_name} at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'energy_intensive': True}
                )
        
        elif query_name == 'synchronization':
            if capture_name == 'sync.statement':
                return InstrumentationPoint(
                    type='synchronization',
                    subtype='synchronized_block',
                    name='synchronized',
                    line=line,
                    column=column,
                    context=f"Synchronized block at line {line}",
                    metadata={'query': query_name, 'capture': capture_name, 'thread_critical': True}
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
    
    def _find_method_name_from_body(self, body_node, source_code: str) -> str:
        """Extract method name from method body by looking at parent"""
        current = body_node.parent
        while current:
            if current.type in ['method_declaration', 'constructor_declaration']:
                for child in current.children:
                    if child.type == 'identifier':
                        return self._extract_name_from_node(child, source_code)
            current = current.parent
        return 'unknown'
    
    def _generate_instrumentation_points_fallback(self, source_code: str) -> List[InstrumentationPoint]:
        """Regex-based fallback analysis for Java"""
        points = []
        lines = source_code.split('\n')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Method declarations (including constructors)
            method_match = re.match(r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:,\s*\w+)*)?\s*\{?\s*$', line)
            if method_match and not any(keyword in line for keyword in ['if', 'while', 'for', 'switch', 'class', 'interface']):
                method_name = method_match.group(1)
                if method_name not in ['if', 'else', 'while', 'for', 'do', 'switch', 'case', 'return', 'class', 'interface']:
                    points.append(InstrumentationPoint(
                        type='method_enter',
                        subtype='method',
                        name=method_name,
                        line=line_num,
                        column=method_match.start(1),
                        context=f"Method entry: {method_name}"
                    ))
            
            # Class declarations
            class_match = re.match(r'^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*class\s+(\w+)', line)
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
            
            # Interface declarations
            interface_match = re.match(r'^\s*(?:(?:public|private|protected)\s+)*interface\s+(\w+)', line)
            if interface_match:
                interface_name = interface_match.group(1)
                points.append(InstrumentationPoint(
                    type='class_enter',
                    subtype='interface',
                    name=interface_name,
                    line=line_num,
                    column=interface_match.start(1),
                    context=f"Interface definition: {interface_name}"
                ))
            
            # For loops (traditional)
            for_match = re.match(r'^\s*for\s*\(', line)
            if for_match:
                loop_type = 'enhanced_for' if ':' in line else 'for'
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
            
            # Lambda expressions
            lambda_match = re.search(r'\([^)]*\)\s*->', line)
            if lambda_match:
                points.append(InstrumentationPoint(
                    type='lambda_expression',
                    subtype='definition',
                    name='lambda',
                    line=line_num,
                    column=lambda_match.start(),
                    context=f"Lambda expression at line {line_num}",
                    metadata={'energy_intensive': True}
                ))
            
            # Stream operations
            stream_match = re.search(r'\.(stream|map|filter|reduce|collect|forEach|parallel)\s*\(', line)
            if stream_match:
                operation_name = stream_match.group(1)
                points.append(InstrumentationPoint(
                    type='stream_operation',
                    subtype='operation',
                    name=operation_name,
                    line=line_num,
                    column=stream_match.start(),
                    context=f"Stream operation: {operation_name} at line {line_num}",
                    metadata={'energy_intensive': True}
                ))
            
            # Synchronized blocks
            sync_match = re.match(r'^\s*synchronized\s*\(', line)
            if sync_match:
                points.append(InstrumentationPoint(
                    type='synchronization',
                    subtype='synchronized_block',
                    name='synchronized',
                    line=line_num,
                    column=sync_match.start(),
                    context=f"Synchronized block at line {line_num}",
                    metadata={'thread_critical': True}
                ))
        
        return points
    
    def _generate_instrumentation_call(self, checkpoint) -> str:
        """Generate Java instrumentation call"""
        return (
            f"        CodeGreenRuntime.measureCheckpoint(\"{checkpoint.id}\", \"{checkpoint.type}\", "
            f"\"{checkpoint.name}\", {checkpoint.line_number}, \"{checkpoint.context}\");"
        )
    
    def instrument_code(self, source_code: str, checkpoints: List) -> str:
        """Instrument Java code with measurement calls"""
        lines = source_code.split('\n')
        
        # Find where to insert the runtime class
        instrumented_runtime = (
            "import java.util.concurrent.atomic.AtomicLong;\n"
            "import java.time.Instant;\n"
            "public class CodeGreenRuntime {\n"
            "    private static final AtomicLong sessionId = new AtomicLong(System.currentTimeMillis());\n"
            "    public static void measureCheckpoint(String id, String type, String name, int line, String context) {\n"
            "        long timestamp = Instant.now().toEpochMilli();\n"
            "        System.out.println(\"CODEGREEN_CHECKPOINT: \" + id + \"|\" + type + \"|\" + name + \"|\" + line + \"|\" + context + \"|\" + timestamp);\n"
            "    }\n"
            "}\n"
        )
        
        # Find insertion point after package declaration and imports
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('package ') or line.strip().startswith('import '):
                insert_pos = i + 1
            elif line.strip() and not line.strip().startswith('//') and not line.strip().startswith('/*'):
                break
        
        lines.insert(insert_pos, instrumented_runtime)
        
        # Apply basic instrumentation
        return self._basic_instrumentation('\n'.join(lines), checkpoints)
    
    def analyze_code(self, source_code: str) -> List[str]:
        """Analyze Java code for optimization opportunities"""
        suggestions = []
        
        # Check for ArrayList usage in loops
        if 'ArrayList' in source_code and re.search(r'for\s*\(', source_code):
            suggestions.append("Consider using LinkedList for frequent insertions/deletions or pre-sizing ArrayList")
        
        # Check for HashMap without initial capacity
        if re.search(r'new\s+HashMap\s*\(\s*\)', source_code):
            suggestions.append("Consider pre-sizing HashMap with expected capacity to avoid rehashing")
        
        # Check for string concatenation in loops
        if re.search(r'\+=.*in\s+for', source_code) and 'String' in source_code:
            suggestions.append("Use StringBuilder for string concatenation in loops")
        
        # Check for inefficient loop patterns
        if re.search(r'for.*\.size\(\)', source_code):
            suggestions.append("Cache collection size or use enhanced for-loop to avoid repeated method calls")
        
        # Check for object creation in loops
        if re.search(r'for.*{[^}]*new\s+', source_code, re.DOTALL):
            suggestions.append("Consider object pooling or reusing objects in loops to reduce GC pressure")
        
        # Check for stream operations complexity
        stream_count = len(re.findall(r'\.(stream|map|filter|reduce|collect)', source_code))
        if stream_count > 3:
            suggestions.append(f"Found {stream_count} stream operations - consider performance impact of complex stream chains")
        
        return suggestions