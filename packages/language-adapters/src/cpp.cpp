#include "cpp.hpp"
#include <sstream>
#include <iostream>

namespace codegreen {

CppAdapter::CppAdapter() : TreeSitterAdapter(tree_sitter_cpp()) {
}

std::string CppAdapter::get_language_id() const {
    return "cpp";
}

std::vector<std::string> CppAdapter::get_file_extensions() const {
    return {".cpp", ".cxx", ".cc", ".hpp", ".h", ".hxx", ".h++"};
}

bool CppAdapter::should_generate_checkpoint(const std::string& node_type) const {
    return node_type == "function_definition" ||
           node_type == "method_definition" ||
           node_type == "constructor_definition" ||
           node_type == "destructor_definition" ||
           node_type == "class_specifier" ||
           node_type == "struct_specifier" ||
           node_type == "for_statement" ||
           node_type == "while_statement" ||
           node_type == "do_statement" ||
           node_type == "range_for_statement" ||
           node_type == "if_statement" ||
           node_type == "switch_statement" ||
           node_type == "try_statement" ||
           node_type == "call_expression" ||
           node_type == "template_declaration" ||
           node_type == "namespace_definition";
}

std::string CppAdapter::extract_function_name(TSNode node, const std::string& source_code) const {
    std::string node_type = get_node_type(node);
    
    if (node_type == "function_definition" || node_type == "method_definition" ||
        node_type == "constructor_definition" || node_type == "destructor_definition") {
        
        // Look for function declarator
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "function_declarator") {
                // Look for identifier in function declarator
                uint32_t grandchild_count = ts_node_child_count(child);
                for (uint32_t j = 0; j < grandchild_count; ++j) {
                    TSNode grandchild = ts_node_child(child, j);
                    std::string grandchild_type = get_node_type(grandchild);
                    
                    if (grandchild_type == "identifier") {
                        return get_node_text(grandchild, source_code);
                    }
                }
            }
        }
    }
    else if (node_type == "class_specifier" || node_type == "struct_specifier") {
        // Look for class/struct name
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "type_identifier") {
                return get_node_text(child, source_code);
            }
        }
    }
    
    return "";
}

std::vector<CodeCheckpoint> CppAdapter::generate_node_checkpoints(
    TSNode node, 
    const std::string& source_code,
    const std::string& node_type) {
    
    std::vector<CodeCheckpoint> checkpoints;
    
    TSPoint start_point = ts_node_start_point(node);
    TSPoint end_point = ts_node_end_point(node);
    
    std::string function_name = extract_function_name(node, source_code);
    if (function_name.empty()) {
        function_name = "anonymous";
    }
    
    // Generate function entry checkpoint
    if (node_type == "function_definition" || node_type == "method_definition" ||
        node_type == "constructor_definition" || node_type == "destructor_definition") {
        
        CodeCheckpoint entry_checkpoint;
        entry_checkpoint.id = generate_checkpoint_id("function_enter", function_name, start_point.row + 1);
        entry_checkpoint.type = "function_enter";
        entry_checkpoint.name = function_name;
        entry_checkpoint.line_number = start_point.row + 1;
        entry_checkpoint.column_number = start_point.column + 1;
        entry_checkpoint.context = "Function entry: " + function_name;
        
        checkpoints.push_back(entry_checkpoint);
        
        // Generate function exit checkpoint
        CodeCheckpoint exit_checkpoint;
        exit_checkpoint.id = generate_checkpoint_id("function_exit", function_name, end_point.row + 1);
        exit_checkpoint.type = "function_exit";
        exit_checkpoint.name = function_name;
        exit_checkpoint.line_number = end_point.row + 1;
        exit_checkpoint.column_number = end_point.column + 1;
        exit_checkpoint.context = "Function exit: " + function_name;
        
        checkpoints.push_back(exit_checkpoint);
    }
    
    // Generate class/struct checkpoints
    else if (node_type == "class_specifier" || node_type == "struct_specifier") {
        CodeCheckpoint class_checkpoint;
        class_checkpoint.id = generate_checkpoint_id("class_enter", function_name, start_point.row + 1);
        class_checkpoint.type = "class_enter";
        class_checkpoint.name = function_name;
        class_checkpoint.line_number = start_point.row + 1;
        class_checkpoint.column_number = start_point.column + 1;
        class_checkpoint.context = "Class definition: " + function_name;
        
        checkpoints.push_back(class_checkpoint);
    }
    
    // Generate loop checkpoints
    else if (node_type == "for_statement" || node_type == "while_statement" || 
             node_type == "do_statement" || node_type == "range_for_statement") {
        
        CodeCheckpoint loop_checkpoint;
        loop_checkpoint.id = generate_checkpoint_id("loop_start", node_type, start_point.row + 1);
        loop_checkpoint.type = "loop_start";
        loop_checkpoint.name = node_type;
        loop_checkpoint.line_number = start_point.row + 1;
        loop_checkpoint.column_number = start_point.column + 1;
        loop_checkpoint.context = "Loop start: " + node_type;
        
        checkpoints.push_back(loop_checkpoint);
    }
    
    return checkpoints;
}

