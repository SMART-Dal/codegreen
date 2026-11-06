#include "../../../include/nemb/core/measurement_coordinator.hpp"

#include <algorithm>
#include <numeric>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <future>
#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#endif

namespace codegreen::nemb {

// A provider reading counts only when it carries an id and a non-negative cumulative energy.
static bool reading_ok(const EnergyReading& r) { return !r.provider_id.empty() && r.energy_joules >= 0; }
static bool sync_ok(const SynchronizedReading& r) { return r.providers_active > 0 && r.providers_failed == 0; }

static void atomic_min(std::atomic<int64_t>& a, int64_t v) { for (int64_t c = a.load(); v < c && !a.compare_exchange_weak(c, v);) {} }
static void atomic_max(std::atomic<int64_t>& a, int64_t v) { for (int64_t c = a.load(); v > c && !a.compare_exchange_weak(c, v);) {} }

// CPUs in the process (main thread) affinity mask, or in thread t's mask; -1 when unreadable.
static int affinity_cpu_count(std::thread* t) {
#ifdef __linux__
    cpu_set_t set;
    CPU_ZERO(&set);
    int rc = t ? pthread_getaffinity_np(t->native_handle(), sizeof(set), &set) : sched_getaffinity(getpid(), sizeof(set), &set);
    return rc == 0 ? CPU_COUNT(&set) : -1;
#else
    (void)t;
    return static_cast<int>(std::thread::hardware_concurrency());
#endif
}

MeasurementCoordinator::MeasurementCoordinator(const CoordinatorConfig& config)
    : config_(config), interval_ms_(config.measurement_interval.count()),
      interval_ms_min_(config.measurement_interval.count()), interval_ms_max_(config.measurement_interval.count()) {
    std::cerr << "[NEMB] measurement_interval=" << config_.measurement_interval.count()
              << "ms buffer_size=" << config_.measurement_buffer_size
              << " cross_validation_threshold=" << config_.cross_validation_threshold
              << std::endl;
}

MeasurementCoordinator::~MeasurementCoordinator() {
    stop_measurements();
}

bool MeasurementCoordinator::add_provider(std::unique_ptr<EnergyProvider> provider, const std::string& name) {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);

    if (!provider) {
        std::cerr << "Cannot add null energy provider" << std::endl;
        return false;
    }

    if (running_.load()) {
        std::cerr << "Cannot add provider while measurements are active" << std::endl;
        return false;
    }

    std::string provider_name = name.empty() ? provider->get_name() : name;
    std::cerr << "Adding energy provider: " << provider_name << std::endl;

    if (!provider->is_available()) {
        std::cerr << "  Provider not available: " << provider_name << std::endl;
        return false;
    }
    provider->set_max_consecutive_failures(config_.max_consecutive_failures);

    ProviderState state;
    state.provider = std::move(provider);
    state.active = true;
    state.failed = false;
    state.consecutive_failures = 0;
    state.last_successful_reading = std::chrono::steady_clock::now();
    
    providers_[provider_name] = std::move(state);
    
    std::cerr << "  Provider added successfully: " << provider_name << std::endl;
    return true;
}

bool MeasurementCoordinator::remove_provider(const std::string& provider_name) {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    
    if (running_.load()) {
        std::cerr << "Cannot remove provider while measurements are active" << std::endl;
        return false;
    }
    
    auto it = providers_.find(provider_name);
    if (it == providers_.end()) {
        std::cerr << "Provider not found: " << provider_name << std::endl;
        return false;
    }
    
    std::cerr << "Removing energy provider: " << provider_name << std::endl;
    it->second.provider->shutdown();
    providers_.erase(it);
    
    return true;
}

bool MeasurementCoordinator::start_measurements() {
    if (running_.load()) {
        std::cerr << "Measurements already active" << std::endl;
        return false;
    }
    
    {
        std::shared_lock<std::shared_mutex> lock(providers_mutex_);
        if (providers_.empty()) {
            std::cerr << "No energy providers available" << std::endl;
            return false;
        }
    }
    
    std::cerr << "Starting coordinated measurements..." << std::endl;
    
    // Reset statistics and filtering state
    {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        statistics_ = CoordinatorStatistics{};
    }
    filtered_power_ = 0.0;
    filter_first_reading_ = true;
    rejected_readings_.store(0);
    interval_ms_min_.store(interval_ms_.load());
    interval_ms_max_.store(interval_ms_.load());
    affinity_cpus_.store(affinity_cpu_count(nullptr));

    running_.store(true);

    // Seed the buffer synchronously so the first marker is bracketed by a real reading.
    SynchronizedReading seed;
    if (sample_now(seed)) buffer_reading(seed);

    // Start worker threads
    measurement_thread_ = std::thread(&MeasurementCoordinator::measurement_loop, this);
    provider_health_thread_ = std::thread(&MeasurementCoordinator::provider_health_loop, this);
    sampler_affinity_cpus_.store(affinity_cpu_count(&measurement_thread_));

    std::cerr << "  Measurements started" << std::endl;
    return true;
}

