#pragma once

#include <string>
#include <memory>

namespace codegreen {

/// Errors that can occur during IDE integration
enum class IdeError {
    InitializationError,
    PluginError,
    ConfigurationError
};

/// Main IDE integration class
class IdeIntegration {
public:
    IdeIntegration();
    ~IdeIntegration() = default;

    /// Initialize the IDE integration system
    bool init();

    /// Register a new IDE plugin
    bool register_plugin(const std::string& name);

    /// Get the last error message
    std::string get_last_error() const;

private:
    std::string last_error_;
};

} // namespace codegreen
