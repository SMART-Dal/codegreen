# Energy Language Adapters

The **Energy Language Adapters** module contains language-specific extensions for Code Green. It includes Tree-sitter query files and instrumentation rules tailored for different programming languages.

**Responsibilities:**
- Provide language-specific queries for detecting method/function definitions.
- Customize instrumentation rules for languages such as Java, Python, and C/C++.
- Act as an extension point to support additional languages in the future.

**Design Patterns:**
- **Plugin Architecture:** Allowing seamless addition of new language support.
- **Separation of Language-Specific Logic:** Ensuring core instrumentation remains language agnostic.

**Usage and Extension:**
- Add new language support by creating new directories with the necessary query files and rules.
- Maintain consistency with existing structures for ease of integration.