void MeasurementCoordinator::stop_measurements() {
    if (!running_.load()) {
        return;
    }

    running_.store(false);

    // Wake up any waiting threads
    {
        std::lock_guard<std::mutex> lock(shutdown_mutex_);
        shutdown_cv_.notify_all();
    }
    readings_condition_.notify_all();

    if (measurement_thread_.joinable()) measurement_thread_.join();
    if (provider_health_thread_.joinable()) provider_health_thread_.join();
}

SynchronizedReading MeasurementCoordinator::get_synchronized_reading() {
    if (!running_.load()) {
        SynchronizedReading reading;
        reading.providers_active = 0;
        reading.providers_failed = 0;
        return reading;
    }
    
    auto provider_readings = collect_provider_readings();
    return align_measurements(provider_readings);
}

bool MeasurementCoordinator::sample_now(SynchronizedReading& out) {
    auto readings = collect_provider_readings();
    out = align_measurements(readings);
    if (sync_ok(out)) return true;
    rejected_readings_++;
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    for (const auto& [name, r] : readings) {
        auto it = providers_.find(name);
        if (!reading_ok(r) && it != providers_.end()) it->second.rejected++;
    }
    return false;
}

std::map<std::string, MeasurementCoordinator::ProviderCounts> MeasurementCoordinator::provider_counts() const {
    std::shared_lock<std::shared_mutex> lock(providers_mutex_);
    std::map<std::string, ProviderCounts> counts;
    for (const auto& [name, state] : providers_)
        counts[name] = {state.rejected, state.provider->get_held_readings(), state.restarts};
    return counts;
}

std::vector<SynchronizedReading> MeasurementCoordinator::collect_measurements_for_duration(
    std::chrono::milliseconds duration) {
    
    std::vector<SynchronizedReading> readings;
    
    auto start_time = std::chrono::steady_clock::now();
    auto end_time = start_time + duration;
    
    while (std::chrono::steady_clock::now() < end_time && running_.load()) {
        readings.push_back(get_synchronized_reading());
        std::this_thread::sleep_for(measurement_interval());
    }
    
    return readings;
}

std::vector<std::string> MeasurementCoordinator::get_active_providers() const {
    std::shared_lock<std::shared_mutex> lock(providers_mutex_);
    
    std::vector<std::string> active_providers;
    for (const auto& [name, state] : providers_) {
        if (state.active && !state.failed) {
            active_providers.push_back(name);
        }
    }
    
    return active_providers;
}

std::vector<std::string> MeasurementCoordinator::get_failed_providers() const {
    std::shared_lock<std::shared_mutex> lock(providers_mutex_);
    
    std::vector<std::string> failed_providers;
    for (const auto& [name, state] : providers_) {
        if (state.failed) {
            failed_providers.push_back(name);
        }
    }
    
    return failed_providers;
}

std::map<std::string, EnergyProviderSpec> MeasurementCoordinator::get_provider_specifications() const {
    std::shared_lock<std::shared_mutex> lock(providers_mutex_);
    
    std::map<std::string, EnergyProviderSpec> specs;
    for (const auto& [name, state] : providers_) {
        specs[name] = state.provider->get_specification();
    }
    
    return specs;
}

bool MeasurementCoordinator::restart_provider(const std::string& provider_name) {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    
    auto it = providers_.find(provider_name);
    if (it == providers_.end()) {
        return false;
    }
    
    auto& state = it->second;
    
    // Try to reinitialize
    if (state.provider->initialize()) {
        state.failed = false;
        state.active = true;
        state.consecutive_failures = 0;
        state.restarts++;
        state.last_successful_reading = std::chrono::steady_clock::now();
        return true;
    }

    return false;
}

std::vector<SynchronizedReading> MeasurementCoordinator::ordered_readings_locked() const {
    std::vector<SynchronizedReading> result;
    result.reserve(readings_buffer_.size());
    size_t start = buffer_full_.load(std::memory_order_acquire) ? buffer_write_index_.load(std::memory_order_acquire) : 0;
    for (size_t i = 0; i < readings_buffer_.size(); ++i)
        result.push_back(readings_buffer_[(start + i) % readings_buffer_.size()]);
    return result;
}

std::vector<SynchronizedReading> MeasurementCoordinator::get_buffered_readings() const {
    std::lock_guard<std::mutex> lock(readings_mutex_);
    return ordered_readings_locked();
}

