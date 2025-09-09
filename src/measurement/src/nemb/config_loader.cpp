#include "nemb/config_loader.hpp"

#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <cstdlib>

// Simple JSON parser (minimal dependency approach)
#include <sstream>
#include <unordered_map>

namespace codegreen::nemb {

namespace {
    // Simplified config parsing without recursive JSON structures
    std::map<std::string, std::string> parse_simple_config(const std::string& content) {
        std::map<std::string, std::string> config;
        std::istringstream stream(content);
        std::string line;
        
        while (std::getline(stream, line)) {
            // Skip comments and empty lines
            line.erase(0, line.find_first_not_of(" \t"));
            if (line.empty() || line[0] == '/' || line[0] == '#' || line[0] == '{' || line[0] == '}') continue;
            
            // Simple key-value parsing
            size_t colon = line.find(':');
            if (colon == std::string::npos) continue;
            
            std::string key = line.substr(0, colon);
            std::string value = line.substr(colon + 1);
            
            // Clean up key and value
            key.erase(0, key.find_first_not_of(" \t\""));
            key.erase(key.find_last_not_of(" \t\",") + 1);
            value.erase(0, value.find_first_not_of(" \t\""));
            value.erase(value.find_last_not_of(" \t\",") + 1);
            
            config[key] = value;
        }
        
        return config;
    }
    
