# CodeGreen Multi-Language Architecture v2.0

Based on research into tree-sitter best practices and analysis of tree-climber project.

## Current Issues with v1.0
- **Manual parser compilation**: Requires tree-sitter CLI installation
- **Hardcoded AST traversal**: Brittle node type checking in each adapter
- **Static linking**: All parsers must be compiled into the binary
- **No extensibility**: Adding new languages requires C++ code changes

## Proposed Architecture v2.0

### 1. Dynamic Language Registry

```python
# Language registry following tree-sitter-languages pattern
class LanguageRegistry:
    """Central registry for all supported languages"""
    
    def __init__(self):
        self._languages = {}
        self._parsers = {}
        
    def register_language(self, language_id: str, adapter_class: type):
        """Register a language adapter"""
        self._languages[language_id] = adapter_class
        
    def get_adapter(self, language_id: str) -> Optional['LanguageAdapter']:
        """Get adapter for language, with fallback support"""
        if language_id not in self._languages:
            return None
            
        try:
            # Try to get parser dynamically
            from tree_sitter_language_pack import get_parser
            parser = get_parser(language_id)
            return self._languages[language_id](parser)
        except ImportError:
            # Fallback: use basic regex-based analysis
            return BasicLanguageAdapter(language_id)
```

### 2. Query-Based Instrumentation

```python
# Instead of hardcoded node type checking
class QueryBasedInstrumenter:
    """Use tree-sitter queries for flexible instrumentation point detection"""
    
    def __init__(self, language: str):
        self.queries = self.load_queries(language)
        
    def load_queries(self, language: str) -> Dict[str, Query]:
        """Load instrumentation queries for language"""
        queries = {}
        
        # Function entry/exit points
        queries['functions'] = Query(language, """
            (function_definition
              name: (identifier) @function.name
              body: (_) @function.body) @function.definition
        """)
        
        # Loop constructs
        queries['loops'] = Query(language, """
            [(for_statement) (while_statement) (do_statement)] @loop
        """)
        
        return queries
        
    def find_instrumentation_points(self, tree: Tree) -> List[InstrumentationPoint]:
        """Find all points where measurements should be taken"""
        points = []
        
        for query_name, query in self.queries.items():
            captures = query.captures(tree.root_node)
            for node, capture_name in captures:
                point = InstrumentationPoint(
                    type=query_name,
                    node=node,
                    capture=capture_name,
                    line=node.start_point.row + 1,
                    column=node.start_point.column + 1
                )
                points.append(point)
                
        return points
```

### 3. Modular Language Adapters

```python
# Base adapter following tree-climber visitor pattern
class LanguageAdapter(ABC):
    """Base class for all language adapters"""
    
    def __init__(self, parser: Optional[Parser] = None):
        self.parser = parser
        self.instrumenter = QueryBasedInstrumenter(self.language_id) if parser else None
        
    @property
    @abstractmethod
    def language_id(self) -> str:
        """Language identifier (e.g., 'python', 'c', 'java')"""
        pass
        
    @abstractmethod 
    def get_file_extensions(self) -> List[str]:
        """File extensions supported by this language"""
        pass
        
    def generate_checkpoints(self, source_code: str) -> List[CodeCheckpoint]:
        """Generate instrumentation checkpoints for source code"""
        if self.parser:
            return self._generate_checkpoints_treesitter(source_code)
        else:
            return self._generate_checkpoints_fallback(source_code)
            
    def _generate_checkpoints_treesitter(self, source_code: str) -> List[CodeCheckpoint]:
        """Use tree-sitter for precise instrumentation"""
        tree = self.parser.parse(bytes(source_code, 'utf8'))
        points = self.instrumenter.find_instrumentation_points(tree)
        
        checkpoints = []
        for point in points:
            checkpoint = self._create_checkpoint_from_point(point, source_code)
            checkpoints.append(checkpoint)
            
        return checkpoints
        
    def _generate_checkpoints_fallback(self, source_code: str) -> List[CodeCheckpoint]:
        """Fallback to regex-based analysis when parser unavailable"""
        # Basic regex patterns for common constructs
        return self._regex_based_analysis(source_code)
```

### 4. Plugin Discovery System

```python
# Automatic plugin discovery
class LanguagePluginManager:
    """Manages language plugins with automatic discovery"""
    
    def __init__(self):
        self.registry = LanguageRegistry()
        self._discover_plugins()
        
    def _discover_plugins(self):
        """Automatically discover and register language plugins"""
        
        # 1. Built-in languages
        self._register_builtin_languages()
        
        # 2. Check tree-sitter-languages availability
        self._register_treesitter_languages()
        
        # 3. Look for external plugins
        self._register_external_plugins()
        
    def _register_treesitter_languages(self):
        """Register all available tree-sitter-languages parsers"""
        try:
            from tree_sitter_language_pack import get_parser
            
            # Common languages supported by tree-sitter-languages
            common_languages = ['python', 'c', 'cpp', 'java', 'javascript', 
                              'rust', 'go', 'typescript', 'bash']
                              
            for lang in common_languages:
                try:
                    parser = get_parser(lang)
                    adapter = self._create_generic_adapter(lang, parser)
                    self.registry.register_language(lang, adapter)
                    logger.info(f"✅ Registered {lang} via tree-sitter-languages")
                except Exception as e:
                    logger.debug(f"⚠️ {lang} not available: {e}")
                    
        except ImportError:
            logger.info("tree-sitter-languages not available, using fallback modes")
```