void MeasurementCoordinator::set_measurement_interval_ms(int interval_ms) {
    int64_t ms = std::clamp(interval_ms, 1, 60000);
    interval_ms_.store(ms);
    atomic_min(interval_ms_min_, ms);
    atomic_max(interval_ms_max_, ms);
    interval_gen_++;
    std::lock_guard<std::mutex> lock(shutdown_mutex_);
    shutdown_cv_.notify_all();
}

bool MeasurementCoordinator::set_buffer_size(size_t size) {
    if (size == 0) return false;
    std::lock_guard<std::mutex> lock(readings_mutex_);
    auto ordered = ordered_readings_locked();
    bool dropped = ordered.size() > size;
    if (dropped) ordered.erase(ordered.begin(), ordered.end() - static_cast<std::ptrdiff_t>(size));
    readings_buffer_ = std::move(ordered);
    readings_buffer_.reserve(size);
    buffer_write_index_.store(0, std::memory_order_release);
    if (dropped) buffer_full_.store(true, std::memory_order_release);
    config_.measurement_buffer_size = static_cast<uint32_t>(size);
    return true;
}

MeasurementCoordinator::CoordinatorStatistics MeasurementCoordinator::get_statistics() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return statistics_;
}

void MeasurementCoordinator::reset_statistics() {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    statistics_ = CoordinatorStatistics{};
}

// Private methods

void MeasurementCoordinator::measurement_loop() {
    while (running_.load()) {
        auto start_time = std::chrono::steady_clock::now();

        try {
            SynchronizedReading synchronized_reading;
            if (!sample_now(synchronized_reading)) {
                update_statistics(synchronized_reading, false);
            } else {
                if (config_.enable_real_time_filtering) apply_real_time_filtering(synchronized_reading);
                bool validation_passed = !config_.enable_outlier_detection || cross_validate_measurements(synchronized_reading);
                buffer_reading(synchronized_reading);
                update_statistics(synchronized_reading, validation_passed);
            }

        } catch (const std::exception& e) {
            std::cerr << "Error in measurement loop: " << e.what() << std::endl;
        }

        // Condition-variable wait: shutdown and interval changes wake the sampler immediately
        uint64_t gen = interval_gen_.load();
        auto elapsed = std::chrono::steady_clock::now() - start_time;
        auto sleep_time = measurement_interval() - elapsed;

        if (sleep_time > std::chrono::milliseconds::zero()) {
            std::unique_lock<std::mutex> lock(shutdown_mutex_);
            shutdown_cv_.wait_for(lock, sleep_time, [this, gen]{ return !running_.load() || interval_gen_.load() != gen; });
        }
    }
}

void MeasurementCoordinator::provider_health_loop() {
    while (running_.load()) {
        {
            std::unique_lock<std::mutex> lock(shutdown_mutex_);
            shutdown_cv_.wait_for(lock, config_.provider_restart_interval, [this]{ return !running_.load(); });
        }
        if (!running_.load()) break;
        if (config_.auto_restart_failed_providers) {
            check_provider_health();
        }
    }
}

std::map<std::string, EnergyReading> MeasurementCoordinator::collect_provider_readings() {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    
    std::map<std::string, EnergyReading> readings;
    
    for (auto& [name, state] : providers_) {
        if (!state.active || state.failed) {
            readings[name] = EnergyReading{};  // counted as failed so the provider set never silently shrinks
            continue;
        }
        
        try {
            // Direct provider reading - no timeout needed with non-blocking I/O
            auto reading = state.provider->get_reading();
            readings[name] = reading;
            
            if (reading_ok(reading)) {
                state.last_successful_reading = std::chrono::steady_clock::now();
                state.consecutive_failures = 0;
            } else {
                state.consecutive_failures++;
                if (state.consecutive_failures > config_.max_consecutive_failures) {
                    state.failed = true;
                    std::cerr << "Provider failed: " << name << std::endl;
                }
            }

        } catch (const std::exception& e) {
            state.consecutive_failures++;
            std::cerr << "Exception reading from " << name << ": " << e.what() << std::endl;

            if (state.consecutive_failures > config_.max_consecutive_failures) {
                state.failed = true;
                std::cerr << "Provider " << name << " marked as failed due to repeated exceptions" << std::endl;
            }
        }
    }
    
    return readings;
}

