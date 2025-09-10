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

# Import our new configuration-driven modules
from language_configs import get_language_config_manager
from ast_processor import ASTProcessor, ASTRewriter, ASTEdit, get_indentation_engine

# Import tree-sitter with graceful fallback
try:
    from tree_sitter import Language, Parser, Tree, Node, Query, QueryCursor
    from tree_sitter_language_pack import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = Parser = Tree = Node = None

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
    # AST-based instrumentation fields
    byte_offset: Optional[int] = None  # Byte position in source code
    node_start_byte: Optional[int] = None  # AST node start byte
    node_end_byte: Optional[int] = None  # AST node end byte
    insertion_mode: str = 'before'  # 'before', 'after', 'inside_start', 'inside_end'
    node: Optional['Node'] = None  # Tree-sitter node for precise AST-based operations
    
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




class ExternalQueryLoader:
    """
    Loads high-quality tree-sitter queries from external sources like nvim-treesitter.
    
    This ensures we stay in sync with community-maintained, well-tested query patterns
    instead of maintaining hardcoded queries that can become outdated.
    """
    
    def __init__(self, nvim_treesitter_path: Optional[str] = None):
        self.nvim_treesitter_path = nvim_treesitter_path or self._find_nvim_treesitter_path()
        self.query_cache = {}
        
        # Standard capture mapping for language-agnostic instrumentation
        # Based on actual nvim-treesitter capture names
        # Priority order: more specific captures first to avoid duplicates
        self.CAPTURE_MAP = {
            'local.definition.function': {'type': 'function_enter', 'subtype': 'function', 'insertion_mode': 'inside_start', 'priority': 1},
            'local.definition.method': {'type': 'function_enter', 'subtype': 'method', 'insertion_mode': 'inside_start', 'priority': 1},
            'local.definition.type': {'type': 'class_enter', 'subtype': 'class', 'insertion_mode': 'inside_start', 'priority': 1},
            'function': {'type': 'function_enter', 'subtype': 'function', 'insertion_mode': 'inside_start', 'priority': 2},
            'function.method': {'type': 'function_enter', 'subtype': 'method', 'insertion_mode': 'inside_start', 'priority': 2},
            'type.definition': {'type': 'class_enter', 'subtype': 'class', 'insertion_mode': 'inside_start', 'priority': 2},
            'keyword.return': {'type': 'function_exit', 'subtype': 'return', 'insertion_mode': 'before', 'priority': 1},
            'return': {'type': 'function_exit', 'subtype': 'return', 'insertion_mode': 'before', 'priority': 2},
        }
        
    def _find_nvim_treesitter_path(self) -> Optional[str]:
        """Find nvim-treesitter installation path"""
        # Try common locations
        possible_paths = [
            "third_party/nvim-treesitter",
            "../third_party/nvim-treesitter", 
            "nvim-treesitter",
            "./third_party/nvim-treesitter"
        ]
        
        for path in possible_paths:
            full_path = Path(path).resolve()
            if full_path.exists() and (full_path / "queries").exists():
                return str(full_path)
        
        logger.warning("⚠️  FALLBACK: nvim-treesitter not found, using hardcoded queries instead of community-maintained queries")
        return None
    
    def get_instrumentation_queries(self, language: str) -> Dict[str, str]:
        """
        Get instrumentation-relevant queries for a language from nvim-treesitter.
        
        Loads full .scm files and compiles them as complete queries, preserving
        all patterns, predicates, and metadata from the community-maintained queries.
        """
        if language in self.query_cache:
            return self.query_cache[language]
        
        queries = {}
        
        if self.nvim_treesitter_path:
            queries = self._load_nvim_queries(language)
        
        # Fallback to built-in queries if external loading fails
        if not queries:
            queries = self._get_fallback_queries(language)
        
        self.query_cache[language] = queries
        return queries
    
    def _load_nvim_queries(self, language: str) -> Dict[str, str]:
        """Load full .scm files from nvim-treesitter submodule"""
        queries = {}
        query_dir = Path(self.nvim_treesitter_path) / "queries" / language
        
        if not query_dir.exists():
            logger.warning(f"⚠️  FALLBACK: No nvim-treesitter queries found for {language}, using hardcoded queries instead of community-maintained queries")
            return {}
        
        try:
            # Automatically discover and load ALL .scm files for comprehensive coverage
            scm_files = list(query_dir.glob('*.scm'))
            combined_content = []
            loaded_files = []
            
            # Sort files for consistent ordering (important for reproducible queries)
            scm_files.sort()
            
            for scm_file in scm_files:
                try:
                    content = scm_file.read_text(encoding='utf-8')
                    # Skip empty files
                    if content.strip():
                        combined_content.append(f";; From {scm_file.name}\n{content}")
                        loaded_files.append(scm_file.name)
                        logger.debug(f"Loaded {scm_file.name} for {language}")
                except Exception as e:
                    logger.warning(f"Failed to load {scm_file.name} for {language}: {e}")
            
            if combined_content:
                # Combine all .scm files into one comprehensive query
                full_query = '\n\n'.join(combined_content)
                queries['full_query'] = full_query
                logger.info(f"Loaded comprehensive nvim-treesitter query for {language} from {len(loaded_files)} files: {', '.join(loaded_files)}")
            else:
                logger.warning(f"No valid .scm files found for {language}")
            
        except Exception as e:
            logger.warning(f"Failed to load nvim-treesitter queries for {language}: {e}")
        
        return queries
    
    def get_capture_mapping(self, language: str) -> Dict[str, Dict[str, str]]:
        """Get capture mapping for a specific language from configuration"""
        # Get capture mapping from language configuration
        config_manager = get_language_config_manager()
        query_config = config_manager.get_query_config(language)
        capture_mapping = query_config.get('capture_mapping', {})
        
        # Convert to the format expected by the engine
        capture_map = {}
        for capture_name, point_type in capture_mapping.items():
            # Determine insertion mode based on point type
            if 'enter' in point_type:
                insertion_mode = 'inside_start'
            elif 'exit' in point_type:
                insertion_mode = 'before'
            else:
                insertion_mode = 'inside_start'
            
            # Determine subtype based on capture name
            if 'function' in capture_name:
                subtype = 'function'
            elif 'method' in capture_name:
                subtype = 'method'
            elif 'class' in capture_name:
                subtype = 'class'
            elif 'loop' in capture_name:
                subtype = 'loop'
            else:
                subtype = 'generic'
            
            capture_map[capture_name] = {
                'type': point_type,
                'subtype': subtype,
                'insertion_mode': insertion_mode,
                'priority': 1
            }
        
        return capture_map
    
    
    def _get_fallback_queries(self, language: str) -> Dict[str, str]:
        """Fallback queries if external queries are not available"""
        # Get fallback queries from language configuration
        config_manager = get_language_config_manager()
        config = config_manager.get_config(language)
        if not config:
            return {}
        
        # Return built-in queries from configuration
        return config.analysis_patterns


