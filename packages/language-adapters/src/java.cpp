#include "java.hpp"
#include <sstream>
#include <iostream>

namespace codegreen {

JavaAdapter::JavaAdapter() : TreeSitterAdapter(tree_sitter_java()) {
}

std::string JavaAdapter::get_language_id() const {
    return "java";
}

std::vector<std::string> JavaAdapter::get_file_extensions() const {
    return {".java"};
}

bool JavaAdapter::should_generate_checkpoint(const std::string& node_type) const {
    return node_type == "method_declaration" ||
           node_type == "constructor_declaration" ||
           node_type == "class_declaration" ||
           node_type == "interface_declaration" ||
           node_type == "for_statement" ||
           node_type == "while_statement" ||
           node_type == "do_statement" ||
           node_type == "enhanced_for_statement" ||
           node_type == "if_statement" ||
           node_type == "switch_statement" ||
           node_type == "try_statement" ||
           node_type == "method_invocation" ||
           node_type == "lambda_expression" ||
           node_type == "enum_declaration";
}

std::string JavaAdapter::extract_function_name(TSNode node, const std::string& source_code) const {
    std::string node_type = get_node_type(node);
    
    if (node_type == "method_declaration" || node_type == "constructor_declaration") {
        // Look for identifier in method/constructor declaration
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "identifier") {
                return get_node_text(child, source_code);
            }
        }
    }
    else if (node_type == "class_declaration" || node_type == "interface_declaration" || 
             node_type == "enum_declaration") {
        // Look for class/interface/enum name
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "identifier") {
                return get_node_text(child, source_code);
            }
        }
    }
    
    return "";
}

std::vector<CodeCheckpoint> JavaAdapter::generate_node_checkpoints(
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
    
    // Generate method/constructor entry checkpoint
    if (node_type == "method_declaration" || node_type == "constructor_declaration") {
        CodeCheckpoint entry_checkpoint;
        entry_checkpoint.id = generate_checkpoint_id("function_enter", function_name, start_point.row + 1);
        entry_checkpoint.type = "function_enter";
        entry_checkpoint.name = function_name;
        entry_checkpoint.line_number = start_point.row + 1;
        entry_checkpoint.column_number = start_point.column + 1;
        entry_checkpoint.context = "Method entry: " + function_name;
        
        checkpoints.push_back(entry_checkpoint);
        
        // Generate method/constructor exit checkpoint
        CodeCheckpoint exit_checkpoint;
        exit_checkpoint.id = generate_checkpoint_id("function_exit", function_name, end_point.row + 1);
        exit_checkpoint.type = "function_exit";
        exit_checkpoint.name = function_name;
        exit_checkpoint.line_number = end_point.row + 1;
        exit_checkpoint.column_number = end_point.column + 1;
        exit_checkpoint.context = "Method exit: " + function_name;
        
        checkpoints.push_back(exit_checkpoint);
    }
    
    // Generate class/interface checkpoints
    else if (node_type == "class_declaration" || node_type == "interface_declaration" || 
             node_type == "enum_declaration") {
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
             node_type == "do_statement" || node_type == "enhanced_for_statement") {
        
        CodeCheckpoint loop_checkpoint;
        loop_checkpoint.id = generate_checkpoint_id("loop_start", node_type, start_point.row + 1);
        loop_checkpoint.type = "loop_start";
        loop_checkpoint.name = node_type;
        loop_checkpoint.line_number = start_point.row + 1;
        loop_checkpoint.column_number = start_point.column + 1;
        loop_checkpoint.context = "Loop start: " + node_type;
        
        checkpoints.push_back(loop_checkpoint);
    }
    
    // Generate conditional checkpoints
    else if (node_type == "if_statement" || node_type == "switch_statement") {
        CodeCheckpoint cond_checkpoint;
        cond_checkpoint.id = generate_checkpoint_id("conditional", node_type, start_point.row + 1);
        cond_checkpoint.type = "conditional";
        cond_checkpoint.name = node_type;
        cond_checkpoint.line_number = start_point.row + 1;
        cond_checkpoint.column_number = start_point.column + 1;
        cond_checkpoint.context = "Conditional: " + node_type;
        
        checkpoints.push_back(cond_checkpoint);
    }
    
    // Generate method call checkpoints
    else if (node_type == "method_invocation") {
        CodeCheckpoint call_checkpoint;
        call_checkpoint.id = generate_checkpoint_id("function_call", "call", start_point.row + 1);
        call_checkpoint.type = "function_call";
        call_checkpoint.name = "call";
        call_checkpoint.line_number = start_point.row + 1;
        call_checkpoint.column_number = start_point.column + 1;
        call_checkpoint.context = "Method call at line " + std::to_string(start_point.row + 1);
        
        checkpoints.push_back(call_checkpoint);
    }
    
    return checkpoints;
}

