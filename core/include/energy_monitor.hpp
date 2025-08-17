#pragma once

#include <memory>
#include <vector>
#include "measurement_session.hpp"
#include "plugin/hardware_plugin.hpp"
#include "plugin/plugin_registry.hpp"

namespace codegreen {

class EnergyMonitor {
public:
    EnergyMonitor();
    ~EnergyMonitor() = default;

    // Register a plugin
    void register_plugin(std::unique_ptr<HardwarePlugin> plugin);

    // Start measurement
    std::unique_ptr<MeasurementSession> start_measurement();

    // Stop measurement
    std::unique_ptr<MeasurementSession> stop_measurement(std::unique_ptr<MeasurementSession> session);

    // Get available plugins
    std::vector<const HardwarePlugin*> get_plugins() const;

private:
    std::unique_ptr<PluginRegistry> registry_;
};

} // namespace codegreen
