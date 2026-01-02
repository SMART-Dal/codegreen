#!/usr/bin/env python3
"""Examine the AST structure of async functions in Python."""

from tree_sitter_language_pack import get_parser

test_code = """
def normal_function():
    pass

async def async_function():
    pass
"""

parser = get_parser("python")
tree = parser.parse(test_code.encode('utf-8'))
root = tree.root_node

def print_tree(node, indent=0):
    """Recursively print the tree structure."""
    prefix = "  " * indent
    text = test_code[node.start_byte:node.end_byte].replace('\n', '\\n')[:50]
    print(f"{prefix}{node.type} [{node.start_point}-{node.end_point}] = {repr(text)}")
    for child in node.children:
        print_tree(child, indent + 1)

print("=" * 70)
print("Python AST Structure - Async vs Normal Functions")
print("=" * 70)
print_tree(root)
