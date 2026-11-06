#include "../../../include/nemb/core/energy_provider.hpp"
#include <iostream>
#include <map>
#include <mutex>
#include <vector>
#include <functional>
#include <algorithm>
#include <cstdlib>
#include <sstream>
#include <stdexcept>

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

// Dedup rule: amd_rapl reads the same package counter (MSR 0xC001029B) that powercap
// exposes as intel_rapl package-0, so amd_rapl is used only when intel_rapl does not initialize.
std::map<std::string, std::unique_ptr<EnergyProvider>> detect_available_providers() {
    std::map<std::string, std::unique_ptr<EnergyProvider>> providers;
    const char* env = std::getenv("CODEGREEN_PROVIDERS");
    bool strict = env && *env;
    std::vector<std::string> names;
    if (strict) {
        std::stringstream ss(env);
        for (std::string n; std::getline(ss, n, ',');) if (!n.empty()) names.push_back(n);
    } else {
        names = EnergyProvider::get_registered_providers();
    }
    std::stable_partition(names.begin(), names.end(), [](const std::string& n) { return n != "amd_rapl"; });
    bool amd_requested = std::find(names.begin(), names.end(), "amd_rapl") != names.end();
    for (const auto& name : names) {
        if (name == "amd_rapl" && providers.count("intel_rapl")) continue;
        auto provider = EnergyProvider::create(name);
        if (!provider) {
            if (strict) throw std::runtime_error("CODEGREEN_PROVIDERS: unknown provider '" + name + "'");
            continue;
        }
        if (!provider->initialize()) {
            if (strict && !(name == "intel_rapl" && amd_requested))
                throw std::runtime_error("CODEGREEN_PROVIDERS: provider '" + name + "' failed to initialize");
            continue;
        }
        std::cerr << "  " << name << " initialized" << std::endl;
        providers[name] = std::move(provider);
    }
    if (strict && providers.empty()) throw std::runtime_error(std::string("CODEGREEN_PROVIDERS: no provider initialized from '") + env + "'");
    return providers;
}

} // namespace codegreen::nemb
