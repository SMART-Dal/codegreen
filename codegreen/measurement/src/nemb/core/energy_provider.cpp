#include "../../../include/nemb/core/energy_provider.hpp"
#include <iostream>
#include <map>
#include <mutex>
#include <vector>
#include <functional>

namespace codegreen::nemb {

// Registry implementation
namespace {
    struct ProviderRegistry {
        std::map<std::string, EnergyProvider::ProviderFactory> factories;
        std::mutex mutex;
        
        static ProviderRegistry& instance() {
            static ProviderRegistry instance;
            return instance;
        }
    };
}

void EnergyProvider::register_provider(const std::string& name, ProviderFactory factory) {
    auto& registry = ProviderRegistry::instance();
    std::lock_guard<std::mutex> lock(registry.mutex);
    registry.factories[name] = factory;
}

std::unique_ptr<EnergyProvider> EnergyProvider::create(const std::string& name) {
    auto& registry = ProviderRegistry::instance();
    std::lock_guard<std::mutex> lock(registry.mutex);
    
    auto it = registry.factories.find(name);
    if (it != registry.factories.end()) {
        return it->second();
    }
    return nullptr;
}

std::vector<std::string> EnergyProvider::get_registered_providers() {
    auto& registry = ProviderRegistry::instance();
    std::lock_guard<std::mutex> lock(registry.mutex);
    
    std::vector<std::string> names;
    for (const auto& [name, _] : registry.factories) {
        names.push_back(name);
    }
    return names;
}

// Factory function implementation (legacy wrapper)
std::unique_ptr<EnergyProvider> create_energy_provider(const std::string& provider_type) {
    // Try strict match first
    auto provider = EnergyProvider::create(provider_type);
    if (provider) return provider;
    
    // Try aliases
    if (provider_type == "nvidia_nvml") return EnergyProvider::create("nvidia_gpu");
    if (provider_type == "amd_rocm_smi") return EnergyProvider::create("amd_gpu");
    if (provider_type == "arm_energy") return EnergyProvider::create("arm_eas");
    if (provider_type == "amd_cpu") return EnergyProvider::create("amd_rapl");
    
    std::cerr << "Unknown energy provider type: " << provider_type << std::endl;
    return nullptr;
}

std::vector<std::unique_ptr<EnergyProvider>> detect_available_providers() {
    std::vector<std::unique_ptr<EnergyProvider>> providers;

    std::cout << "Detecting available energy providers..." << std::endl;

    auto registered = EnergyProvider::get_registered_providers();
    for (const auto& name : registered) {
        auto provider = EnergyProvider::create(name);
        if (!provider) continue;
        if (provider->initialize()) {
            std::cout << "  " << provider->get_name() << " initialized" << std::endl;
            providers.push_back(std::move(provider));
        }
    }

    if (providers.empty()) {
        std::cout << "  No energy providers available" << std::endl;
    } else {
        std::cout << "  Successfully initialized " << providers.size() << " energy provider(s)" << std::endl;
    }
    
    return providers;
}

} // namespace codegreen::nemb
