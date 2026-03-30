#pragma once

#include <string>
#include <vector>
#include <memory>

namespace codegreen {

/// Main optimizer class for code energy optimization
class Optimizer {
public:
    Optimizer();
    ~Optimizer() = default;

    /// Analyze code for optimization opportunities
    bool analyze_code(const std::string& source_code, const std::string& language);

    /// Get optimization suggestions
    std::vector<std::string> get_suggestions() const;

    /// Apply optimizations to code
    std::string apply_optimizations(const std::string& source_code);

    /// Get optimization metrics
    std::vector<std::pair<std::string, double>> get_metrics() const;

private:
    std::vector<std::string> suggestions_;
    std::vector<std::pair<std::string, double>> metrics_;
};

} // namespace codegreen
