#include "tree_sitter_adapter.hpp"
#include <sstream>
#include <iostream>
#include <iomanip>
#include <unordered_map>
#include <algorithm>
#include <cmath>

namespace codegreen {

TreeSitterAdapter::TreeSitterAdapter(const TSLanguage* language) 
    : parser_(ts_parser_new()), tree_(nullptr), language_(language) {
    ts_parser_set_language(parser_, language_);
}

TreeSitterAdapter::~TreeSitterAdapter() {
    if (tree_) {
        ts_tree_delete(tree_);
    }
    if (parser_) {
        ts_parser_delete(parser_);
    }
}

std::unique_ptr<ASTNode> TreeSitterAdapter::parse(const std::string& source_code) {
    if (tree_) {
        ts_tree_delete(tree_);
        tree_ = nullptr;
    }

    tree_ = ts_parser_parse_string(parser_, nullptr, source_code.c_str(), source_code.length());
    if (!tree_) {
        return nullptr;
    }

    TSNode root_node = ts_tree_root_node(tree_);
    return convert_node(root_node, source_code);
}

std::vector<CodeCheckpoint> TreeSitterAdapter::generate_checkpoints(const std::string& source_code) {
    std::vector<CodeCheckpoint> checkpoints;
    
    if (tree_) {
        ts_tree_delete(tree_);
        tree_ = nullptr;
    }

    tree_ = ts_parser_parse_string(parser_, nullptr, source_code.c_str(), source_code.length());
    if (!tree_) {
        return checkpoints;
    }

    TSNode root_node = ts_tree_root_node(tree_);
    traverse_for_checkpoints(root_node, source_code, checkpoints);
    
    return checkpoints;
}

std::unique_ptr<ASTNode> TreeSitterAdapter::convert_node(TSNode node, const std::string& source_code) {
    auto ast_node = std::make_unique<ASTNode>();
    
    ast_node->type = get_node_type(node);
    ast_node->name = extract_function_name(node, source_code);
    
    TSPoint start_point = ts_node_start_point(node);
    TSPoint end_point = ts_node_end_point(node);
    
    ast_node->start_line = start_point.row + 1;  // Convert to 1-based indexing
    ast_node->end_line = end_point.row + 1;
    ast_node->start_column = start_point.column + 1;
    ast_node->end_column = end_point.column + 1;
    
    convert_children(node, ast_node.get(), source_code);
    
    return ast_node;
}

void TreeSitterAdapter::convert_children(TSNode node, ASTNode* ast_node, const std::string& source_code) {
    uint32_t child_count = ts_node_child_count(node);
    
    for (uint32_t i = 0; i < child_count; ++i) {
        TSNode child = ts_node_child(node, i);
        auto child_ast = convert_node(child, source_code);
        if (child_ast) {
            ast_node->children.push_back(std::move(child_ast));
        }
    }
}

void TreeSitterAdapter::traverse_for_checkpoints(
    TSNode node, 
    const std::string& source_code, 
    std::vector<CodeCheckpoint>& checkpoints,
    int depth) {
    
    std::string node_type = get_node_type(node);
    
    // Debug output to see what nodes we're processing
    if (depth == 0) {
        std::cout << "🔍 Processing node: " << node_type << std::endl;
    }
    
    if (should_generate_checkpoint_adaptive(node_type, node, source_code)) {
        std::cout << "✅ Generating checkpoints for: " << node_type << std::endl;
        auto node_checkpoints = generate_node_checkpoints(node, source_code, node_type);
        checkpoints.insert(checkpoints.end(), node_checkpoints.begin(), node_checkpoints.end());
    }
    
    // Recursively process children
    uint32_t child_count = ts_node_child_count(node);
    for (uint32_t i = 0; i < child_count; ++i) {
        TSNode child = ts_node_child(node, i);
        traverse_for_checkpoints(child, source_code, checkpoints, depth + 1);
    }
}

std::vector<CodeCheckpoint> TreeSitterAdapter::generate_node_checkpoints(
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
        node_type == "function_declaration") {
        
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
    
    // Generate loop checkpoints
    if (node_type == "for_statement" || node_type == "while_statement" || 
        node_type == "for_in_statement" || node_type == "with_statement") {
        
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

std::string TreeSitterAdapter::get_node_type(TSNode node) const {
    return std::string(ts_node_type(node));
}

std::string TreeSitterAdapter::get_node_text(TSNode node, const std::string& source_code) const {
    uint32_t start_byte = ts_node_start_byte(node);
    uint32_t end_byte = ts_node_end_byte(node);
    
    if (start_byte >= source_code.length() || end_byte > source_code.length()) {
        return "";
    }
    
    return source_code.substr(start_byte, end_byte - start_byte);
}

bool TreeSitterAdapter::should_generate_checkpoint(const std::string& node_type) const {
    // Default implementation - can be overridden by language-specific adapters
    return node_type == "function_definition" || 
           node_type == "method_definition" ||
           node_type == "function_declaration" ||
           node_type == "for_statement" ||
           node_type == "while_statement" ||
           node_type == "for_in_statement" ||
           node_type == "with_statement" ||
           node_type == "class_definition";
}

std::string TreeSitterAdapter::extract_function_name(TSNode node, const std::string& source_code) const {
    // Default implementation - should be overridden by language-specific adapters
    std::string node_type = get_node_type(node);
    
    if (node_type == "function_definition" || node_type == "method_definition" ||
        node_type == "class_definition") {
        
        // Look for identifier child node
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; ++i) {
            TSNode child = ts_node_child(node, i);
            std::string child_type = get_node_type(child);
            
            if (child_type == "identifier" || child_type == "name") {
                return get_node_text(child, source_code);
            }
        }
    }
    
    return "";
}

std::string TreeSitterAdapter::generate_checkpoint_id(
    const std::string& type, 
    const std::string& name, 
    size_t line) const {
    
    std::ostringstream oss;
    oss << type << "_" << name << "_" << line;
    return oss.str();
}

bool TreeSitterAdapter::should_skip_checkpoint_insertion(const std::string& line, 
                                                        const std::vector<std::string>& lines, 
                                                        size_t line_index) const {
    // Default implementation - always allow insertion
    // Language-specific adapters can override this for more sophisticated logic
    return false;
}

bool TreeSitterAdapter::should_generate_checkpoint_adaptive(const std::string& node_type, 
                                                           TSNode node, 
                                                           const std::string& source_code) const {
    // First check basic node type eligibility
    if (!should_generate_checkpoint(node_type)) {
        return false;
    }
    
    // Skip trivial operations that don't consume significant energy
    if (is_trivial_operation(node_type, node, source_code)) {
        return false;
    }
    
    // Estimate execution time for this node
    double estimated_time_ms = estimate_node_execution_time(node, node_type, source_code);
    
    // Skip checkpoints for very short operations to reduce noise
    if (estimated_time_ms < MIN_MEASURABLE_TIME_MS) {
        return false;
    }
    
    // Always generate checkpoints for function entries/exits (critical for energy attribution)
    if (node_type.find("function") != std::string::npos || 
        node_type.find("method") != std::string::npos ||
        node_type.find("class") != std::string::npos) {
        return true;
    }
    
    // For loops and computationally intensive operations, always generate checkpoints
    if (node_type.find("for_statement") != std::string::npos || 
        node_type.find("while_statement") != std::string::npos ||
        node_type.find("comprehension") != std::string::npos) {
        return true;
    }
    
    // For other node types, apply stricter filtering based on estimated execution time
    return estimated_time_ms >= NOISE_THRESHOLD_MS;
}

double TreeSitterAdapter::estimate_node_execution_time(TSNode node, const std::string& node_type, 
                                                      const std::string& source_code) const {
    // Baseline estimates in milliseconds based on node type complexity
    static const std::unordered_map<std::string, double> base_estimates = {
        // Function definitions - always important
        {"function_definition", 10.0},
        {"method_definition", 10.0},
        {"function_declaration", 10.0},
        
        // Loops - potentially high energy consumers
        {"for_statement", 5.0},
        {"while_statement", 5.0},
        {"for_in_statement", 5.0},
        
        // Control flow
        {"if_statement", 2.0},
        {"switch_statement", 3.0},
        
        // Expressions and calls
        {"call", 1.0},
        {"expression_statement", 0.5},
        {"assignment", 0.3},
        
        // Comprehensions (Python-specific but can be extended)
        {"list_comprehension", 3.0},
        {"dictionary_comprehension", 3.0},
        {"set_comprehension", 3.0},
        
        // Context managers
        {"with_statement", 2.0},
        {"async_with_statement", 2.0},
        
        // Classes
        {"class_definition", 5.0},
        
        // Default for unknown types
        {"default", 1.0}
    };
    
    double base_time = base_estimates.count(node_type) ? 
                      base_estimates.at(node_type) : 
                      base_estimates.at("default");
    
    // Adjust based on node complexity (number of children, text length)
    uint32_t child_count = ts_node_child_count(node);
    size_t text_length = get_node_text(node, source_code).length();
    
    // Complexity multiplier based on children count
    double complexity_multiplier = 1.0 + (child_count * 0.1);
    
    // Length multiplier for text-heavy nodes
    double length_multiplier = 1.0 + (text_length / 1000.0);
    
    // Apply multipliers with reasonable bounds
    complexity_multiplier = std::min(complexity_multiplier, 5.0);
    length_multiplier = std::min(length_multiplier, 3.0);
    
    double estimated_time = base_time * complexity_multiplier * length_multiplier;
    
    // Ensure minimum threshold for measurement noise reduction
    return std::max(estimated_time, 0.01);  // At least 10 microseconds
}

bool TreeSitterAdapter::is_trivial_operation(const std::string& node_type, TSNode node,
                                             const std::string& source_code) const {
    // Skip simple assignments unless they involve function calls
    if (node_type == "assignment" || node_type == "expression_statement") {
        std::string node_text = get_node_text(node, source_code);
        
        // Skip simple variable assignments (no function calls or complex operations)
        if (node_text.length() < MIN_NODE_SIZE_FOR_CHECKPOINT &&
            node_text.find('(') == std::string::npos &&  // No function calls
            node_text.find('[') == std::string::npos &&  // No array/dict access
            node_text.find('.') == std::string::npos) {   // No method calls
            return true;
        }
    }
    
    // Skip simple function calls to basic built-ins
    if (node_type == "call") {
        std::string node_text = get_node_text(node, source_code);
        static const std::vector<std::string> trivial_calls = {
            "print(", "len(", "str(", "int(", "float(", "bool("
        };
        
        for (const auto& trivial : trivial_calls) {
            if (node_text.find(trivial) != std::string::npos) {
                return true;
            }
        }
    }
    
    return false;
}

bool TreeSitterAdapter::is_checkpoint_redundant(const std::string& node_type, TSNode node,
                                              const std::vector<CodeCheckpoint>& existing_checkpoints) const {
    TSPoint node_start = ts_node_start_point(node);
    size_t current_line = node_start.row + 1;
    
    // Check if we already have a checkpoint within 2 lines for similar node types
    for (const auto& checkpoint : existing_checkpoints) {
        if (std::abs(static_cast<int>(checkpoint.line_number) - static_cast<int>(current_line)) <= 2) {
            // Same type of checkpoint nearby - potentially redundant
            if (checkpoint.type == node_type || 
                (checkpoint.type.find("call") != std::string::npos && node_type.find("call") != std::string::npos)) {
                return true;
            }
        }
    }
    
    return false;
}

} // namespace codegreen