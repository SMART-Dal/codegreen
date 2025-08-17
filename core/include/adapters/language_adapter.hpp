#pragma once

#include <string>
#include <memory>

namespace codegreen {

/// Abstract base class for language adapters
class LanguageAdapter {
public:
    virtual ~LanguageAdapter() = default;

    /// Get the language ID this adapter supports
    virtual std::string get_language_id() const = 0;

    /// Parse source code and return an AST
    virtual std::unique_ptr<void> parse(const std::string& source_code) = 0;

    /// Analyze code for energy optimization opportunities
    virtual bool analyze(const std::string& source_code) = 0;

    /// Get optimization suggestions
    virtual std::vector<std::string> get_suggestions() const = 0;
};

} // namespace codegreen
