#pragma once

#include "energy_provider.hpp"
#include <memory>
#include <vector>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <thread>
#include <atomic>
#include <condition_variable>
#include <chrono>

namespace codegreen::nemb {

/**
 * @brief Synchronized multi-source energy reading
 * 
 * Contains time-aligned measurements from multiple energy providers
 * with confidence metrics and validation status.
 */
struct SynchronizedReading {
    uint64_t common_timestamp_ns{0};                   ///< Aligned timestamp for all readings
    std::vector<EnergyReading> provider_readings;      ///< Individual provider measurements
    double total_system_power_watts{0.0};             ///< Aggregated system power (raw, never filtered)
    double filtered_system_power_watts{0.0};          ///< EMA of total_system_power_watts; set only when power_filtered
    bool power_filtered{false};                       ///< real-time filtering was on for this reading
    double total_system_energy_joules{0.0};           ///< Aggregated system energy
    double measurement_confidence{0.0};               ///< Overall confidence (0-1)
    
    // Quality metrics
    uint32_t providers_active{0};                      ///< Number of active providers
    uint32_t providers_failed{0};                     ///< Number of failed providers
    bool temporal_alignment_valid{true};               ///< Time alignment succeeded
    double max_provider_uncertainty{0.0};             ///< Worst provider uncertainty
    
    // Cross-validation results
    bool cross_validation_passed{true};               ///< Provider readings are consistent
    double max_provider_deviation{0.0};               ///< Maximum deviation between providers
};

/**
 * @brief Configuration for measurement coordination
 */
struct CoordinatorConfig {
    std::chrono::milliseconds measurement_interval{10};  ///< Target measurement interval
    double temporal_alignment_tolerance_ms{1.0};         ///< Time alignment tolerance
    double cross_validation_threshold{0.1};              ///< 10% deviation threshold
    bool enable_real_time_filtering{false};              ///< Add an EMA power next to the raw power (never replaces it)
    bool enable_outlier_detection{true};                 ///< Remove measurement outliers
    uint32_t measurement_buffer_size{1000};              ///< Circular buffer size
    bool auto_restart_failed_providers{true};            ///< Restart failed providers
    std::chrono::seconds provider_restart_interval{30};  ///< How often to retry failed providers
    uint32_t max_consecutive_failures{5};                ///< Failed reads (or devices' failed reads) before a provider/device is lost
};

/**
 * @brief Central coordinator for multi-source energy measurements
 * 
 * Manages multiple energy providers, synchronizes their measurements,
 * performs cross-validation, and provides unified energy readings.
 * 
 * Key responsibilities:
 * - Multi-source measurement synchronization
 * - Temporal alignment of measurements with different update rates
 * - Cross-validation between providers
 * - Real-time noise filtering and outlier detection
 * - Automatic failover and provider management
 */
class MeasurementCoordinator {
public:
    explicit MeasurementCoordinator(const CoordinatorConfig& config = CoordinatorConfig{});
    ~MeasurementCoordinator();
    
    // Core functionality
    
    /**
     * @brief Add an initialized, self-tested provider (detect_available_providers does both)
     * @param provider Unique pointer to energy provider
     * @param name Key for the provider (registry name); empty = provider->get_name()
     * @return true if the provider is available and was added before start_measurements()
     */
    bool add_provider(std::unique_ptr<EnergyProvider> provider, const std::string& name = "");
    
    /**
     * @brief Remove a provider by name
     * @param provider_name Name of provider to remove
     * @return true if provider was found and removed
     */
    bool remove_provider(const std::string& provider_name);
    
    /**
     * @brief Start coordinated measurements
     * @return true if measurement system started successfully
     */
    bool start_measurements();
    
    /**
     * @brief Stop coordinated measurements
     */
    void stop_measurements();
    
