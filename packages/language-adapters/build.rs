fn main() {
    cc::Build::new()
        .include("src")
        .file("src/tree-sitter-python/src/parser.c")
        .file("src/tree-sitter-python/src/scanner.c")
        .compile("tree-sitter-python");
} 