std::string CppAdapter::instrument_code(const std::string& source_code, 
                                       const std::vector<CodeCheckpoint>& checkpoints) {
    if (checkpoints.empty()) {
        return source_code;
    }
    
    auto lines = split_lines(source_code);
    std::string instrumented_include = generate_measurement_include();
    
    // Add include at the beginning
    lines.insert(lines.begin(), instrumented_include);
    
    // Sort checkpoints by line number (descending) to avoid line number shifts
    auto sorted_checkpoints = checkpoints;
    std::sort(sorted_checkpoints.begin(), sorted_checkpoints.end(), 
              [](const CodeCheckpoint& a, const CodeCheckpoint& b) {
                  return a.line_number > b.line_number;
              });
    
    // Insert checkpoint calls
    for (const auto& checkpoint : sorted_checkpoints) {
        // Account for the include statement that was added at the beginning
        size_t adjusted_line = checkpoint.line_number + 1; // +1 for the include line
        if (adjusted_line <= lines.size()) {
            size_t insert_line = adjusted_line;
            
            std::string checkpoint_call = generate_checkpoint_call(checkpoint);
            
            if (checkpoint.type == "function_enter") {
                // Function entry: insert at beginning of function body
                std::string original_line = lines[insert_line - 1];
                std::string def_indentation = get_indentation(original_line);
                std::string body_indentation = def_indentation + "    "; // Always add 4 spaces
                
                checkpoint_call = body_indentation + checkpoint_call;
                
                // Find where to insert the checkpoint call (after the function signature)
                size_t insert_pos = insert_line;
                
                // Skip empty lines immediately after function definition
                while (insert_pos < lines.size() && lines[insert_pos].empty()) {
                    insert_pos++;
                }
                
                lines.insert(lines.begin() + insert_pos, checkpoint_call);
            }
            else {
                // Other types: insert before the line with same indentation
                std::string original_line = lines[insert_line - 1];
                std::string indentation = get_indentation(original_line);
                
                checkpoint_call = indentation + checkpoint_call;
                lines.insert(lines.begin() + insert_line - 1, checkpoint_call);
            }
        }
    }
    
    return join_lines(lines);
}

bool CppAdapter::analyze(const std::string& source_code) {
    optimization_suggestions_.clear();
    
    analyze_loops(source_code);
    analyze_memory_usage(source_code);
    analyze_templates(source_code);
    analyze_containers(source_code);
    
    return !optimization_suggestions_.empty();
}

std::vector<std::string> CppAdapter::get_suggestions() const {
    return optimization_suggestions_;
}

// Private helper methods

std::string CppAdapter::generate_measurement_include() const {
    return "#include <codegreen_runtime.h>";
}

std::string CppAdapter::generate_checkpoint_call(const CodeCheckpoint& checkpoint) const {
    std::string result;
    result.reserve(100 + checkpoint.id.length() + checkpoint.type.length() + 
                   checkpoint.name.length() + checkpoint.context.length());
    
    result = "codegreen_measure_checkpoint(\"";
    result += checkpoint.id;
    result += "\", \"";
    result += checkpoint.type;
    result += "\", \"";
    result += checkpoint.name;
    result += "\", ";
    result += std::to_string(checkpoint.line_number);
    result += ", \"";
    result += checkpoint.context;
    result += "\");";
    
    return result;
}

std::vector<std::string> CppAdapter::split_lines(const std::string& source_code) const {
    std::vector<std::string> lines;
    std::istringstream stream(source_code);
    std::string line;
    
    while (std::getline(stream, line)) {
        lines.push_back(line);
    }
    
    return lines;
}

std::string CppAdapter::join_lines(const std::vector<std::string>& lines) const {
    std::ostringstream oss;
    for (size_t i = 0; i < lines.size(); ++i) {
        oss << lines[i];
        if (i < lines.size() - 1) {
            oss << "\n";
        }
    }
    return oss.str();
}

std::string CppAdapter::get_indentation(const std::string& line) const {
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

void CppAdapter::analyze_loops(const std::string& source_code) {
    // Look for inefficient loop patterns
    if (source_code.find("for (int i = 0; i < vec.size(); ++i)") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using range-based for loops or iterators instead of index-based loops for better performance");
    }
}

void CppAdapter::analyze_memory_usage(const std::string& source_code) {
    // Check for memory allocation patterns
    if (source_code.find("new ") != std::string::npos && 
        source_code.find("delete ") == std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using smart pointers (std::unique_ptr, std::shared_ptr) instead of raw pointers for automatic memory management");
    }
}

void CppAdapter::analyze_templates(const std::string& source_code) {
    // Check for template usage
    if (source_code.find("template") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using concepts (C++20) to constrain template parameters for better error messages and performance");
    }
}

void CppAdapter::analyze_containers(const std::string& source_code) {
    // Check for container usage patterns
    if (source_code.find("std::vector") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider reserving capacity for std::vector if you know the approximate size to avoid reallocations");
    }
}

} // namespace codegreen