    /**
     * @brief Get current synchronized reading from all providers (boundary: their get_boundary_reading)
     * @return SynchronizedReading with aligned measurements
     */
    SynchronizedReading get_synchronized_reading(bool boundary = false);

    /**
     * @brief Take one sampler reading now. A reading with a failed provider is counted in
     * rejected_readings() and in that provider's rejected count; returns false then.
     */
    bool sample_now(SynchronizedReading& out);
    
    /**
     * @brief Get time-aligned measurements over a specific duration
     * @param duration Duration to collect measurements
     * @return Vector of synchronized readings
     */
    std::vector<SynchronizedReading> collect_measurements_for_duration(
        std::chrono::milliseconds duration);
    
    // Provider management
    
    /**
     * @brief Get list of active provider names
     * @return Vector of provider names currently active
     */
    std::vector<std::string> get_active_providers() const;
    
    /**
     * @brief Get list of failed provider names
     * @return Vector of provider names currently failed
     */
    std::vector<std::string> get_failed_providers() const;
    
    /**
     * @brief Get provider specifications
     * @return Map of provider name to specification
     */
    std::map<std::string, EnergyProviderSpec> get_provider_specifications() const;
    
    /**
     * @brief Manually restart a failed provider
     * @param provider_name Name of provider to restart
     * @return true if restart was successful
     */
    bool restart_provider(const std::string& provider_name);
    
    /**
     * @brief Get all currently buffered readings
     * @return Vector of synchronized readings in chronological order
     */
    std::vector<SynchronizedReading> get_buffered_readings() const;
    
    /**
     * @brief Resize the circular buffer, keeping the newest readings in order. Readings that no
     * longer fit are dropped and reported through buffer_wrapped(). Returns false for size 0.
     */
    bool set_buffer_size(size_t size);

    /**
     * @brief Set the sampling interval at runtime (safe while sampling).
     * @param interval_ms New interval in milliseconds; clamped to [1, 60000]
     */
    void set_measurement_interval_ms(int interval_ms);

    /** @brief Per-provider counts keyed by provider name; inputs for the sampler report. */
    struct ProviderCounts {
        uint64_t rejected{0};   ///< sampler readings rejected because this provider's read failed
        uint64_t held{0};       ///< device reads the provider answered with a held value
        uint64_t boundary_held{0}, boundary_held_max_ns{0};  ///< boundary reads answered from the previous one; longest span
        uint64_t restarts{0};   ///< re-initializations; each is a discontinuity in its cumulative energy
    };
    std::map<std::string, ProviderCounts> provider_counts() const;

    // Statistics and diagnostics
    
    /**
     * @brief Get measurement statistics
     */
    struct CoordinatorStatistics {
        uint64_t total_synchronized_readings{0};
        uint64_t failed_synchronizations{0};
        double average_measurement_latency_ms{0.0};
        double average_temporal_alignment_error_ms{0.0};
        uint32_t cross_validation_failures{0};
        std::map<std::string, uint64_t> provider_success_counts;
        std::map<std::string, uint64_t> provider_failure_counts;
    };
    
    CoordinatorStatistics get_statistics() const;
    
    /**
     * @brief Reset all statistics counters
     */
    void reset_statistics();
    
    /**
     * @brief Check if coordinator is running
     * @return true if measurement coordination is active
     */
    bool is_running() const { return running_.load(); }

    /** @brief True once the ring buffer has overwritten its oldest reading. */
    bool buffer_wrapped() const { return buffer_full_.load(); }
    /** @brief Sampler readings not buffered because a provider failed. */
    uint64_t rejected_readings() const { return rejected_readings_.load(); }
    std::chrono::milliseconds measurement_interval() const { return std::chrono::milliseconds(interval_ms_.load()); }
    /** @brief Smallest and largest sampling interval in effect since start_measurements(). */
    int64_t interval_ms_min() const { return interval_ms_min_.load(); }
    int64_t interval_ms_max() const { return interval_ms_max_.load(); }
    uint32_t buffer_capacity() const { std::lock_guard<std::mutex> l(readings_mutex_); return config_.measurement_buffer_size; }
    /** @brief CPUs in the process affinity mask and in the sampler thread's mask, captured at start (-1 unreadable). */
    int affinity_cpus() const { return affinity_cpus_.load(); }
    int sampler_affinity_cpus() const { return sampler_affinity_cpus_.load(); }

private:
    // Configuration
    CoordinatorConfig config_;
    
