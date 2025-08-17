#include "ide_integration.hpp"

namespace codegreen {

IdeIntegration::IdeIntegration() = default;

bool IdeIntegration::init() {
    // TODO: Initialize IDE integration components
    return true;
}

bool IdeIntegration::register_plugin(const std::string& name) {
    // TODO: Implement plugin registration
    return true;
}

std::string IdeIntegration::get_last_error() const {
    return last_error_;
}

} // namespace codegreen