### 5. Configuration-Based Language Support

```python
# languages.yaml - External configuration
languages:
  python:
    extensions: [".py"]
    queries:
      functions: |
        (function_definition
          name: (identifier) @function.name) @function.def
      classes: |
        (class_definition
          name: (identifier) @class.name) @class.def
    fallback_patterns:
      function_def: "^\\s*def\\s+(\\w+)"
      class_def: "^\\s*class\\s+(\\w+)"
      
  c:
    extensions: [".c", ".h"]  
    queries:
      functions: |
        (function_definition
          declarator: (function_declarator
            declarator: (identifier) @function.name)) @function.def
    fallback_patterns:
      function_def: "^\\w+\\s+\\w+\\s*\\("
```

### 6. Benefits of New Architecture

1. **Zero Compilation**: Uses `tree-sitter-languages` package for instant parser availability
2. **Extensible**: New languages added via configuration files and plugins
3. **Graceful Degradation**: Falls back to regex when tree-sitter unavailable  
4. **Industry Standard**: Follows patterns from nvim-treesitter and tree-climber
5. **Future-Proof**: Easy to add new analysis types and measurement strategies

### 7. Migration Strategy

1. **Phase 1**: Implement new architecture alongside existing system
2. **Phase 2**: Add comprehensive query files for Python, C, C++, Java
3. **Phase 3**: Migrate CLI to use new plugin system
4. **Phase 4**: Remove old hardcoded adapter system
5. **Phase 5**: Add support for additional languages via community queries

This architecture transforms CodeGreen from a "compile each parser" system to a "plug and play" extensible platform that can support new languages with minimal effort.

## Implementation Status ✅

The v2.0 architecture has been **fully implemented** with the following components:

### Core System
- ✅ **Base Architecture** (`codegreen/languages/base.py`): Abstract adapter interface with tree-sitter + fallback support
- ✅ **Language Registry** (`codegreen/languages/registry.py`): Plugin-style registration and discovery
- ✅ **Plugin Manager** (`codegreen/languages/manager.py`): Automatic discovery with tree-sitter-languages integration
- ✅ **Integration Layer** (`codegreen/languages/integration.py`): Backward compatibility and high-level API

### Language Adapters
- ✅ **Python Adapter** (`codegreen/languages/adapters/python.py`): Complete with tree-sitter queries + regex fallback
- ✅ **C Adapter** (`codegreen/languages/adapters/c.py`): Function/loop detection, memory operation analysis
- ✅ **C++ Adapter** (`codegreen/languages/adapters/cpp.py`): Classes, templates, smart pointers, range-based loops
- ✅ **Java Adapter** (`codegreen/languages/adapters/java.py`): Methods, lambdas, streams, synchronization

### Key Features Implemented
1. **Query-Based Instrumentation**: Using tree-sitter queries instead of hardcoded AST traversal
2. **Dynamic Parser Loading**: Automatic detection via `tree-sitter-languages` package
3. **Graceful Fallbacks**: Regex-based analysis when tree-sitter unavailable
4. **Extensible Design**: Add new languages via configuration and plugins
5. **Backward Compatibility**: Works with existing CLI through integration layer

### Usage Example
```python
from codegreen.languages import get_language_service

service = get_language_service()

# Analyze any supported language
result = service.analyze_source_code(source_code, language_id='python')
print(f"Found {result['instrumentation_points']} measurement points")

# Get language info
info = service.get_language_info('java')
print(f"Java support: parser={info['parser_available']}, queries={info['queries_available']}")

# Batch analyze multiple files
results = service.batch_analyze_files(['src/main.c', 'app.py', 'Utils.java'])
```

### Integration Strategy
The new architecture is designed for **seamless migration**:

1. **Phase 1**: ✅ Implemented - New system works alongside existing v1
2. **Phase 2**: Update CLI to use `codegreen.languages.integration.analyze_code()`
3. **Phase 3**: Test with all existing functionality
4. **Phase 4**: Remove old hardcoded C++ adapters
5. **Phase 5**: Add community language support

### Immediate Benefits
- **Zero Compilation**: No more parser.c generation issues
- **Instant Language Support**: Python, C, C++, Java work immediately
- **Future-Proof**: Easy to add Rust, Go, TypeScript, etc.
- **Industry Standard**: Follows patterns from nvim-treesitter and tree-climber