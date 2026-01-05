#!/usr/bin/env python3
from tree_sitter_language_pack import get_parser

test_code = """
class DataProcessor {
    std::vector<double> process_data() {
        return results;
    }
};
"""

parser = get_parser("cpp")
tree = parser.parse(test_code.encode('utf-8'))
root = tree.root_node

def print_tree(node, indent=0):
    prefix = "  " * indent
    text = test_code[node.start_byte:node.end_byte].replace('\n', '\\n')[:50]
    print(f"{prefix}{node.type} [{node.start_point}-{node.end_point}] = {repr(text)}")
    for child in node.children:
        print_tree(child, indent + 1)

print_tree(root)