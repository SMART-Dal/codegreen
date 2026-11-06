#include "../../../include/nemb/core/energy_provider.hpp"
#include <iostream>
#include <map>
#include <mutex>
#include <set>
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

static std::vector<std::string> split(const std::string& s, char sep) {
    std::vector<std::string> out(1);
    for (char c : s) if (c == sep) out.emplace_back(); else out.back() += c;
    return out;
}

namespace {
// Collects what a provider logs while it initializes (its reason when it fails) and passes it on unchanged.
struct LogCapture {
    std::ostringstream log;
    std::streambuf* prev;
    LogCapture() : prev(std::cerr.rdbuf(log.rdbuf())) {}
    ~LogCapture() { std::cerr.rdbuf(prev); std::cerr << log.str(); }
    std::string last_line() const {
        std::string line, last;
        for (std::istringstream in(log.str()); std::getline(in, line);)
            if (line.find_first_not_of(" \t") != std::string::npos) last = line.substr(line.find_first_not_of(" \t"));
        return last;
    }
};
}  // namespace

std::map<std::string, std::unique_ptr<EnergyProvider>> detect_available_providers(std::vector<ProviderOutcome>* outcomes) {
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
    std::map<std::string, std::string> readers;  // counter_group -> the provider reading it
    std::string missing;
    auto record = [&](const std::string& name, const char* status, const std::string& group, const std::string& detail) {
        if (outcomes) outcomes->push_back({name, status, group, detail});
    };
    for (const auto& alts : items) {
        bool found = false;
        for (const auto& name : alts) {
            auto provider = EnergyProvider::create(name);
            const std::string group = provider->get_specification().counter_group;
            if (found) {
                record(name, "not_tried", group, "");
                continue;
            }
            found = true;
            const std::string reader = providers.count(name) ? name : group.empty() || !readers.count(group) ? "" : readers[group];
            if (!reader.empty()) {
                std::cerr << "  " << name << " skipped: counter already read by " << reader << std::endl;
                record(name, "counter_already_read", group, reader);
                continue;
            }
            bool ok;
            std::string why;
            {
                LogCapture capture;
                ok = provider->initialize() && provider->self_test();
                why = capture.last_line();
            }
            if (!ok) {
                std::cerr << "  " << name << " unavailable" << std::endl;
                record(name, "unavailable", group, why.empty() ? "initialize or self_test failed; the provider logged no reason" : why);
                found = false;
                continue;
            }
            std::cerr << "  " << name << " initialized" << std::endl;
            record(name, "initialized", group, "");
            if (!group.empty()) readers[group] = name;
            providers[name] = std::move(provider);
        }
        if (strict && !found) {
            std::string item;
            for (const auto& name : alts) item += (item.empty() ? "" : "|") + name;
            missing += (missing.empty() ? "'" : ", '") + item + "'";
        }
    }
    if (!missing.empty()) throw std::runtime_error("CODEGREEN_PROVIDERS: no working provider for " + missing);
    return providers;
}

} // namespace codegreen::nemb
