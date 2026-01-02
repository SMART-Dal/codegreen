#include "../../../include/nemb/core/measurement_coordinator.hpp"

#include <algorithm>
#include <numeric>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <future>

namespace codegreen::nemb {

MeasurementCoordinator::MeasurementCoordinator(const CoordinatorConfig& config)
    : config_(config) {
}

MeasurementCoordinator::~MeasurementCoordinator() {
    stop_measurements();
}

bool MeasurementCoordinator::add_provider(std::unique_ptr<EnergyProvider> provider) {
    std::unique_lock<std::shared_mutex> lock(providers_mutex_);
    
    if (!provider) {
        std::cerr << "Cannot add null energy provider" << std::endl;
        return false;
    }
    
    if (running_.load()) {
        std::cerr << "Cannot add provider while measurements are active" << std::endl;
        return false;
    }
    
    std::string provider_name = provider->get_name();
    std::cout << "🔌 Adding energy provider: " << provider_name << std::endl;
    
    if (!provider->is_available()) {
        std::cerr << "  ⚠️  Provider not available: " << provider_name << std::endl;
        return false;
    }
    
    if (!provider->initialize()) {
        std::cerr << "  ❌ Failed to initialize provider: " << provider_name << std::endl;
        return false;
    }
    
    // Run self-test
    if (!provider->self_test()) {
        std::cerr << "  ❌ Provider self-test failed: " << provider_name << std::endl;
        provider->shutdown();
        return false;
    }
    
    // Add to provider map
    ProviderState state;
    state.provider = std::move(provider);
    state.active = true;
    state.failed = false;
    state.consecutive_failures = 0;
    state.last_successful_reading = std::chrono::steady_clock::now();
    
    providers_[provider_name] = std::move(state);
    
    std::cout << "  ✅ Provider added successfully: " << provider_name << std::endl;
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
    
    std::cout << "🔌 Removing energy provider: " << provider_name << std::endl;
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
    
    std::cout << "▶️  Starting coordinated measurements..." << std::endl;
    
    // Reset statistics
    {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        statistics_ = CoordinatorStatistics{};
    }
    
    running_.store(true);
    
    // Start worker threads
    measurement_thread_ = std::thread(&MeasurementCoordinator::measurement_loop, this);
    provider_health_thread_ = std::thread(&MeasurementCoordinator::provider_health_loop, this);
    
    std::cout << "  ✅ Measurements started" << std::endl;
    return true;
}

void MeasurementCoordinator::stop_measurements() {
    if (!running_.load()) {
        return;
    }
    
    std::cout << "⏹️  Stopping coordinated measurements..." << std::endl;
    
    running_.store(false);
    
    // Wake up any waiting threads
    readings_condition_.notify_all();
    
    // Wait for threads to finish
    if (measurement_thread_.joinable()) {
        measurement_thread_.join();
    }
    
    if (provider_health_thread_.joinable()) {
        provider_health_thread_.join();
    }
    
    std::cout << "  ✅ Measurements stopped" << std::endl;
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

std::vector<SynchronizedReading> MeasurementCoordinator::collect_measurements_for_duration(
    std::chrono::milliseconds duration) {
    
    std::vector<SynchronizedReading> readings;
    
    auto start_time = std::chrono::steady_clock::now();
    auto end_time = start_time + duration;
    
    while (std::chrono::steady_clock::now() < end_time && running_.load()) {
        readings.push_back(get_synchronized_reading());
        std::this_thread::sleep_for(config_.measurement_interval);
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
        state.last_successful_reading = std::chrono::steady_clock::now();
        return true;
    }
    
    return false;
}

std::vector<SynchronizedReading> MeasurementCoordinator::get_buffered_readings() const {
    std::lock_guard<std::mutex> lock(readings_mutex_);
    
    std::vector<SynchronizedReading> result;
    if (readings_buffer_.empty()) return result;
    
    result.reserve(readings_buffer_.size());
    
    if (!buffer_full_) {
        // Simple case: just copy the readings
        result.assign(readings_buffer_.begin(), readings_buffer_.end());
    } else {
        // Circular buffer: start from buffer_write_index_ and wrap around
        for (size_t i = 0; i < readings_buffer_.size(); ++i) {
            result.push_back(readings_buffer_[(buffer_write_index_ + i) % readings_buffer_.size()]);
        }
    }
    
    return result;
}

void MeasurementCoordinator::set_buffer_size(size_t size) {
    std::lock_guard<std::mutex> lock(readings_mutex_);
    
    readings_buffer_.clear();
    readings_buffer_.reserve(size);
    buffer_write_index_ = 0;
    buffer_full_ = false;
    config_.measurement_buffer_size = static_cast<uint32_t>(size);
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
            auto provider_readings = collect_provider_readings();
            auto synchronized_reading = align_measurements(provider_readings);
            
            // Apply filtering and validation
            if (config_.enable_real_time_filtering) {
                apply_real_time_filtering(synchronized_reading);
            }
            
            bool validation_passed = true;
            if (config_.enable_outlier_detection) {
                validation_passed = cross_validate_measurements(synchronized_reading);
            }
            
            // Buffer the reading
            buffer_reading(synchronized_reading);
            
            // Update statistics
            update_statistics(synchronized_reading, validation_passed);
            
        } catch (const std::exception& e) {
            std::cerr << "Error in measurement loop: " << e.what() << std::endl;
        }
        
        // Maintain target interval
        auto elapsed = std::chrono::steady_clock::now() - start_time;
        auto sleep_time = config_.measurement_interval - elapsed;
        
        if (sleep_time > std::chrono::milliseconds::zero()) {
            std::this_thread::sleep_for(sleep_time);
        }
    }
}

