#include "../../../include/nemb/core/energy_provider.hpp"
#include <iostream>
#include <map>
#include <mutex>
#include <set>
#include <vector>
#include <functional>
#include <algorithm>
#include <cstdlib>
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

static std::vector<std::string> split(const std::string& s, char sep) {
    std::vector<std::string> out(1);
    for (char c : s) if (c == sep) out.emplace_back(); else out.back() += c;
    return out;
}

std::map<std::string, std::unique_ptr<EnergyProvider>> detect_available_providers() {
    const char* env = std::getenv("CODEGREEN_PROVIDERS");
    const bool strict = env && *env;
    const auto registered = EnergyProvider::get_registered_providers();
    std::vector<std::vector<std::string>> items;
    if (strict) {
        for (const auto& item : split(env, ',')) {
            items.push_back(split(item, '|'));
            for (const auto& name : items.back()) {
                if (name.empty()) throw std::runtime_error(std::string("CODEGREEN_PROVIDERS: empty provider name in '") + env + "'");
                if (std::find(registered.begin(), registered.end(), name) == registered.end())
                    throw std::runtime_error("CODEGREEN_PROVIDERS: unknown provider '" + name + "'");
            }
        }
    } else {
        for (const auto& name : registered) items.push_back({name});
    }
    std::map<std::string, std::unique_ptr<EnergyProvider>> providers;
    std::set<std::string> groups;
    for (const auto& alts : items) {
        bool found = false;
        for (const auto& name : alts) {
            auto provider = EnergyProvider::create(name);
            const std::string group = provider->get_specification().counter_group;
            if (providers.count(name) || (!group.empty() && groups.count(group))) {
                std::cerr << "  " << name << " skipped: counter already read by another provider" << std::endl;
                found = true;
                break;
            }
            if (!provider->initialize() || !provider->self_test()) {
                std::cerr << "  " << name << " unavailable" << std::endl;
                continue;
            }
            std::cerr << "  " << name << " initialized" << std::endl;
            if (!group.empty()) groups.insert(group);
            providers[name] = std::move(provider);
            found = true;
            break;
        }
        if (strict && !found) {
            std::string item;
            for (const auto& name : alts) item += (item.empty() ? "" : "|") + name;
            throw std::runtime_error("CODEGREEN_PROVIDERS: no working provider for '" + item + "'");
        }
    }
    return providers;
}

} // namespace codegreen::nemb
