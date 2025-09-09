#pragma once

#include <memory>
#include <string>
#include <vector>
#include <chrono>
#include <atomic>
#include <map>
#include <optional>

namespace codegreen::nemb {

/**
 * @brief Energy measurement reading with comprehensive metadata
 * 
 * Contains all energy/power data plus hardware context and quality metrics
 * for production-grade energy analysis.
 */
struct EnergyReading {
    // Temporal Information
    uint64_t timestamp_ns{0};                          ///< Nanosecond precision timestamp
    std::chrono::steady_clock::time_point system_time; ///< System clock reference
    
    // Energy and Power Data  
    double energy_joules{0.0};                         ///< Cumulative energy consumption
    double instantaneous_power_watts{0.0};             ///< Current power draw
    double average_power_watts{0.0};                   ///< Average power since last reading
    
    // Hardware State Context
    uint32_t cpu_frequency_mhz{0};                     ///< Current CPU/GPU frequency
    double temperature_celsius{0.0};                   ///< Die/junction temperature
    uint8_t power_state{0};                            ///< P-state, C-state information
    
    // Measurement Quality Metrics
    double measurement_uncertainty{0.0};               ///< Statistical uncertainty (0-1)
    uint32_t sample_count{1};                          ///< Samples averaged for this reading
    std::string source_type;                           ///< Hardware component source
    std::string provider_id;                           ///< Unique provider identifier
    
    // CRITICAL: Per-domain measurements - preserve detailed energy breakdown
    std::map<std::string, double> domain_energy_joules; ///< Energy per domain (package, core, dram, etc.)
    std::map<std::string, double> domain_power_watts;   ///< Power per domain
    std::optional<std::string> component_name;          ///< Specific component identifier
    
    // Validation Flags
    bool counter_wrapped{false};                       ///< Counter overflow detected
    bool temperature_valid{false};                     ///< Temperature reading valid
    bool frequency_valid{false};                       ///< Frequency reading valid
    
    // Additional metadata for advanced analysis
    double power_limit_watts{0.0};                     ///< Hardware power limit
    double utilization_percent{0.0};                   ///< Component utilization
    uint64_t memory_used_bytes{0};                     ///< Memory usage (for GPU)
    uint64_t memory_total_bytes{0};                    ///< Total memory (for GPU)
    
    // Quality metrics per measurement
    double confidence{1.0};                            ///< Measurement confidence (0-1)
    double uncertainty_percent{0.0};                   ///< Measurement uncertainty percentage
};

/**
 * @brief Hardware energy provider specification
 * 
 * Describes the capabilities and limitations of an energy measurement provider.
 */
struct EnergyProviderSpec {
    // Provider identification
    std::string hardware_type;                         ///< "cpu", "gpu", "memory", "system"
    std::string vendor;                                ///< "intel", "amd", "nvidia", "arm"
    std::string model;                                 ///< Specific hardware model
    std::string provider_name;                         ///< Human-readable provider name
    
    // Measurement capabilities - CRITICAL: preserve domain information
    std::vector<std::string> measurement_domains;      ///< Available measurement domains (package, core, dram, etc.)
    double energy_resolution_joules{0.0};             ///< Minimum measurable energy (queried from hardware)
    double power_resolution_watts{0.0};               ///< Minimum measurable power (queried from hardware)  
    std::chrono::microseconds update_interval{1000};   ///< Hardware update frequency
    uint32_t counter_bits{32};                        ///< Counter width for wraparound handling
    
    // Advanced capabilities
    bool supports_temperature{false};                  ///< Temperature monitoring available
    bool supports_frequency{false};                    ///< Frequency monitoring available
    bool supports_power_limiting{false};               ///< Power capping support
    bool supports_per_core_measurement{false};         ///< Per-core energy breakdown
    
    // Performance characteristics
    double max_measurement_frequency_hz{1000.0};       ///< Maximum sampling rate
    std::chrono::microseconds min_measurement_interval{1000}; ///< Minimum time between readings
    double typical_accuracy_percent{5.0};              ///< Typical measurement accuracy
    double measurement_overhead_percent{0.1};          ///< Overhead of taking measurements
    
    // Hardware-specific metadata
    std::map<std::string, std::string> hardware_info;  ///< Additional hardware details
    std::vector<std::string> supported_metrics;        ///< List of available metrics beyond energy
};

/**
 * @brief Abstract base class for all energy measurement providers
 * 
 * Defines the interface that all hardware-specific energy providers must implement.
 * Provides common functionality for validation, error handling, and statistics.
 */
class EnergyProvider {
public:
    virtual ~EnergyProvider() = default;
    
    /**
     * @brief Initialize the energy provider
     * @return true if initialization successful
     */
    virtual bool initialize() = 0;
    
    /**
     * @brief Get current energy reading
     * @return EnergyReading structure with current measurement data
     */
    virtual EnergyReading get_reading() = 0;
    
    /**
     * @brief Get provider specification and capabilities
     * @return EnergyProviderSpec describing this provider
     */
    virtual EnergyProviderSpec get_specification() const = 0;
    
    /**
     * @brief Perform self-test and validation
     * @return true if provider passes all self-tests
     */
    virtual bool self_test() = 0;
    
    /**
     * @brief Check if provider is currently functional
     * @return true if provider can provide measurements
     */
    virtual bool is_available() const = 0;
    
    /**
     * @brief Shutdown and cleanup provider resources
     */
    virtual void shutdown() = 0;
    
    /**
     * @brief Get human-readable provider name
     * @return Provider name string
     */
    virtual std::string get_name() const = 0;
    
    // Statistics and diagnostics
    uint64_t get_total_measurements() const { return total_measurements_.load(); }
    uint64_t get_failed_measurements() const { return failed_measurements_.load(); }
    double get_success_rate() const {
        uint64_t total = total_measurements_.load();
        return (total > 0) ? (1.0 - static_cast<double>(failed_measurements_.load()) / total) : 0.0;
    }
    
protected:
    // Statistics tracking
    mutable std::atomic<uint64_t> total_measurements_{0};
    mutable std::atomic<uint64_t> failed_measurements_{0};
    
    // Helper method for derived classes to update statistics
    void record_measurement_attempt(bool success) {
        total_measurements_.fetch_add(1);
        if (!success) {
            failed_measurements_.fetch_add(1);
        }
    }
};

/**
 * @brief Factory function for creating energy providers
 * @param provider_type Type of provider to create ("intel_rapl", "nvidia_nvml", etc.)
 * @return Unique pointer to created provider, or nullptr if creation failed
 */
std::unique_ptr<EnergyProvider> create_energy_provider(const std::string& provider_type);

/**
 * @brief Auto-detect and create all available energy providers
 * @return Vector of all successfully initialized providers
 */
std::vector<std::unique_ptr<EnergyProvider>> detect_available_providers();

} // namespace codegreen::nemb