void MeasurementCoordinator::provider_health_loop() {
    while (running_.load()) {
        std::this_thread::sleep_for(config_.provider_restart_interval);
        
        if (config_.auto_restart_failed_providers) {
            check_provider_health();
        }
    }
}

std::map<std::string, EnergyReading> MeasurementCoordinator::collect_provider_readings() {
    std::shared_lock<std::shared_mutex> lock(providers_mutex_);
    
    std::map<std::string, EnergyReading> readings;
    
    for (auto& [name, state] : providers_) {
        if (!state.active || state.failed) {
            continue;
        }
        
        try {
            // Direct provider reading - no timeout needed with non-blocking I/O
            auto reading = state.provider->get_reading();
            readings[name] = reading;
            
            if (!reading.provider_id.empty()) {
                state.last_successful_reading = std::chrono::steady_clock::now();
                state.consecutive_failures = 0;
            } else {
                state.consecutive_failures++;
                if (state.consecutive_failures > 5) {
                    state.failed = true;
                    std::cerr << "Provider failed: " << name << std::endl;
                }
            }
            
        } catch (const std::exception& e) {
            state.consecutive_failures++;
            std::cerr << "Exception reading from " << name << ": " << e.what() << std::endl;
            
            // Mark provider as failed if too many exceptions
            if (state.consecutive_failures > 3) {
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
        if (!reading.provider_id.empty()) {
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
        
        if (!reading.provider_id.empty()) {
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
    // Simple noise filtering - could be enhanced with Kalman filtering
    const double alpha = 0.1; // Smoothing factor
    
    static double filtered_power = 0.0;
    static bool first_reading = true;
    
    if (first_reading) {
        filtered_power = reading.total_system_power_watts;
        first_reading = false;
    } else {
        filtered_power = alpha * reading.total_system_power_watts + (1.0 - alpha) * filtered_power;
        reading.total_system_power_watts = filtered_power;
    }
}

void MeasurementCoordinator::buffer_reading(const SynchronizedReading& reading) {
    std::lock_guard<std::mutex> lock(readings_mutex_);
    
    if (readings_buffer_.size() < config_.measurement_buffer_size) {
        readings_buffer_.push_back(reading);
    } else {
        // Circular buffer - overwrite oldest
        readings_buffer_[buffer_write_index_] = reading;
        buffer_write_index_ = (buffer_write_index_ + 1) % config_.measurement_buffer_size;
        buffer_full_ = true;
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
                std::cout << "Attempting to restart failed provider: " << name << std::endl;
                state.last_restart_attempt = now;
                
                if (state.provider->initialize()) {
                    state.failed = false;
                    state.active = true;
                    state.consecutive_failures = 0;
                    state.last_successful_reading = now;
                    std::cout << "Successfully restarted provider: " << name << std::endl;
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
        
        if (!provider_reading.provider_id.empty()) {
            statistics_.provider_success_counts[name]++;
        } else {
            statistics_.provider_failure_counts[name]++;
        }
    }
}

} // namespace codegreen::nemb