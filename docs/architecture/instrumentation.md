# CodeGreen Instrumentation System

This document provides an in-depth technical reference for CodeGreen's instrumentation system, which automatically injects energy measurement checkpoints into source code.

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Language Configuration](#language-configuration)
6. [Tree-sitter Integration](#tree-sitter-integration)
7. [Checkpoint Injection](#checkpoint-injection)
8. [Adding New Languages](#adding-new-languages)

## Overview

The instrumentation system transforms source code by inserting checkpoint markers at function entry/exit points, enabling the NEMB backend to attribute energy consumption to specific code regions.

**Key Characteristics:**
- Language-agnostic design using tree-sitter for AST parsing
- Configuration-driven behavior via JSON files
- Community-maintained queries from nvim-treesitter
- Automatic fallback to regex analysis when tree-sitter unavailable
- Support for Python, C, C++, Java, JavaScript

**Location:** `src/instrumentation/`

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLI / C++ Backend                                │
│                    (codegreen measure <file>)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │  bridge_analyze.py │           │bridge_instrument.py│
        │   (Analysis Phase) │           │(Instrumentation)  │
        └─────────┬─────────┘           └─────────┬─────────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                    ┌─────────────────────────┐
                    │     LanguageEngine      │
                    │  (Main Orchestrator)    │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ExternalQuery  │     │LanguageConfig   │     │  ASTProcessor   │
│    Loader     │     │    Manager      │     │   ASTRewriter   │
│(nvim-treesitter)│   │ (JSON configs)  │     │(Code Transform) │
└───────────────┘     └─────────────────┘     └─────────────────┘
        │                     │                       │
        ▼                     ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│third_party/   │     │configs/         │     │tree-sitter      │
│nvim-treesitter│     │  python.json    │     │language-pack    │
│  /queries/    │     │  cpp.json       │     │(AST parsing)    │
└───────────────┘     │  java.json      │     └─────────────────┘
                      │  c.json         │
                      └─────────────────┘
```

## Core Components

### 1. LanguageEngine

**Location:** `src/instrumentation/language_engine.py:345-2200`

The main orchestrator that coordinates all instrumentation operations.

```python
class LanguageEngine:
    def __init__(self, max_file_size_mb=100, parser_timeout_ms=30000):
        self._parsers: Dict[str, Parser] = {}      # tree-sitter parsers
        self._languages: Dict[str, Language] = {}   # tree-sitter languages
        self._queries: Dict[str, Dict[str, Query]] = {}  # compiled queries
        self._config_manager = get_language_config_manager()
        self._external_query_loader = ExternalQueryLoader()
        self._language_agnostic_generator = LanguageAgnosticInstrumentationGenerator()
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `analyze_code(source, language, filename)` | Analyze source and find instrumentation points |
| `instrument_code(source, points, language)` | Inject checkpoints at specified points |
| `detect_language(filename)` | Detect language from file extension |
| `get_supported_languages()` | List all supported language identifiers |

### 2. ExternalQueryLoader

**Location:** `src/instrumentation/language_engine.py:94-268`

Loads tree-sitter queries from nvim-treesitter for comprehensive AST pattern matching.

```python
class ExternalQueryLoader:
    def __init__(self, nvim_treesitter_path=None):
        self.nvim_treesitter_path = nvim_treesitter_path or self._find_nvim_treesitter_path()
        self.query_cache = {}

        # Maps capture names to instrumentation point types
        self.CAPTURE_MAP = {
            'local.definition.function': {'type': 'function_enter', ...},
            'function': {'type': 'function_enter', ...},
            'keyword.return': {'type': 'function_exit', ...},
        }
```

**Query Loading Process:**
1. Searches for nvim-treesitter in `third_party/nvim-treesitter`
2. Loads all `.scm` files from `queries/<language>/`
3. Combines into single comprehensive query
4. Falls back to built-in queries if external unavailable

### 3. LanguageAgnosticInstrumentationGenerator

**Location:** `src/instrumentation/language_engine.py:270-343`

Generates language-specific checkpoint code from configuration templates.

```python
class LanguageAgnosticInstrumentationGenerator:
    def generate_instrumentation(self, point: InstrumentationPoint, language: str) -> str:
        config = self.config_manager.get_instrumentation_config(language)
        templates = config.get('templates', {})
        template = templates.get(point.type)

        # Template substitution
        code = template.replace("{checkpoint_id}", point.id)
        code = code.replace("{name}", point.name)
        return code
```

### 4. ASTProcessor

**Location:** `src/instrumentation/ast_processor.py:48-300`

Handles AST navigation and finding precise insertion points.

```python
class ASTProcessor:
    def __init__(self, language: str, source_code: str, tree: Tree):
        self.language = language
        self.source_code = source_code
        self.tree = tree
        self.config = config_manager.get_config(language)
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `find_body_node(node)` | Find function/class body for checkpoint insertion |
| `find_insertion_point(node, mode)` | Calculate byte offset for insertion |
| `_find_target_with_query(node, rule)` | Execute insertion query to find target |

### 5. ASTRewriter

**Location:** `src/instrumentation/ast_processor.py:300-500`

Applies edits to source code while maintaining correctness.

```python
@dataclass
class ASTEdit:
    byte_offset: int
    insertion_text: str
    edit_type: str  # 'insert_before', 'insert_after', 'insert_inside_start'
    node_info: Optional[str] = None

class ASTRewriter:
    def __init__(self, source_code: str, language: str, parser: Parser, tree: Tree):
        self.source_code = source_code
        self.edits: List[ASTEdit] = []
        self.ast_processor = ASTProcessor(language, source_code, tree)

    def apply_edits(self) -> str:
        # Sort edits by byte offset (descending) to preserve positions
        sorted_edits = sorted(self.edits, key=lambda e: e.byte_offset, reverse=True)
        result = self.source_code
        for edit in sorted_edits:
            result = result[:edit.byte_offset] + edit.insertion_text + result[edit.byte_offset:]
        return result
```

### 6. LanguageConfigManager

**Location:** `src/instrumentation/language_configs.py:62-210`

Centralized configuration management loading per-language JSON files.

```python
class LanguageConfigManager:
    def __init__(self, config_dir=None):
        self.config_dir = config_dir or Path(__file__).parent / "configs"
        self._configs: Dict[str, LanguageConfig] = {}
        self._load_configs()

    def get_config(self, language: str) -> Optional[LanguageConfig]
    def get_instrumentation_config(self, language: str) -> Dict[str, Any]
    def get_ast_config(self, language: str) -> Dict[str, Any]
    def get_query_config(self, language: str) -> Dict[str, Any]
```

### 7. Bridge Scripts

**bridge_analyze.py** - Called by C++ to analyze source files:
```python
def main():
    engine = LanguageEngine()
    result = engine.analyze_code(source_code, filename=source_file)
    for point in result.instrumentation_points:
        print(f"POINT|{point.id}|{point.type}|{point.name}|{point.line}")
```

**bridge_instrument.py** - Called by C++ to instrument source files:
```python
def main():
    engine = LanguageEngine()
    result = engine.analyze_code(source_code, filename=source_file)
    instrumented = engine.instrument_code(source_code, result.instrumentation_points, result.language)
    sys.stdout.write(instrumented)
```

## Data Flow

### Analysis Phase

```
Source File
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Language Detection                                           │
│    detect_language(filename) → "python"                         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. AST Parsing                                                  │
│    parser.parse(source_code.encode('utf-8')) → Tree             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Query Execution                                              │
│    cursor = QueryCursor(query)                                  │
│    captures = cursor.captures(tree.root_node)                   │
│    → {'function': [node1, node2], 'return': [node3]}           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Capture Mapping                                              │
│    'function' → function_enter                                  │
│    'return' → function_exit                                     │
│    → [InstrumentationPoint(...), ...]                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Deduplication                                                │
│    Remove duplicate points at same location                     │
│    Prefer higher-priority captures                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
AnalysisResult(instrumentation_points=[...])
```

### Instrumentation Phase

```
InstrumentationPoints + Source Code
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Create ASTRewriter                                           │
│    rewriter = ASTRewriter(source_code, language, parser, tree)  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Generate Import Statement                                    │
│    import_stmt = "from codegreen_core.energy_meter import..."  │
│    Insert at top of file after shebang/docstring               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. For Each InstrumentationPoint:                               │
│    a. Find body node (function/class body)                      │
│    b. Calculate insertion byte offset                           │
│    c. Generate checkpoint code from template                    │
│    d. Create ASTEdit with proper indentation                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Apply Edits                                                  │
│    Sort edits by byte offset (descending)                       │
│    Apply each edit to preserve byte positions                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Instrumented Source Code
```

## Data Structures

### InstrumentationPoint

Represents a precise location for checkpoint injection:

```python
@dataclass
class InstrumentationPoint:
    id: str                    # Unique identifier (e.g., "function_enter_fibonacci_10")
    type: str                  # "function_enter", "function_exit", "loop_start", etc.
    subtype: str               # "method", "function", "constructor", "for", "while"
    name: str                  # Function/class/variable name
    line: int                  # Line number (1-indexed)
    column: int                # Column number
    context: str               # Human-readable description
    metadata: Dict[str, Any]   # Additional info (energy_intensive, etc.)
    byte_offset: Optional[int] # Byte position in source
    node_start_byte: Optional[int]
    node_end_byte: Optional[int]
    insertion_mode: str        # 'before', 'after', 'inside_start', 'inside_end'
    node: Optional[Node]       # Tree-sitter node reference
    priority: int              # For deduplication (lower = higher priority)
```

### AnalysisResult

Complete analysis output:

```python
@dataclass
class AnalysisResult:
    language: str                              # Detected language
    success: bool                              # Analysis succeeded
    instrumentation_points: List[InstrumentationPoint]
    optimization_suggestions: List[str]        # Performance hints
    metadata: Dict[str, Any]                   # Timing, method used, etc.
    error: Optional[str]                       # Error message if failed
```

### LanguageConfig

Per-language configuration:

```python
@dataclass
class LanguageConfig:
    name: str                          # "python", "cpp", etc.
    extensions: List[str]              # [".py", ".pyw"]
    tree_sitter_name: str              # tree-sitter language name
    ast_config: Dict[str, Any]         # AST navigation rules
    query_config: Dict[str, Any]       # Capture mappings
    instrumentation_config: Dict       # Templates and settings
    formatting_config: Dict            # Indentation rules
    rules: Dict[str, Any]              # Language-specific rules
    analysis_patterns: Dict            # Regex fallback patterns
    node_types: Dict[str, Any]         # AST node type mappings
```

## Language Configuration

Each language has a JSON configuration file in `src/instrumentation/configs/`.

### Configuration Structure

```json
{
  "name": "python",
  "extensions": [".py", ".pyw"],
  "tree_sitter_name": "python",

  "ast_config": {
    "body_field": "body",
    "block_type": "block",
    "function_types": ["function_definition"],
    "class_types": ["class_definition"],
    "insertion_rules": {
      "function_enter": {
        "mode": "inside_start",
        "skip_docstrings": true
      }
    },
    "insertion_queries": {
      "function_body_start": "(function_definition body: (block (_) @target))"
    }
  },

  "query_config": {
    "capture_mapping": {
      "local.definition.function": "function_enter",
      "function": "function_enter",
      "keyword.return": "function_exit"
    },
    "deduplication_rules": {
      "function_enter": {
        "scope": "function",
        "max_per_function": 1
      }
    }
  },

  "instrumentation_config": {
    "import_statement": "from codegreen_core.energy_meter import EnergyMeter as _cg_meter",
    "templates": {
      "function_enter": "_cg_meter.mark_checkpoint(\"{checkpoint_id}\")",
      "function_exit": "_cg_meter.mark_checkpoint(\"{checkpoint_id}_exit\")"
    },
    "statement_terminator": "",
    "comment_prefix": "#"
  },

  "formatting_config": {
    "indent_char": " ",
    "indent_size": 4,
    "uses_braces": false
  },

  "node_types": {
    "body_types": ["block"],
    "function_types": ["function_definition"],
    "class_types": ["class_definition"]
  }
}
```

### Key Configuration Sections

**ast_config:** Controls AST navigation
- `insertion_rules`: How to find insertion points for each checkpoint type
- `insertion_queries`: Tree-sitter queries for precise targeting

**query_config:** Maps tree-sitter captures to checkpoint types
- `capture_mapping`: Maps nvim-treesitter capture names to point types
- `deduplication_rules`: Prevents multiple checkpoints at same location

**instrumentation_config:** Code generation templates
- `import_statement`: Import to add at file top
- `templates`: Code templates with `{checkpoint_id}`, `{name}` placeholders

## Tree-sitter Integration

### Query Sources

CodeGreen uses tree-sitter queries from two sources:

1. **nvim-treesitter (preferred):** Community-maintained, comprehensive queries
   - Location: `third_party/nvim-treesitter/queries/<language>/*.scm`
   - Loaded automatically when available
   - Contains captures like `@function`, `@local.definition.function`, `@keyword.return`

2. **Built-in fallback:** Minimal queries for basic functionality
   ```python
   'functions': '''
       (function_definition
         name: (identifier) @function_name
         body: (block) @function_body) @function_def
   '''
   ```

### Query Execution

```python
# Load and compile query
query = Query(language, query_text)

# Execute on AST
cursor = QueryCursor(query)
captures = cursor.captures(tree.root_node)

# captures = {'function': [node1, node2], 'return': [node3, node4]}
```

### Capture Mapping

Captures are mapped to instrumentation point types:

| Capture Name | Point Type | Insertion Mode |
|--------------|------------|----------------|
| `local.definition.function` | function_enter | inside_start |
| `function` | function_enter | inside_start |
| `function.method` | function_enter | inside_start |
| `keyword.return` | function_exit | before |
| `return` | function_exit | before |
| `local.definition.type` | class_enter | inside_start |

## Checkpoint Injection

### Insertion Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `inside_start` | After opening brace/colon, before first statement | Function entry |
| `inside_end` | Before closing brace, after last statement | Function exit |
| `before` | Immediately before the node | Return statements |
| `after` | Immediately after the node | Rare cases |

### Example: Python Function

**Original:**
```python
def fibonacci(n):
    """Calculate fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

**Instrumented:**
```python
from codegreen_core.energy_meter import EnergyMeter as _cg_meter

def fibonacci(n):
    """Calculate fibonacci number."""
    _cg_meter.mark_checkpoint("function_enter_fibonacci_3")
    if n <= 1:
        _cg_meter.mark_checkpoint("function_exit_fibonacci_5")
        return n
    _cg_meter.mark_checkpoint("function_exit_fibonacci_7")
    return fibonacci(n-1) + fibonacci(n-2)
```

### Indentation Handling

The system preserves proper indentation by:

1. Detecting the indentation of surrounding code
2. Using language-specific indent settings from config
3. Applying consistent indentation to inserted code

```python
def get_indentation(self, node: Node) -> IndentationInfo:
    # Find the line's existing indentation
    line_start = source_code.rfind('\n', 0, node.start_byte) + 1
    line_content = source_code[line_start:node.start_byte]

    # Count leading whitespace
    indent_level = len(line_content) - len(line_content.lstrip())
    return IndentationInfo(indent_level, ' ', 4, ' ' * indent_level)
```

## Adding New Languages

### Step 1: Create Configuration File

Create `src/instrumentation/configs/<language>.json`:

```json
{
  "name": "rust",
  "extensions": [".rs"],
  "tree_sitter_name": "rust",
  "ast_config": {
    "body_field": "body",
    "function_types": ["function_item"],
    "insertion_rules": {
      "function_enter": {
        "mode": "inside_start"
      }
    }
  },
  "query_config": {
    "capture_mapping": {
      "function": "function_enter"
    }
  },
  "instrumentation_config": {
    "import_statement": "use codegreen::energy_meter;",
    "templates": {
      "function_enter": "energy_meter::mark_checkpoint(\"{checkpoint_id}\");"
    },
    "statement_terminator": ";"
  },
  "formatting_config": {
    "indent_char": " ",
    "indent_size": 4,
    "uses_braces": true
  },
  "node_types": {
    "body_types": ["block"],
    "function_types": ["function_item"]
  }
}
```

### Step 2: Add nvim-treesitter Queries (Optional)

If nvim-treesitter has queries for the language, they'll be loaded automatically. Otherwise, add built-in queries:

```python
# In language_engine.py _get_builtin_queries()
elif language == 'rust':
    return {
        'functions': '''
            (function_item
              name: (identifier) @function_name
              body: (block) @function_body) @function_def
        '''
    }
```

### Step 3: Install tree-sitter Grammar

Ensure `tree-sitter-language-pack` includes the language, or install separately:

```bash
pip install tree-sitter-rust
```

### Step 4: Test

```bash
codegreen analyze test.rs
codegreen measure python run_test.py  # If instrumenting Rust called from Python
```

## Debugging

### Enable Verbose Logging

```python
import logging
logging.getLogger('src.instrumentation.language_engine').setLevel(logging.DEBUG)
```

### Common Issues

**No instrumentation points found:**
- Check if tree-sitter grammar is installed
- Verify capture_mapping matches query capture names
- Enable debug logging to see query execution

**Wrong insertion position:**
- Check insertion_rules in language config
- Verify body_types includes correct AST node types
- Debug with `ast_processor.find_insertion_point()`

**Missing imports:**
- Verify import_statement in instrumentation_config
- Check `_find_import_insertion_point()` logic for edge cases

## References

- Implementation: `src/instrumentation/`
- Configs: `src/instrumentation/configs/*.json`
- nvim-treesitter: `third_party/nvim-treesitter/`
- tree-sitter docs: https://tree-sitter.github.io/
- Checkpointing: [checkpointing-architecture.md](checkpointing-architecture.md)
- NEMB Design: [nemb-design.md](nemb-design.md)
