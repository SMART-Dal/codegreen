#pragma once

#include <string>
#include <memory>
#include <vector>

namespace codegreen {

/// Represents a code location for energy measurement
struct CodeCheckpoint {
    std::string id;           // Unique identifier for this checkpoint
    std::string type;         // Type: function_enter, function_exit, loop_start, etc.
    std::string name;         // Function/method/class name
    size_t line_number;       // Line number in source code
    size_t column_number;     // Column number in source code
    std::string context;      // Additional context information
};

/// AST node representation for language-agnostic processing
struct ASTNode {
    std::string type;         // Node type (function, class, loop, etc.)
    std::string name;         // Node name if applicable
    size_t start_line;        // Starting line number
    size_t end_line;          // Ending line number
    size_t start_column;      // Starting column
    size_t end_column;        // Ending column
    std::vector<std::unique_ptr<ASTNode>> children;  // Child nodes
};

/// Abstract base class for language adapters
class LanguageAdapter {
public:
    virtual ~LanguageAdapter() = default;

    /// Get the language ID this adapter supports
    virtual std::string get_language_id() const = 0;

    /// Parse source code and return a language-agnostic AST
    virtual std::unique_ptr<ASTNode> parse(const std::string& source_code) = 0;

    /// Generate energy measurement checkpoints from source code
    virtual std::vector<CodeCheckpoint> generate_checkpoints(const std::string& source_code) = 0;

    /// Instrument source code with energy measurement calls
    virtual std::string instrument_code(const std::string& source_code, 
                                       const std::vector<CodeCheckpoint>& checkpoints) = 0;

    /// Analyze code for energy optimization opportunities
    virtual bool analyze(const std::string& source_code) = 0;

    /// Get optimization suggestions
    virtual std::vector<std::string> get_suggestions() const = 0;

    /// Get the file extensions this adapter supports
    virtual std::vector<std::string> get_file_extensions() const = 0;
};

} // namespace codegreen
