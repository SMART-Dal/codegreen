#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'bin/src/instrumentation'))

from instrumentation.ast_processor import ASTProcessor
from instrumentation.language_configs import get_language_config_manager
from tree_sitter_language_pack import get_parser

code = """
class DataProcessor {
    std::vector<double> data;
    int processed_count;
    
public:
    DataProcessor(const std::vector<double>& input_data) 
        : data(input_data), processed_count(0) {}
};
"""

parser = get_parser("cpp")
tree = parser.parse(code.encode('utf-8'))
root = tree.root_node

# Find the function definition node
def find_constructor(node):
    if node.type == 'function_definition':
        return node
    for child in node.children:
        res = find_constructor(child)
        if res: return res
    return None

func_node = find_constructor(root)
print(f"Found function node: {func_node.type} at {func_node.start_point}")

processor = ASTProcessor("cpp", code, tree)
body_node = processor.find_body_node(func_node)

if body_node:
    print(f"Found body node: {body_node.type} at {body_node.start_point}-{body_node.end_point}")
    
    # Check insertion point
    rule = {
        "mode": "inside_start",
        "find_first_statement": False,
        "skip_docstrings": False,
        "skip_comments": True
    }
    
    # We need to access private method to test manual logic exactly as used
    point = processor._find_insertion_point_manual(func_node, "inside_start", rule)
    print(f"Calculated insertion point: {point}")
    print(f"Code at insertion point: {repr(code[point:point+10])}")
    
    # Check if point is inside braces
    brace_pos = code.find('{', body_node.start_byte)
    print(f"Body start: {body_node.start_byte}, Brace pos in code: {brace_pos}")
    
else:
    print("Body node NOT found")
