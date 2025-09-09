#pragma once

#include <cstdint>
#include <atomic>
#include <mutex>
#include <chrono>
#include <vector>
#include <string>
#include <map>
#include <memory>
#include <optional>

namespace codegreen::nemb::hal {

/**
 * @brief Counter wraparound detection and handling
 * 
 * Hardware energy counters (especially RAPL) are often 32-bit and wrap around
 * frequently. This class provides robust wraparound detection and accumulation
 * to maintain accurate energy measurements over long periods.
 */
template<typename T>
class WraparoundCounter {
    static_assert(std::is_unsigned_v<T>, "Counter type must be unsigned integer");
    
public:
    /**
     * @brief Constructor with maximum counter value
     * @param max_value Maximum value before wraparound (e.g., UINT32_MAX)
     * @param counter_name Human-readable counter name for debugging
     */
    explicit WraparoundCounter(T max_value = std::numeric_limits<T>::max(),
                              const std::string& counter_name = "Counter")
        : max_value_(max_value), counter_name_(counter_name) {}
    
    /**
     * @brief Initialize counter with first reading
     * @param initial_value First counter value
     * @param timestamp_ns Timestamp of first reading
     */
    void initialize(T initial_value, uint64_t timestamp_ns) {
        std::lock_guard<std::mutex> lock(mutex_);
        last_raw_value_ = initial_value;
        accumulated_value_ = 0;
        wraparound_count_ = 0;
        last_timestamp_ns_ = timestamp_ns;
        initialized_ = true;
    }
    
    /**
     * @brief Update counter with new reading
     * @param raw_value New raw counter value from hardware
     * @param timestamp_ns Timestamp of reading
     * @return Accumulated counter value accounting for wraparounds
     */
    uint64_t update(T raw_value, uint64_t timestamp_ns) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (!initialized_) {
            initialize(raw_value, timestamp_ns);
            return 0;
        }
        
        // Detect wraparound
        if (raw_value < last_raw_value_) {
            // Check if this is a legitimate wraparound or counter reset
            if (is_legitimate_wraparound(raw_value, timestamp_ns)) {
                wraparound_count_++;
                
                // Add the remaining count from last reading to max
                uint64_t remaining = max_value_ - last_raw_value_;
                accumulated_value_ += remaining;
                
                // Add current value (assumes counter wrapped to 0 then counted up)
                accumulated_value_ += raw_value;
            } else {
                // Counter was likely reset - reinitialize
                initialize(raw_value, timestamp_ns);
                return accumulated_value_;
            }
        } else {
            // Normal increment
            accumulated_value_ += (raw_value - last_raw_value_);
        }
        
        last_raw_value_ = raw_value;
        last_timestamp_ns_ = timestamp_ns;
        
        return accumulated_value_;
    }
    
    /**
     * @brief Get current accumulated value
     * @return Total accumulated counter value
     */
    uint64_t get_accumulated() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return accumulated_value_;
    }
    
    /**
     * @brief Get number of wraparounds detected
     * @return Wraparound count
     */
    uint32_t get_wraparound_count() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return wraparound_count_;
    }
    
    /**
     * @brief Reset counter accumulation
     */
    void reset() {
        std::lock_guard<std::mutex> lock(mutex_);
        accumulated_value_ = 0;
        wraparound_count_ = 0;
        initialized_ = false;
    }
    
    /**
     * @brief Get counter statistics
     */
    struct Statistics {
        uint64_t accumulated_value;
        uint32_t wraparound_count;
        T last_raw_value;
        T max_value;
        uint64_t last_timestamp_ns;
        bool initialized;
        std::string counter_name;
    };
    
    Statistics get_statistics() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {
            accumulated_value_,
            wraparound_count_,
            last_raw_value_,
            max_value_,
            last_timestamp_ns_,
            initialized_,
            counter_name_
        };
    }

private:
    /**
     * @brief Determine if counter decrease is legitimate wraparound
     * @param new_value Current counter value
     * @param timestamp_ns Current timestamp
     * @return true if this appears to be a wraparound
     */
    bool is_legitimate_wraparound(T new_value, uint64_t timestamp_ns) {
        // Time-based heuristic: wraparound should happen within reasonable time
        uint64_t time_delta_ms = (timestamp_ns - last_timestamp_ns_) / 1000000;
        
        // If too much time passed, likely a reset
        if (time_delta_ms > 60000) { // 1 minute
            return false;
        }
        
        // If new value is very close to 0 and we were near max, likely wraparound
        double distance_from_zero = static_cast<double>(new_value) / max_value_;
        double distance_from_max = static_cast<double>(max_value_ - last_raw_value_) / max_value_;
        
        return (distance_from_zero < 0.1 && distance_from_max < 0.1);
    }
    
    T max_value_;
    T last_raw_value_{0};
    uint64_t accumulated_value_{0};
    uint32_t wraparound_count_{0};
    uint64_t last_timestamp_ns_{0};
    bool initialized_{false};
    std::string counter_name_;
    mutable std::mutex mutex_;
};

// Common counter types
using Counter32 = WraparoundCounter<uint32_t>;
using Counter64 = WraparoundCounter<uint64_t>;

/**
 * @brief Multi-counter manager for synchronized counter handling
 * 
 * Manages multiple related counters (e.g., different RAPL domains)
 * ensuring they are read and processed atomically for consistency.
 */
class CounterManager {
public:
    /**
     * @brief Counter configuration
     */
    struct CounterConfig {
        std::string name;           ///< Human-readable counter name
        std::string domain;         ///< Counter domain (package, core, uncore, dram)
        uint32_t bit_width;         ///< Counter bit width (32 or 64)
        uint64_t max_value;         ///< Maximum counter value before wraparound
        double conversion_factor;   ///< Factor to convert to standard units
        std::string unit;           ///< Counter unit (μJ, mJ, J)
        bool active;                ///< Whether counter is actively monitored
    };
    
