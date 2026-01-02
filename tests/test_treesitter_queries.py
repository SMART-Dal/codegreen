#!/usr/bin/env python3
"""Test tree-sitter queries for Python to validate query syntax and API usage."""

from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

# Test code with various Python constructs
test_code = """
def simple_function():
    \"\"\"A simple docstring.\"\"\"
    print("Simple function body")

async def async_worker():
    \"\"\"Async function docstring.\"\"\"
    await asyncio.sleep(0.1)
    return "done"

class MyClass:
    def __init__(self):
        self.value = 0
"""

def test_query_api():
    """Test the correct tree-sitter-language-pack API for queries."""
    print("=" * 60)
    print("Testing tree-sitter-language-pack API")
    print("=" * 60)

    # Get language and parser
    lang = get_language("python")
    parser = get_parser("python")

    # Parse the test code
    tree = parser.parse(test_code.encode('utf-8'))
    root = tree.root_node

    print(f"\nRoot node: {root.type}")
    print(f"Root children: {len(root.children)}")

    # Test 1: Simple query to find all function definitions
    print("\n" + "-" * 60)
    print("Test 1: Find all function definitions")
    print("-" * 60)

    query1 = Query(lang, "(function_definition) @func")
    cursor1 = QueryCursor(query1)
    captures_dict = cursor1.captures(root)

    for name, nodes in captures_dict.items():
        for node in nodes:
            print(f"  {name}: {node.type} at {node.start_point}")
            if node.child_by_field_name('name'):
                func_name = test_code[node.child_by_field_name('name').start_byte:node.child_by_field_name('name').end_byte]
                print(f"    Name: {func_name}")

    # Test 2: Skip - async is not a named node type in Python grammar

    # Test 3: Find function body with docstring handling (MAIN TEST)
    print("\n" + "-" * 60)
    print("Test 3: Function body start query (sync and async)")
    print("-" * 60)

    # This is the actual query from language_configs.py
    function_body_query = """
        (function_definition
          body: (block
            (expression_statement (string))?
            .
            (_) @target
          )
        )
    """

    query3 = Query(lang, function_body_query)
    cursor3 = QueryCursor(query3)
    captures_dict = cursor3.captures(root)

    print(f"  Found {sum(len(nodes) for nodes in captures_dict.values())} captures")
    for name, nodes in captures_dict.items():
        for node in nodes:
            # Find parent function to identify which function this belongs to
            parent = node.parent
            while parent and parent.type != 'function_definition':
                parent = parent.parent

            if parent:
                func_name_node = parent.child_by_field_name('name')
                func_name = test_code[func_name_node.start_byte:func_name_node.end_byte] if func_name_node else "unknown"
                # Check if async
                is_async = any(child.type == 'async' for child in parent.children)
                async_label = " (async)" if is_async else ""

                text = test_code[node.start_byte:node.end_byte]
                print(f"  {name} in {func_name}{async_label}:")
                print(f"    Node type: {node.type}")
                print(f"    Position: byte {node.start_byte}, point {node.start_point}")
                print(f"    Text: {repr(text[:60])}")

                # Show the line content at this position
                line_start = test_code.rfind('\n', 0, node.start_byte) + 1
                line_end = test_code.find('\n', node.start_byte)
                if line_end == -1:
                    line_end = len(test_code)
                line_content = test_code[line_start:line_end]
                indent = len(line_content) - len(line_content.lstrip())
                print(f"    Line indent: {indent} spaces")
                print(f"    Line: {repr(line_content)}")
                print()

    # Test 4: Find class body first statement
    print("\n" + "-" * 60)
    print("Test 4: Find class body first statement")
    print("-" * 60)

    query4 = Query(lang, """
        (class_definition
          body: (block
            .
            (_) @target
          )
        )
    """)
    cursor4 = QueryCursor(query4)
    captures_dict = cursor4.captures(root)

    for name, nodes in captures_dict.items():
        for node in nodes:
            text = test_code[node.start_byte:node.end_byte]
            print(f"  {name}: {node.type} = {repr(text[:50])}")

    print("\n" + "=" * 60)
    print("API Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_query_api()
