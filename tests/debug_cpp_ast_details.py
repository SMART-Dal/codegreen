#!/usr/bin/env python3
from tree_sitter_language_pack import get_parser
import sys

# Read the actual sample file
with open('tests/cpp_sample.cpp', 'r') as f:
    source_code = f.read()

parser = get_parser("cpp")
tree = parser.parse(source_code.encode('utf-8'))
root = tree.root_node

def print_tree(node, indent=0):
    # Print only interesting nodes to avoid huge output, or limited depth
    # We are interested in DataProcessor constructor and the strange "ond <<"
    
    # Simple recursive print
    prefix = "  " * indent
    
    # Get text
    text = source_code[node.start_byte:node.end_byte]
    # Truncate text for display
    display_text = text.replace('\n', '\\n')
    if len(display_text) > 40:
        display_text = display_text[:37] + "..."
        
    print(f"{prefix}{node.type} [{node.start_point.row+1}:{node.start_point.column}] - {display_text}")
    
    for child in node.children:
        print_tree(child, indent + 1)

print_tree(root)