    CounterManager() = default;
    ~CounterManager() = default;
    
    /**
     * @brief Register a new counter
     * @param counter_id Unique counter identifier
     * @param config Counter configuration
     * @return true if registered successfully
     */
    bool register_counter(const std::string& counter_id, const CounterConfig& config);
    
    /**
     * @brief Initialize all registered counters
     * @param initial_values Map of counter_id to initial value
     * @param timestamp_ns Initialization timestamp
     * @return true if all counters initialized successfully
     */
    bool initialize_counters(const std::map<std::string, uint64_t>& initial_values,
                           uint64_t timestamp_ns);
    
    /**
     * @brief Update all counters atomically
     * @param raw_values Map of counter_id to raw value
     * @param timestamp_ns Reading timestamp
     * @return Map of counter_id to accumulated value
     */
    std::map<std::string, uint64_t> update_counters(
        const std::map<std::string, uint64_t>& raw_values,
        uint64_t timestamp_ns);
    
    /**
     * @brief Get accumulated values for all counters
     * @return Map of counter_id to accumulated value
     */
    std::map<std::string, uint64_t> get_accumulated_values() const;
    
    /**
     * @brief Get accumulated value in standard units (joules)
     * @param counter_id Counter identifier
     * @return Energy value in joules
     */
    double get_energy_joules(const std::string& counter_id) const;
    
    /**
     * @brief Get total energy from all active counters
     * @return Total energy in joules
     */
    double get_total_energy_joules() const;
    
    /**
     * @brief Get counter statistics
     * @param counter_id Counter identifier
     * @return Counter statistics or nullopt if not found
     */
    std::optional<Counter64::Statistics> get_counter_statistics(
        const std::string& counter_id) const;
    
    /**
     * @brief Get all counter configurations
     * @return Map of counter_id to configuration
     */
    std::map<std::string, CounterConfig> get_counter_configs() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return counter_configs_;
    }
    
    /**
     * @brief Reset all counters
     */
    void reset_all_counters();
    
    /**
     * @brief Set counter active state
     * @param counter_id Counter identifier
     * @param active Whether counter should be monitored
     */
    void set_counter_active(const std::string& counter_id, bool active);
    
    /**
     * @brief Validate counter consistency
     * @return true if all counters are consistent
     */
    bool validate_counter_consistency() const;
    
    /**
     * @brief Get summary of all counters
     * @return Human-readable summary string
     */
    std::string get_summary() const;

private:
    struct ManagedCounter {
        CounterConfig config;
        std::unique_ptr<Counter64> counter;
        bool initialized{false};
    };
    
    std::map<std::string, ManagedCounter> counters_;
    std::map<std::string, CounterConfig> counter_configs_;
    mutable std::mutex mutex_;
    
    // Helper methods
    bool is_valid_counter_id(const std::string& counter_id) const;
    double convert_to_joules(uint64_t raw_value, const CounterConfig& config) const;
    void log_counter_event(const std::string& event, const std::string& counter_id) const;
};

/**
 * @brief RAPL-specific counter manager
 * 
 * Specialized counter manager for Intel RAPL energy counters
 * with domain-specific handling and energy unit conversion.
 */
class RAPLCounterManager : public CounterManager {
public:
    /**
     * @brief RAPL energy domains
     */
    enum class Domain {
        PACKAGE = 0,    ///< Entire processor package
        PP0 = 1,        ///< Processor cores (CPU)
        PP1 = 2,        ///< Uncore/GPU (integrated graphics)
        DRAM = 3,       ///< DRAM subsystem
        PSYS = 4        ///< Platform/System (Skylake+)
    };
    
    /**
     * @brief Initialize RAPL counter manager
     * @param energy_unit Energy unit from MSR_RAPL_POWER_UNIT (typically 15.3 μJ)
     * @param available_domains Bitmask of available RAPL domains
     * @return true if initialized successfully
     */
    bool initialize_rapl_counters(double energy_unit, uint32_t available_domains);
    
    /**
     * @brief Update RAPL counters with MSR values
     * @param package_energy Raw package energy counter
     * @param pp0_energy Raw PP0 energy counter (if available)
     * @param pp1_energy Raw PP1 energy counter (if available) 
     * @param dram_energy Raw DRAM energy counter (if available)
     * @param psys_energy Raw PSYS energy counter (if available)
     * @param timestamp_ns Reading timestamp
     * @return Map of domain to energy in joules
     */
    std::map<Domain, double> update_rapl_readings(
        uint32_t package_energy,
        uint32_t pp0_energy,
        uint32_t pp1_energy,
        uint32_t dram_energy,
        uint32_t psys_energy,
        uint64_t timestamp_ns);
    
    /**
     * @brief Get energy for specific RAPL domain
     * @param domain RAPL domain
     * @return Energy in joules
     */
    double get_domain_energy(Domain domain) const;
    
    /**
     * @brief Get total package energy (all domains)
     * @return Total energy in joules
     */
    double get_total_package_energy() const;
    
    /**
     * @brief Check if domain is available
     * @param domain RAPL domain to check
     * @return true if domain is available
     */
    bool is_domain_available(Domain domain) const;
    
    /**
     * @brief Get domain name string
     * @param domain RAPL domain
     * @return Human-readable domain name
     */
    static std::string get_domain_name(Domain domain);

private:
    double energy_unit_{15.3e-6}; // Default: 15.3 μJ
    uint32_t available_domains_{0};
    
    std::string domain_to_counter_id(Domain domain) const;
    Domain counter_id_to_domain(const std::string& counter_id) const;
};

} // namespace codegreen::nemb::hal