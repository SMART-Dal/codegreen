#include "energy_monitor.hpp"
#include "plugin/plugin_registry.hpp"
#include <algorithm>

namespace codegreen {

EnergyMonitor::EnergyMonitor()
    : registry_(std::make_unique<PluginRegistry>()) {
}

void EnergyMonitor::register_plugin(std::unique_ptr<HardwarePlugin> plugin) {
    registry_->register_plugin(std::move(plugin));
}

std::unique_ptr<MeasurementSession> EnergyMonitor::start_measurement() {
    auto session = std::make_unique<MeasurementSession>();
    auto plugins = registry_->get_plugins();
    
    for (const auto& plugin : plugins) {
        auto measurement = plugin->get_measurement();
        if (measurement) {
            session->add_start_measurement(plugin->name(), *measurement);
        }
    }
    
    return session;
}

std::unique_ptr<MeasurementSession> EnergyMonitor::stop_measurement(std::unique_ptr<MeasurementSession> session) {
    auto plugins = registry_->get_plugins();
    
    for (const auto& plugin : plugins) {
        auto measurement = plugin->get_measurement();
        if (measurement) {
            session->add_end_measurement(plugin->name(), *measurement);
        }
    }
    
    return session;
}

std::vector<const HardwarePlugin*> EnergyMonitor::get_plugins() const {
    return registry_->get_available_plugins();
}

} // namespace codegreen
