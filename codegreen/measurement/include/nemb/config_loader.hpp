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
 * Loads configuration from the CodeGreen config file; there is no file-less fallback.
 * Member defaults below apply only to keys missing from that file and equal the bundled config.json.
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
        std::string precision{"high"};
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
        uint32_t measurement_interval_ms{10};
        bool cross_validation{true};
        double cross_validation_threshold{0.05};
        double temporal_alignment_tolerance_ms{0.1};
        uint32_t measurement_buffer_size{100000};
        bool auto_restart_failed_providers{true};
        std::chrono::seconds provider_restart_interval{5};
        uint32_t max_consecutive_failures{5};
        bool real_time_filtering{false};  // EMA power reported next to (never instead of) raw power
    };

    struct NEMBConfig {
        std::string path;  // file the values came from
        bool enabled{true};
        std::string accuracy_mode{"production"};
        AccuracyConfig accuracy;
        TimingConfig timing;
        CoordinatorConfig coordinator;
        std::map<std::string, ProviderConfig> providers;
        uint32_t max_checkpoints{2000000};  // measurement.report.max_checkpoints; markers beyond it are dropped and counted
        std::string rapl_superset_zone{".*(psys|platform).*"};  // measurement.nemb.providers.intel_rapl.superset_zone
        std::string rapl_disjoint_subzone{"dram.*"};           // measurement.nemb.providers.intel_rapl.disjoint_subzone
    };
    
    /**
     * @brief Load NEMB configuration from file
     * @param config_path Path to config file (empty: find_config_file())
     * @return Parsed configuration
     * @throws std::runtime_error when no file is found, or naming the path when it cannot be read or parsed
     */
    static NEMBConfig load_config(const std::string& config_path = "");
    
    /**
     * @brief Config file the loader resolves: $CODEGREEN_CONFIG (must exist, else throws), then the
     * bundled config.json next to this library (<libdir>/../config.json, ../codegreen/config.json,
     * ../share/codegreen/config.json);
     * empty when none exists (load_config then throws).
     */
    static std::string find_config_file();

private:
    static NEMBConfig parse_json_config(const std::string& json_content);
};

} // namespace codegreen::nemb