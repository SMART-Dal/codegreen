#include "sensor_validator.hpp"
#include <pmt.h>
#include <pmt/common/PMT.h>
#include <iostream>
#include <algorithm>
#include <numeric>
#include <cmath>
#include <thread>
#include <chrono>

namespace codegreen {

PMTSensorValidator::PMTSensorValidator(const std::string& sensor_name, 
                                       std::unique_ptr<pmt::PMT> sensor)
    : sensor_name_(sensor_name), sensor_(std::move(sensor)) {
}

SensorHealth PMTSensorValidator::validate_sensor() {
    SensorHealth health;
    health.total_readings = 5; // We'll test with 5 readings
    
    try {
        // Test 1: Basic functionality
        if (!test_basic_functionality()) {
            health.status_message = "Sensor failed basic functionality test";
            fundamental_failure_ = true;
            return health;
        }
        
        // Test 2: Stability test with multiple readings
        auto test_readings = perform_stability_test(5);
        
        if (test_readings.size() < 3) {
            health.status_message = "Sensor failed to provide consistent readings";
            fundamental_failure_ = true;
            return health;
        }
        
        health.successful_readings = static_cast<int>(test_readings.size());
        health.is_available = true;
        health.baseline_reading = test_readings.back();
        
        // Calculate variance for stability assessment
        health.variance = calculate_variance(test_readings);
        
        // Determine stability based on variance and sensor type
        double stability_threshold = 1000.0; // Base threshold in Joules
        
        // Adjust threshold based on sensor type
        if (sensor_name_ == "rapl") {
            stability_threshold = 100.0; // RAPL is usually very stable
        } else if (sensor_name_ == "nvml" || sensor_name_ == "amdsmi") {
            stability_threshold = 500.0; // GPU sensors can have some variance
        } else if (sensor_name_ == "powersensor3" || sensor_name_ == "powersensor2") {
            stability_threshold = 2000.0; // External sensors may have more variance
        }
        
        health.is_stable = health.variance < stability_threshold;
        
        if (health.is_stable) {
            health.status_message = "Sensor operational and stable";
        } else {
            health.status_message = "Sensor available but readings are unstable (variance: " + 
                                   std::to_string(static_cast<int>(health.variance)) + ")";
        }
        
    } catch (const std::exception& e) {
        last_error_ = e.what();
        health.status_message = "Sensor error: " + last_error_;
        fundamental_failure_ = true;
    }
    
    return health;
}

bool PMTSensorValidator::is_fundamentally_broken() const {
    return fundamental_failure_;
}

std::string PMTSensorValidator::get_error_details() const {
    return last_error_;
}

bool PMTSensorValidator::test_basic_functionality() {
    try {
        // Test 1: Can we create a sensor?
        if (!sensor_) {
            last_error_ = "Sensor object is null";
            return false;
        }
        
        // Test 2: Can we read from the sensor?
        auto state = sensor_->Read();
        if (state.NrMeasurements() == 0) {
            last_error_ = "Sensor returned no measurements";
            return false;
        }
        
        // Test 3: Are the readings reasonable?
        auto joules = state.joules(0);
        auto watts = state.watts(0);
        
        // Basic sanity checks
        if (joules < 0 || watts < 0) {
            last_error_ = "Sensor returned negative values (joules: " + std::to_string(joules) + 
                         ", watts: " + std::to_string(watts) + ")";
            return false;
        }
        
        // Check for unreasonably high values (likely sensor malfunction)
        if (joules > 1e12 || watts > 1e9) { // 1 TJ or 1 GW
            last_error_ = "Sensor returned unreasonably high values (joules: " + std::to_string(joules) + 
                         ", watts: " + std::to_string(watts) + ")";
            return false;
        }
        
        return true;
        
    } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
    }
}

std::vector<double> PMTSensorValidator::perform_stability_test(int num_readings) {
    std::vector<double> readings;
    
    for (int i = 0; i < num_readings; ++i) {
        try {
            auto start_time = std::chrono::high_resolution_clock::now();
            
            auto state = sensor_->Read();
            if (state.NrMeasurements() > 0) {
                readings.push_back(state.joules(0));
            }
            
            auto end_time = std::chrono::high_resolution_clock::now();
            auto response_time = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
            
            // Small delay between readings to avoid overwhelming the sensor
            if (i < num_readings - 1) {
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            
        } catch (const std::exception& e) {
            last_error_ = e.what();
            break; // Stop testing if sensor fails
        }
    }
    
    return readings;
}

double PMTSensorValidator::calculate_variance(const std::vector<double>& readings) const {
    if (readings.size() < 2) return 0.0;
    
    // Calculate mean
    double sum = std::accumulate(readings.begin(), readings.end(), 0.0);
    double mean = sum / readings.size();
    
    // Calculate variance
    double variance = 0.0;
    for (double reading : readings) {
        variance += std::pow(reading - mean, 2);
    }
    variance /= readings.size();
    
    return variance;
}

std::unique_ptr<SensorValidator> CreateSensorValidator(const std::string& sensor_type, 
                                                      std::unique_ptr<pmt::PMT> sensor) {
    if (sensor_type == "pmt" || sensor_type.empty()) {
        return std::make_unique<PMTSensorValidator>(sensor_type, std::move(sensor));
    }
    
    // Future: Add other sensor types
    std::cerr << "Unknown sensor type: " << sensor_type << ", falling back to PMT validator" << std::endl;
    return std::make_unique<PMTSensorValidator>(sensor_type, std::move(sensor));
}

} // namespace codegreen
