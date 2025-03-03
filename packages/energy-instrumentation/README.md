# Energy Instrumentation

The **Energy Instrumentation** module leverages Tree-sitter for language-agnostic parsing and code instrumentation. It identifies method or function boundaries and injects measurement hooks to capture energy consumption at a fine granularity.

**Responsibilities:**
- Parse source code using Tree-sitter across multiple programming languages.
- Detect method/function definitions and boundaries.
- Insert instrumentation hooks to record energy consumption data.
- Provide a plugin system for language-specific parsing rules and instrumentation queries.

**Design Patterns:**
- **Plugin Architecture:** For extensibility across different languages.
- **Separation of Concerns:** Distinguishing parsing logic from instrumentation logic.

**Usage and Extension:**
- Add support for new languages by including Tree-sitter queries and instrumentation rules in the plugins folder.
- Customize instrumentation strategies for specialized scenarios without altering the core parsing logic.
