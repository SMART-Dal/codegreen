#include "c.hpp"
#include <sstream>
#include <regex>
#include <algorithm>

namespace codegreen {

CAdapter::CAdapter() : TreeSitterAdapter(tree_sitter_c()) {
}

std::string CAdapter::get_language_id() const {
    return "c";
}

std::vector<std::string> CAdapter::get_file_extensions() const {
    return {".c", ".h"};
}

bool CAdapter::should_generate_checkpoint(const std::string& node_type) const {
    return node_type == "function_definition" ||
           node_type == "function_declarator" ||
           node_type == "for_statement" ||
           node_type == "while_statement" ||
           node_type == "do_statement" ||
           node_type == "switch_statement" ||
           node_type == "if_statement";
}

std::string CAdapter::extract_function_name(TSNode node, const std::string& source_code) const {
    std::string node_type = get_node_type(node);
    
    if (node_type == "function_definition") {
        // Look for function_declarator child
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "function_declarator") {
                // Look for identifier in function_declarator
                uint32_t decl_child_count = ts_node_child_count(child);
                for (uint32_t j = 0; j < decl_child_count; ++j) {
                    TSNode decl_child = ts_node_child(child, j);
                    std::string decl_child_type = get_node_type(decl_child);
                    
                    if (decl_child_type == "identifier") {
                        return get_node_text(decl_child, source_code);
                    }
                }
            }
        }
    }
    
    return "";
}

std::vector<CodeCheckpoint> CAdapter::generate_node_checkpoints(
    TSNode node, 
    const std::string& source_code,
    const std::string& node_type) {
    
    std::vector<CodeCheckpoint> checkpoints;
    
    TSPoint start_point = ts_node_start_point(node);
    TSPoint end_point = ts_node_end_point(node);
    
    std::string name = extract_function_name(node, source_code);
    if (name.empty()) {
        name = "anonymous_" + node_type;
    }
    
    // Function checkpoints
    if (node_type == "function_definition") {
        CodeCheckpoint entry;
        entry.id = generate_checkpoint_id("function_enter", name, start_point.row + 1);
        entry.type = "function_enter";
        entry.name = name;
        entry.line_number = start_point.row + 1;
        entry.column_number = start_point.column + 1;
        entry.context = "Function entry: " + name;
        checkpoints.push_back(entry);
        
        CodeCheckpoint exit;
        exit.id = generate_checkpoint_id("function_exit", name, end_point.row + 1);
        exit.type = "function_exit";
        exit.name = name;
        exit.line_number = end_point.row + 1;
        exit.column_number = end_point.column + 1;
        exit.context = "Function exit: " + name;
        checkpoints.push_back(exit);
    }
    
    // Loop checkpoints
    else if (node_type == "for_statement" || node_type == "while_statement" || 
             node_type == "do_statement") {
        CodeCheckpoint loop;
        loop.id = generate_checkpoint_id("loop_start", node_type, start_point.row + 1);
        loop.type = "loop_start";
        loop.name = node_type;
        loop.line_number = start_point.row + 1;
        loop.column_number = start_point.column + 1;
        loop.context = "Loop start: " + node_type;
        checkpoints.push_back(loop);
    }
    
    // Control flow checkpoints
    else if (node_type == "switch_statement" || node_type == "if_statement") {
        CodeCheckpoint control;
        control.id = generate_checkpoint_id("control_flow", node_type, start_point.row + 1);
        control.type = "control_flow";
        control.name = node_type;
        control.line_number = start_point.row + 1;
        control.column_number = start_point.column + 1;
        control.context = "Control flow: " + node_type;
        checkpoints.push_back(control);
    }
    
    return checkpoints;
}

std::string CAdapter::instrument_code(const std::string& source_code, 
                                     const std::vector<CodeCheckpoint>& checkpoints) {
    if (checkpoints.empty()) {
        return source_code;
    }
    
    auto lines = split_lines(source_code);
    std::string instrumented_includes = generate_measurement_includes();
    
    // Add includes at the beginning, after existing includes
    size_t insert_pos = 0;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (lines[i].find("#include") != std::string::npos) {
            insert_pos = i + 1;
        } else if (lines[i].find("#") == 0) {
            // Other preprocessor directives
            insert_pos = i + 1;
        } else if (!lines[i].empty() && lines[i].find_first_not_of(" \t") != std::string::npos) {
            // First non-preprocessor, non-empty line
            break;
        }
    }
    
    lines.insert(lines.begin() + insert_pos, instrumented_includes);
    
    // Sort checkpoints by line number (descending) to avoid line number shifts
    auto sorted_checkpoints = checkpoints;
    std::sort(sorted_checkpoints.begin(), sorted_checkpoints.end(), 
              [](const CodeCheckpoint& a, const CodeCheckpoint& b) {
                  return a.line_number > b.line_number;
              });
    
    // Insert checkpoint calls
    for (const auto& checkpoint : sorted_checkpoints) {
        if (checkpoint.line_number <= lines.size()) {
            size_t insert_line = checkpoint.line_number + 1; // Adjusted for includes
            
            std::string checkpoint_call = "    " + generate_checkpoint_call(checkpoint);
            
            if (checkpoint.type == "function_enter") {
                // Insert after opening brace of function
                for (size_t i = insert_line; i < lines.size(); ++i) {
                    if (lines[i].find("{") != std::string::npos) {
                        lines.insert(lines.begin() + i + 1, checkpoint_call);
                        break;
                    }
                }
            } else if (checkpoint.type == "function_exit") {
                // Insert before closing brace or return statements
                for (size_t i = insert_line; i > 0; --i) {
                    if (lines[i-1].find("return") != std::string::npos || 
                        lines[i-1].find("}") != std::string::npos) {
                        lines.insert(lines.begin() + i - 1, checkpoint_call);
                        break;
                    }
                }
            } else {
                // Insert at the appropriate location for loops and control flow
                lines.insert(lines.begin() + insert_line, checkpoint_call);
            }
        }
    }
    
    return join_lines(lines);
}

