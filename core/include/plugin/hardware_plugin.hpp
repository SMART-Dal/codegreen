#pragma once

#include <string>
#include <memory>
#include "measurement.hpp"

namespace codegreen {

/// Abstract base class for hardware plugins
class HardwarePlugin {
public:
    virtual ~HardwarePlugin() = default;

    /// Get the name of the plugin
    virtual std::string name() const = 0;

    /// Get a measurement from the hardware
    virtual std::unique_ptr<Measurement> get_measurement() = 0;

    /// Initialize the plugin
    virtual bool init() = 0;

    /// Cleanup the plugin
    virtual void cleanup() = 0;

    /// Check if the plugin is available on this system
    virtual bool is_available() const = 0;
};

} // namespace codegreen