std::string JavaAdapter::instrument_code(const std::string& source_code, 
                                        const std::vector<CodeCheckpoint>& checkpoints) {
    if (checkpoints.empty()) {
        return source_code;
    }
    
    auto lines = split_lines(source_code);
    std::string instrumented_import = generate_measurement_import();
    
    // Add import at the beginning, after package declaration
    size_t insert_pos = 0;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (lines[i].find("package ") != std::string::npos) {
            insert_pos = i + 1;
        } else if (lines[i].find("import ") != std::string::npos) {
            insert_pos = i + 1;
        } else if (!lines[i].empty() && lines[i].find_first_not_of(" \t") != std::string::npos) {
            // First non-package, non-import, non-empty line
            break;
        }
    }
    
    lines.insert(lines.begin() + insert_pos, instrumented_import);
    
    // Sort checkpoints by line number (descending) to avoid line number shifts
    auto sorted_checkpoints = checkpoints;
    std::sort(sorted_checkpoints.begin(), sorted_checkpoints.end(), 
              [](const CodeCheckpoint& a, const CodeCheckpoint& b) {
                  return a.line_number > b.line_number;
              });
    
    // Insert checkpoint calls
    for (const auto& checkpoint : sorted_checkpoints) {
        // Account for the import statement that was added at the beginning
        size_t adjusted_line = checkpoint.line_number + 1; // +1 for the import line
        if (adjusted_line <= lines.size()) {
            size_t insert_line = adjusted_line;
            
            std::string checkpoint_call = generate_checkpoint_call(checkpoint);
            
            if (checkpoint.type == "function_enter") {
                // Method entry: insert at beginning of method body
                std::string original_line = lines[insert_line - 1];
                std::string def_indentation = get_indentation(original_line);
                std::string body_indentation = def_indentation + "    "; // Always add 4 spaces
                
                checkpoint_call = body_indentation + checkpoint_call;
                
                // Find where to insert the checkpoint call (after the method signature)
                size_t insert_pos = insert_line;
                
                // Skip empty lines immediately after method definition
                while (insert_pos < lines.size() && lines[insert_pos].empty()) {
                    insert_pos++;
                }
                
                // If next line starts with a docstring, insert after it
                if (insert_pos < lines.size()) {
                    std::string line = lines[insert_pos];
                    if (line.find("/**") != std::string::npos || line.find("//") != std::string::npos) {
                        insert_pos++; // Skip the comment line
                    }
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

bool JavaAdapter::analyze(const std::string& source_code) {
    optimization_suggestions_.clear();
    
    analyze_collections(source_code);
    analyze_string_operations(source_code);
    analyze_loops(source_code);
    analyze_memory_usage(source_code);
    
    return !optimization_suggestions_.empty();
}

std::vector<std::string> JavaAdapter::get_suggestions() const {
    return optimization_suggestions_;
}

// Private helper methods

std::string JavaAdapter::generate_measurement_import() const {
    return "import java.util.concurrent.atomic.AtomicLong;\n"
           "import java.time.Instant;\n"
           "public class CodeGreenRuntime {\n"
           "    private static final AtomicLong sessionId = new AtomicLong(System.currentTimeMillis());\n"
           "    public static void measureCheckpoint(String id, String type, String name, int line, String context) {\n"
           "        long timestamp = Instant.now().toEpochMilli();\n"
           "        System.out.println(\"CODEGREEN_CHECKPOINT: \" + id + \"|\" + type + \"|\" + name + \"|\" + line + \"|\" + context + \"|\" + timestamp);\n"
           "    }\n"
           "}";
}

std::string JavaAdapter::generate_checkpoint_call(const CodeCheckpoint& checkpoint) const {
    std::string result;
    result.reserve(100 + checkpoint.id.length() + checkpoint.type.length() + 
                   checkpoint.name.length() + checkpoint.context.length());
    
    result = "CodeGreenRuntime.measureCheckpoint(\"";
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

std::vector<std::string> JavaAdapter::split_lines(const std::string& source_code) const {
    std::vector<std::string> lines;
    std::istringstream stream(source_code);
    std::string line;
    
    while (std::getline(stream, line)) {
        lines.push_back(line);
    }
    
    return lines;
}

std::string JavaAdapter::join_lines(const std::vector<std::string>& lines) const {
    std::ostringstream oss;
    for (size_t i = 0; i < lines.size(); ++i) {
        oss << lines[i];
        if (i < lines.size() - 1) {
            oss << "\n";
        }
    }
    return oss.str();
}

std::string JavaAdapter::get_indentation(const std::string& line) const {
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

void JavaAdapter::analyze_collections(const std::string& source_code) {
    // Look for inefficient collection usage
    if (source_code.find("ArrayList") != std::string::npos && 
        source_code.find("for") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using LinkedList for frequent insertions/deletions or pre-sizing ArrayList for known capacity");
    }
    
    if (source_code.find("HashMap") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider pre-sizing HashMap with expected capacity to avoid rehashing");
    }
}

void JavaAdapter::analyze_string_operations(const std::string& source_code) {
    // Look for string concatenation in loops
    if (source_code.find("+=") != std::string::npos && 
        (source_code.find("for") != std::string::npos || source_code.find("while") != std::string::npos)) {
        optimization_suggestions_.push_back(
            "Use StringBuilder for string concatenation in loops to avoid creating multiple String objects");
    }
}

void JavaAdapter::analyze_loops(const std::string& source_code) {
    // Look for inefficient loop patterns
    if (source_code.find("for (int i = 0; i < list.size(); i++)") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Cache list.size() in a variable or use enhanced for-loop to avoid repeated method calls");
    }
}

void JavaAdapter::analyze_memory_usage(const std::string& source_code) {
    // Check for object creation patterns
    if (source_code.find("new ") != std::string::npos && 
        source_code.find("for") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider object pooling or reusing objects in loops to reduce garbage collection pressure");
    }
}

} // namespace codegreen
