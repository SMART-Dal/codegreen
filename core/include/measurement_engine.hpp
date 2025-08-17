#pragma once

#include <memory>
#include <vector>
#include <string>
#include <chrono>
#include <unordered_map>
#include "measurement_session.hpp"
#include "plugin/hardware_plugin.hpp"
#include "adapters/language_adapter.hpp"

namespace codegreen {

class MeasurementEngine {
public:
    MeasurementEngine();
    ~MeasurementEngine() = default;

    // Register a language adapter
    void register_language_adapter(std::unique_ptr<LanguageAdapter> adapter);

    // Get all registered language adapters
    const std::vector<std::unique_ptr<LanguageAdapter>>& language_adapters() const;

    // Analyze code with language adapters
    bool analyze_code(const std::string& source_code, const std::string& language_id);

private:
    std::unique_ptr<PluginRegistry> plugin_registry_;
    std::vector<std::unique_ptr<LanguageAdapter>> language_adapters_;
};

} // namespace codegreen
