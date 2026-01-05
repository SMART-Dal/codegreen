#!/usr/bin/env python3
import sys
from pathlib import Path
from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

test_code = """
#include <iostream>

int add(int a, int b) {
    return a + b;
}

int main() {
    int x = add(1, 2);
    std::cout << "Result: " << x << std::endl;
    return 0;
}
"""

lang = get_language("cpp")
parser = get_parser("cpp")
tree = parser.parse(test_code.encode('utf-8'))

# Load all queries like LanguageEngine does
query_dir = Path("third_party/nvim-treesitter/queries/cpp")
scm_files = list(query_dir.glob('*.scm'))
combined = ""
for f in scm_files:
    combined += f.read_text() + "\n"

query = Query(lang, combined)
cursor = QueryCursor(query)
captures = cursor.captures(tree.root_node)

print(f"Found {len(captures)} capture types")
for name, nodes in captures.items():
    print(f"Capture '{name}': {len(nodes)} nodes")
    for node in nodes[:3]:
        text = test_code[node.start_byte:node.end_byte]
        print(f"  - {node.type}: {repr(text)}")
