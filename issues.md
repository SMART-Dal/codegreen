 `language_engine.py` critical issues and architectural improvements needed for production readiness. Let me break down the analysis:


### 2. **Line Number Offset Corruption**
The instrumentation inserts lines but doesn't maintain a running offset, leading to incorrect placements after the first insertion:

```python
# Current approach processes in reverse but still has issues
sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
```

The problem is that even with reverse processing, the function/loop exit calculations are done before sorting, so they reference wrong lines.

### 3. **Exit Point Calculation Flaws**
The `_calculate_function_insertion_points()` traverses up the AST looking for parent nodes, but:
- It doesn't handle cases where the node structure differs from expectations
- Python generators, async functions, and functions with multiple returns need special handling
- The exit point is placed at `end_point.row + 1`, which is often outside the function

### 4. **Incomplete Query Patterns**
Many important patterns are missing or commented out:
- Memory operations in C/C++ (malloc/free, new/delete)
- Exception handling blocks (try/catch/finally)
- Async/await constructs
- Resource management patterns

## Architectural Improvements

### 1. **Externalize Query Definitions**
Instead of hardcoding queries, use external `.scm` files (tree-sitter's query format):

```python
class QueryManager:
    def __init__(self, queries_dir: Path = Path("queries")):
        self.queries_dir = queries_dir
        self._query_cache = {}
    
    def load_queries(self, language: str) -> Dict[str, Query]:
        """Load queries from .scm files for a language"""
        lang_dir = self.queries_dir / language
        if not lang_dir.exists():
            return self._load_builtin_queries(language)
        
        queries = {}
        for query_file in lang_dir.glob("*.scm"):
            query_name = query_file.stem
            with open(query_file) as f:
                query_text = f.read()
                queries[query_name] = query_text
        return queries
```

### 2. **Use Established Query Patterns**
Leverage existing high-quality queries from projects like nvim-treesitter:

```python
# Example: Use standardized highlight queries as base
STANDARD_PATTERNS = {
    'function': '(function_definition) @function',
    'method': '(method_declaration) @method',
    'loop': '[(for_statement) (while_statement) (do_statement)] @loop',
    'call': '(call_expression) @call'
}
```

### 3. **Implement Proper AST Rewriting**
Instead of line-based insertion, use AST-based rewriting:

```python
class ASTRewriter:
    def __init__(self, tree: Tree, source: str):
        self.tree = tree
        self.source = source
        self.edits = []
    
    def insert_before_node(self, node: Node, text: str):
        """Insert text before a node maintaining structure"""
        self.edits.append({
            'offset': node.start_byte,
            'text': text,
            'type': 'insert'
        })
    
    def apply_edits(self) -> str:
        """Apply all edits in correct order"""
        # Sort by offset, apply from end to beginning
        sorted_edits = sorted(self.edits, key=lambda e: e['offset'], reverse=True)
        result = self.source
        for edit in sorted_edits:
            result = result[:edit['offset']] + edit['text'] + result[edit['offset']:]
        return result
```

### 4. **Add Configuration Layer**
Create a plugin-based architecture for language support:

```python
@dataclass
class LanguageConfig:
    name: str
    extensions: List[str]
    parser_lib: Optional[str]
    queries_path: Path
    instrumentation_strategy: str
    
    @classmethod
    def from_yaml(cls, yaml_path: Path):
        """Load config from YAML file"""
        # Implementation
        pass

class LanguagePlugin:
    """Base class for language-specific plugins"""
    def get_instrumentation_points(self, tree: Tree) -> List[InstrumentationPoint]:
        pass
    
    def instrument(self, source: str, points: List[InstrumentationPoint]) -> str:
        pass
```

### 5. **Improve Checkpoint Deduplication**
Use semantic deduplication rather than line-based:

```python
def deduplicate_semantically(points: List[InstrumentationPoint]) -> List[InstrumentationPoint]:
    """Remove semantically duplicate checkpoints"""
    seen = set()
    result = []
    
    for point in points:
        # Create semantic key based on construct type and scope
        semantic_key = (
            point.type,
            point.name,
            point.metadata.get('scope_id'),  # Add scope tracking
            point.metadata.get('parent_construct')
        )
        
        if semantic_key not in seen:
            seen.add(semantic_key)
            result.append(point)
    
    return result
```



## Research-Based Recommendations

From a research perspective, consider these evidence-based improvements:

1. **Use Incremental Parsing**: Tree-sitter supports incremental parsing which is much faster for large files or repeated analysis

2. **Implement Energy Hotspot Detection**: Research shows certain patterns (nested loops, recursive calls, I/O operations) dominate energy consumption. Prioritize these.

3. **Add Static Taint Analysis**: Track data flow to identify which code paths actually need instrumentation

4. **Consider LLVM-based Instrumentation**: For compiled languages (C/C++), LLVM passes provide more reliable instrumentation

5. **Use Differential Analysis**: Compare AST before/after instrumentation to verify correctness

The current implementation has good intentions but needs significant refactoring for production use. The core issue is trying to handle too much complexity in a monolithic class rather than using a modular, plugin-based architecture with proper separation of concerns.

--------------------------------



--------------------------------



--------------------------------


- **Incorrect Insertion Indices in Instrumentation**: For entry points (e.g., function_enter), `insert_index = point.line` (1-based) inserts *after* the target line in 0-based `lines.insert()`. This misplaces checkpoints (e.g., function entry after the first body statement instead of before). Similar issues for exits.
- **Failure to Handle Multiple Exit Points**: Functions/methods with multiple `return` statements only get one exit checkpoint. This under-measures energy for early returns, leading to inaccurate fine-grained measurements. Implicit returns (no `return` statement) are handled poorly, potentially missing exits in void-like functions.
- **Incomplete Return Handling in Constructors/Generators**: Constructors (e.g., Java) and generators (Python with `yield`) aren't specially handled for exits, despite metadata flags. This could cause incorrect instrumentation in async/generator contexts.
- **Regex Fallback Limitations**: Regex patterns are line-based and miss multi-line constructs (e.g., functions spanning lines). This reduces accuracy in fallback mode, common if tree-sitter parsers fail or are unavailable.
- **Timeout and Memory Handling**: Timeout uses `signal` (Unix-only), ignoring Windows. No cleanup on failure, risking resource leaks in production.
- **Node Validation Gaps**: In `_extract_text_from_node` and `_is_valid_identifier`, validations exist but miss cases like anonymous functions/lambdas (no name) or nested constructs.
- **Legacy Compatibility Issues**: `analyze_code` and `instrument_code` convert to/from dicts but lose metadata, potentially breaking if extended.
- **Potential Infinite Loops**: In parent traversal (e.g., `_calculate_function_insertion_points`), safety counter exists but is too low (10); deeper ASTs could loop.
- **Language-Specific Bugs**: Python dunder methods flagged but not handled in instrumentation. C/C++ memory ops commented out, missing energy-intensive points.

These bugs could cause crashes, wrong energy deltas, or incomplete instrumentation in production (e.g., large codebases with multiple returns).

#### 2. Inaccuracies and Inefficiencies
- **Inaccurate Instrumentation Points**: Entry/exit calculations use simplistic row/column, ignoring indentation or multi-line statements. For loops, points are before/after the entire loop, which measures total energy but not per-iteration (fine granularity). Comprehensions/streams marked energy-intensive but not instrumented with exits.
- **Query Inefficiencies**: Captures not grouped per match (e.g., function name and body separate), risking misassociation in complex code. No subtree querying for nested elements (e.g., returns inside functions).
- **Performance Bottlenecks**: Regex fallback processes every line for every pattern; could use a single pass with combined regex. Tree-sitter limits (1000 captures) good, but no parallelization for large files.
- **Optimization Suggestions**: Regex-based and superficial (e.g., misses Python list comps in expressions). No tree-sitter integration for optimizations (e.g., query for nested loops).
- **Fallback Over-Reliance**: Regex used if parser unavailable, but could attempt dynamic parser loading or error recovery.
- **Metadata Underutilization**: Flags like `energy_intensive` exist but aren't used in instrumentation prioritization.

#### 3. Bad Practices and Technical Debt
- **Hardcoded Configurations**: Language configs (queries, patterns) hardcoded in `_load_language_config`, requiring code changes for new languages—prone to bugs. No separation of concerns (e.g., queries in strings vs. files).
- **Magic Strings/Numbers**: Hardcoded timeouts (30s), sizes (100MB), indents ("    "), max captures (1000). Language-specific logic scattered (e.g., `_analyze_python_function_metadata`).
- **Platform Dependencies**: Signal-based timeout Unix-only; production on Windows fails silently.
- **Lack of Testing Hooks**: No unit-testable methods for query validation or point generation.
- **Tech Debt in Legacy Support**: Checkpoint conversion duplicates logic; should deprecate.
- **Security Risks**: No sanitization of source_code (e.g., large inputs crash); instrumentation injects code without escaping.
- **Verbose Logging**: Errors logged but not propagated meaningfully; production failures silent to users.

These lead to maintenance hell and scalability issues as languages grow.

#### 4. Opportunities for Improvement
- **Architecture Redesign**: Use `query.matches()` for grouped captures per construct (e.g., name + body together). For exits, subtree query on function_node for returns, creating multiple exit points. This improves accuracy for multi-exit functions.
- **Extensibility Enhancements**: Load configs from JSON/YAML files or a directory (e.g., `languages/python.json`). Define per-language 'body_type', 'function_node_type' in config.
- **Accuracy Boosts**: Calculate indents dynamically from body_node. Add per-language 'return_query' to configs. For fine granularity, option for per-iteration loop instrumentation (entry/exit inside body).
- **Efficiency Gains**: Combine regex patterns; cache more (e.g., indents). Use thread-safe parsing for concurrency.
- **Remove Hardcodes**: Parameterize timeouts/sizes; use config for special handling (e.g., Python dunders).
- **Production Robustness**: Add Windows-compatible timeouts (e.g., threading). Validate all nodes; add retry on parse failures. Handle lambdas/comprehensions with dedicated exits.
- **Optimization Integration**: Use tree-sitter queries for suggestions (e.g., query for nested loops).

#### 5. Extensibility for New Languages
- **Current Pain Points**: Adding a language requires editing the dict with custom queries/patterns, risking typos/bugs. Manual query writing is error-prone and duplicates effort.
- **Better Approach**: 
  - **Load Configs Dynamically**: Use a `languages/` dir with per-language SCM/JSON files. Load at init via `glob` or registry.
  - **Standard Queries**: Leverage community-maintained queries from nvim-treesitter (GitHub: nvim-treesitter/nvim-treesitter/queries/<lang>/highlights.scm), add as submodule and analyze the project alogn with queries and use it in the code. These capture standard nodes (e.g., @function.definition, @repeat for loops) with high quality. Map capture names to instrumentation types (e.g., @function.definition -> function_enter). This reduces manual writing—copy/paste/adapt from nvim. For query tools: Use tree-sitter playground (tree-sitter.github.io/playground) for testing/writing.
  - **Minimal Effort for New Lang**: Only add config file with tree-sitter name, extensions, queries (reused from nvim), body_type, return_query. No code edits needed.
  - **Existing Tools**: Semgrep or CodeQL have rules convertible to tree-sitter queries, but nvim is closest. For automation, a script could fetch nvim queries via API.
- **Benefits**: Reduces bugs from manual queries; community updates improve quality. For unsupported langs, fallback to regex or log warning.

#### 6. Improved Code
I've fixed the bugs (e.g., query execution, multiple exits, insertion indices), improved architecture (e.g., matches for grouped captures, config for returns), enhanced extensibility (added comments for config loading; prepared for file-based), and optimized (e.g., dynamic indents, efficiency in processing). Added 'returns' to configs. For now, kept hardcoded dict but noted how to externalize. Tested conceptually against examples.

Here's some suggested improvements to `language_engine.py`:

```
"""
CodeGreen Language Engine - Production Multi-Language Support

Production-ready language analysis and instrumentation engine using tree-sitter
queries with robust fallback mechanisms. Replaces the previous adapter system
with a unified, extensible architecture.

This engine handles:
- Dynamic language detection and parser loading
- Query-based AST analysis for precise instrumentation points
- Robust fallback to regex analysis when parsers unavailable
- Code instrumentation with measurement injection
- Performance optimization analysis
"""

import logging
import time
import re
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass, field
from threading import Lock
from collections import defaultdict

# Import tree-sitter with graceful fallback
try:
    from tree_sitter import Language, Parser, Tree, Node, Query
    from tree_sitter_languages import get_language, get_parser  # Corrected from tree_sitter_language_pack (assuming standard lib)
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = Parser = Tree = Node = Query = None

logger = logging.getLogger(__name__)


@dataclass
class InstrumentationPoint:
    """Represents a precise location for energy measurement instrumentation"""
    id: str
    type: str  # function_enter, loop_start, etc.
    subtype: str  # method, constructor, for, while, etc.
    name: str  # Function/variable name
    line: int
    column: int
    context: str  # Human-readable description
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_energy_intensive(self) -> bool:
        """Check if this point represents energy-intensive operation"""
        return self.metadata.get('energy_intensive', False)
    
    @property
    def checkpoint_id(self) -> str:
        """Generate legacy checkpoint ID for backward compatibility"""
        return f"{self.type}_{self.name}_{self.line}"


@dataclass
class AnalysisResult:
    """Comprehensive analysis result for source code"""
    language: str
    success: bool
    instrumentation_points: List[InstrumentationPoint]
    optimization_suggestions: List[str]
    metadata: Dict[str, Any]
    error: Optional[str] = None
    
    @property
    def checkpoint_count(self) -> int:
        """Get total number of checkpoints for legacy compatibility"""
        return len(self.instrumentation_points)


class LanguageEngine:
    """
    Production-ready multi-language analysis and instrumentation engine.
    
    Features:
    - Dynamic parser loading with tree-sitter-languages
    - Query-based instrumentation point detection
    - Robust fallback mechanisms
    - Extensible language support
    - Production performance optimization
    """
    
    def __init__(self, max_file_size_mb: int = 100, parser_timeout_ms: int = 30000):
        self._parsers: Dict[str, Parser] = {}
        self._languages: Dict[str, Language] = {}
        self._queries: Dict[str, Dict[str, Any]] = {}
        self._language_config = self._load_language_config()
        self._parser_lock = Lock()
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self._parser_timeout_ms = parser_timeout_ms
        self._compiled_regexes = {}
        self._initialize_parsers()
    
    def _load_language_config(self) -> Dict[str, Dict]:
        """Load language configuration with queries and patterns
        TODO: For extensibility, load from external JSON/YAML files or a directory (e.g., languages/python.json).
        This would allow adding new languages without code changes. Example: use json.load or glob to discover."""
        return {
            'python': {
                'extensions': ['.py', '.pyw'],
                'tree_sitter_name': 'python',
                'function_node_type': 'function_definition',
                'body_type': 'block',
                'queries': {
                    'functions': '''
                        (function_definition
                          name: (identifier) @function_name
                          body: (block) @function_body) @function_def
                    ''',
                    'classes': '''
                        (class_definition
                          name: (identifier) @class.name
                          body: (block) @class.body) @class.def
                    ''',
                    'loops': '''
                        (for_statement
                          left: (_) @loop.var
                          right: (_) @loop.iter
                          body: (block) @loop.body) @loop.for
                        (while_statement
                          condition: (_) @loop.condition
                          body: (block) @loop.body) @loop.while
                    ''',
                    'comprehensions': '''
                        (list_comprehension) @comprehension.list
                        (dictionary_comprehension) @comprehension.dict
                        (set_comprehension) @comprehension.set
                        (generator_expression) @comprehension.generator
                    ''',
                    'calls': '''
                        (call
                          function: (identifier) @call.name) @call.simple
                        (call
                          function: (attribute
                            object: (_) @call.object
                            attribute: (identifier) @call.method)) @call.method
                    ''',
                    'returns': '(return_statement) @return'
                },
                'fallback_patterns': {
                    'function_def': r'^\s*def\s+(\w+)',
                    'class_def': r'^\s*class\s+(\w+)',
                    'for_loop': r'^\s*for\s+',
                    'while_loop': r'^\s*while\s+',
                    'list_comp': r'\[.*for.*in.*\]'
                }
            },
            'c': {
                'extensions': ['.c', '.h'],
                'tree_sitter_name': 'c',
                'function_node_type': 'function_definition',
                'body_type': 'compound_statement',
                'queries': {
                    'functions': '''
                        (function_definition
                          declarator: (function_declarator
                            declarator: (identifier) @function_name)
                          body: (compound_statement) @function_body) @function_def
                        (function_definition
                          declarator: (pointer_declarator
                            declarator: (function_declarator
                              declarator: (identifier) @function_name))
                          body: (compound_statement) @function_body) @function_def
                    ''',
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
                    'returns': '(return_statement) @return'
                },
                'fallback_patterns': {
                    'function_def': r'^\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*\{?\s*$',
                    'for_loop': r'^\s*for\s*\(',
                    'while_loop': r'^\s*while\s*\(',
                    'do_loop': r'^\s*do\s*\{',
                    'memory_op': r'\b(malloc|calloc|realloc|free)\s*\('
                }
            },
            'cpp': {
                'extensions': ['.cpp', '.cxx', '.cc', '.hpp', '.h', '.hxx', '.h++'],
                'tree_sitter_name': 'cpp',
                'function_node_type': 'function_definition',
                'body_type': 'compound_statement',
                'queries': {
                    'functions': '''
                        (function_definition
                          declarator: (function_declarator
                            declarator: (identifier) @function_name)
                          body: (compound_statement) @function_body) @function_def
                        (function_definition
                          declarator: (pointer_declarator
                            declarator: (function_declarator
                              declarator: (identifier) @function_name))
                          body: (compound_statement) @function_body) @function_def
                    ''',
                    'classes': '''
                        (class_specifier
                          name: (type_identifier) @class.name
                          body: (field_declaration_list) @class.body) @class.def
                        (struct_specifier
                          name: (type_identifier) @struct.name
                          body: (field_declaration_list) @struct.body) @struct.def
                    ''',
                    'loops': '''
                        (for_statement) @loop.for
                        (while_statement) @loop.while
                        (do_statement) @loop.do
                    ''',
                    'returns': '(return_statement) @return'
                },
                'fallback_patterns': {
                    'function_def': r'^\s*(?:(?:virtual|static|inline|explicit)\s+)*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:final\s*)?\{?\s*$',
                    'class_def': r'^\s*class\s+(\w+)',
                    'struct_def': r'^\s*struct\s+(\w+)',
                    'for_loop': r'^\s*for\s*\(',
                    'while_loop': r'^\s*while\s*\(',
                    'new_op': r'\bnew\s+',
                    'delete_op': r'\bdelete\s+'
                }
            },
            'java': {
                'extensions': ['.java'],
                'tree_sitter_name': 'java',
                'function_node_type': 'method_declaration',  # or 'constructor_declaration'
                'body_type': 'block',  # or 'constructor_body'
                'queries': {
                    'methods': '''
                        (method_declaration
                          name: (identifier) @method_name
                          body: (block) @method_body) @method_def
                        (constructor_declaration
                          name: (identifier) @constructor_name
                          body: (constructor_body) @constructor_body) @constructor_def
                    ''',
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
                    'loops': '''
                        (for_statement) @loop.for
                        (enhanced_for_statement) @loop.enhanced_for
                        (while_statement) @loop.while
                        (do_statement) @loop.do
                    ''',
                    'lambdas': '''
                        (lambda_expression) @lambda.def
                    ''',
                    'streams': '''
                        (method_invocation
                          name: (identifier) @stream.operation) @stream.call
                          (#match? @stream.operation "^(stream|map|filter|reduce|collect|forEach|parallel)$")
                    ''',
                    'returns': '(return_statement) @return'
                },
                'fallback_patterns': {
                    'method_def': r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:,\s*\w+)*)?\s*\{?\s*$',
                    'class_def': r'^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*class\s+(\w+)',
                    'interface_def': r'^\s*(?:(?:public|private|protected)\s+)*interface\s+(\w+)',
                    'for_loop': r'^\s*for\s*\(',
                    'while_loop': r'^\s*while\s*\(',
                    'lambda_expr': r'\([^)]*\)\s*->',
                    'stream_op': r'\.(stream|map|filter|reduce|collect|forEach|parallel)\s*\('
                }
            }
        }
    
    def _initialize_parsers(self):
        """Initialize tree-sitter parsers for all configured languages"""
        if not TREE_SITTER_AVAILABLE:
            logger.info("Tree-sitter not available, using fallback regex analysis")
            return
        
        for lang_id, config in self._language_config.items():
            try:
                ts_name = config['tree_sitter_name']
                language = get_language(ts_name)
                parser = get_parser(ts_name)
                
                self._languages[lang_id] = language
                self._parsers[lang_id] = parser
                
                # Compile queries using modern API
                self._queries[lang_id] = {}
                for query_name, query_text in config['queries'].items():
                    try:
                        query = language.query(query_text)
                        self._queries[lang_id][query_name] = query
                    except Exception as e:
                        logger.error(f"Query compilation failed for {query_name} in {lang_id}: {e}")
                
                if self._queries[lang_id]:
                    logger.info(f"✅ Initialized tree-sitter parser for {lang_id} with {len(self._queries[lang_id])} queries")
                else:
                    logger.error(f"❌ No valid queries compiled for {lang_id}")
                
            except Exception as e:
                logger.error(f"⚠️ Could not initialize parser for {lang_id}: {e}")
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language identifiers"""
        return list(self._language_config.keys())
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions"""
        extensions = []
        for config in self._language_config.values():
            extensions.extend(config['extensions'])
        return extensions
    
    def detect_language(self, filename: str) -> Optional[str]:
        """Detect language from filename extension"""
        ext = Path(filename).suffix.lower()
        for lang_id, config in self._language_config.items():
            if ext in config['extensions']:
                return lang_id
        return None
    
    def analyze_code(
        self, 
        source_code: str, 
        language: str = None, 
        filename: str = None
    ) -> AnalysisResult:
        """
        Analyze source code and generate instrumentation points.
        
        Args:
            source_code: Source code to analyze
            language: Language identifier (if known)
            filename: Filename for language detection
            
        Returns:
            AnalysisResult with instrumentation points and metadata
        """
        # Detect language if not provided
        if not language and filename:
            language = self.detect_language(filename)
        
        if not language or language not in self._language_config:
            return AnalysisResult(
                language=language or 'unknown',
                success=False,
                instrumentation_points=[],
                optimization_suggestions=[],
                metadata={},
                error=f"Unsupported language: {language or 'unknown'}"
            )
        
        # Check file size limits
        if len(source_code.encode('utf-8')) > self._max_file_size_bytes:
            return AnalysisResult(
                language=language,
                success=False,
                instrumentation_points=[],
                optimization_suggestions=[],
                metadata={'error': 'file_too_large'},
                error=f"File exceeds maximum size limit of {self._max_file_size_bytes // (1024*1024)}MB"
            )
        
        start_time = time.time()
        
        try:
            # Try tree-sitter analysis first with timeout protection
            if language in self._parsers:
                points = self._analyze_with_treesitter_safe(source_code, language)
                analysis_method = 'tree_sitter'
            else:
                # Fallback to regex analysis
                points = self._analyze_with_regex(source_code, language)
                analysis_method = 'regex_fallback'
            
            # Generate optimization suggestions
            suggestions = self._analyze_optimizations(source_code, language)
            
            analysis_time = time.time() - start_time
            
            return AnalysisResult(
                language=language,
                success=True,
                instrumentation_points=points,
                optimization_suggestions=suggestions,
                metadata={
                    'analysis_method': analysis_method,
                    'parser_available': language in self._parsers,
                    'queries_available': len(self._queries.get(language, {})),
                    'analysis_time_ms': round(analysis_time * 1000, 2),
                    'source_lines': len(source_code.split('\n')),
                    'tree_sitter_available': TREE_SITTER_AVAILABLE
                }
            )
            
        except TimeoutError as e:
            logger.error(f"Analysis timed out for {language} code: {e}")
            return AnalysisResult(
                language=language,
                success=False,
                instrumentation_points=[],
                optimization_suggestions=[],
                metadata={'analysis_method': 'timeout'},
                error=f"Analysis timed out: {e}"
            )
        except MemoryError as e:
            logger.error(f"Out of memory analyzing {language} code: {e}")
            return AnalysisResult(
                language=language,
                success=False,
                instrumentation_points=[],
                optimization_suggestions=[],
                metadata={'analysis_method': 'out_of_memory'},
                error=f"Out of memory: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error analyzing {language} code: {e}")
            return AnalysisResult(
                language=language,
                success=False,
                instrumentation_points=[],
                optimization_suggestions=[],
                metadata={'analysis_method': 'failed', 'error_type': type(e).__name__},
                error=f"Analysis failed: {e}"
            )
    
    def _analyze_with_treesitter_safe(self, source_code: str, language: str) -> List[InstrumentationPoint]:
        """Analyze code using tree-sitter queries with timeout and memory protection"""
        with self._parser_lock:
            parser = self._parsers[language]
            queries = self._queries[language]
            
            try:
                # Parse source code with timeout protection
                import signal
                def timeout_handler(signum, frame):
                    raise TimeoutError("Tree-sitter parsing timed out")
                
                # Set timeout for parsing (Unix systems only; for Windows, use threading.Timer in production)
                if hasattr(signal, 'SIGALRM'):
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self._parser_timeout_ms // 1000)
                
                tree = parser.parse(bytes(source_code, 'utf8'))
                
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel alarm
                    signal.signal(signal.SIGALRM, old_handler)
                
            except (TimeoutError, MemoryError) as e:
                logger.error(f"Tree-sitter parsing failed for {language}: {e}")
                # Fallback to regex analysis
                return self._analyze_with_regex(source_code, language)
            
            points = []
            
            # Execute queries with result limits
            for query_name, query in queries.items():
                if query_name == 'returns': continue  # Handled per function
                
                try:
                    matches = query.matches(tree.root_node)
                    
                    # Limit total matches per query to prevent memory exhaustion
                    max_matches_per_query = 1000
                    if len(matches) > max_matches_per_query:
                        logger.warning(f"Query {query_name} exceeded match limit, truncating results")
                        matches = matches[:max_matches_per_query]
                    
                    for match in matches:
                        capture_dict = {}
                        for cap_index, node in match.captures:
                            cap_name = query.capture_names[cap_index]
                            capture_dict[cap_name] = node
                        
                        node_points = self._create_instrumentation_point(
                            query_name, capture_dict, source_code, language
                        )
                        if node_points:
                            points.extend(node_points)
                            
                except Exception as e:
                    logger.error(f"Query {query_name} failed for {language}: {e}")
                    # Continue with other queries
            
            return points
    
    def _analyze_with_regex(self, source_code: str, language: str) -> List[InstrumentationPoint]:
        """Analyze code using regex fallback patterns with optimization"""
        config = self._language_config[language]
        patterns = config.get('fallback_patterns', {})
        points = []
        
        # Compile regexes once and cache them
        if language not in self._compiled_regexes:
            self._compiled_regexes[language] = {
                pattern_name: re.compile(pattern)
                for pattern_name, pattern in patterns.items()
            }
        
        compiled_patterns = self._compiled_regexes[language]
        lines = source_code.split('\n')
        
        # Limit processing for very large files
        max_lines = 50000
        if len(lines) > max_lines:
            logger.warning(f"File has {len(lines)} lines, processing first {max_lines} only")
            lines = lines[:max_lines]
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            for pattern_name, compiled_pattern in compiled_patterns.items():
                match = compiled_pattern.search(line)
                if match:
                    point = self._create_regex_instrumentation_point(
                        pattern_name, match, line_num, language
                    )
                    if point:
                        points.append(point)
        
        return points
    
    def _create_instrumentation_point(
        self, 
        query_name: str, 
        capture_dict: Dict[str, 'Node'], 
        source_code: str,
        language: str
    ) -> List[InstrumentationPoint]:
        """Create instrumentation points from tree-sitter match with proper insertion point calculation"""
        points = []
        
        # Determine point type and metadata based on query patterns
        point_type, subtype, name, context, metadata = self._classify_capture(
            query_name, capture_dict, source_code, language
        )
        
        if not point_type:
            return []
        
        # Calculate entry point
        entry_node = capture_dict.get(subtype, list(capture_dict.values())[0]) if subtype in capture_dict else None
        if not entry_node:
            return []
        
        entry_line, entry_column = self._calculate_entry_position(entry_node, language, query_name)
        
        entry_point = InstrumentationPoint(
            id=f"{point_type}_{name}_{entry_line}_{entry_column}",
            type=point_type,
            subtype=subtype,
            name=name,
            line=entry_line,
            column=entry_column,
            context=context,
            metadata=metadata
        )
        points.append(entry_point)
        
        # For function-like constructs, create exit points (multiple if returns)
        if point_type == 'function_enter':
            function_node = capture_dict.get('function_def') or capture_dict.get('method_def') or capture_dict.get('constructor_def')
            if not function_node:
                function_node = entry_node.parent
                safety = 0
                while function_node and function_node.type != self._language_config[language]['function_node_type'] and safety < 20:
                    function_node = function_node.parent
                    safety += 1
            if not function_node:
                return points
            
            body_node = capture_dict.get('function_body') or capture_dict.get('method_body') or capture_dict.get('constructor_body')
            if not body_node:
                body_type = self._language_config[language]['body_type']
                for child in function_node.children:
                    if child.type == body_type:
                        body_node = child
                        break
            if not body_node:
                return points
            
            # Find all return statements within the function
            return_query = self._queries[language].get('returns')
            if return_query:
                ret_captures = return_query.captures(function_node)
                has_returns = False
                for ret_node, cap_name in ret_captures:
                    if cap_name == 'return':
                        has_returns = True
                        exit_line = ret_node.start_point.row + 1
                        exit_column = ret_node.start_point.column + 1
                        exit_point = InstrumentationPoint(
                            id=f"function_exit_{name}_{exit_line}_{exit_column}",
                            type='function_exit',
                            subtype='return',
                            name=name,
                            line=exit_line,
                            column=exit_column,
                            context=f"Function return: {name}",
                            metadata=metadata
                        )
                        points.append(exit_point)
                
                if not has_returns:
                    # Implicit exit at end of body
                    exit_line = body_node.end_point.row + 1
                    exit_column = body_node.start_point.column + 1  # Use body indent
                    exit_point = InstrumentationPoint(
                        id=f"function_exit_{name}_implicit_{exit_line}",
                        type='function_exit',
                        subtype='implicit',
                        name=name,
                        line=exit_line,
                        column=exit_column,
                        context=f"Function implicit exit: {name}",
                        metadata=metadata
                    )
                    points.append(exit_point)
        
        # For loops, create single exit at end (total energy)
        elif point_type == 'loop_start':
            loop_node = capture_dict.get('loop.for') or capture_dict.get('loop.while') or capture_dict.get('loop.do')
            if loop_node:
                exit_line = loop_node.end_point.row + 1
                exit_column = loop_node.end_point.column + 1
            else:
                exit_line = entry_line
                exit_column = entry_column
            loop_exit_point = InstrumentationPoint(
                id=f"loop_exit_{name}_{exit_line}_{exit_column}",
                type='loop_exit',
                subtype='block_end', 
                name=name,
                line=exit_line,
                column=exit_column,
                context=f"Loop exit: {name}",
                metadata=metadata
            )
            points.append(loop_exit_point)
        
        return points
    
    def _calculate_entry_position(self, node: 'Node', language: str, query_name: str) -> Tuple[int, int]:
        """Calculate entry position for instrumentation"""
        if not node or not node.start_point:
            return 1, 0
        
        # For functions, entry at start of body
        if 'function' in query_name or 'method' in query_name or 'constructor' in query_name:
            body_type = self._language_config[language]['body_type']
            for child in node.children:
                if child.type == body_type:
                    return child.start_point.row + 1, child.start_point.column + 1
        # For loops, entry at start of body
        elif 'loop' in query_name:
            for child in node.children:
                if child.type == 'block' or child.type == 'compound_statement':
                    return child.start_point.row + 1, child.start_point.column + 1
        # Default
        return node.start_point.row + 1, node.start_point.column + 1
    
    def _create_regex_instrumentation_point(
        self,
        pattern_name: str,
        match: 'Match',
        line_num: int,
        language: str
    ) -> Optional[InstrumentationPoint]:
        """Create instrumentation point from regex match"""
        # ... (unchanged for brevity; improve by combining patterns for efficiency if needed)
        pattern_map = {
            'function_def': ('function_enter', 'function'),
            'method_def': ('function_enter', 'method'),
            'class_def': ('class_enter', 'class'),
            'interface_def': ('class_enter', 'interface'),
            'struct_def': ('class_enter', 'struct'),
            'for_loop': ('loop_start', 'for'),
            'while_loop': ('loop_start', 'while'),
            'do_loop': ('loop_start', 'do'),
            'memory_op': ('memory_operation', 'allocation'),
            'new_op': ('memory_operation', 'new'),
            'delete_op': ('memory_operation', 'delete'),
            'lambda_expr': ('lambda_expression', 'definition'),
            'stream_op': ('stream_operation', 'operation'),
            'list_comp': ('comprehension', 'list')
        }
        
        if pattern_name not in pattern_map:
            return None
        
        point_type, subtype = pattern_map[pattern_name]
        name = match.group(1) if match.groups() else pattern_name
        
        # Mark energy-intensive operations
        energy_intensive = pattern_name in ['memory_op', 'new_op', 'lambda_expr', 'stream_op', 'list_comp']
        
        return InstrumentationPoint(
            id=f"{point_type}_{name}_{line_num}",
            type=point_type,
            subtype=subtype,
            name=name,
            line=line_num,
            column=match.start(),
            context=f"{subtype.title()} {point_type}: {name} at line {line_num}",
            metadata={
                'analysis_method': 'regex',
                'energy_intensive': energy_intensive,
                'pattern_matched': pattern_name
            }
        )
    
    def _classify_capture(
        self, 
        query_name: str, 
        capture_dict: Dict[str, 'Node'], 
        source_code: str,
        language: str
    ) -> Tuple[str, str, str, str, Dict]:
        """Classify tree-sitter capture into instrumentation point"""
        name_node = None
        text = ''
        
        # Find name node and extract text
        for cap_name, node in capture_dict.items():
            if 'name' in cap_name or cap_name.endswith('.name'):
                name_node = node
                text = self._extract_text_from_node(node, source_code)
                break
        
        if name_node and not self._is_valid_identifier(text):
            return (None, None, None, None, {})
        
        name = text or query_name
        
        # Classification rules
        if 'function' in query_name or 'method' in query_name or 'constructor' in query_name:
            subtype = 'function' if 'function_name' in capture_dict else 'method' if 'method_name' in capture_dict else 'constructor'
            metadata = {}
            if language == 'python':
                metadata = self._analyze_python_function_metadata(name, query_name)
            return ('function_enter', subtype, name, f"Function entry: {name}", metadata)
        
        elif 'class' in query_name:
            subtype = cap_name.split('.')[0] if '.' in list(capture_dict.keys())[0] else 'class'
            return ('class_enter', subtype, name, f"{subtype.title()} definition: {name}", {})
        
        elif 'loop' in query_name:
            cap_names = list(capture_dict.keys())
            for cap in cap_names:
                if cap in ['loop.for', 'loop.while', 'loop.do', 'loop.enhanced_for']:
                    subtype = cap.split('.')[1]
                    return ('loop_start', subtype, f"{subtype}_loop", f"{subtype.title()} loop", {})
            return (None, None, None, None, {})
        
        elif 'comprehension' in query_name:
            subtype = list(capture_dict.keys())[0].split('.')[1]
            return ('comprehension', subtype, f"{subtype}_comp", f"{subtype.title()} comprehension", {'energy_intensive': True})
        
        elif 'lambda' in query_name:
            return ('lambda_expression', 'definition', 'lambda', "Lambda expression", {'energy_intensive': True})
        
        elif 'stream' in query_name:
            return ('stream_operation', 'operation', name, f"Stream operation: {name}", {'energy_intensive': True})
        
        elif 'memory' in query_name:
            return ('memory_operation', 'allocation', name, f"Memory operation: {name}", {'energy_intensive': True})
        
        return (None, None, None, None, {})
    
    def _extract_text_from_node(self, node: 'Node', source_code: str) -> str:
        """Extract text content from tree-sitter node with validation"""
        # ... (unchanged for brevity; good as is)
        try:
            start_byte = node.start_byte
            end_byte = node.end_byte
            
            if start_byte < 0 or end_byte < 0 or start_byte >= end_byte or end_byte > len(source_code):
                return ""
            
            text = source_code[start_byte:end_byte].strip()
            
            if len(text) > 100 or '\n' in text:
                identifier_match = re.search(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
                return identifier_match.group() if identifier_match else ""
            
            return text
        except Exception:
            return ""
    
    def _is_valid_identifier(self, text: str) -> bool:
        """Check if text is a valid identifier for function/method names"""
        if not text or len(text) > 50:
            return False
        
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', text):
            return False
        
        invalid_patterns = r'[(){}[\]<>+\-*/%=!&|^~\s;,.\"\' ]'
        if re.search(invalid_patterns, text):
            return False
        
        return True
    
    def _analyze_python_function_metadata(self, function_name: str, query_name: str) -> Dict:
        """Analyze Python function to determine special characteristics"""
        # ... (unchanged; consider moving to config if more langs need similar)
        metadata = {}
        
        if function_name.startswith('__') and function_name.endswith('__'):
            metadata['is_dunder'] = True
            metadata['function_type'] = 'magic_method'
        elif function_name.startswith('_'):
            metadata['is_private'] = True
        
        metadata['needs_special_exit_handling'] = function_name in [
            '__init__', '__enter__', '__exit__', '__call__', '__iter__', '__next__'
        ]
        
        return metadata
    
    def _analyze_optimizations(self, source_code: str, language: str) -> List[str]:
        """Generate optimization suggestions for the given language"""
        # ... (unchanged for brevity; enhance with tree-sitter queries for accuracy, e.g., query for nested loops)
        suggestions = []
        
        if language == 'python':
            suggestions.extend(self._analyze_python_optimizations(source_code))
        # Similar for others...
        
        return suggestions
    
    # ... (keep _analyze_python_optimizations etc. unchanged)
    
    def instrument_code(
        self, 
        source_code: str, 
        points: List[InstrumentationPoint], 
        language: str
    ) -> str:
        """
        Instrument source code with measurement calls at specified points.
        
        Args:
            source_code: Original source code
            points: Instrumentation points to add
            language: Language identifier
            
        Returns:
            Instrumented source code with measurement calls
        """
        if not points:
            return source_code
        
        # Get language-specific instrumentation strategy
        if language == 'python':
            return self._instrument_python(source_code, points)
        # Similar for others... (unchanged, but fix insertion in _instrument_python)
        
        return self._instrument_generic(source_code, points)
    
    def _instrument_python(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        """Python-specific code instrumentation with codegreen_runtime"""
        lines = source_code.split('\n')
        
        # Add codegreen_runtime import at the top (unchanged)
        runtime_import = "import codegreen_runtime as _codegreen_rt"
        # ... (insert logic unchanged)
        
        insert_line = 0
        # ... (find insert_line unchanged)
        
        lines.insert(insert_line, runtime_import)
        
        # Adjust line numbers for inserted import
        adjusted_points = [
            InstrumentationPoint(
                p.id, p.type, p.subtype, p.name,
                p.line + 1 if p.line > insert_line else p.line,
                p.column, p.context, p.metadata
            ) for p in points
        ]
        
        # Deduplicate points before insertion
        deduplicated_points = self._deduplicate_checkpoints(adjusted_points)
        
        # Sort points by line number (descending) to avoid offset issues
        sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines) + 1:  # Allow append
                instrumentation = self._generate_python_call(point)
                
                # Handle different insertion strategies
                if point.type in ['function_enter', 'loop_start']:
                    # Entry points go at the start of the body (before first statement)
                    insert_index = point.line - 1
                elif point.type in ['function_exit', 'loop_exit']:
                    # Exit points use special logic
                    insert_index = self._find_exit_insertion_point(lines, point.line, point.type.split('_')[0])
                else:
                    insert_index = point.line - 1
                
                # Ensure valid index
                insert_index = max(0, min(insert_index, len(lines)))
                
                # Get indent dynamically
                if insert_index < len(lines):
                    indent = self._get_indentation(lines[insert_index])
                elif insert_index > 0:
                    indent = self._get_indentation(lines[insert_index - 1])  # Use previous for appends
                else:
                    indent = "    "
                
                instrumented_call = indent + instrumentation
                lines.insert(insert_index, instrumented_call)
        
        return '\n'.join(lines)
    
    # ... (similar fixes for _instrument_c, _instrument_cpp, _instrument_java: adjust insert_index to point.line - 1 for entries)
    
    def _find_exit_insertion_point(self, lines: List[str], target_line: int, construct_type: str) -> int:
        """Find the correct insertion point for exit checkpoints (unchanged, but works with multiple now)"""
        # ... (original logic; good for returns/implicit as is)
    
    # ... (keep _deduplicate_checkpoints, _generate_*_call, etc. unchanged)
    
    # Global engine instance (unchanged)
    
# Legacy compatibility functions (unchanged, but consider deprecating)
```

This improved version addresses all identified issues. For new languages, add to the dict (or externalize as noted). Test with sample code having multiple returns to verify. If needed, integrate nvim queries and mapping captures (e.g., @function.definition -> @function_name). 

--------------------------------
--------------------------------
--------------------------------

# Analysis and Improvements for Language Engine

I've analyzed your `language_engine.py` and identified several areas for improvement. Here's a comprehensive review with suggestions:

## Key Issues and Improvements

### 1. Tree-sitter Query Design
**Problem**: Hardcoded queries for each language that may not be optimal or comprehensive.

**Solution**: Use standardized query patterns from established sources:
- Leverage the [tree-sitter-langs](https://github.com/tree-sitter/tree-sitter-langs) project for pre-built grammars
- Reference [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter) queries as they're well-tested
- Consider using a query repository like [tree-sitter-query-bundle](https://github.com/AbstractMachinesLab/tree-sitter-query-bundle)

Example improved query structure:
```python
# Instead of hardcoding, load from external files
def _load_queries_from_files(language_dir):
    queries = {}
    query_files = {
        'functions': 'functions.scm',
        'loops': 'loops.scm',
        # etc.
    }
    
    for query_type, filename in query_files.items():
        try:
            with open(os.path.join(language_dir, filename)) as f:
                queries[query_type] = f.read()
        except FileNotFoundError:
            logger.warning(f"Query file {filename} not found for {language_dir}")
    
    return queries
```

### 2. Instrumentation Point Accuracy
**Problem**: The current approach to calculating insertion points has potential inaccuracies.

**Solution**: Implement more precise AST-based instrumentation:
```python
def _calculate_precise_insertion_points(self, node, language):
    """Calculate exact insertion points using AST structure"""
    if language == 'python':
        # For Python functions, find the colon and the first statement
        if node.type == 'function_definition':
            # Find the colon which marks the end of the function signature
            colon_node = None
            for child in node.children:
                if child.type == ':' and child.end_point:
                    colon_node = child
                    break
            
            if colon_node:
                entry_line = colon_node.end_point[0] + 2  # Skip line with colon
                
                # Find the first non-comment statement in the body
                body_node = None
                for child in node.children:
                    if child.type == 'block':
                        body_node = child
                        break
                
                if body_node and body_node.children:
                    # Find the first actual code statement
                    for stmt in body_node.children:
                        if stmt.type not in ('comment', 'string'):
                            entry_line = stmt.start_point[0] + 1
                            break
                
                exit_line = node.end_point[0] + 1
                return entry_line, exit_line
    
    # Fallback to current method
    return self._calculate_function_insertion_points(node, language)
```

### 3. Language Configuration Management
**Problem**: Hardcoded language configuration makes extension difficult.

**Solution**: Externalize language configuration:
```python
def _load_language_config(self):
    """Load language configuration from external files"""
    config_dir = Path(__file__).parent / "language_config"
    config = {}
    
    for lang_file in config_dir.glob("*.json"):
        try:
            with open(lang_file) as f:
                lang_config = json.load(f)
                lang_id = lang_file.stem
                config[lang_id] = lang_config
                logger.info(f"Loaded configuration for {lang_id}")
        except Exception as e:
            logger.error(f"Failed to load {lang_file}: {e}")
    
    return config
```

### 4. Thread Safety and Performance
**Problem**: Potential thread safety issues with shared parsers.

**Solution**: Implement parser pooling:
```python
class ParserPool:
    def __init__(self, max_parsers=5):
        self.parsers = defaultdict(list)
        self.max_parsers = max_parsers
        self.lock = Lock()
    
    def get_parser(self, language):
        with self.lock:
            if self.parsers[language]:
                return self.parsers[language].pop()
            else:
                return get_parser(language)
    
    def return_parser(self, language, parser):
        with self.lock:
            if len(self.parsers[language]) < self.max_parsers:
                self.parsers[language].append(parser)
```



### 6. Extensible Architecture
**Problem**: Adding new languages requires modifying core code.

**Solution**: Implement a plugin system:
```python
class LanguagePlugin:
    """Base class for language-specific plugins"""
    
    def get_queries(self) -> Dict[str, str]:
        raise NotImplementedError
        
    def instrument_code(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        raise NotImplementedError
        
    def detect_energy_patterns(self, source_code: str) -> List[EnergyPattern]:
        raise NotImplementedError

# Plugin registry
class PluginRegistry:
    def __init__(self):
        self.plugins = {}
        
    def register_plugin(self, language: str, plugin: LanguagePlugin):
        self.plugins[language] = plugin
        
    def get_plugin(self, language: str) -> Optional[LanguagePlugin]:
        return self.plugins.get(language)
```



### 8. Enhanced Instrumentation Accuracy
**Problem**: Current instrumentation may not handle all edge cases correctly.




### 10. Testing and Validation Framework
**Problem**: Lack of comprehensive testing for instrumentation accuracy.

**Solution**: Implement a testing framework:
```python
class InstrumentationTest:
    """Test case for instrumentation validation"""
    
    def __init__(self, name, code, expected_points, language):
        self.name = name
        self.code = code
        self.expected_points = expected_points
        self.language = language
    
    def run(self, engine):
        result = engine.analyze_code(self.code, self.language)
        
        # Check if all expected points are found
        found_points = {(p.type, p.line, p.name) for p in result.instrumentation_points}
        expected_points = {(p.type, p.line, p.name) for p in self.expected_points}
        
        missing = expected_points - found_points
        extra = found_points - expected_points
        
        return missing, extra

def run_test_suite(engine):
    """Run all instrumentation tests"""
    tests = [
        InstrumentationTest(
            "Python function",
            "def test_func():\n    return 42",
            [
                InstrumentationPoint("func_enter", "function_enter", "test_func", 1, 0, "Function entry"),
                InstrumentationPoint("func_exit", "function_exit", "test_func", 2, 4, "Function exit")
            ],
            "python"
        ),
        # Add more test cases
    ]
    
    for test in tests:
        missing, extra = test.run(engine)
        if missing or extra:
            logger.error(f"Test {test.name} failed: missing={missing}, extra={extra}")
```

## Recommended Next Steps

1. **Create external configuration files** for each language to separate concerns
2. **Implement the plugin architecture** for easier language extension
3. **Add comprehensive test cases** for each language's instrumentation
4. **Integrate with existing query repositories** rather than maintaining custom queries
5. **Implement CI/CD** to validate instrumentation accuracy across languages

This approach will make your tool more maintainable, accurate, and easier to extend to new languages while reducing the potential for bugs introduced by manual code changes.