class LanguageAgnosticInstrumentationGenerator:
    """
    Language-agnostic instrumentation code generator.
    
    This class abstracts away language-specific details and provides a unified
    interface for generating instrumentation code across different programming languages.
    """
    
    def __init__(self):
        self.config_manager = get_language_config_manager()
    
    def generate_instrumentation(self, point: InstrumentationPoint, language: str) -> Optional[str]:
        """
        Generate instrumentation code for a given point in a language-agnostic way.
        
        This method uses templates and language configurations to generate
        appropriate instrumentation code without hardcoding language specifics.
        """
        config = self.config_manager.get_instrumentation_config(language)
        if not config:
            # Fallback for unsupported languages
            logger.warning(f"⚠️  FALLBACK: No instrumentation config found for {language}, using generic comment instead of language-specific instrumentation")
            return f'{self._get_comment_prefix(language)} CodeGreen checkpoint: {point.id}'
        
        # Get templates from configuration
        templates = config.get('templates', {})
        
        # Determine the appropriate template based on instrumentation point type
        template_key = self._get_template_key(point.type, point.subtype)
        template = templates.get(template_key)
        
        if not template:
            # Fallback to generic comment
            logger.warning(f"⚠️  FALLBACK: No template found for {point.type} in {language}, using generic comment instead of specific template")
            comment_prefix = config.get('comment_prefix', '//')
            return f'{comment_prefix} CodeGreen {point.type}: {point.name}'
        
        # Generate the instrumentation code using the template
        instrumentation_code = template.format(
            checkpoint_id=point.id,
            name=point.name,
            function_name=point.name,
            loop_name=point.name
        )
        
        # Add statement terminator if needed
        terminator = config.get('statement_terminator', '')
        if terminator and not instrumentation_code.endswith(terminator):
            instrumentation_code += terminator
            
        return instrumentation_code
    
    def _get_template_key(self, point_type: str, subtype: str) -> str:
        """Map instrumentation point types to template keys"""
        # The configuration uses the same keys as point types
        return point_type
    
    def _get_comment_prefix(self, language: str) -> str:
        """Get comment prefix for unsupported languages from configuration"""
        config = self.config_manager.get_instrumentation_config(language)
        if config:
            return config.get('comment_prefix', '//')
        return '//'  # Default fallback
    
    def get_import_statement(self, language: str) -> Optional[str]:
        """Get the appropriate import/include statement for a language"""
        config = self.config_manager.get_instrumentation_config(language)
        return config.get('import_statement') if config else None
    
    def get_language_config(self, language: str) -> Dict[str, str]:
        """Get complete language configuration"""
        config = self.config_manager.get_instrumentation_config(language)
        return config if config else {}


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
        self._config_manager = get_language_config_manager()  # Use centralized config manager
        self._parser_lock = Lock()
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self._parser_timeout_ms = parser_timeout_ms
        self._compiled_regexes = {}
        self._external_query_loader = ExternalQueryLoader()  # Load external queries
        self._language_agnostic_generator = LanguageAgnosticInstrumentationGenerator()  # Language-agnostic instrumentation
        self._initialize_parsers()
    
    def _get_language_config(self, language: str) -> Optional[Dict[str, Any]]:
        """Get language configuration from the centralized config manager."""
        config = self._config_manager.get_config(language)
        if not config:
            return None
        
        # Convert LanguageConfig to the format expected by the engine
        return {
            'extensions': config.extensions,
            'tree_sitter_name': config.tree_sitter_name,
            'queries': self._get_builtin_queries(language),
            'fallback_patterns': config.analysis_patterns
        }
    
    def _get_builtin_queries(self, language: str) -> Dict[str, str]:
        """Get built-in queries for fallback when external queries fail."""
        # These are minimal fallback queries - external queries are preferred
        if language == 'python':
            return {
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
                    (for_statement) @loop.for
                    (while_statement) @loop.while
                ''',
                'returns': '''
                    (return_statement) @return
                '''
            }
        elif language in ['c', 'cpp']:
            return {
                    'functions': '''
                        (function_definition
                          declarator: (function_declarator
                            declarator: (identifier) @function_name)
                          body: (compound_statement) @function_body) @function_def
                    ''',
                    'loops': '''
                        (for_statement) @loop.for
                        (while_statement) @loop.while
                        (do_statement) @loop.do
                    ''',
                'returns': '''
                    (return_statement) @return
                '''
            }
        elif language == 'java':
            return {
                    'methods': '''
                        (method_declaration
                          name: (identifier) @method_name
                          body: (block) @method_body) @method_def
                    ''',
                    'classes': '''
                        (class_declaration
                          name: (identifier) @class.name
                          body: (class_body) @class.body) @class.def
                    ''',
                    'loops': '''
                        (for_statement) @loop.for
                        (while_statement) @loop.while
                ''',
                'returns': '''
                    (return_statement) @return
                '''
            }
        
        return {}
    
    def _initialize_parsers(self):
        """Initialize tree-sitter parsers for all configured languages"""
        if not TREE_SITTER_AVAILABLE:
            logger.warning("⚠️  FALLBACK: Tree-sitter not available, using regex analysis instead of AST-based analysis")
            return
        
        # Get supported languages from config manager
        supported_languages = self._config_manager.get_supported_languages()
        
        for lang_id in supported_languages:
            config = self._get_language_config(lang_id)
            if not config:
                continue
            try:
                ts_name = config['tree_sitter_name']
                language = get_language(ts_name)
                parser = get_parser(ts_name)
                
                self._languages[lang_id] = language
                self._parsers[lang_id] = parser
                
                # Load external queries from nvim-treesitter with fallback to built-in
                self._queries[lang_id] = {}
                external_queries = self._external_query_loader.get_instrumentation_queries(lang_id)
                
                # Use external full query if available, otherwise use built-in config queries
                if external_queries and 'full_query' in external_queries:
                    try:
                        # Compile the full .scm query
                        query = Query(language, external_queries['full_query'])
                        self._queries[lang_id]['instrumentation'] = query
                        logger.info(f"✅ Compiled comprehensive nvim-treesitter query for {lang_id}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Full query compilation failed for {lang_id}: {e}")
                        # Fall back to built-in queries
                        self._compile_builtin_queries(lang_id, language, config['queries'])
                    except Exception as e:
                        logger.error(f"Unexpected error compiling full query for {lang_id}: {e}")
                        # Fall back to built-in queries
                        self._compile_builtin_queries(lang_id, language, config['queries'])
                else:
                    # Use built-in queries
                    self._compile_builtin_queries(lang_id, language, config['queries'])
                
                if not self._queries[lang_id]:
                    logger.error(f"❌ No valid queries compiled for {lang_id}")
                
            except ImportError as e:
                logger.error(f"Missing tree-sitter language support for {lang_id}: {e}")
            except Exception as e:
                logger.error(f"⚠️ Could not initialize parser for {lang_id}: {e}")
    
    def _compile_builtin_queries(self, lang_id: str, language: Language, queries_config: Dict[str, str]):
        """Compile built-in queries as fallback"""
        for query_name, query_text in queries_config.items():
            try:
                query = Query(language, query_text)
                self._queries[lang_id][query_name] = query
                logger.debug(f"Compiled built-in {query_name} query for {lang_id}")
            except (ValueError, TypeError) as e:
                logger.error(f"Built-in query compilation failed for {query_name} in {lang_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error compiling built-in {query_name} query for {lang_id}: {e}")
        
        if self._queries[lang_id]:
            logger.info(f"✅ Initialized tree-sitter parser for {lang_id} with {len(self._queries[lang_id])} built-in queries")
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language identifiers"""
        return self._config_manager.get_supported_languages()
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions"""
        return self._config_manager.get_supported_extensions()
    
    def detect_language(self, filename: str) -> Optional[str]:
        """Detect language from filename extension"""
        return self._config_manager.detect_language_from_filename(filename)
    
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
        
        if not language or language not in self._config_manager.get_supported_languages():
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
                logger.warning(f"⚠️  FALLBACK: Tree-sitter not available for {language}, using regex analysis instead of AST-based analysis")
                points = self._analyze_with_regex(source_code, language)
                analysis_method = 'regex_fallback'
            
            #TODO: Generate optimization suggestions
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
                
                # Set timeout for parsing (Unix systems only)
                if hasattr(signal, 'SIGALRM'):
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self._parser_timeout_ms // 1000)
                
                tree = parser.parse(bytes(source_code, 'utf8'))
                
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel alarm
                    signal.signal(signal.SIGALRM, old_handler)
                
            except (TimeoutError, MemoryError) as e:
                logger.error(f"Tree-sitter parsing failed for {language}: {e}")
                logger.warning(f"⚠️  FALLBACK: Tree-sitter parsing failed, using regex analysis instead of AST-based analysis for {language}")
                # Fallback to regex analysis
                return self._analyze_with_regex(source_code, language)
            
            points = []
            
            # Execute queries using the new capture-based approach
            logger.info(f"🔍 Executing {len(queries)} queries for {language} instrumentation")
            for query_name, query in queries.items():
                logger.debug(f"🔧 Processing query '{query_name}' for {language}")
                try:
                    # Use QueryCursor.captures() for direct capture access
                    logger.debug(f"   Creating QueryCursor for query '{query_name}'")
                    cursor = QueryCursor(query)
                    
                    logger.debug(f"   Executing captures on AST root node")
                    captures = cursor.captures(tree.root_node)
                    
                    # captures is a dictionary of {capture_name: [nodes]}
                    logger.info(f"✅ Query '{query_name}' found {len(captures)} capture types with total {sum(len(nodes) for nodes in captures.values())} nodes")
                    
                    # Log capture details
                    for capture_name, node_list in captures.items():
                        logger.debug(f"   📋 Capture '{capture_name}': {len(node_list)} nodes")
                    
                    # Limit total captures to prevent memory exhaustion
                    limits = self._config_manager.get_processing_limits(language)
                    max_captures_per_query = limits.get('max_captures_per_query', 1000)
                    total_captures = sum(len(nodes) for nodes in captures.values())
                    logger.debug(f"   Total captures before processing: {total_captures} (limit: {max_captures_per_query})")
                    
                    if total_captures > max_captures_per_query:
                        logger.warning(f"⚠️  TRUNCATION: Query '{query_name}' exceeded capture limit ({total_captures} > {max_captures_per_query})")
                        logger.warning(f"   This may result in missing instrumentation points. Consider increasing max_captures_per_query.")
                        
                        # Truncate captures by limiting each capture type
                        truncated_captures = {}
                        current_count = 0
                        for capture_name, node_list in captures.items():
                            if current_count + len(node_list) <= max_captures_per_query:
                                truncated_captures[capture_name] = node_list
                                current_count += len(node_list)
                                logger.debug(f"   ✅ Kept all {len(node_list)} nodes for '{capture_name}'")
                            else:
                                remaining = max_captures_per_query - current_count
                                if remaining > 0:
                                    truncated_captures[capture_name] = node_list[:remaining]
                                    logger.warning(f"   ⚠️  Truncated '{capture_name}': kept {remaining}/{len(node_list)} nodes")
                                else:
                                    logger.warning(f"   ❌ Dropped all {len(node_list)} nodes for '{capture_name}' (limit exceeded)")
                                break
                        
                        original_count = total_captures  
                        captures = truncated_captures
                        new_total = sum(len(nodes) for nodes in captures.values())
                        logger.warning(f"   Truncation result: {original_count} -> {new_total} captures")
                    
                    # Get capture mapping for this language (use ExternalQueryLoader's CAPTURE_MAP)
                    logger.debug(f"   Using CAPTURE_MAP with {len(self._external_query_loader.CAPTURE_MAP)} mappings")
                    capture_map = self._external_query_loader.CAPTURE_MAP
                    
                    # Process each capture, handling duplicates
                    processed_nodes = set()  # Track processed nodes to avoid duplicates
                    points_created = 0
                    points_skipped = 0
                    
                    logger.debug(f"   🔄 Processing captures against CAPTURE_MAP...")
                    
                    for capture_name, node_list in captures.items():
                        if capture_name in capture_map:
                            logger.debug(f"   📍 Processing capture '{capture_name}' -> {capture_map[capture_name]} ({len(node_list)} nodes)")
                            
                            if not node_list:
                                logger.debug(f"   ⚠️  Empty node list for capture '{capture_name}'")
                                continue
                                
                            # Process each node in the capture
                            for i, node in enumerate(node_list):
                                # Create a unique identifier for this node
                                node_id = (node.start_byte, node.end_byte, capture_name)
                                
                                # Skip if we've already processed this node
                                if node_id in processed_nodes:
                                    logger.debug(f"   ⏭️  Skipping duplicate node {i+1}/{len(node_list)} for '{capture_name}'")
                                    points_skipped += 1
                                    continue
                                
                                processed_nodes.add(node_id)
                                logger.debug(f"   🔧 Creating point {i+1}/{len(node_list)} for '{capture_name}' (node: {node.type})")
                                
                                # Create instrumentation point from capture
                                point = self._create_instrumentation_point_from_capture(
                                    node, capture_name, capture_map[capture_name], 
                                    source_code, language
                                )
                                if point:
                                    points.append(point)
                                    points_created += 1
                                    logger.debug(f"   ✅ Successfully created instrumentation point for '{capture_name}'")
                                else:
                                    logger.debug(f"   ❌ Failed to create instrumentation point for '{capture_name}' (validation failed or error)")
                        else:
                            logger.debug(f"   ⏭️  Skipping unmapped capture '{capture_name}' ({len(node_list)} nodes)")
                    
                    logger.info(f"📊 Query '{query_name}' processing summary: {points_created} points created, {points_skipped} duplicates skipped")
                            
                except Exception as e:
                    # Enhanced error logging for query failures
                    import traceback
                    logger.error(f"❌ CRITICAL: Query '{query_name}' execution failed for {language}")
                    logger.error(f"   Error type: {type(e).__name__}")
                    logger.error(f"   Error message: {str(e)}")
                    logger.error(f"   Query type: {type(query)}")
                    
                    # Log traceback for debugging
                    tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                    logger.error(f"   Query execution traceback:")
                    for line in tb_lines:
                        logger.error(f"     {line.rstrip()}")
                    
                    logger.warning(f"⚠️  FALLBACK: Continuing with other queries despite '{query_name}' failure")
            
            return points
    
    def _analyze_with_regex(self, source_code: str, language: str) -> List[InstrumentationPoint]:
        """Analyze code using regex fallback patterns with optimization"""
        logger.warning(f"⚠️  FALLBACK: Using regex analysis for {language} instead of AST-based analysis")
        patterns = self._config_manager.get_analysis_patterns(language)
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
        limits = self._config_manager.get_processing_limits(language)
        max_lines = limits.get('max_lines_for_processing', 50000)
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
    
    def _create_instrumentation_point_from_capture(
        self,
        node: 'Node',
        capture_name: str,
        capture_config: Dict[str, str],
        source_code: str,
        language: str
    ) -> Optional[InstrumentationPoint]:
        """Create instrumentation point from a single tree-sitter capture"""
        logger.debug(f"🔧 Creating instrumentation point for capture '{capture_name}' in {language}")
        logger.debug(f"   Node type: {node.type}, Position: {node.start_point}-{node.end_point}")
        logger.debug(f"   Capture config: {capture_config}")
        
        try:
            # Extract node information
            start_point = node.start_point
            end_point = node.end_point
            logger.debug(f"   Extracted node points: start={start_point}, end={end_point}")
            
            # Extract text content
            logger.debug(f"   Calling _extract_text_from_node with language='{language}'")
            text = self._extract_text_from_node(node, source_code, language)
            logger.debug(f"   Extracted text: '{text}' (length: {len(text)})")
            
            # Validate identifier if it's a function/method name
            if capture_config['type'] in ['function_enter', 'class_enter']:
                logger.debug(f"   Validating identifier for {capture_config['type']}: '{text}'")
                if not self._is_valid_identifier(text, language):
                    logger.debug(f"   ❌ Invalid identifier '{text}' for {capture_config['type']}, skipping point creation")
                    return None
                logger.debug(f"   ✅ Valid identifier '{text}' for {capture_config['type']}")
            
            # Determine the name for the instrumentation point
            name = text if text else capture_name
            logger.debug(f"   Point name determined: '{name}'")
            
            # For function entry points, we need to find the function body for proper insertion
            if capture_config['type'] == 'function_enter':
                # Find the parent function definition node
                function_node = self._find_parent_function(node, language)
                if function_node:
                    # Find the function body for insertion
                    body_node = self._find_function_body(function_node, language)
                    if body_node:
                        # Use the body node for insertion - find the first line inside the body
                        insertion_point = body_node.start_point
                        insertion_byte = body_node.start_byte
                        
                        # Use AST processor to find the correct insertion point  
                        # TODO: Pass tree parameter for TreeSitter indentation engine
                        ast_processor = ASTProcessor(language, source_code, None)
                        insertion_byte = ast_processor.find_insertion_point(function_node, 'inside_start')
                        if insertion_byte is not None:
                            # Convert byte offset to point
                            insertion_point = self._byte_to_point(source_code, insertion_byte)
                        else:
                            insertion_point = body_node.start_point
                            insertion_byte = body_node.start_byte
                    else:
                        # Fallback to function node
                        insertion_point = function_node.start_point
                        insertion_byte = function_node.start_byte
                else:
                    # Fallback to current node
                    insertion_point = start_point
                    insertion_byte = node.start_byte
            else:
                # For other types, use the current node
                insertion_point = start_point
                insertion_byte = node.start_byte
            
            # Create the instrumentation point
            point = InstrumentationPoint(
                id=f"{capture_config['type']}_{name}_{insertion_point[0] + 1}_{insertion_point[1] + 1}",
                type=capture_config['type'],
                subtype=capture_config['subtype'],
                name=name,
                line=insertion_point[0] + 1,
                column=insertion_point[1] + 1,
                context=f"{capture_config['subtype'].title()} {capture_config['type']}: {name}",
                metadata={'capture_name': capture_name, 'analysis_method': 'tree_sitter'},
                byte_offset=None,  # Let ASTRewriter calculate the correct offset
                node_start_byte=node.start_byte,
                node_end_byte=node.end_byte,
                insertion_mode=capture_config['insertion_mode'],
                node=node  # Add the node for AST-based operations
            )
            
            return point
            
        except Exception as e:
            # Enhanced error logging with context and traceback
            import traceback
            logger.error(f"❌ CRITICAL: Failed to create instrumentation point from capture '{capture_name}' in language '{language}'")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   Node type: {node.type if hasattr(node, 'type') else 'Unknown'}")
            logger.error(f"   Capture config: {capture_config}")
            logger.error(f"   Language parameter: {repr(language)}")
            logger.error(f"   Source code length: {len(source_code)}")
            
            # Log the full traceback for debugging
            tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
            logger.error(f"   Full traceback:")
            for line in tb_lines:
                logger.error(f"     {line.rstrip()}")
            
            return None
    
    def _find_parent_function(self, node: 'Node', language: str) -> Optional['Node']:
        """Find the parent function definition node"""
        node_types = self._config_manager.get_node_types(language)
        function_types = node_types.get('function_types', ['function_definition'])
        
        current = node
        while current:
            if current.type in function_types:
                return current
            current = current.parent
        return None
    
    def _find_function_body(self, function_node: 'Node', language: str) -> Optional['Node']:
        """Find the function body node for proper insertion"""
        if not function_node:
            return None
        
        node_types = self._config_manager.get_node_types(language)
        body_types = node_types.get('body_types', ['block'])
        
        # Look for block or body child
        for child in function_node.children:
            if child.type in body_types:
                return child
        
        return None
    
    def _create_instrumentation_point_from_match(
        self, 
        query_name: str, 
        capture_dict: Dict[str, List['Node']], 
        source_code: str,
        language: str
    ) -> List[InstrumentationPoint]:
        """Create instrumentation points from grouped tree-sitter match with proper insertion point calculation"""
        # This replaces the old single-capture approach with grouped captures
        points = []
        
        # Determine point type and metadata based on query patterns and grouped captures
        point_type, subtype, name, context, metadata = self._classify_grouped_capture(
            query_name, capture_dict, source_code, language
        )
        
        if not point_type:
            return []
        
        # Find the main node for positioning (usually the definition node)
        main_node = self._find_main_node_from_captures(capture_dict, query_name)
        if not main_node:
            return []
        
        # Calculate insertion points using the main node
        entry_line, exit_line = self._calculate_insertion_points_from_grouped_captures(
            capture_dict, language, query_name
        )
        
        start_column = main_node.start_point.column + 1 if main_node.start_point else 0
        end_column = main_node.end_point.column + 1 if main_node.end_point else 0
        
        # Find the body node for proper byte offset calculation
        body_node = None
        if 'function' in query_name or 'method' in query_name:
            for key in ['function_body', 'method_body', 'constructor_body']:
                if key in capture_dict and capture_dict[key]:
                    body_node = capture_dict[key][0]
                    break
        
        # Use body node for byte offset if available, otherwise use main node
        offset_node = body_node if body_node else main_node
        
        # Create entry point with AST information
        entry_point = InstrumentationPoint(
            id=f"{point_type}_{name}_{entry_line}_{start_column}",
            type=point_type,
            subtype=subtype,
            name=name,
            line=entry_line,
            column=start_column,
            context=context,
            metadata=metadata,
            byte_offset=offset_node.start_byte if offset_node else None,
            node_start_byte=offset_node.start_byte if offset_node else None,
            node_end_byte=offset_node.end_byte if offset_node else None,
            insertion_mode='inside_start' if point_type in ['function_enter', 'loop_start'] else 'before'
        )
        points.append(entry_point)
        
        # Create exit points based on type
        if point_type == 'function_enter':
            # For functions, find all return statements or create implicit exit
            exit_points = self._create_function_exit_points(capture_dict, name, metadata, language)
            points.extend(exit_points)
        elif point_type == 'loop_start':
            # Create loop exit point
            loop_exit_point = InstrumentationPoint(
                id=f"loop_exit_{name}_{exit_line}_{end_column}",
                type='loop_exit',
                subtype='block_end', 
                name=name,
                line=exit_line,
                column=end_column,
                context=f"Loop exit: {name}",
                metadata=metadata,
                byte_offset=main_node.end_byte if main_node else None,
                node_start_byte=main_node.start_byte if main_node else None,
                node_end_byte=main_node.end_byte if main_node else None,
                insertion_mode='inside_end'
            )
            points.append(loop_exit_point)
        
        return points
    
    def _classify_grouped_capture(
        self, 
        query_name: str, 
        capture_dict: Dict[str, List['Node']], 
        source_code: str,
        language: str
    ) -> Tuple[str, str, str, str, Dict]:
        """Classify grouped tree-sitter captures into instrumentation point"""
        # Find name node and extract text
        name_node = None
        text = ''
        
        # Look for name captures in the grouped dict
        for cap_name, node_list in capture_dict.items():
            if 'name' in cap_name or cap_name.endswith('_name'):
                if node_list:  # Take the first node from the list
                    name_node = node_list[0]
                    text = self._extract_text_from_node(name_node, source_code)
                break
        
        if name_node and not self._is_valid_identifier(text):
            return (None, None, None, None, {})
        
        name = text or query_name
        
        # Classification rules based on query patterns
        if 'function' in query_name or 'method' in query_name or 'constructor' in query_name:
            subtype = 'function' if 'function_name' in capture_dict else 'method' if 'method_name' in capture_dict else 'constructor'
            metadata = self._analyze_function_metadata(name, query_name, language)
            return ('function_enter', subtype, name, f"Function entry: {name}", metadata)
        
        elif 'class' in query_name:
            subtype = 'class'
            for cap_name in capture_dict.keys():
                if '.' in cap_name:
                    subtype = cap_name.split('.')[0]
                    break
            return ('class_enter', subtype, name, f"{subtype.title()} definition: {name}", {})
        
        elif 'loop' in query_name:
            # Look for specific loop type captures
            for cap_name in capture_dict.keys():
                if cap_name.startswith('loop.'):
                    subtype = cap_name.split('.')[1]
                    return ('loop_start', subtype, f"{subtype}_loop", f"{subtype.title()} loop", {})
            return ('loop_start', 'generic', 'loop', "Loop", {})
        
        elif 'comprehension' in query_name:
            subtype = 'generic'
            for cap_name in capture_dict.keys():
                if '.' in cap_name:
                    subtype = cap_name.split('.')[1]
                    break
            return ('comprehension', subtype, f"{subtype}_comp", f"{subtype.title()} comprehension", {'energy_intensive': True})
        
        elif 'lambda' in query_name:
            return ('lambda_expression', 'definition', 'lambda', "Lambda expression", {'energy_intensive': True})
        
        elif 'stream' in query_name:
            return ('stream_operation', 'operation', name, f"Stream operation: {name}", {'energy_intensive': True})
        
        return (None, None, None, None, {})
    
    def _find_main_node_from_captures(self, capture_dict: Dict[str, List['Node']], query_name: str) -> Optional['Node']:
        """Find the main node for positioning from grouped captures"""
        # Priority order for finding the main node
        if 'function' in query_name or 'method' in query_name:
            # For functions, prefer the definition node, then name
            for key in ['function_def', 'method_def', 'constructor_def', 'function_name', 'method_name', 'constructor_name']:
                if key in capture_dict and capture_dict[key]:
                    return capture_dict[key][0]  # Take first node from list
        elif 'class' in query_name:
            # For classes, prefer the definition node, then name
            for key in ['class_def', 'class.def', 'class.name']:
                if key in capture_dict and capture_dict[key]:
                    return capture_dict[key][0]
        elif 'loop' in query_name:
            # For loops, prefer the specific loop construct
            for key in ['loop.for', 'loop.while', 'loop.do', 'loop.enhanced_for']:
                if key in capture_dict and capture_dict[key]:
                    return capture_dict[key][0]
        
        # Fallback: return the first node from the first capture
        for node_list in capture_dict.values():
            if node_list:
                return node_list[0]
        return None
    
    def _calculate_insertion_points_from_grouped_captures(
        self, 
        capture_dict: Dict[str, List['Node']], 
        language: str, 
        query_name: str
    ) -> Tuple[int, int]:
        """Calculate insertion points from grouped captures"""
        main_node = self._find_main_node_from_captures(capture_dict, query_name)
        if not main_node:
            return 1, 1
        
        # For functions, find the body start
        if 'function' in query_name or 'method' in query_name:
            body_node = None
            for key in ['function_body', 'method_body', 'constructor_body']:
                if key in capture_dict and capture_dict[key]:
                    body_node = capture_dict[key][0]  # Take first node from list
                    break
            
            if body_node:
                entry_line = body_node.start_point.row + 1
                exit_line = body_node.end_point.row + 1
            else:
                # Fallback to main node
                entry_line = main_node.start_point.row + 1
                exit_line = main_node.end_point.row + 1
        elif 'class' in query_name:
            # For classes, find the body start (inside the class, not at class definition)
            body_node = None
            for key in ['class_body', 'class.body']:
                if key in capture_dict and capture_dict[key]:
                    body_node = capture_dict[key][0]  # Take first node from list
                    break
            
            if body_node:
                # Place checkpoint at the start of the class body (after the colon)
                entry_line = body_node.start_point.row + 1
                exit_line = body_node.end_point.row + 1
            else:
                # Fallback: place after the class definition line
                entry_line = main_node.end_point.row + 1
                exit_line = main_node.end_point.row + 1
        else:
            # For other constructs, use main node boundaries
            entry_line = main_node.start_point.row + 1
            exit_line = main_node.end_point.row + 1
        
        return entry_line, exit_line
    
    def _create_function_exit_points(
        self, 
        capture_dict: Dict[str, List['Node']], 
        function_name: str, 
        metadata: Dict, 
        language: str
    ) -> List[InstrumentationPoint]:
        """Create exit points for functions, handling multiple returns"""
        points = []
        
        # Find the function body node
        body_node = None
        for key in ['function_body', 'method_body', 'constructor_body']:
            if key in capture_dict and capture_dict[key]:
                body_node = capture_dict[key][0]  # Take first node from list
                break
        
        if not body_node:
            return points
        
        # Look for return statements within the function body
        if language in self._queries and 'returns' in self._queries[language]:
            returns_query = self._queries[language]['returns']
            cursor = QueryCursor(returns_query)
            return_matches = cursor.matches(body_node)
            
            if return_matches:
                # Create exit point for each return statement
                for pattern_index, return_capture_dict in return_matches:
                    for cap_name, return_node_list in return_capture_dict.items():
                        if cap_name == 'return' and return_node_list:
                            # return_node_list is a list, take the first node
                            return_node = return_node_list[0]
                            exit_line = return_node.start_point.row + 1
                            exit_column = return_node.start_point.column + 1
                            exit_point = InstrumentationPoint(
                                id=f"function_exit_{function_name}_{exit_line}_{exit_column}",
                                type='function_exit',
                                subtype='return',
                                name=function_name,
                                line=exit_line,
                                column=exit_column,
                                context=f"Function return: {function_name}",
                                metadata=metadata
                            )
                            points.append(exit_point)
            else:
                # No explicit returns, create implicit exit at end of body
                exit_line = body_node.end_point.row + 1
                exit_column = body_node.start_point.column + 1
                exit_point = InstrumentationPoint(
                    id=f"function_exit_{function_name}_implicit_{exit_line}",
                    type='function_exit',
                    subtype='implicit',
                    name=function_name,
                    line=exit_line,
                    column=exit_column,
                    context=f"Function implicit exit: {function_name}",
                    metadata=metadata
                )
                points.append(exit_point)
        
        return points

    def _create_instrumentation_point(
        self, 
        query_name: str, 
        capture_name: str, 
        node: 'Node', 
        source_code: str,
        language: str
    ) -> List[InstrumentationPoint]:
        """Create instrumentation points from tree-sitter capture with proper insertion point calculation"""
        # Validate node before processing
        if not node or not hasattr(node, 'start_point') or not hasattr(node, 'end_point'):
            logger.warning(f"Invalid node in {query_name} query for {language}")
            return []
        
        try:
            points = []
            
            # Calculate insertion points based on the type of construct
            if capture_name in ['function_name', 'method_name', 'constructor_name']:
                # For function entries, we need to find the function body start
                entry_line, exit_line = self._calculate_function_insertion_points(node, language)
            elif capture_name.startswith('loop.') or 'loop' in capture_name:
                # For loops, use the loop construct boundaries
                entry_line, exit_line = self._calculate_loop_insertion_points(node, language)
            else:
                # Default: use node boundaries with validation
                if not node.start_point or not node.end_point:
                    logger.warning(f"Node has invalid position data in {query_name}")
                    return []
                entry_line = node.start_point.row + 1
                exit_line = node.end_point.row + 1
                
            start_line = entry_line
            start_column = node.start_point.column + 1 if node.start_point else 0
            end_line = exit_line
            end_column = node.end_point.column + 1 if node.end_point else 0
            
            text = self._extract_text_from_node(node, source_code, language)
            
        except (AttributeError, TypeError) as e:
            logger.error(f"Error accessing node properties in {query_name}: {e}")
            return []
        
        # Determine point type and metadata based on query patterns
        point_type, subtype, name, context, metadata = self._classify_capture(
            query_name, capture_name, text, language
        )
        
        if not point_type:
            return []
        
        # Create entry point
        entry_point = InstrumentationPoint(
            id=f"{point_type}_{name}_{start_line}_{start_column}",
            type=point_type,
            subtype=subtype,
            name=name,
            line=start_line,
            column=start_column,
            context=context,
            metadata=metadata
        )
        points.append(entry_point)
        
        # Create exit point for function-like constructs (like V1 did)
        if point_type == 'function_enter':
            # Check if this function needs special exit handling based on configuration
            should_create_exit = True
            if metadata and metadata.get('needs_special_exit_handling'):
                # Mark exit points specially for functions that need special handling
                    metadata['exit_handling'] = 'special'
            
            if should_create_exit:
                exit_point = InstrumentationPoint(
                    id=f"function_exit_{name}_{end_line}_{end_column}",
                    type='function_exit',
                    subtype='block_end',
                    name=name,
                    line=end_line,
                    column=end_column,
                    context=f"Function exit: {name}",
                    metadata=metadata
                )
                points.append(exit_point)
        
        # Create loop exit points
        elif point_type == 'loop_start':
            loop_exit_point = InstrumentationPoint(
                id=f"loop_exit_{name}_{end_line}_{end_column}",
                type='loop_exit',
                subtype='block_end', 
                name=name,
                line=end_line,
                column=end_column,
                context=f"Loop exit: {name}",
                metadata=metadata
            )
            points.append(loop_exit_point)
        
        return points
    
    def _create_regex_instrumentation_point(
        self,
        pattern_name: str,
        match: 'Match',
        line_num: int,
        language: str
    ) -> Optional[InstrumentationPoint]:
        """Create instrumentation point from regex match"""
        
        # Map regex patterns to instrumentation types
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
        capture_name: str, 
        text: str, 
        language: str
    ) -> Tuple[str, str, str, str, Dict]:
        """Classify tree-sitter capture into instrumentation point"""
        
        # Classification rules based on query patterns
        if 'function' in query_name or 'method' in query_name or 'constructor' in query_name:
            if capture_name in ['function_name', 'method_name', 'constructor_name', 'function.name', 'method.name']:
                # Validate function name
                if not text or not self._is_valid_identifier(text):
                    return (None, None, None, None, {})
                
                # Determine if this is a special function type
                metadata = {}
                # Use configuration-driven metadata analysis
                metadata = self._analyze_function_metadata(text, query_name, language)
                
                return ('function_enter', 'function', text, f"Function entry: {text}", metadata)
            elif capture_name in ['function_body', 'method_body', 'constructor_body', 'function.body', 'method.body']:
                # Skip body captures - exit points are generated from function_enter logic
                return (None, None, None, None, {})
        
        elif 'class' in query_name:
            if 'name' in capture_name:
                class_type = capture_name.split('.')[0] if '.' in capture_name else 'class'
                return ('class_enter', class_type, text, f"{class_type.title()} definition: {text}", {})
        
        elif 'loop' in query_name:
            # Only create checkpoints for main loop constructs, not sub-components
            valid_loop_captures = [
                'loop.for', 'loop.while', 'loop.do',          # C/C++/Java
                'loop.enhanced_for'                           # Java specific
            ]
            if capture_name in valid_loop_captures:
                loop_type = capture_name.split('.')[1]
                return ('loop_start', loop_type, f"{loop_type}_loop", f"{loop_type.title()} loop", {})
            else:
                # Skip loop sub-components (var, iter, condition, body, etc.)
                return (None, None, None, None, {})
        
        elif 'comprehension' in query_name:
            comp_type = capture_name.split('.')[1] if '.' in capture_name else 'comprehension'
            return ('comprehension', comp_type, f"{comp_type}_comp", 
                   f"{comp_type.title()} comprehension", {'energy_intensive': True})
        
        elif 'lambda' in query_name:
            return ('lambda_expression', 'definition', 'lambda', 
                   "Lambda expression", {'energy_intensive': True})
        
        elif 'stream' in query_name:
            return ('stream_operation', 'operation', text, 
                   f"Stream operation: {text}", {'energy_intensive': True})
        
        elif 'memory' in query_name:
            return ('memory_operation', 'allocation', text, 
                   f"Memory operation: {text}", {'energy_intensive': True})
        
        return (None, None, None, None, {})
    
    def _extract_text_from_node(self, node: 'Node', source_code: str, language: str = "python") -> str:
        """Extract text content from tree-sitter node with validation"""
        try:
            start_byte = node.start_byte
            end_byte = node.end_byte
            
            # Basic validation
            if start_byte < 0 or end_byte < 0 or start_byte >= end_byte:
                return ""
            
            if end_byte > len(source_code):
                end_byte = len(source_code)
            
            text = source_code[start_byte:end_byte].strip()
            
            # Additional validation for function/method names
            limits = self._config_manager.get_processing_limits(language)
            max_name_length = limits.get('max_function_name_length', 100)
            if len(text) > max_name_length:  # Function names shouldn't be extremely long
                return ""
            
            # Check for malformed content (like containing newlines in function names)
            if '\n' in text and len(text.split('\n')) > 2:
                # If it's multi-line, try to extract just the identifier
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and line.isidentifier():
                        return line
                # Fallback: try to find identifier pattern
                identifier_match = re.search(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
                if identifier_match:
                    return identifier_match.group()
                return ""
            
            return text
            
        except Exception:
            return ""
    
    def _is_valid_identifier(self, text: str, language: str = "python") -> bool:
        """Check if text is a valid identifier for function/method names"""
        if not text:
            return False
        
        # Basic identifier validation
        
        # Must start with letter or underscore, contain only letters, digits, underscores
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', text):
            return False
        
        # Reject overly long names (likely extraction errors)
        limits = self._config_manager.get_processing_limits(language)
        max_identifier_length = limits.get('max_identifier_length', 50)
        if len(text) > max_identifier_length:
            return False
        
        # Reject names with common syntax elements that indicate parsing errors
        invalid_patterns = [
            r'[(){}[\]<>]',  # Brackets, parentheses
            r'[+\-*/%=!&|^~]',  # Operators
            r'[;,.]',  # Punctuation
            r'\s',  # Whitespace
            r'["\']',  # Quotes
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, text):
                return False
        
        return True
    
    def _byte_to_point(self, code: str, byte_offset: int) -> Tuple[int, int]:
        """Convert byte offset to (row, column) point"""
        if byte_offset >= len(code):
            byte_offset = len(code)
        
        # Count lines and calculate column
        lines = code[:byte_offset].split('\n')
        row = len(lines) - 1
        column = len(lines[-1]) if lines else 0
        
        return (row, column)
    
    def _calculate_function_insertion_points(self, function_name_node: 'Node', language: str):
        """Calculate where to insert function entry and exit checkpoints"""
        # Validate input node
        if not function_name_node or not hasattr(function_name_node, 'parent'):
            logger.warning(f"Invalid function name node for {language}")
            return 1, 1  # Safe fallback
        
        # Find the parent function definition
        parent = function_name_node.parent
        safety_counter = 0
        while parent and parent.type not in ['function_definition', 'method_definition', 'constructor_definition']:
            parent = parent.parent
            safety_counter += 1
            limits = self._config_manager.get_processing_limits(language)
            max_safety_counter = limits.get('max_safety_counter', 10)
            if safety_counter > max_safety_counter:  # Prevent infinite loops
                logger.warning(f"Deep AST traversal for function in {language}, stopping")
                break
        
        if not parent or not hasattr(parent, 'start_point') or not hasattr(parent, 'end_point'):
            # Fallback: use name node location with validation
            if hasattr(function_name_node, 'start_point') and hasattr(function_name_node, 'end_point'):
                return function_name_node.start_point.row + 1, function_name_node.end_point.row + 1
            else:
                return 1, 1  # Safe fallback
        
        # For function entry: find the opening brace or first statement in body
        entry_line = parent.start_point.row + 1
        
        # Use AST processor to find the correct insertion point
        # TODO: Pass tree parameter for TreeSitter indentation engine
        ast_processor = ASTProcessor(language, source_code, None)
        insertion_byte = ast_processor.find_insertion_point(parent, 'inside_start')
        if insertion_byte is not None:
            # Convert byte offset to line number
            entry_line = self._byte_to_point(source_code, insertion_byte)[0] + 1
        
        # For function exit: use the end of the function
        exit_line = parent.end_point.row + 1
        
        return entry_line, exit_line
    
    def _calculate_loop_insertion_points(self, loop_node: 'Node', language: str):
        """Calculate where to insert loop entry and exit checkpoints"""
        # Validate input node
        if not loop_node or not hasattr(loop_node, 'type'):
            logger.warning(f"Invalid loop node for {language}")
            return 1, 1  # Safe fallback
        
        # Find the actual loop construct using configuration
        node_types = self._config_manager.get_node_types(language)
        loop_types = node_types.get('loop_types', ['for_statement', 'while_statement', 'do_statement'])
        
        if loop_node.type in loop_types:
            loop_construct = loop_node
        else:
            # The node might be a child of the loop, find the parent loop
            parent = loop_node.parent
            safety_counter = 0
            while parent and parent.type not in loop_types:
                parent = parent.parent
                safety_counter += 1
                limits = self._config_manager.get_processing_limits(language)
                max_safety_counter = limits.get('max_safety_counter', 10)
                if safety_counter > max_safety_counter:  # Prevent infinite loops
                    logger.warning(f"Deep AST traversal for loop in {language}, stopping")
                    break
            loop_construct = parent if parent else loop_node
        
        # Validate loop construct has position data
        if not hasattr(loop_construct, 'start_point') or not hasattr(loop_construct, 'end_point'):
            logger.warning(f"Loop construct missing position data in {language}")
            return 1, 1  # Safe fallback
        
        # Entry point: just before the loop starts
        entry_line = loop_construct.start_point.row + 1 if loop_construct.start_point else 1
        
        # Exit point: just after the loop ends  
        exit_line = loop_construct.end_point.row + 1 if loop_construct.end_point else 1
        
        return entry_line, exit_line
    
    def _analyze_function_metadata(self, function_name: str, query_name: str, language: str) -> Dict:
        """Analyze function to determine special characteristics using configuration"""
        metadata = {}
        
        # Get language-specific rules
        rules = self._config_manager.get_rules(language)
        
        # Detect special function types based on naming conventions
        if function_name.startswith('__') and function_name.endswith('__'):
            metadata['is_dunder'] = True
            metadata['function_type'] = 'magic_method'
        elif function_name.startswith('_'):
            metadata['is_private'] = True
        
        # Check if function needs special exit handling based on configuration
        special_functions = rules.get('special_exit_functions', [])
        metadata['needs_special_exit_handling'] = function_name in special_functions
        
        return metadata
    
    def _analyze_optimizations(self, source_code: str, language: str) -> List[str]:
        """Generate optimization suggestions for the given language"""
        suggestions = []
        
        # Get analysis patterns for optimization analysis
        patterns = self._config_manager.get_analysis_patterns(language)
        
        # Use configuration-driven optimization analysis
        if 'import_star' in patterns and patterns['import_star'] in source_code:
            suggestions.append("Avoid wildcard imports for better performance and clarity")
        
        if 'nested_loops' in patterns:
            import re
            nested_loops = len(re.findall(patterns['nested_loops'], source_code, re.MULTILINE))
            if nested_loops > 0:
                suggestions.append(f"Found {nested_loops} nested loops - consider algorithmic optimizations")
        
        # Language-agnostic optimizations based on patterns
        for pattern_name, pattern in patterns.items():
            if pattern_name.endswith('_in_loop') and pattern:
                import re
                if re.search(pattern, source_code):
                    suggestions.append(f"Consider optimizing {pattern_name.replace('_in_loop', '')} usage in loops")
        
        if 'new_op' in patterns and 'smart_ptr' not in source_code:
            import re
            if re.search(patterns['new_op'], source_code):
                suggestions.append("Consider using smart pointers instead of raw pointers")
        
        return suggestions
    
    
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
        
        # Use AST-based instrumentation if tree-sitter is available
        if TREE_SITTER_AVAILABLE:
            return self._instrument_code_ast_based(source_code, points, language)
        else:
            # Fallback to line-based instrumentation
            logger.warning("Tree-sitter unavailable, using legacy line-based instrumentation")
            return self._instrument_code_legacy(source_code, points, language)
    
    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get parser for the specified language"""
        return self._parsers.get(language)
    
    def _find_import_insertion_point(self, source_code: str, language: str) -> Optional[int]:
        """Find the correct byte offset for inserting import statements"""
        lines = source_code.split('\n')
        insert_line = 0
        in_docstring = False
        docstring_marker = None
        
        # Language-specific handling
        if language in ['c', 'cpp']:
            # For C/C++, insert after existing #include statements
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('#include'):
                    insert_line = i + 1
                elif stripped and not stripped.startswith('#'):
                    break
        elif language == 'java':
            # For Java, insert after package/import statements
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('package ') or stripped.startswith('import '):
                    insert_line = i + 1
                elif stripped and not stripped.startswith('//'):
                    break
        else:
            # For Python and other languages, use the original logic
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Handle shebang
                if stripped.startswith('#!'):
                    insert_line = i + 1
                    continue
                    
                # Handle docstring start
                if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                    docstring_marker = stripped[:3]
                    # Check if single-line docstring
                    if stripped.count(docstring_marker) >= 2 and len(stripped) > 3:
                        insert_line = i + 1
                        continue
                    else:
                        in_docstring = True
                        continue
                        
                # Handle docstring end
                if in_docstring and docstring_marker and stripped.endswith(docstring_marker):
                    in_docstring = False
                    insert_line = i + 1
                    continue
                    
                # Skip empty lines and comments at start
                if not stripped or stripped.startswith('#'):
                    if insert_line <= i:
                        insert_line = i + 1
                    continue
                    
                # Found first code line
                if not in_docstring:
                    break
        
        # Convert line number to byte offset
        if insert_line >= len(lines):
            return len(source_code)
        
        # Calculate byte offset
        byte_offset = 0
        for i in range(insert_line):
            byte_offset += len(lines[i]) + 1  # +1 for newline
        
        return byte_offset
    
    def _instrument_code_ast_based(self, source_code: str, points: List[InstrumentationPoint], language: str) -> str:
        """
        AST-based instrumentation using tree-sitter incremental parsing.
        
        This is the preferred approach as it maintains syntax correctness.
        """
        try:
            # Get parser and parse initial tree
            parser = self._get_parser(language)
            if not parser:
                logger.warning(f"⚠️  FALLBACK: No parser available for {language}, using legacy instrumentation instead of AST-based instrumentation")
                return self._instrument_code_legacy(source_code, points, language)
            
            tree = parser.parse(source_code.encode('utf-8'))
            if not tree:
                logger.warning(f"⚠️  FALLBACK: Failed to parse {language} code, using legacy instrumentation instead of AST-based instrumentation")
                return self._instrument_code_legacy(source_code, points, language)
            
            # Create AST rewriter
            rewriter = ASTRewriter(source_code, language, parser, tree)
            
            # Add import statement first if we have points to instrument
            if points:
                import_statement = self._language_agnostic_generator.get_import_statement(language)
                if import_statement:
                    # Find the correct insertion point for import (after shebang/docstring)
                    import_offset = self._find_import_insertion_point(source_code, language)
                    if import_offset is not None:
                        import_point = InstrumentationPoint(
                            id="import_runtime",
                            type="import",
                            subtype="runtime",
                            name="codegreen_import",
                            line=1,
                            column=0,
                            context="CodeGreen runtime import",
                            byte_offset=import_offset,
                            insertion_mode='before'
                        )
                        rewriter.add_instrumentation(import_point, import_statement + '\n')
            
            # Deduplicate and sort points before instrumentation
            deduplicated_points = self._deduplicate_checkpoints(points)
            
            # Sort points by byte offset (reverse order for correct insertion)
            # Function entries should come before exits, so we also sort by type
            sorted_points = sorted(deduplicated_points, key=lambda p: (
                getattr(p, 'byte_offset', 0) if hasattr(p, 'byte_offset') and p.byte_offset is not None else p.line * 1000,
                0 if p.type == 'function_enter' else 1  # Ensure function_enter comes before function_exit
            ), reverse=True)
            
            logger.debug(f"📊 After deduplication and sorting: {len(sorted_points)} points (was {len(points)})")
            
            # Add instrumentation for each point
            successful_instrumentations = 0
            for i, point in enumerate(sorted_points):
                logger.debug(f"🔧 Processing instrumentation point {i+1}/{len(sorted_points)}: {point.type} '{point.name}'")
                logger.debug(f"   Point details: line={point.line}, column={point.column}, mode={point.insertion_mode}")
                logger.debug(f"   Byte offset: {getattr(point, 'byte_offset', 'None')}")
                logger.debug(f"   Node info: {getattr(point, 'node', 'None')}")
                
                # Generate instrumentation code
                instrumentation_code = self._generate_instrumentation_code(point, language)
                if instrumentation_code:
                    logger.debug(f"   Generated instrumentation: '{instrumentation_code}'")
                    success = rewriter.add_instrumentation(point, instrumentation_code)
                    if success:
                        successful_instrumentations += 1
                        logger.debug(f"   ✅ Successfully added instrumentation")
                    else:
                        logger.warning(f"   ❌ Failed to add instrumentation")
                else:
                    logger.warning(f"   ❌ No instrumentation code generated")
            
            # Apply all edits using proper tree-sitter workflow
            if successful_instrumentations > 0:
                instrumented_code = rewriter.apply_edits()
                logger.info(f"AST-based instrumentation added {successful_instrumentations} checkpoints to {language} code")
                return instrumented_code
            else:
                logger.warning(f"No successful instrumentations for {language}, returning original code")
                return source_code
                
        except Exception as e:
            logger.warning(f"⚠️  FALLBACK: AST-based instrumentation failed for {language}: {e}, using legacy instrumentation instead")
            return self._instrument_code_legacy(source_code, points, language)
    
    def _instrument_code_legacy(self, source_code: str, points: List[InstrumentationPoint], language: str) -> str:
        """Legacy line-based instrumentation (fallback)"""
        logger.warning(f"⚠️  FALLBACK: Using legacy line-based instrumentation for {language} instead of AST-based instrumentation")
        # Use generic instrumentation for all languages
        return self._instrument_generic(source_code, points, language)
    
    def _generate_instrumentation_code(self, point: InstrumentationPoint, language: str) -> Optional[str]:
        """Generate language-agnostic instrumentation code for a given point"""
        return self._language_agnostic_generator.generate_instrumentation(point, language)
    
    def _instrument_python(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        """Python-specific code instrumentation with codegreen_runtime"""
        lines = source_code.split('\n')
        
        # Add codegreen_runtime import at the top
        runtime_import = "import codegreen_runtime as _codegreen_rt"
        
        # Find insertion point for import (after shebang/docstring)
        insert_line = 0
        in_docstring = False
        docstring_marker = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Handle shebang
            if stripped.startswith('#!'):
                insert_line = i + 1
                continue
                
            # Handle docstring start
            if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                docstring_marker = stripped[:3]
                # Check if single-line docstring
                if stripped.count(docstring_marker) >= 2 and len(stripped) > 3:
                    insert_line = i + 1
                    continue
                else:
                    in_docstring = True
                    continue
                    
            # Handle docstring end
            if in_docstring and docstring_marker and stripped.endswith(docstring_marker):
                in_docstring = False
                insert_line = i + 1
                continue
                
            # Skip empty lines and comments at start
            if not stripped or stripped.startswith('#'):
                if insert_line <= i:
                    insert_line = i + 1
                continue
                
            # Found first code line
            if not in_docstring:
                break
        
        lines.insert(insert_line, runtime_import)
        
        # Adjust line numbers for inserted import
        adjusted_points = [
            InstrumentationPoint(
                p.id, p.type, p.subtype, p.name,
                p.line + 1,  # Add 1 for the import line
                p.column, p.context, p.metadata
            ) for p in points
        ]
        
        # Deduplicate points before insertion
        deduplicated_points = self._deduplicate_checkpoints(adjusted_points)
        
        # Sort points by line number (descending) to avoid offset issues
        sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines):
                instrumentation = self._generate_python_call(point)
                
                # Handle different insertion strategies
                if point.type == 'function_enter':
                    # Entry points go at the FIRST line inside the function body (not after def line)
                    insert_index = point.line - 1  # Convert 1-based to 0-based
                    if insert_index < len(lines):
                        # Use indentation of the target line + one level
                        original_line = lines[insert_index]
                        base_indent = self._get_indentation(original_line)
                        indent = base_indent + "    "  # Add one indentation level for function body
                    else:
                        indent = "    "  # Default Python indent
                elif point.type == 'class_enter':
                    # Class entry points go at the FIRST line inside the class body
                    insert_index = point.line - 1  # Convert 1-based to 0-based
                    if insert_index < len(lines):
                        # For classes, use standard class body indentation (4 spaces)
                        # Don't add extra indentation since we're already inside the class
                        indent = "    "  # Standard class body indentation
                    else:
                        indent = "    "  # Default Python indent
                elif point.type == 'function_exit':
                    # Exit points go BEFORE the function end (before return statements)
                    insert_index = self._find_exit_insertion_point(lines, point.line, 'function')
                    if insert_index < len(lines):
                        # Use same indentation as the target line
                        original_line = lines[insert_index]
                        indent = self._get_indentation(original_line)
                    else:
                        indent = "    "  # Default Python indent
                elif point.type == 'loop_exit':
                    # Loop exits go AFTER the loop ends
                    insert_index = self._find_exit_insertion_point(lines, point.line, 'loop')
                    if insert_index < len(lines):
                        # Use same indentation as the loop
                        original_line = lines[insert_index]
                        indent = self._get_indentation(original_line)
                    else:
                        indent = "    "  # Default Python indent
                else:
                    # Default behavior for other types (loop_start, etc.)
                    insert_index = point.line - 1  # Convert 1-based to 0-based
                    if insert_index < len(lines):
                        original_line = lines[insert_index]
                        base_indent = self._get_indentation(original_line)
                        indent = base_indent + "    "  # Add appropriate indentation
                    else:
                        indent = "    "
                
                instrumented_call = indent + instrumentation
                lines.insert(insert_index, instrumented_call)
        
        return '\n'.join(lines)
    
    def _instrument_c(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        """C-specific code instrumentation"""
        lines = source_code.split('\n')
        
        # Add runtime header
        runtime_header = self._generate_c_runtime()
        lines.insert(0, runtime_header)
        
        # Adjust line numbers for inserted header
        adjusted_points = [
            InstrumentationPoint(
                p.id, p.type, p.subtype, p.name,
                p.line + runtime_header.count('\n'),
                p.column, p.context, p.metadata
            ) for p in points
        ]
        
        # Deduplicate points before insertion
        deduplicated_points = self._deduplicate_checkpoints(adjusted_points)
        
        # Insert instrumentation calls
        sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines):
                instrumentation = self._generate_c_call(point)
                
                # Handle different insertion strategies
                if point.type == 'function_enter':
                    # For function entry, insert after the opening brace
                    insert_index = self._find_c_function_body_start(lines, point.line - 1)
                    if insert_index == -1:
                        # Fallback: insert at function name line + 1
                        insert_index = point.line
                elif point.type == 'function_exit':
                    # For function exit, use the exit placement logic
                    insert_index = self._find_exit_insertion_point(lines, point.line, 'function')
                elif point.type == 'loop_exit':
                    # For loop exit, use the exit placement logic  
                    insert_index = self._find_exit_insertion_point(lines, point.line, 'loop')
                else:
                    # Default behavior for other types
                    insert_index = point.line - 1
                
                # Ensure valid index
                insert_index = max(0, min(insert_index, len(lines)))
                
                if insert_index < len(lines):
                    indent = self._get_indentation(lines[insert_index])
                else:
                    indent = "    "  # Default indent
                    
                instrumented_call = indent + instrumentation
                lines.insert(insert_index, instrumented_call)
        
        return '\n'.join(lines)
    
    def _instrument_cpp(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        """C++-specific code instrumentation"""
        lines = source_code.split('\n')
        
        # Add include
        include_line = "#include <codegreen_runtime.h>"
        lines.insert(0, include_line)
        
        # Adjust and insert calls
        adjusted_points = [
            InstrumentationPoint(
                p.id, p.type, p.subtype, p.name, p.line + 1,
                p.column, p.context, p.metadata
            ) for p in points
        ]
        
        # Deduplicate points before insertion
        deduplicated_points = self._deduplicate_checkpoints(adjusted_points)
        
        sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines):
                instrumentation = self._generate_cpp_call(point)
                insert_index = point.line - 1
                
                indent = self._get_indentation(lines[insert_index])
                instrumented_call = indent + instrumentation
                
                lines.insert(insert_index, instrumented_call)
        
        return '\n'.join(lines)
    
    def _instrument_java(self, source_code: str, points: List[InstrumentationPoint]) -> str:
        """Java-specific code instrumentation"""
        lines = source_code.split('\n')
        
        # Add runtime class
        runtime_class = self._generate_java_runtime()
        
        # Find insertion point after package/imports
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('package ') or line.strip().startswith('import '):
                insert_pos = i + 1
            elif line.strip() and not line.strip().startswith('//'):
                break
        
        lines.insert(insert_pos, runtime_class)
        line_offset = runtime_class.count('\n') + 1
        
        # Adjust and insert calls
        adjusted_points = [
            InstrumentationPoint(
                p.id, p.type, p.subtype, p.name, p.line + line_offset,
                p.column, p.context, p.metadata
            ) for p in points
        ]
        
        # Deduplicate points before insertion
        deduplicated_points = self._deduplicate_checkpoints(adjusted_points)
        
        sorted_points = sorted(deduplicated_points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines):
                instrumentation = self._generate_java_call(point)
                insert_index = point.line - 1
                
                indent = self._get_indentation(lines[insert_index])
                instrumented_call = indent + instrumentation
                
                lines.insert(insert_index, instrumented_call)
        
        return '\n'.join(lines)
    
    def _instrument_generic(self, source_code: str, points: List[InstrumentationPoint], language: str) -> str:
        """Generic instrumentation for all languages using configuration"""
        lines = source_code.split('\n')
        
        # Get language-specific configuration
        config = self._config_manager.get_instrumentation_config(language)
        comment_prefix = config.get('comment_prefix', '//') if config else '//'
        
        sorted_points = sorted(points, key=lambda p: p.line, reverse=True)
        
        for point in sorted_points:
            if 1 <= point.line <= len(lines):
                # Generate instrumentation code using the language-agnostic generator
                instrumentation_code = self._generate_instrumentation_code(point, language)
                if instrumentation_code:
                    insert_index = point.line - 1
                    lines.insert(insert_index, instrumentation_code)
        
        return '\n'.join(lines)
    
    def _generate_python_call(self, point: InstrumentationPoint) -> str:
        """Generate Python measurement call using codegreen_runtime"""
        return (
            f"_codegreen_rt.checkpoint('{point.checkpoint_id}', '{point.name}', '{point.type.split('_')[1]}')"
        )
    
    def _generate_c_call(self, point: InstrumentationPoint) -> str:
        """Generate C measurement call"""
        return (
            f"codegreen_measure_checkpoint(\"{point.checkpoint_id}\", \"{point.type}\", "
            f"\"{point.name}\", {point.line}, \"{point.context}\");"
        )
    
    def _generate_cpp_call(self, point: InstrumentationPoint) -> str:
        """Generate C++ measurement call"""
        return (
            f"codegreen_measure_checkpoint(\"{point.checkpoint_id}\", \"{point.type}\", "
            f"\"{point.name}\", {point.line}, \"{point.context}\");"
        )
    
    def _generate_java_call(self, point: InstrumentationPoint) -> str:
        """Generate Java measurement call"""
        return (
            f"CodeGreenRuntime.measureCheckpoint(\"{point.checkpoint_id}\", \"{point.type}\", "
            f"\"{point.name}\", {point.line}, \"{point.context}\");"
        )
    
    def _generate_c_runtime(self) -> str:
        """Generate C runtime header"""
        return (
            "#include <stdio.h>\n"
            "#include <sys/time.h>\n"
            "void codegreen_measure_checkpoint(const char* id, const char* type, const char* name, int line, const char* context) {\n"
            "    struct timeval tv; gettimeofday(&tv, NULL);\n"
            "    printf(\"CODEGREEN_CHECKPOINT: %s|%s|%s|%d|%s|%ld.%06ld\\n\", id, type, name, line, context, tv.tv_sec, tv.tv_usec);\n"
            "}\n"
        )
    
    def _generate_java_runtime(self) -> str:
        """Generate Java runtime class"""
        return (
            "import java.time.Instant;\n"
            "class CodeGreenRuntime {\n"
            "    public static void measureCheckpoint(String id, String type, String name, int line, String context) {\n"
            "        long timestamp = Instant.now().toEpochMilli();\n"
            "        System.out.println(\"CODEGREEN_CHECKPOINT: \" + id + \"|\" + type + \"|\" + name + \"|\" + line + \"|\" + context + \"|\" + timestamp);\n"
            "    }\n"
            "}\n"
        )
    
    def _get_indentation(self, line: str) -> str:
        """Extract indentation from line"""
        indent_end = 0
        for char in line:
            if char in ' \t':
                indent_end += 1
            else:
                break
        return line[:indent_end]
    
    def _find_exit_insertion_point(self, lines: List[str], target_line: int, construct_type: str) -> int:
        """
        Find the correct insertion point for exit checkpoints.
        
        For functions: Insert before return statements or at the end of the function body
        For loops: Insert after the loop construct ends
        """
        if construct_type == 'function':
            # Find the best location before the function ends
            # Look backwards from target_line to find return statements or end of function
            for i in range(target_line - 1, 0, -1):
                if i >= len(lines):
                    continue
                    
                line = lines[i].strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # If we find a return statement, insert before it
                if line.startswith('return '):
                    return i
                
                # If we find substantial code, this might be the end of function body
                # Insert after this line
                if line and not line.startswith(('"""', "'''", '#')):
                    return i + 1
            
            # Fallback: insert before target line
            return max(0, target_line - 1)
            
        elif construct_type == 'loop':
            # For loops, we want to insert AFTER the loop ends
            # The target_line is the end of the loop, so insert after it
            return min(len(lines), target_line)
            
        else:
            # Default case
            return max(0, target_line - 1)
    
    def _deduplicate_checkpoints(self, points: List[InstrumentationPoint]) -> List[InstrumentationPoint]:
        """
        Remove duplicate checkpoints using optimized O(n log n) algorithm.
        
        Two checkpoints are considered duplicates if they:
        1. Have the same type and line number
        2. Or have the same type, name, and are within 1 line of each other
        """
        if not points:
            return []
        
        # Sort points by (type, line, name) for efficient deduplication
        sorted_points = sorted(points, key=lambda p: (p.type, p.line, p.name))
        
        deduplicated = []
        seen_keys = set()
        
        for point in sorted_points:
            # Primary deduplication key
            primary_key = (point.type, point.line, point.name)
            
            # Alternative keys for nearby duplicates
            nearby_keys = [
                (point.type, point.line - 1, point.name),
                (point.type, point.line + 1, point.name)
            ]
            
            # Check if this point or nearby duplicates already exist
            if (primary_key not in seen_keys and 
                not any(key in seen_keys for key in nearby_keys)):
                
                deduplicated.append(point)
                seen_keys.add(primary_key)
        
        return deduplicated
    
    def _find_c_function_body_start(self, lines: List[str], func_line_index: int) -> int:
        """Find the first line inside a C function body (after opening brace)"""
        brace_count = 0
        found_opening = False
        
        # Look for the function's opening brace, being careful about nested braces
        for i in range(max(0, func_line_index), min(len(lines), func_line_index + 10)):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//') or line.startswith('/*'):
                continue
            
            # Look for opening brace - should be at the end of function signature
            if '{' in line and not found_opening:
                # Check if this looks like a function signature line
                if ('(' in line and ')' in line) or found_opening or i > func_line_index:
                    found_opening = True
                    # Return the line after the opening brace
                    if line.strip().endswith('{'):
                        return i + 1
                    else:
                        # Brace is not at end of line, look for insertion point
                        brace_pos = line.find('{')
                        if brace_pos != -1:
                            return i + 1
        
        # Fallback: return line after function signature
        return func_line_index + 1


# Global engine instance
_language_engine = None


def get_language_engine() -> LanguageEngine:
    """Get global language engine instance"""
    global _language_engine
    if _language_engine is None:
        _language_engine = LanguageEngine()
    return _language_engine


# Legacy compatibility functions
def analyze_code(source_code: str, language: str) -> List[Dict]:
    """Legacy function for backward compatibility"""
    engine = get_language_engine()
    result = engine.analyze_code(source_code, language)
    
    # Convert to legacy checkpoint format
    checkpoints = []
    for point in result.instrumentation_points:
        checkpoints.append({
            'id': point.checkpoint_id,
            'type': point.type,
            'name': point.name,
            'line_number': point.line,
            'column_number': point.column,
            'context': point.context
        })
    
    return checkpoints


def instrument_code(source_code: str, checkpoints: List[Dict], language: str) -> str:
    """Legacy function for backward compatibility"""
    engine = get_language_engine()
    
    # Convert legacy checkpoints to instrumentation points
    points = []
    for checkpoint in checkpoints:
        point = InstrumentationPoint(
            id=checkpoint['id'],
            type=checkpoint['type'],
            subtype='legacy',
            name=checkpoint['name'],
            line=checkpoint['line_number'],
            column=checkpoint.get('column_number', 0),
            context=checkpoint['context']
        )
        points.append(point)
    
    return engine.instrument_code(source_code, points, language)