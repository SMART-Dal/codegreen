#pragma once

#include "measurement.hpp"
#include "config.hpp"
#include <pmt/common/PMT.h>
#include <pmt/common/State.h>
#include <memory>
#include <vector>
#include <string>
#include <mutex>

namespace codegreen {

struct PMTConfiguration {
    std::vector<std::string> preferred_sensors;
    bool fallback_enabled = true;
    bool validation_enabled = true;
    int max_init_time_ms = 5000;
    int measurement_interval_ms = 1;
};

struct SensorHealth {
    bool is_available = false;
    bool is_stable = false;
    std::string status_message;
    double baseline_reading = 0.0;
    std::string sensor_name;
};

/**
 * Centralized PMT Manager - Singleton Pattern
 * Eliminates double initialization and provides consistent sensor access
 */
class PMTManager {
public:

    // Singleton access
    static PMTManager& get_instance();
    static void destroy_instance(); // For proper cleanup at program exit
    
    // Initialization and cleanup
    bool initialize(const PMTConfiguration& config = PMTConfiguration{});
    bool initialize_from_config();
    void cleanup();
    bool is_initialized() const { return initialized_; }
    
    // Sensor management
    std::vector<SensorHealth> get_sensor_health() const;
    std::vector<std::string> get_available_sensor_names() const;
    std::vector<std::string> get_active_sensor_names() const;
    
    // Measurement collection
    std::unique_ptr<Measurement> collect_measurement();
    std::vector<std::unique_ptr<Measurement>> collect_measurements_from_all_sensors();
    
    // Sensor validation and health checks
    bool validate_all_sensors();
    SensorHealth validate_sensor(const std::string& sensor_name);
    
    // Configuration
    void set_measurement_interval(int interval_ms) { measurement_interval_ms_ = interval_ms; }
    int get_measurement_interval() const { return measurement_interval_ms_; }
    
    // Statistics
    size_t get_sensor_count() const { return sensors_.size(); }
    size_t get_active_sensor_count() const;
    double get_total_initialization_time_ms() const { return init_time_ms_; }

    // Destructor must be public for unique_ptr
    ~PMTManager();

private:
    PMTManager() = default;
    PMTManager(const PMTManager&) = delete;
    PMTManager& operator=(const PMTManager&) = delete;
    
    // Internal sensor management
    bool create_sensor(const std::string& sensor_type);
    SensorHealth test_sensor(pmt::PMT* sensor, const std::string& name);
    void remove_failed_sensors();
    
    // Helper methods
    double calculate_variance(const std::vector<double>& readings) const;
    std::unique_ptr<Measurement> convert_pmt_state(const pmt::State& state, const std::string& sensor_name) const;
    void log_sensor_status() const;
    
    // Thread safety
    mutable std::mutex sensors_mutex_;
    static std::mutex instance_mutex_;
    static std::unique_ptr<PMTManager> instance_;
    
    // State
    bool initialized_ = false;
    std::vector<std::unique_ptr<pmt::PMT>> sensors_;
    std::vector<std::string> sensor_names_;
    std::vector<SensorHealth> sensor_health_;
    PMTConfiguration config_;
    
    // Performance tracking
    double init_time_ms_ = 0.0;
    int measurement_interval_ms_ = 1;
    
    // Statistics
    mutable size_t successful_measurements_ = 0;
    mutable size_t failed_measurements_ = 0;
};

/**
 * RAII wrapper for PMT Manager initialization
 */
class PMTManagerGuard {
public:
    explicit PMTManagerGuard(const PMTConfiguration& config = PMTConfiguration{});
    ~PMTManagerGuard();
    
    PMTManager& get_manager() { return PMTManager::get_instance(); }
    bool is_initialized() const { return initialized_; }
    const std::string& get_error() const { return error_message_; }

private:
    bool initialized_;
    std::string error_message_;
};

} // namespace codegreen