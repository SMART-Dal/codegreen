#pragma once

#include "adapters/language_adapter.hpp"
#include <filesystem>

namespace codegreen {

/// Python Bridge Adapter that calls the Python AST-based instrumentation system
class PythonBridgeAdapter : public LanguageAdapter {
public:
    PythonBridgeAdapter();
    
    // LanguageAdapter interface
    std::string get_language_id() const override;
    std::unique_ptr<ASTNode> parse(const std::string& source_code) override;
    std::vector<CodeCheckpoint> generate_checkpoints(const std::string& source_code) override;
    std::string instrument_code(const std::string& source_code, 
                               const std::vector<CodeCheckpoint>& checkpoints) override;
    bool analyze(const std::string& source_code) override;
    std::vector<std::string> get_suggestions() const override;
    std::vector<std::string> get_file_extensions() const override;

private:
    std::filesystem::path instrumentation_path_;
    
    /// Parse results from Python instrumentation system
    std::vector<CodeCheckpoint> parse_python_results(const std::string& output);
};

} // namespace codegreen