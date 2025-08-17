#pragma once

#include <string>

namespace codegreen {

/// IntelliJ plugin configuration
struct IntelliJConfig {
    std::string plugin_id;
    std::string display_name;
    std::string version;

    IntelliJConfig() = default;
    
    IntelliJConfig(const std::string& id, const std::string& name, const std::string& ver)
        : plugin_id(id), display_name(name), version(ver) {}
};

/// Initialize IntelliJ integration
bool init_intellij(const IntelliJConfig& config);

/// Register IntelliJ actions
bool register_actions();

} // namespace codegreen
