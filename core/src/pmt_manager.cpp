#include "pmt_manager.hpp"
#include <pmt.h>
#include <iostream>
#include <chrono>
#include <thread>
#include <algorithm>
#include <numeric>
#include <cmath>

namespace codegreen {

// Static member initialization
std::mutex PMTManager::instance_mutex_;
std::unique_ptr<PMTManager> PMTManager::instance_;

PMTManager& PMTManager::get_instance() {
    std::lock_guard<std::mutex> lock(instance_mutex_);
    if (!instance_) {
        instance_ = std::unique_ptr<PMTManager>(new PMTManager());
    }
    return *instance_;
}

void PMTManager::destroy_instance() {
    std::lock_guard<std::mutex> lock(instance_mutex_);
    if (instance_) {
        instance_->cleanup(); // Ensure proper cleanup
        instance_.reset(); // Explicitly destroy the singleton
    }
}

PMTManager::~PMTManager() {
    cleanup();
}

bool PMTManager::initialize(const PMTConfiguration& config) {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    if (initialized_) {
        std::cout << "PMT Manager already initialized" << std::endl;
        return true;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    config_ = config;
    sensors_.clear();
    sensor_names_.clear();
    sensor_health_.clear();
    
    std::cout << "🔍 Smart PMT sensor detection..." << std::endl;
    
    // Try preferred sensors in order
    for (const auto& sensor_type : config_.preferred_sensors) {
        if (create_sensor(sensor_type)) {
            std::cout << "  ✅ " << sensor_type << " - Available and working" << std::endl;
        } else {
            std::cout << "  ❌ " << sensor_type << " - Not available" << std::endl;
        }
    }
    
    // Validate all sensors if enabled
    if (config_.validation_enabled) {
        validate_all_sensors();
    }
    
    // Remove failed sensors
    remove_failed_sensors();
    
    auto end_time = std::chrono::high_resolution_clock::now();
    init_time_ms_ = std::chrono::duration<double, std::milli>(end_time - start_time).count();
    
    initialized_ = !sensors_.empty();
    
    if (initialized_) {
        std::cout << "💡 All sensors are built - availability will be checked at runtime" << std::endl;
        log_sensor_status();
    } else {
        std::cerr << "❌ No PMT sensors available - energy measurements will be limited" << std::endl;
        return false;
    }
    
    return true;
}

bool PMTManager::initialize_from_config() {
    auto& config = Config::instance();
    
    PMTConfiguration pmt_config;
    pmt_config.preferred_sensors = config.get_preferred_pmt_sensors();
    pmt_config.fallback_enabled = config.get_bool("measurement.pmt.fallback_enabled", true);
    pmt_config.validation_enabled = config.get_bool("measurement.pmt.validation_enabled", true);
    pmt_config.max_init_time_ms = config.get_int("measurement.pmt.max_init_time_ms", 5000);
    pmt_config.measurement_interval_ms = config.get_int("measurement.pmt.measurement_interval_ms", 1);
    
    return initialize(pmt_config);
}

void PMTManager::cleanup() {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    if (!initialized_) {
        return; // Already cleaned up
    }
    
    // Explicitly reset all sensors to ensure proper cleanup
    for (auto& sensor : sensors_) {
        if (sensor) {
            try {
                // Perform any final readings or cleanup operations if needed
                sensor.reset(); // Explicitly reset unique_ptr
            } catch (const std::exception& e) {
                std::cerr << "Warning: Error during sensor cleanup: " << e.what() << std::endl;
            }
        }
    }
    
    // Clear all containers
    sensors_.clear();
    sensors_.shrink_to_fit(); // Force memory deallocation
    sensor_names_.clear();
    sensor_names_.shrink_to_fit();
    sensor_health_.clear();
    sensor_health_.shrink_to_fit();
    
    // Reset statistics
    successful_measurements_ = 0;
    failed_measurements_ = 0;
    init_time_ms_ = 0.0;
    
    initialized_ = false;
    
    std::cout << "PMT Manager cleaned up with proper resource deallocation" << std::endl;
}

bool PMTManager::create_sensor(const std::string& sensor_type) {
    try {
        auto sensor = pmt::Create(sensor_type);
        if (!sensor) {
            return false;
        }
        
        // Test the sensor
        SensorHealth health = test_sensor(sensor.get(), sensor_type);
        
        if (health.is_available) {
            sensors_.push_back(std::move(sensor));
            sensor_names_.push_back(sensor_type);
            sensor_health_.push_back(health);
            return true;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to create sensor " << sensor_type << ": " << e.what() << std::endl;
    }
    
    return false;
}

SensorHealth PMTManager::test_sensor(pmt::PMT* sensor, const std::string& name) {
    SensorHealth health;
    health.sensor_name = name;
    
    if (!sensor) {
        health.status_message = "Null sensor pointer";
        return health;
    }
    
    try {
        // Test sensor with multiple readings for stability
        std::vector<double> test_readings;
        const int num_tests = 3;
        
        for (int i = 0; i < num_tests; ++i) {
            auto state = sensor->Read();
            if (state.NrMeasurements() > 0) {
                test_readings.push_back(state.joules(0));
            }
            
            if (i < num_tests - 1) {
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
        
        if (test_readings.size() >= 2) {
            health.is_available = true;
            health.baseline_reading = test_readings.back();
            
            // Check for stability (readings shouldn't vary wildly)
            double variance = calculate_variance(test_readings);
            health.is_stable = variance < 1000.0; // Reasonable threshold for energy readings
            
            if (health.is_stable) {
                health.status_message = "Sensor operational and stable";
            } else {
                health.status_message = "Sensor available but readings are unstable (variance: " + 
                                      std::to_string(variance) + ")";
            }
        } else {
            health.status_message = "Sensor failed to provide sufficient readings";
        }
        
    } catch (const std::exception& e) {
        health.status_message = std::string("Sensor error: ") + e.what();
    }
    
    return health;
}

std::vector<SensorHealth> PMTManager::get_sensor_health() const {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    return sensor_health_;
}

std::vector<std::string> PMTManager::get_available_sensor_names() const {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    std::vector<std::string> available;
    for (size_t i = 0; i < sensor_health_.size(); ++i) {
        if (sensor_health_[i].is_available) {
            available.push_back(sensor_names_[i]);
        }
    }
    return available;
}

std::vector<std::string> PMTManager::get_active_sensor_names() const {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    std::vector<std::string> active;
    for (size_t i = 0; i < sensor_health_.size(); ++i) {
        if (sensor_health_[i].is_available && sensor_health_[i].is_stable) {
            active.push_back(sensor_names_[i]);
        }
    }
    return active;
}

std::unique_ptr<Measurement> PMTManager::collect_measurement() {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    if (!initialized_ || sensors_.empty()) {
        ++failed_measurements_;
        return nullptr;
    }
    
    // Try sensors in priority order (first = highest priority)
    for (size_t i = 0; i < sensors_.size(); ++i) {
        if (!sensor_health_[i].is_available) {
            continue; // Skip unavailable sensors
        }
        
        try {
            auto state = sensors_[i]->Read();
            auto measurement = convert_pmt_state(state, sensor_names_[i]);
            
            if (measurement && measurement->joules >= 0.0) {
                ++successful_measurements_;
                return measurement;
            }
        } catch (const std::exception& e) {
            // Log error but continue trying other sensors
            std::cerr << "Warning: Sensor " << sensor_names_[i] 
                     << " measurement failed: " << e.what() << std::endl;
            
            // Mark sensor as potentially problematic
            sensor_health_[i].is_stable = false;
            sensor_health_[i].status_message = "Recent measurement failure: " + std::string(e.what());
        }
    }
    
    ++failed_measurements_;
    return nullptr; // All sensors failed
}

std::vector<std::unique_ptr<Measurement>> PMTManager::collect_measurements_from_all_sensors() {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    std::vector<std::unique_ptr<Measurement>> measurements;
    
    if (!initialized_) {
        return measurements;
    }
    
    for (size_t i = 0; i < sensors_.size(); ++i) {
        if (!sensor_health_[i].is_available) {
            continue;
        }
        
        try {
            auto state = sensors_[i]->Read();
            auto measurement = convert_pmt_state(state, sensor_names_[i]);
            
            if (measurement) {
                measurements.push_back(std::move(measurement));
            }
        } catch (const std::exception& e) {
            std::cerr << "Warning: Sensor " << sensor_names_[i] 
                     << " measurement failed: " << e.what() << std::endl;
        }
    }
    
    return measurements;
}

bool PMTManager::validate_all_sensors() {
    if (!initialized_) {
        return false;
    }
    
    bool all_valid = true;
    
    for (size_t i = 0; i < sensors_.size(); ++i) {
        SensorHealth health = test_sensor(sensors_[i].get(), sensor_names_[i]);
        sensor_health_[i] = health;
        
        if (!health.is_available) {
            all_valid = false;
        }
    }
    
    return all_valid;
}

SensorHealth PMTManager::validate_sensor(const std::string& sensor_name) {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    auto it = std::find(sensor_names_.begin(), sensor_names_.end(), sensor_name);
    if (it != sensor_names_.end()) {
        size_t index = std::distance(sensor_names_.begin(), it);
        SensorHealth health = test_sensor(sensors_[index].get(), sensor_name);
        sensor_health_[index] = health;
        return health;
    }
    
    SensorHealth not_found;
    not_found.sensor_name = sensor_name;
    not_found.status_message = "Sensor not found";
    return not_found;
}

void PMTManager::remove_failed_sensors() {
    auto it_sensor = sensors_.begin();
    auto it_name = sensor_names_.begin();
    auto it_health = sensor_health_.begin();
    
    while (it_sensor != sensors_.end()) {
        if (!it_health->is_available) {
            it_sensor = sensors_.erase(it_sensor);
            it_name = sensor_names_.erase(it_name);
            it_health = sensor_health_.erase(it_health);
        } else {
            ++it_sensor;
            ++it_name;
            ++it_health;
        }
    }
}

size_t PMTManager::get_active_sensor_count() const {
    std::lock_guard<std::mutex> lock(sensors_mutex_);
    
    return std::count_if(sensor_health_.begin(), sensor_health_.end(),
                        [](const SensorHealth& health) {
                            return health.is_available && health.is_stable;
                        });
}

double PMTManager::calculate_variance(const std::vector<double>& readings) const {
    if (readings.size() < 2) {
        return 0.0;
    }
    
    double mean = std::accumulate(readings.begin(), readings.end(), 0.0) / readings.size();
    double variance = 0.0;
    
    for (double reading : readings) {
        variance += std::pow(reading - mean, 2);
    }
    
    return variance / (readings.size() - 1);
}

std::unique_ptr<Measurement> PMTManager::convert_pmt_state(const pmt::State& state, const std::string& sensor_name) const {
    if (state.NrMeasurements() == 0) {
        return nullptr;
    }
    
    auto measurement = std::make_unique<Measurement>();
    measurement->timestamp = std::chrono::system_clock::now();
    measurement->joules = state.joules(0);
    measurement->watts = state.watts(0);
    measurement->temperature = 0.0; // Not all sensors provide temperature
    measurement->source = sensor_name;
    
    return measurement;
}

void PMTManager::log_sensor_status() const {
    std::cout << "📊 PMT Sensor Status:" << std::endl;
    
    size_t working = 0, disabled = 0, failed = 0;
    
    for (const auto& health : sensor_health_) {
        if (health.is_available && health.is_stable) {
            ++working;
        } else if (health.is_available) {
            ++disabled;
        } else {
            ++failed;
        }
    }
    
    std::cout << "  ✅ Working sensors: " << working << std::endl;
    std::cout << "  ⚠️  Runtime disabled: " << disabled << std::endl;
    std::cout << "  ❌ Failed sensors: " << failed << std::endl;
    
    if (working > 0) {
        std::cout << "  🎯 Primary sensors: ";
        bool first = true;
        for (size_t i = 0; i < sensor_health_.size(); ++i) {
            if (sensor_health_[i].is_available && sensor_health_[i].is_stable) {
                if (!first) std::cout << ", ";
                std::cout << sensor_names_[i];
                first = false;
            }
        }
        std::cout << std::endl;
    }
    
    std::cout << std::endl;
    std::cout << "💡 Smart behavior:" << std::endl;
    std::cout << "   - Working sensors will be used for measurements" << std::endl;
    std::cout << "   - Runtime disabled sensors will be automatically skipped" << std::endl;
    std::cout << "   - Failed sensors will show clear error messages" << std::endl;
}

// PMTManagerGuard implementation
PMTManagerGuard::PMTManagerGuard(const PMTConfiguration& config) : initialized_(false) {
    auto& manager = PMTManager::get_instance();
    
    if (config.preferred_sensors.empty()) {
        initialized_ = manager.initialize_from_config();
    } else {
        initialized_ = manager.initialize(config);
    }
    
    if (!initialized_) {
        error_message_ = "Failed to initialize PMT Manager";
    }
}

PMTManagerGuard::~PMTManagerGuard() {
    // PMT Manager will clean up automatically when singleton is destroyed
    // or can be explicitly cleaned up if needed
}

} // namespace codegreen