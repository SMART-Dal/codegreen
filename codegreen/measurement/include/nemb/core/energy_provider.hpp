#pragma once

#include <memory>
#include <string>
#include <vector>
#include <chrono>
#include <atomic>
#include <map>
#include <functional>
#include <optional>
#include <cstdint>

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
    std::chrono::microseconds update_interval{0};      ///< Hardware update period of the energy value; 0 = unknown
    uint32_t counter_bits{32};                        ///< Counter width for wraparound handling
    std::string energy_source{"counter"};             ///< "counter" (hardware cumulative energy) | "integrated_power" (power samples integrated in software)
    std::string boundary_source;                      ///< energy_source of get_boundary_reading(); empty = energy_source
    std::string counter_group;                        ///< Providers reading the same physical counter share a group; detection keeps one per group
    
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

/** @brief Energy of a provider's boundary counter and of its power integral over the same span (first to last counter
 *  read), and the counter reads in it. */
struct CounterCheck {
    double counter_j{0}, integral_j{0};
    uint64_t span_ns{0}, reads{0};
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
     * @brief Reading at a session boundary (start/stop); the sampler and one-shot reads use get_reading().
     * A provider whose hardware keeps a cumulative counter that sampling would disturb reads it only here
     * (spec boundary_source); its cumulative values are then comparable only with other boundary readings.
     * shared: another session is open across this read. A counter read would discard energy of that session, so such a
     * provider answers from its last counter read plus its power integral since (energy_source over the read).
     */
    virtual EnergyReading get_boundary_reading(bool shared) { (void)shared; return get_reading(); }

    /**
     * @brief Per domain, a provider with both a boundary counter and a power integral reports their energies over the
     * same span; another reader of the counter makes them diverge. Empty for a provider with one energy source.
     */
    virtual std::map<std::string, CounterCheck> counter_checks() const { return {}; }

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
    /** @brief Device reads for which the provider kept a held value instead of a fresh hardware value (failed reads). */
    uint64_t get_held_readings() const { return held_readings_.load(); }
    /** @brief Boundary device reads answered with the previous boundary read (a fresh read would discard energy),
     *  and the longest time span one such answer covered. */
    uint64_t get_boundary_held() const { return boundary_held_.load(); }
    uint64_t get_boundary_held_max_ns() const { return boundary_held_max_ns_.load(); }
    /** @brief Consecutive failed reads after which a provider or one of its devices is treated as lost. */
    void set_max_consecutive_failures(uint32_t n) { max_consecutive_failures_.store(n); }
    uint32_t max_consecutive_failures() const { return max_consecutive_failures_.load(); }

    // Factory registration
    using ProviderFactory = std::function<std::unique_ptr<EnergyProvider>()>;
    
    static void register_provider(const std::string& name, ProviderFactory factory);
    static std::unique_ptr<EnergyProvider> create(const std::string& name);
    static std::vector<std::string> get_registered_providers();
    
protected:
    // Statistics tracking
    mutable std::atomic<uint64_t> total_measurements_{0};
    mutable std::atomic<uint64_t> failed_measurements_{0};
    std::atomic<uint64_t> held_readings_{0};
    std::atomic<uint64_t> boundary_held_{0}, boundary_held_max_ns_{0};
    std::atomic<uint32_t> max_consecutive_failures_{5};

    void record_boundary_hold(uint64_t span_ns) {
        boundary_held_++;
        for (uint64_t c = boundary_held_max_ns_.load(); span_ns > c && !boundary_held_max_ns_.compare_exchange_weak(c, span_ns);) {}
    }

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

/** @brief What detect_available_providers did with one provider it was asked for. */
struct ProviderOutcome {
    std::string name;
    std::string status;         ///< initialized | unavailable | counter_already_read | not_tried (an earlier alternative is used)
    std::string counter_group;
    std::string detail;         ///< unavailable: the provider's last log line; counter_already_read: the provider reading it
};

/**
 * @brief Create, initialize and self-test energy providers, keyed by registry name.
 * CODEGREEN_PROVIDERS (the only place it is read) is a comma-separated list of items, each a
 * registry name or alternatives `a|b` (the first that initializes and self-tests is used); it
 * makes unknown names and empty names throw, and items with no working alternative throw after
 * every item was tried. Unset: every registered provider that works. Either way only the first
 * working provider of each EnergyProviderSpec::counter_group is kept. outcomes, when given,
 * receives one entry per provider named (or registered), in selection order.
 */
std::map<std::string, std::unique_ptr<EnergyProvider>> detect_available_providers(std::vector<ProviderOutcome>* outcomes = nullptr);

/**
 * @brief Integrates per-device power samples into cumulative joules (trapezoid rule).
 * A missed sample keeps the device's cumulative value (held); the next good sample integrates
 * across the gap. A device with more than max_misses consecutive misses is lost for good and
 * lost_devices() becomes non-zero. Not locked: the owning provider serializes all calls.
 */
class PowerIntegrator {
public:
    explicit PowerIntegrator(size_t devices = 0) : dev_(devices) {}
    /** @brief watts empty = failed read. Returns true when the device's value was held. */
    bool add(size_t i, std::optional<double> watts, uint64_t t_ns, uint32_t max_misses) {
        Device& d = dev_.at(i);
        if (!watts) {
            if (++d.misses > max_misses && !d.lost) { d.lost = true; ++lost_; }
            return true;
        }
        if (d.t_ns) d.joules += 0.5 * (d.watts + *watts) * static_cast<double>(t_ns - d.t_ns) / 1e9;
        d.watts = *watts;
        d.t_ns = t_ns;
        d.misses = 0;
        return false;
    }
    double joules(size_t i) const { return dev_.at(i).joules; }
    uint32_t lost_devices() const { return lost_; }
    void reset() { for (auto& d : dev_) d = Device{}; lost_ = 0; }
private:
    struct Device { double joules{0}, watts{0}; uint64_t t_ns{0}; uint32_t misses{0}; bool lost{false}; };
    std::vector<Device> dev_;
    uint32_t lost_{0};
};

} // namespace codegreen::nemb