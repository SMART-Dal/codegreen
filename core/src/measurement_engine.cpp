#include "measurement_engine.hpp"
#include "plugin/plugin_registry.hpp"
#include <algorithm>

namespace codegreen {

MeasurementEngine::MeasurementEngine()
    : plugin_registry_(std::make_unique<PluginRegistry>()) {
}

void MeasurementEngine::register_language_adapter(std::unique_ptr<LanguageAdapter> adapter) {
    language_adapters_.push_back(std::move(adapter));
}

const std::vector<std::unique_ptr<LanguageAdapter>>& MeasurementEngine::language_adapters() const {
    return language_adapters_;
}

bool MeasurementEngine::analyze_code(const std::string& source_code, const std::string& language_id) {
    auto it = std::find_if(language_adapters_.begin(), language_adapters_.end(),
        [&language_id](const std::unique_ptr<LanguageAdapter>& adapter) {
            return adapter->get_language_id() == language_id;
        });
    
    if (it != language_adapters_.end()) {
        auto ast = (*it)->parse(source_code);
        // TODO: Implement code analysis logic
        return true;
    }
    
    return false;
}

} // namespace codegreen