    // Provider management
    struct ProviderState {
        std::unique_ptr<EnergyProvider> provider;
        bool active{false};
        bool failed{false};
        std::chrono::steady_clock::time_point last_successful_reading;
        std::chrono::steady_clock::time_point last_restart_attempt;
        uint32_t consecutive_failures{0};
        uint64_t rejected{0};
        uint64_t restarts{0};
        EnergyReading last_reading;
    };
    
    std::map<std::string, ProviderState> providers_;
    mutable std::shared_mutex providers_mutex_;
    
    // Measurement coordination
    std::atomic<bool> running_{false};
    std::thread measurement_thread_;
    std::thread provider_health_thread_;
    
    // Synchronization and buffering
    mutable std::mutex readings_mutex_;
    std::condition_variable readings_condition_;
    std::vector<SynchronizedReading> readings_buffer_;
    std::atomic<size_t> buffer_write_index_{0};
    std::atomic<bool> buffer_full_{false};
    std::atomic<uint64_t> rejected_readings_{0};
    std::atomic<int64_t> interval_ms_, interval_ms_min_, interval_ms_max_;
    std::atomic<uint64_t> interval_gen_{0};  // bumped on every interval change; wakes a sleeping sampler
    std::atomic<int> affinity_cpus_{-1}, sampler_affinity_cpus_{-1};

    // Shutdown synchronization
    mutable std::mutex shutdown_mutex_;
    std::condition_variable shutdown_cv_;
    
    // Statistics
    mutable std::mutex stats_mutex_;
    CoordinatorStatistics statistics_;

    // Real-time filtering state (non-static for thread safety)
    double filtered_power_{0.0};
    bool filter_first_reading_{true};
    
    // Private methods
    
    /**
     * @brief Main measurement loop (runs in separate thread)
     */
    void measurement_loop();
    
    /**
     * @brief Provider health monitoring loop (runs in separate thread)
     */
    void provider_health_loop();
    
    /**
     * @brief Collect readings from all active providers
     * @return Map of provider name to reading
     */
    std::map<std::string, EnergyReading> collect_provider_readings(bool boundary = false);
    
    /**
     * @brief Time-align measurements from different providers
     * @param provider_readings Raw readings from providers
     * @return Time-aligned synchronized reading
     */
    SynchronizedReading align_measurements(
        const std::map<std::string, EnergyReading>& provider_readings);
    
    /**
     * @brief Cross-validate measurements between providers
     * @param reading Synchronized reading to validate
     * @return true if cross-validation passed
     */
    bool cross_validate_measurements(SynchronizedReading& reading);
    
    /**
     * @brief Apply real-time filtering to measurements
     * @param reading Synchronized reading to filter
     */
    void apply_real_time_filtering(SynchronizedReading& reading);
    
    /**
     * @brief Add reading to circular buffer
     * @param reading Synchronized reading to buffer
     */
    void buffer_reading(const SynchronizedReading& reading);

    /** @brief Buffered readings in chronological order; caller holds readings_mutex_. */
    std::vector<SynchronizedReading> ordered_readings_locked() const;

    /**
     * @brief Check and restart failed providers
     */
    void check_provider_health();
    
    /**
     * @brief Update measurement statistics
     * @param reading Processed synchronized reading
     * @param success Whether measurement was successful
     */
    void update_statistics(const SynchronizedReading& reading, bool success);
};

} // namespace codegreen::nemb