SynchronizedReading MeasurementCoordinator::align_measurements(
    const std::map<std::string, EnergyReading>& provider_readings) {
    
    SynchronizedReading result;
    
    if (provider_readings.empty()) {
        result.providers_active = 0;
        result.providers_failed = 0;
        return result;
    }
    
    // Use the most recent timestamp as the common timestamp
    uint64_t max_timestamp = 0;
    for (const auto& [name, reading] : provider_readings) {
        if (reading_ok(reading)) {
            max_timestamp = std::max(max_timestamp, reading.timestamp_ns);
        }
    }
    
    result.common_timestamp_ns = max_timestamp;
    
    // Aggregate measurements
    double total_power = 0.0;
    double total_energy = 0.0;
    uint32_t valid_count = 0;
    
    for (const auto& [name, reading] : provider_readings) {
        result.provider_readings.push_back(reading);
        
        if (reading_ok(reading)) {
            total_power += reading.average_power_watts;
            total_energy += reading.energy_joules;
            valid_count++;
        }
    }
    
    result.total_system_power_watts = total_power;
    result.total_system_energy_joules = total_energy;
    result.providers_active = valid_count;
    result.providers_failed = static_cast<uint32_t>(provider_readings.size()) - valid_count;
    
    // Simple confidence calculation
    if (valid_count > 0) {
        result.measurement_confidence = static_cast<double>(valid_count) / provider_readings.size();
    }
    
    return result;
}

bool MeasurementCoordinator::cross_validate_measurements(SynchronizedReading& reading) {
    if (reading.provider_readings.size() < 2) {
        return true; // Can't cross-validate with single provider
    }
    
    // Simple validation: check if power readings are within reasonable range of each other
    std::vector<double> power_values;
    for (const auto& provider_reading : reading.provider_readings) {
        if (!provider_reading.provider_id.empty() && provider_reading.average_power_watts > 0) {
            power_values.push_back(provider_reading.average_power_watts);
        }
    }
    
    if (power_values.size() < 2) {
        return true;
    }
    
    double mean = std::accumulate(power_values.begin(), power_values.end(), 0.0) / power_values.size();
    
    for (double power : power_values) {
        double deviation = std::abs(power - mean) / mean;
        if (deviation > config_.cross_validation_threshold) {
            reading.cross_validation_passed = false;
            reading.max_provider_deviation = std::max(reading.max_provider_deviation, deviation);
            return false;
        }
    }
    
    return true;
}

void MeasurementCoordinator::apply_real_time_filtering(SynchronizedReading& reading) {
    const double alpha = 0.1;
    if (filter_first_reading_) {
        filtered_power_ = reading.total_system_power_watts;
        filter_first_reading_ = false;
    } else {
        filtered_power_ = alpha * reading.total_system_power_watts + (1.0 - alpha) * filtered_power_;
        reading.total_system_power_watts = filtered_power_;
    }
}

void MeasurementCoordinator::buffer_reading(const SynchronizedReading& reading) {
    std::lock_guard<std::mutex> lock(readings_mutex_);

    if (readings_buffer_.size() < config_.measurement_buffer_size) {
        readings_buffer_.push_back(reading);
    } else {
        // Circular buffer - overwrite oldest
        size_t write_idx = buffer_write_index_.load(std::memory_order_relaxed);
        readings_buffer_[write_idx] = reading;
        buffer_write_index_.store((write_idx + 1) % config_.measurement_buffer_size, std::memory_order_release);
        buffer_full_.store(true, std::memory_order_release);
    }

    readings_condition_.notify_one();
}

void MeasurementCoordinator::check_provider_health() {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    
    auto now = std::chrono::steady_clock::now();
    
    for (auto& [name, state] : providers_) {
        if (state.failed) {
            auto time_since_restart = now - state.last_restart_attempt;
            
            if (time_since_restart >= config_.provider_restart_interval) {
                std::cerr << "Attempting to restart failed provider: " << name << std::endl;
                state.last_restart_attempt = now;
                
                if (state.provider->initialize()) {
                    state.failed = false;
                    state.active = true;
                    state.consecutive_failures = 0;
                    state.restarts++;
                    state.last_successful_reading = now;
                    std::cerr << "Restarted provider " << name << "; its cumulative energy is discontinuous here" << std::endl;
                }
            }
        }
    }
}

void MeasurementCoordinator::update_statistics(const SynchronizedReading& reading, bool success) {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    
    statistics_.total_synchronized_readings++;
    
    if (!success) {
        statistics_.failed_synchronizations++;
    }
    
    if (!reading.cross_validation_passed) {
        statistics_.cross_validation_failures++;
    }
    
    // Update per-provider statistics
    for (const auto& provider_reading : reading.provider_readings) {
        const std::string& name = provider_reading.provider_id;
        
        if (reading_ok(provider_reading)) {
            statistics_.provider_success_counts[name]++;
        } else {
            statistics_.provider_failure_counts[name]++;
        }
    }
}

} // namespace codegreen::nemb