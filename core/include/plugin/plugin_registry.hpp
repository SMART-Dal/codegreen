#pragma once

#include <memory>
#include <vector>
#include <unordered_map>
#include <string>
#include "hardware_plugin.hpp"

namespace codegreen {

/// Registry for managing hardware plugins
class PluginRegistry {
public:
    PluginRegistry();
    ~PluginRegistry() = default;

    /// Register a new plugin
    void register_plugin(std::unique_ptr<HardwarePlugin> plugin);

    /// Get all registered plugins
    std::vector<const HardwarePlugin*> get_plugins() const;

    /// Get available plugins
    std::vector<const HardwarePlugin*> get_available_plugins() const;

    /// Get a plugin by name
    const HardwarePlugin* get_plugin(const std::string& name) const;

    /// Remove a plugin by name
    bool remove_plugin(const std::string& name);

private:
    std::vector<std::unique_ptr<HardwarePlugin>> plugins_;
    std::unordered_map<std::string, HardwarePlugin*> plugin_map_;
};

} // namespace codegreen
