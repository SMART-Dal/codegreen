#pragma once

#include <string>

namespace codegreen {

/// VSCode extension configuration
struct VSCodeConfig {
    std::string extension_id;
    std::string display_name;
    std::string version;

    VSCodeConfig() = default;
    
    VSCodeConfig(const std::string& id, const std::string& name, const std::string& ver)
        : extension_id(id), display_name(name), version(ver) {}
};

/// Initialize VSCode integration
bool init_vscode(const VSCodeConfig& config);

/// Register VSCode commands
bool register_commands();

} // namespace codegreen
