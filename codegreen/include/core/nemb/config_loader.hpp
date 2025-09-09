#pragma once

#include <string>
#include <map>
#include <vector>
#include <optional>
#include <chrono>

namespace codegreen::nemb {

/**
 * @brief Configuration loader for NEMB settings
 * 
 * Loads configuration from CodeGreen config file with fallback to defaults.
 * Optimized for accuracy-first operation with minimal measurement noise.
 */
class ConfigLoader {
public:
    struct AccuracyConfig {
        double target_uncertainty_percent{1.0};
        bool measurement_validation{true};
        bool outlier_detection{true};
        std::string noise_filtering{"adaptive"};
        bool statistical_validation{true};
        double confidence_threshold{0.95};
        
        // System noise minimization
        bool minimize_io_during_measurement{true};
        bool minimize_system_noise{true};
        bool memory_prefaulting{true};
        std::string cpu_affinity{"auto"};
        bool disable_frequency_scaling{false};
    };
    
    struct TimingConfig {
        std::string precision{"maximum"};
        std::string clock_source{"auto"};
        std::string sync_method{"tsc"};
        uint32_t calibration_samples{100};
    };
    
    struct ProviderConfig {
        bool enabled{true};
        std::string access_method{"auto"};
        bool validation_enabled{true};
        std::map<std::string, std::string> specific_settings;
    };
    
    struct CoordinatorConfig {
        bool cross_validation{true};
        double cross_validation_threshold{0.05};
        double temporal_alignment_tolerance_ms{0.1};
        uint32_t measurement_buffer_size{1000};
        bool auto_restart_failed_providers{true};
        std::chrono::seconds provider_restart_interval{30};
    };
    
    struct NEMBConfig {
        bool enabled{true};
        std::string accuracy_mode{"production"};
        AccuracyConfig accuracy;
        TimingConfig timing;
        CoordinatorConfig coordinator;
        std::map<std::string, ProviderConfig> providers;
    };
    
    /**
     * @brief Load NEMB configuration from file
     * @param config_path Path to config file (empty for default)
     * @return Parsed configuration
     */
    static NEMBConfig load_config(const std::string& config_path = "");
    
    /**
     * @brief Get default configuration for maximum accuracy
     * @return Default accuracy-optimized configuration
     */
    static NEMBConfig get_accuracy_optimized_config();
    
    /**
     * @brief Get default configuration for minimal overhead
     * @return Default performance-optimized configuration
     */
    static NEMBConfig get_performance_optimized_config();
    
private:
    static std::string find_config_file();
    static NEMBConfig parse_json_config(const std::string& json_content);
    static std::string get_default_config_path();
};

} // namespace codegreen::nemb