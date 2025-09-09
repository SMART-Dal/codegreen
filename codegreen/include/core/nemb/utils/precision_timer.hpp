#pragma once

#include <chrono>
#include <atomic>
#include <memory>

namespace codegreen::nemb::utils {

/**
 * @brief High-precision timestamp provider
 * 
 * Provides sub-microsecond precision timestamps using the best available
 * clock source on the current system. Automatically selects between:
 * - TSC (Time Stamp Counter) for maximum precision on x86
 * - CLOCK_MONOTONIC_RAW for reliable monotonic time
 * - CLOCK_MONOTONIC as fallback
 */
class PrecisionTimer {
public:
    enum class ClockSource {
        TSC_INVARIANT,      ///< Time Stamp Counter (x86 only, highest precision)
        MONOTONIC_RAW,      ///< Raw monotonic clock (no NTP adjustments)
        MONOTONIC,          ///< Standard monotonic clock
        REALTIME            ///< System realtime clock (last resort)
    };
    
    PrecisionTimer();
    ~PrecisionTimer() = default;
    
    /**
     * @brief Initialize the precision timer
     * @return true if initialization successful
     */
    bool initialize();
    
    /**
     * @brief Get current timestamp in nanoseconds
     * @return Timestamp in nanoseconds since epoch
     */
    uint64_t get_timestamp_ns() const;
    
    /**
     * @brief Get current timestamp using steady_clock reference
     * @return std::chrono::steady_clock::time_point
     */
    std::chrono::steady_clock::time_point get_steady_time() const {
        return std::chrono::steady_clock::now();
    }
    
    /**
     * @brief Get timer resolution in nanoseconds
     * @return Resolution of selected clock source
     */
    double get_resolution_ns() const { return resolution_ns_; }
    
    /**
     * @brief Get selected clock source
     * @return Currently active clock source
     */
    ClockSource get_clock_source() const { return clock_source_; }
    
    /**
     * @brief Get clock source name as string
     * @return Human-readable clock source name
     */
    std::string get_clock_source_name() const;
    
    /**
     * @brief Check if TSC is available and invariant
     * @return true if TSC can be used for timing
     */
    static bool is_tsc_available();
    
    /**
     * @brief Measure elapsed time between two timestamps
     * @param start_ns Start timestamp in nanoseconds
     * @param end_ns End timestamp in nanoseconds
     * @return Elapsed time in nanoseconds
     */
    static uint64_t elapsed_ns(uint64_t start_ns, uint64_t end_ns) {
        return (end_ns >= start_ns) ? (end_ns - start_ns) : 0;
    }
    
    /**
     * @brief Convert nanoseconds to seconds
     * @param nanoseconds Timestamp in nanoseconds
     * @return Time in seconds as double
     */
    static double ns_to_seconds(uint64_t nanoseconds) {
        return static_cast<double>(nanoseconds) / 1e9;
    }
    
    /**
     * @brief Convert seconds to nanoseconds
     * @param seconds Time in seconds
     * @return Timestamp in nanoseconds
     */
    static uint64_t seconds_to_ns(double seconds) {
        return static_cast<uint64_t>(seconds * 1e9);
    }

private:
    ClockSource clock_source_{ClockSource::MONOTONIC};
    double resolution_ns_{1000.0}; // Default 1μs resolution
    
    // TSC-specific members
    bool tsc_available_{false};
    uint64_t tsc_frequency_hz_{0};
    uint64_t tsc_offset_{0};
    
    // Initialization methods
    bool initialize_tsc();
    bool initialize_posix_clock();
    bool detect_tsc_invariant();
    uint64_t measure_tsc_frequency();
    double measure_clock_resolution(clockid_t clock_id);
    
    // TSC access methods
    uint64_t read_tsc() const;
    uint64_t tsc_to_nanoseconds(uint64_t tsc_value) const;
    
    // POSIX clock methods  
    uint64_t read_posix_clock_ns(clockid_t clock_id) const;
};

/**
 * @brief RAII timer for measuring code execution time
 */
class ScopedTimer {
public:
    explicit ScopedTimer(const std::string& name = "ScopedTimer");
    ~ScopedTimer();
    
    /**
     * @brief Get elapsed time so far
     * @return Elapsed time in nanoseconds
     */
    uint64_t elapsed_ns() const;
    
    /**
     * @brief Get elapsed time in seconds
     * @return Elapsed time in seconds
     */
    double elapsed_seconds() const {
        return PrecisionTimer::ns_to_seconds(elapsed_ns());
    }
    
    /**
     * @brief Reset the timer
     */
    void reset();

private:
    std::string name_;
    std::unique_ptr<PrecisionTimer> timer_;
    uint64_t start_time_ns_;
};

/**
 * @brief High-precision interval timer for periodic measurements
 */
class IntervalTimer {
public:
    explicit IntervalTimer(std::chrono::nanoseconds interval);
    ~IntervalTimer() = default;
    
    /**
     * @brief Start the interval timer
     * @return true if started successfully
     */
    bool start();
    
    /**
     * @brief Stop the interval timer
     */
    void stop();
    
    /**
     * @brief Wait for next interval
     * @return true if interval elapsed normally
     */
    bool wait_for_next();
    
    /**
     * @brief Check if timer is running
     * @return true if timer is active
     */
    bool is_running() const { return running_.load(); }
    
    /**
     * @brief Get configured interval
     * @return Interval duration in nanoseconds
     */
    std::chrono::nanoseconds get_interval() const { return interval_; }
    
    /**
     * @brief Set new interval (takes effect after current interval)
     * @param new_interval New interval duration
     */
    void set_interval(std::chrono::nanoseconds new_interval) {
        interval_ = new_interval;
    }
    
    /**
     * @brief Get timing statistics
     */
    struct TimingStats {
        uint64_t intervals_completed{0};
        uint64_t total_drift_ns{0};
        uint64_t max_drift_ns{0};
        double average_drift_ns{0.0};
    };
    
    TimingStats get_stats() const;
    void reset_stats();

private:
    std::chrono::nanoseconds interval_;
    std::unique_ptr<PrecisionTimer> timer_;
    std::atomic<bool> running_{false};
    
    // Timing accuracy tracking
    uint64_t next_target_time_ns_{0};
    uint64_t intervals_completed_{0};
    uint64_t total_drift_ns_{0};
    uint64_t max_drift_ns_{0};
};

} // namespace codegreen::nemb::utils