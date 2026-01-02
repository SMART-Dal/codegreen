# CodeGreen Language Configuration Schema

This document defines the structure of the language configuration JSON files used by CodeGreen. Adding support for a new language requires creating a `<language>.json` file in this directory.

## 🏗️ Top-Level Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Internal identifier for the language (e.g., "python"). |
| `extensions` | `array[string]` | List of file extensions associated with this language. |
| `tree_sitter_name` | `string` | The name of the Tree-sitter parser to load. |
| `ast_config` | `object` | Defines how to navigate the language's AST. |
| `query_config` | `object` | Maps Tree-sitter capture names to instrumentation actions. |
| `instrumentation_config` | `object` | Defines the actual code snippets to be injected. |
| `node_types` | `object` | Maps generic categories to language-specific AST node names. |

---

## 🌲 `ast_config` Details

This object tells the `ASTProcessor` how to find body blocks and insertion points.

*   **`body_field`**: The field name in Tree-sitter used for the body (e.g., "body" in Python, "declarator" in C).
*   **`block_type`**: The node type that represents a scope block (e.g., "block" or "compound_statement").
*   **`insertion_rules`**: A dictionary where keys are `function_enter`, `function_exit`, etc.
    *   **`mode`**: Strategy for insertion. Options: `"inside_start"`, `"inside_end"`, `"before"`, `"after"`.
    *   **`find_first_statement`**: (Boolean) If true, walks inside the block to find the first real code line.
    *   **`skip_docstrings`**: (Boolean) If true, skips nodes identified as documentation.

---

## 🔍 `query_config` Details

CodeGreen executes Tree-sitter queries found in `third_party/nvim-treesitter/queries/<language>/`.

*   **`capture_mapping`**: Maps the capture tag in the `.scm` file to an internal action.
    *   *Example:* `"function.definition": "function_enter"`
*   **`priority_order`**: An array defining which captures should "win" if they overlap.

---

## ⚡ `instrumentation_config` Details

*   **`import_statement`**: The line to add at the top of the file (e.g., `import codegreen`).
*   **`templates`**: A dictionary of code templates. Use `{checkpoint_id}` and `{name}` as placeholders.
    *   *Example:* `"_codegreen_rt.checkpoint('{checkpoint_id}', '{name}', 'enter')"`

---

## 🛠️ Step-by-Step: Adding a Language

1.  **Clone Template**: Copy `TEMPLATE.json` to `yourlang.json`.
2.  **Define Nodes**: Use `tree-sitter parse` on a sample file to find the node names for functions and blocks.
3.  **Set Strategy**: Decide if the language uses braces (like Java) or whitespace (like Python) and set `insertion_rules` accordingly.
4.  **Add Templates**: Copy the language's "print" or "log" syntax into the `templates` section.
5.  **Install**: Run `./install.sh` to sync the new config.
