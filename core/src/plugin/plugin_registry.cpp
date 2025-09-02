#include "plugin/plugin_registry.hpp"
#include <algorithm>

namespace codegreen {

PluginRegistry::PluginRegistry() = default;

void PluginRegistry::register_plugin(std::unique_ptr<HardwarePlugin> plugin) {
    if (plugin) {
        std::string name = plugin->name();
        plugin_map_[name] = plugin.get();
        plugins_.push_back(std::move(plugin));
    }
}

std::vector<const HardwarePlugin*> PluginRegistry::get_plugins() const {
    std::vector<const HardwarePlugin*> result;
    result.reserve(plugins_.size());
    
    for (const auto& plugin : plugins_) {
        result.push_back(plugin.get());
    }
    
    return result;
}

std::vector<const HardwarePlugin*> PluginRegistry::get_available_plugins() const {
    std::vector<const HardwarePlugin*> result;
    result.reserve(plugins_.size());
    
    for (const auto& plugin : plugins_) {
        if (plugin->is_available()) {
            result.push_back(plugin.get());
        }
    }
    
    return result;
}

const HardwarePlugin* PluginRegistry::get_plugin(const std::string& name) const {
    auto it = plugin_map_.find(name);
    return (it != plugin_map_.end()) ? it->second : nullptr;
}

bool PluginRegistry::remove_plugin(const std::string& name) {
    auto it = plugin_map_.find(name);
    if (it == plugin_map_.end()) {
        return false;
    }
    
    // Remove from plugins vector
    auto vec_it = std::find_if(plugins_.begin(), plugins_.end(),
        [&name](const std::unique_ptr<HardwarePlugin>& plugin) {
            return plugin->name() == name;
        });
    
    if (vec_it != plugins_.end()) {
        plugins_.erase(vec_it);
    }
    
    // Remove from map
    plugin_map_.erase(it);
    return true;
}

} // namespace codegreen