bool CAdapter::analyze(const std::string& source_code) {
    optimization_suggestions_.clear();
    
    analyze_loops(source_code);
    analyze_memory_allocation(source_code);
    analyze_io_operations(source_code);
    analyze_recursion(source_code);
    
    return !optimization_suggestions_.empty();
}

std::vector<std::string> CAdapter::get_suggestions() const {
    return optimization_suggestions_;
}

// Private helper methods

std::string CAdapter::generate_measurement_includes() const {
    return "#include <stdio.h>\n"
           "#include <sys/time.h>\n"
           "void codegreen_measure_checkpoint(const char* id, const char* type, const char* name, int line, const char* context) {\n"
           "    struct timeval tv; gettimeofday(&tv, NULL);\n"
           "    printf(\"CODEGREEN_CHECKPOINT: %s|%s|%s|%d|%s|%ld.%06ld\\n\", id, type, name, line, context, tv.tv_sec, tv.tv_usec);\n"
           "}";
}

std::string CAdapter::generate_checkpoint_call(const CodeCheckpoint& checkpoint) const {
    std::ostringstream oss;
    oss << "codegreen_measure_checkpoint(\""
        << checkpoint.id << "\", \""
        << checkpoint.type << "\", \""
        << checkpoint.name << "\", "
        << checkpoint.line_number << ", \""
        << checkpoint.context << "\");";
    return oss.str();
}

std::vector<std::string> CAdapter::split_lines(const std::string& source_code) const {
    std::vector<std::string> lines;
    std::istringstream stream(source_code);
    std::string line;
    
    while (std::getline(stream, line)) {
        lines.push_back(line);
    }
    
    return lines;
}

std::string CAdapter::join_lines(const std::vector<std::string>& lines) const {
    std::ostringstream oss;
    for (size_t i = 0; i < lines.size(); ++i) {
        oss << lines[i];
        if (i < lines.size() - 1) {
            oss << "\n";
        }
    }
    return oss.str();
}

std::string CAdapter::get_indentation(const std::string& line) const {
    size_t indent_end = 0;
    for (char c : line) {
        if (c == ' ' || c == '\t') {
            indent_end++;
        } else {
            break;
        }
    }
    return line.substr(0, indent_end);
}

void CAdapter::analyze_loops(const std::string& source_code) {
    // Look for inefficient loop patterns
    if (source_code.find("strlen") != std::string::npos && 
        source_code.find("for") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Avoid calling strlen() in loop conditions; cache the length in a variable");
    }
}

void CAdapter::analyze_memory_allocation(const std::string& source_code) {
    // Check for memory allocation patterns
    if (source_code.find("malloc") != std::string::npos && 
        source_code.find("for") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider pre-allocating memory outside loops to reduce allocation overhead");
    }
    
    if (source_code.find("malloc") != std::string::npos && 
        source_code.find("free") == std::string::npos) {
        optimization_suggestions_.push_back(
            "Ensure all malloc() calls have corresponding free() calls to prevent memory leaks");
    }
}

void CAdapter::analyze_io_operations(const std::string& source_code) {
    // Look for I/O operations in loops
    if ((source_code.find("printf") != std::string::npos || 
         source_code.find("fprintf") != std::string::npos) && 
        (source_code.find("for") != std::string::npos || 
         source_code.find("while") != std::string::npos)) {
        optimization_suggestions_.push_back(
            "Consider buffering output or reducing I/O operations inside loops");
    }
}

void CAdapter::analyze_recursion(const std::string& source_code) {
    // Basic recursion detection (function calling itself)
    std::regex func_def_pattern(R"(\w+\s*\([^)]*\)\s*\{)");
    std::smatch match;
    
    if (std::regex_search(source_code, match, func_def_pattern)) {
        std::string func_name = match.str();
        if (source_code.find(func_name) != source_code.rfind(func_name)) {
            optimization_suggestions_.push_back(
                "Consider iterative alternatives to recursion for better energy efficiency");
        }
    }
}

} // namespace codegreen