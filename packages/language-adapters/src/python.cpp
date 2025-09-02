#include "python.hpp"
#include <sstream>
#include <regex>
#include <algorithm>

namespace codegreen {

PythonAdapter::PythonAdapter() : TreeSitterAdapter(tree_sitter_python()) {
}

std::string PythonAdapter::get_language_id() const {
    return "python";
}

std::vector<std::string> PythonAdapter::get_file_extensions() const {
    return {".py", ".pyw", ".pyi"};
}

bool PythonAdapter::should_generate_checkpoint(const std::string& node_type) const {
    return node_type == "function_definition" ||
           node_type == "async_function_definition" ||
           node_type == "class_definition" ||
           node_type == "for_statement" ||
           node_type == "async_for_statement" ||
           node_type == "while_statement" ||
           node_type == "with_statement" ||
           node_type == "async_with_statement" ||
           node_type == "list_comprehension" ||
           node_type == "dictionary_comprehension" ||
           node_type == "set_comprehension" ||
           node_type == "expression_statement" ||  // For print() and other expressions
           node_type == "if_statement" ||          // For if/elif/else blocks
           node_type == "try_statement" ||         // For try/except blocks
           node_type == "assignment" ||            // For variable assignments
           node_type == "call";                    // For function calls
}

std::string PythonAdapter::extract_function_name(TSNode node, const std::string& source_code) const {
    std::string node_type = get_node_type(node);
    
    if (node_type == "function_definition" || 
        node_type == "async_function_definition" ||
        node_type == "class_definition") {
        
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

std::vector<CodeCheckpoint> PythonAdapter::generate_node_checkpoints(
    TSNode node, 
    const std::string& source_code,
    const std::string& node_type) {
    
    std::vector<CodeCheckpoint> checkpoints;
    
    TSPoint start_point = ts_node_start_point(node);
    TSPoint end_point = ts_node_end_point(node);
    
    std::string name = extract_function_name(node, source_code);
    if (name.empty() && (node_type.find("comprehension") != std::string::npos)) {
        name = node_type;
    } else if (name.empty()) {
        name = "anonymous_" + node_type;
    }
    
    // Function and method checkpoints
    if (node_type == "function_definition" || node_type == "async_function_definition") {
        CodeCheckpoint entry;
        entry.id = generate_checkpoint_id("function_enter", name, start_point.row + 1);
        entry.type = "function_enter";
        entry.name = name;
        entry.line_number = start_point.row + 1;
        entry.column_number = start_point.column + 1;
        entry.context = (node_type.find("async") != std::string::npos ? "Async function" : "Function") + std::string(" entry: ") + name;
        checkpoints.push_back(entry);
        
        CodeCheckpoint exit;
        exit.id = generate_checkpoint_id("function_exit", name, end_point.row + 1);
        exit.type = "function_exit";
        exit.name = name;
        exit.line_number = end_point.row + 1;
        exit.column_number = end_point.column + 1;
        exit.context = (node_type.find("async") != std::string::npos ? "Async function" : "Function") + std::string(" exit: ") + name;
        checkpoints.push_back(exit);
    }
    
    // Class checkpoints
    else if (node_type == "class_definition") {
        CodeCheckpoint entry;
        entry.id = generate_checkpoint_id("class_enter", name, start_point.row + 1);
        entry.type = "class_enter";
        entry.name = name;
        entry.line_number = start_point.row + 1;
        entry.column_number = start_point.column + 1;
        entry.context = "Class definition: " + name;
        checkpoints.push_back(entry);
    }
    
    // Loop checkpoints
    else if (node_type == "for_statement" || node_type == "async_for_statement" || 
             node_type == "while_statement") {
        CodeCheckpoint loop;
        loop.id = generate_checkpoint_id("loop_start", node_type, start_point.row + 1);
        loop.type = "loop_start";
        loop.name = node_type;
        loop.line_number = start_point.row + 1;
        loop.column_number = start_point.column + 1;
        loop.context = "Loop start: " + node_type;
        checkpoints.push_back(loop);
    }
    
    // Context manager checkpoints (with statements)
    else if (node_type == "with_statement" || node_type == "async_with_statement") {
        CodeCheckpoint with_start;
        with_start.id = generate_checkpoint_id("context_enter", node_type, start_point.row + 1);
        with_start.type = "context_enter";
        with_start.name = node_type;
        with_start.line_number = start_point.row + 1;
        with_start.column_number = start_point.column + 1;
        with_start.context = "Context manager entry: " + node_type;
        checkpoints.push_back(with_start);
    }
    
    // Comprehension checkpoints
    else if (node_type.find("comprehension") != std::string::npos) {
        CodeCheckpoint comp;
        comp.id = generate_checkpoint_id("comprehension_start", node_type, start_point.row + 1);
        comp.type = "comprehension_start";
        comp.name = node_type;
        comp.line_number = start_point.row + 1;
        comp.column_number = start_point.column + 1;
        comp.context = "Comprehension: " + node_type;
        checkpoints.push_back(comp);
    }
    
    // Expression statement checkpoints (for print() and other expressions)
    else if (node_type == "expression_statement") {
        CodeCheckpoint expr;
        expr.id = generate_checkpoint_id("expression", "statement", start_point.row + 1);
        expr.type = "expression";
        expr.name = "statement";
        expr.line_number = start_point.row + 1;
        expr.column_number = start_point.column + 1;
        expr.context = "Expression statement at line " + std::to_string(start_point.row + 1);
        checkpoints.push_back(expr);
    }
    
    // Function call checkpoints
    else if (node_type == "call") {
        CodeCheckpoint call;
        call.id = generate_checkpoint_id("function_call", "call", start_point.row + 1);
        call.type = "function_call";
        call.name = "call";
        call.line_number = start_point.row + 1;
        call.column_number = start_point.column + 1;
        call.context = "Function call at line " + std::to_string(start_point.row + 1);
        checkpoints.push_back(call);
    }
    
    // Assignment checkpoints
    else if (node_type == "assignment") {
        CodeCheckpoint assign;
        assign.id = generate_checkpoint_id("assignment", "assignment", start_point.row + 1);
        assign.type = "assignment";
        assign.name = "assignment";
        assign.line_number = start_point.row + 1;
        assign.column_number = start_point.column + 1;
        assign.context = "Variable assignment at line " + std::to_string(start_point.row + 1);
        checkpoints.push_back(assign);
    }
    
    return checkpoints;
}

std::string PythonAdapter::instrument_code(const std::string& source_code, 
                                         const std::vector<CodeCheckpoint>& checkpoints) {
    if (checkpoints.empty()) {
        return source_code;
    }
    
    auto lines = split_lines(source_code);
    std::string instrumented_import = generate_measurement_import();
    
    // Add import at the beginning
    lines.insert(lines.begin(), instrumented_import);
    
    // Sort checkpoints by line number (descending) to avoid line number shifts
    auto sorted_checkpoints = checkpoints;
    std::sort(sorted_checkpoints.begin(), sorted_checkpoints.end(), 
              [](const CodeCheckpoint& a, const CodeCheckpoint& b) {
                  return a.line_number > b.line_number;
              });
    
            // Insert checkpoint calls - simplified approach
        for (const auto& checkpoint : sorted_checkpoints) {
            // Account for the import statement that was added at the beginning
            size_t adjusted_line = checkpoint.line_number + 1; // +1 for the import line
            if (adjusted_line <= lines.size()) {
                size_t insert_line = adjusted_line;
                
                // Handle all checkpoint types
                std::string checkpoint_call = generate_checkpoint_call(checkpoint);
                
                if (checkpoint.type == "function_enter") {
                    // Function entry: insert at beginning of function body
                    std::string original_line = lines[insert_line - 1];
                    std::string def_indentation = get_indentation(original_line);
                    std::string body_indentation = def_indentation + "    "; // Always add 4 spaces
                    
                    checkpoint_call = body_indentation + checkpoint_call;
                    
                    // Find where to insert the checkpoint call (after the def line and any docstring)
                    size_t insert_pos = insert_line;
                    
                    // Skip empty lines immediately after function definition
                    while (insert_pos < lines.size() && lines[insert_pos].empty()) {
                        insert_pos++;
                    }
                    
                    // If next line starts with a docstring, insert after it
                    if (insert_pos < lines.size()) {
                        std::string line = lines[insert_pos];
                        if (line.find("\"\"\"") != std::string::npos || line.find("'''") != std::string::npos) {
                            insert_pos++; // Skip the docstring line
                        }
                    }
                    
                    lines.insert(lines.begin() + insert_pos, checkpoint_call);
                }
                else if (checkpoint.type == "function_call" || checkpoint.type == "expression") {
                    // Function calls and expressions: insert before the line
                    std::string original_line = lines[insert_line - 1];
                    std::string indentation = get_indentation(original_line);
                    
                    // Skip insertion if the line is part of a dictionary literal or complex expression
                    if (should_skip_checkpoint_insertion(original_line, lines, insert_line - 1)) {
                        continue;
                    }
                    
                    checkpoint_call = indentation + checkpoint_call;
                    lines.insert(lines.begin() + insert_line - 1, checkpoint_call);
                }
                else {
                    // Other types: insert before the line with same indentation
                    std::string original_line = lines[insert_line - 1];
                    std::string indentation = get_indentation(original_line);
                    
                    // Skip insertion if the line is part of a dictionary literal or complex expression
                    if (should_skip_checkpoint_insertion(original_line, lines, insert_line - 1)) {
                        continue;
                    }
                    
                    checkpoint_call = indentation + checkpoint_call;
                    lines.insert(lines.begin() + insert_line - 1, checkpoint_call);
                }
            }
        }
    
    return join_lines(lines);
}

bool PythonAdapter::analyze(const std::string& source_code) {
    optimization_suggestions_.clear();
    
    analyze_list_comprehensions(source_code);
    analyze_loops(source_code);
    analyze_imports(source_code);
    analyze_string_operations(source_code);
    
    return !optimization_suggestions_.empty();
}

std::vector<std::string> PythonAdapter::get_suggestions() const {
    return optimization_suggestions_;
}

// Private helper methods

std::string PythonAdapter::generate_measurement_import() const {
    return "import codegreen_runtime as _codegreen_rt";
}

std::string PythonAdapter::generate_checkpoint_call(const CodeCheckpoint& checkpoint) const {
    // Pre-allocate string with estimated size for better performance
    std::string result;
    result.reserve(100 + checkpoint.id.length() + checkpoint.type.length() + 
                   checkpoint.name.length() + checkpoint.context.length());
    
    result = "_codegreen_rt.measure_checkpoint('";
    result += checkpoint.id;
    result += "', '";
    result += checkpoint.type;
    result += "', '";
    result += checkpoint.name;
    result += "', ";
    result += std::to_string(checkpoint.line_number);
    result += ", '";
    result += checkpoint.context;
    result += "')";
    
    return result;
}

std::vector<std::string> PythonAdapter::split_lines(const std::string& source_code) const {
    std::vector<std::string> lines;
    std::istringstream stream(source_code);
    std::string line;
    
    while (std::getline(stream, line)) {
        lines.push_back(line);
    }
    
    return lines;
}

std::string PythonAdapter::join_lines(const std::vector<std::string>& lines) const {
    std::ostringstream oss;
    for (size_t i = 0; i < lines.size(); ++i) {
        oss << lines[i];
        if (i < lines.size() - 1) {
            oss << "\n";
        }
    }
    return oss.str();
}

std::string PythonAdapter::get_indentation(const std::string& line) const {
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

bool PythonAdapter::should_skip_checkpoint_insertion(const std::string& line, 
                                                    const std::vector<std::string>& lines, 
                                                    size_t line_index) const {
    // Skip if line is empty or only whitespace
    if (line.empty() || line.find_first_not_of(" \t") == std::string::npos) {
        return true;
    }
    
    // Skip if line is a comment
    std::string trimmed = line;
    size_t first_non_space = trimmed.find_first_not_of(" \t");
    if (first_non_space != std::string::npos && trimmed[first_non_space] == '#') {
        return true;
    }
    
    // Skip if line is part of a dictionary literal (contains ':' and looks like a dict entry)
    if (line.find(':') != std::string::npos) {
        // Check if this looks like a dictionary entry
        size_t colon_pos = line.find(':');
        std::string before_colon = line.substr(0, colon_pos);
        std::string after_colon = line.substr(colon_pos + 1);
        
        // If there's a quote before the colon and content after, it's likely a dict entry
        if ((before_colon.find('"') != std::string::npos || before_colon.find("'") != std::string::npos) &&
            !after_colon.empty() && after_colon.find_first_not_of(" \t") != std::string::npos) {
            return true;
        }
    }
    
    // Skip if line is part of a list literal (contains ',')
    if (line.find(',') != std::string::npos && 
        (line.find('[') != std::string::npos || line.find(']') != std::string::npos)) {
        return true;
    }
    
    // Skip if line is a string literal (starts and ends with quotes)
    if ((line.find('"') != std::string::npos || line.find("'") != std::string::npos) &&
        line.find('=') == std::string::npos) {
        return true;
    }
    
    // Skip if line is a docstring
    if (line.find("\"\"\"") != std::string::npos || line.find("'''") != std::string::npos) {
        return true;
    }
    
    // Skip if line is an import statement
    if (line.find("import ") != std::string::npos || line.find("from ") != std::string::npos) {
        return true;
    }
    
    // Skip if line is a class/function definition
    if (line.find("class ") != std::string::npos || 
        line.find("def ") != std::string::npos ||
        line.find("async def ") != std::string::npos) {
        return true;
    }
    
    // Skip if line is part of a return statement with dictionary/list
    if (line.find("return {") != std::string::npos || 
        line.find("return [") != std::string::npos ||
        line.find("return (") != std::string::npos) {
        return true;
    }
    
    // Skip if line is a closing brace/bracket/parenthesis
    std::string trimmed_line = line;
    size_t first_non_space_pos = trimmed_line.find_first_not_of(" \t");
    if (first_non_space_pos != std::string::npos) {
        char first_char = trimmed_line[first_non_space_pos];
        if (first_char == '}' || first_char == ']' || first_char == ')') {
            return true;
        }
    }
    
    return false;
}

void PythonAdapter::analyze_list_comprehensions(const std::string& source_code) {
    // Look for inefficient patterns in list comprehensions
    if (source_code.find("[") != std::string::npos && 
        source_code.find("for") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using generator expressions instead of list comprehensions for large datasets to save memory");
    }
}

void PythonAdapter::analyze_loops(const std::string& source_code) {
    // Analyze loop patterns
    std::regex range_pattern(R"(for\s+\w+\s+in\s+range\(len\()");
    if (std::regex_search(source_code, range_pattern)) {
        optimization_suggestions_.push_back(
            "Replace 'for i in range(len(seq))' with 'for i, item in enumerate(seq)' for better performance");
    }
}

void PythonAdapter::analyze_imports(const std::string& source_code) {
    // Check for inefficient import patterns
    if (source_code.find("from") == std::string::npos && 
        source_code.find("import") != std::string::npos) {
        optimization_suggestions_.push_back(
            "Consider using 'from module import specific_function' instead of importing entire modules");
    }
}

void PythonAdapter::analyze_string_operations(const std::string& source_code) {
    // Look for string concatenation in loops
    if (source_code.find("+=") != std::string::npos && 
        (source_code.find("for") != std::string::npos || source_code.find("while") != std::string::npos)) {
        optimization_suggestions_.push_back(
            "Avoid string concatenation in loops; use list.join() or f-strings for better performance");
    }
}

} // namespace codegreen