    std::string expand_path(const std::string& path) {
        std::string expanded = path;
        
        // Expand environment variables
        size_t pos = 0;
        while ((pos = expanded.find("${", pos)) != std::string::npos) {
            size_t end = expanded.find("}", pos);
            if (end == std::string::npos) break;
            
            std::string var_name = expanded.substr(pos + 2, end - pos - 2);
            const char* env_value = std::getenv(var_name.c_str());
            
            std::string replacement;
            if (env_value) {
                replacement = env_value;
            } else if (var_name == "EXECUTABLE_DIR") {
                // Fallback for executable directory
                replacement = std::filesystem::current_path();
            } else if (var_name == "USER_HOME") {
                const char* home = std::getenv("HOME");
                replacement = home ? home : "/tmp";
            } else if (var_name == "SYSTEM_TEMP") {
                replacement = "/tmp";
            }
            
            expanded.replace(pos, end - pos + 1, replacement);
            pos += replacement.length();
        }
        
        return expanded;
    }
}

std::string ConfigLoader::find_config_file() {
    std::vector<std::string> search_paths = {
        "./config/codegreen.json",
        "./codegreen.json",
        std::string(std::getenv("HOME") ? std::getenv("HOME") : "/tmp") + "/.codegreen/config.json",
        "/etc/codegreen/config.json"
    };
    
    for (const auto& path : search_paths) {
        if (std::filesystem::exists(path)) {
            return path;
        }
    }
    
    return "";
}

std::string ConfigLoader::get_default_config_path() {
    return "./config/codegreen.json";
}

ConfigLoader::NEMBConfig ConfigLoader::parse_json_config(const std::string& json_content) {
    NEMBConfig config;
    
    try {
        // Use simplified config parsing
        auto parsed_config = parse_simple_config(json_content);
        
        // Set accuracy-optimized defaults
        config.enabled = true;
        config.accuracy_mode = "production";
        
        // Accuracy configuration
        config.accuracy.target_uncertainty_percent = 1.0;
        config.accuracy.measurement_validation = true;
        config.accuracy.outlier_detection = true;
        config.accuracy.noise_filtering = "adaptive";
        config.accuracy.statistical_validation = true;
        config.accuracy.confidence_threshold = 0.95;
        config.accuracy.minimize_io_during_measurement = true;
        config.accuracy.minimize_system_noise = true;
        config.accuracy.memory_prefaulting = true;
        config.accuracy.cpu_affinity = "auto";
        config.accuracy.disable_frequency_scaling = false;
        
        // Timing configuration
        config.timing.precision = "maximum";
        config.timing.clock_source = "auto";
        config.timing.sync_method = "tsc";
        config.timing.calibration_samples = 100;
        
        // Coordinator configuration
        config.coordinator.cross_validation = true;
        config.coordinator.cross_validation_threshold = 0.05;
        config.coordinator.temporal_alignment_tolerance_ms = 0.1;
        config.coordinator.measurement_buffer_size = 1000;
        config.coordinator.auto_restart_failed_providers = true;
        config.coordinator.provider_restart_interval = std::chrono::seconds(30);
        
        // Provider configurations
        ProviderConfig intel_rapl;
        intel_rapl.enabled = true;
        intel_rapl.access_method = "auto";
        intel_rapl.validation_enabled = true;
        config.providers["intel_rapl"] = intel_rapl;
        
        ProviderConfig nvidia_gpu;
        nvidia_gpu.enabled = true;
        nvidia_gpu.access_method = "auto";  
        nvidia_gpu.validation_enabled = true;
        config.providers["nvidia_gpu"] = nvidia_gpu;
        
        ProviderConfig amd_cpu;
        amd_cpu.enabled = true;
        amd_cpu.access_method = "auto";
        amd_cpu.validation_enabled = true;
        config.providers["amd_cpu"] = amd_cpu;
        
    } catch (const std::exception& e) {
        // Fall back to defaults if parsing fails
        return get_accuracy_optimized_config();
    }
    
    return config;
}

ConfigLoader::NEMBConfig ConfigLoader::load_config(const std::string& config_path) {
    std::string path_to_use = config_path;
    if (path_to_use.empty()) {
        path_to_use = find_config_file();
        if (path_to_use.empty()) {
            // No config file found, use accuracy-optimized defaults
            return get_accuracy_optimized_config();
        }
    }
    
    try {
        std::ifstream file(path_to_use);
        if (!file.is_open()) {
            return get_accuracy_optimized_config();
        }
        
        std::string content((std::istreambuf_iterator<char>(file)),
                           std::istreambuf_iterator<char>());
        file.close();
        
        return parse_json_config(content);
        
    } catch (const std::exception& e) {
        // Fall back to defaults on any error
        return get_accuracy_optimized_config();
    }
}

ConfigLoader::NEMBConfig ConfigLoader::get_accuracy_optimized_config() {
    NEMBConfig config;
    
    config.enabled = true;
    config.accuracy_mode = "production";
    
    // Maximum accuracy settings
    config.accuracy.target_uncertainty_percent = 0.5;
    config.accuracy.measurement_validation = true;
    config.accuracy.outlier_detection = true;
    config.accuracy.noise_filtering = "adaptive";
    config.accuracy.statistical_validation = true;
    config.accuracy.confidence_threshold = 0.99;
    config.accuracy.minimize_io_during_measurement = true;
    config.accuracy.minimize_system_noise = true;
    config.accuracy.memory_prefaulting = true;
    config.accuracy.cpu_affinity = "auto";
    config.accuracy.disable_frequency_scaling = false;
    
    // High precision timing
    config.timing.precision = "maximum";
    config.timing.clock_source = "tsc";
    config.timing.sync_method = "tsc";
    config.timing.calibration_samples = 1000;
    
    // Strict coordination
    config.coordinator.cross_validation = true;
    config.coordinator.cross_validation_threshold = 0.02;
    config.coordinator.temporal_alignment_tolerance_ms = 0.05;
    config.coordinator.measurement_buffer_size = 2000;
    config.coordinator.auto_restart_failed_providers = true;
    config.coordinator.provider_restart_interval = std::chrono::seconds(10);
    
    // Enable all providers with validation
    ProviderConfig provider_default;
    provider_default.enabled = true;
    provider_default.access_method = "auto";
    provider_default.validation_enabled = true;
    
    config.providers["intel_rapl"] = provider_default;
    config.providers["nvidia_gpu"] = provider_default;
    config.providers["amd_cpu"] = provider_default;
    
    return config;
}

ConfigLoader::NEMBConfig ConfigLoader::get_performance_optimized_config() {
    NEMBConfig config;
    
    config.enabled = true;
    config.accuracy_mode = "performance";
    
    // Balanced accuracy/performance settings
    config.accuracy.target_uncertainty_percent = 2.0;
    config.accuracy.measurement_validation = true;
    config.accuracy.outlier_detection = false;  // Disabled for performance
    config.accuracy.noise_filtering = "basic";
    config.accuracy.statistical_validation = false;  // Disabled for performance
    config.accuracy.confidence_threshold = 0.90;
    config.accuracy.minimize_io_during_measurement = false;
    config.accuracy.minimize_system_noise = false;
    config.accuracy.memory_prefaulting = false;
    config.accuracy.cpu_affinity = "none";
    config.accuracy.disable_frequency_scaling = false;
    
    // Standard precision timing
    config.timing.precision = "standard";
    config.timing.clock_source = "auto";
    config.timing.sync_method = "posix";
    config.timing.calibration_samples = 50;
    
    // Relaxed coordination
    config.coordinator.cross_validation = false;  // Disabled for performance
    config.coordinator.cross_validation_threshold = 0.10;
    config.coordinator.temporal_alignment_tolerance_ms = 1.0;
    config.coordinator.measurement_buffer_size = 100;
    config.coordinator.auto_restart_failed_providers = false;
    config.coordinator.provider_restart_interval = std::chrono::seconds(60);
    
    // Fewer providers for performance
    ProviderConfig provider_basic;
    provider_basic.enabled = true;
    provider_basic.access_method = "auto";
    provider_basic.validation_enabled = false;  // Disabled for performance
    
    config.providers["intel_rapl"] = provider_basic;
    
    return config;
}

} // namespace codegreen::nemb