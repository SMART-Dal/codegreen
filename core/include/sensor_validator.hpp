#pragma once

#include <string>
#include <vector>
#include <memory>
#include <chrono>

// Forward declaration to avoid circular dependencies
namespace pmt {
    class PMT;
}

namespace codegreen {

/// Sensor health status and validation results
struct SensorHealth {
    bool is_available = false;
    bool is_stable = false;
    std::string status_message;
    double baseline_reading = 0.0;
    double variance = 0.0;
    int successful_readings = 0;
    int total_readings = 0;
    std::chrono::milliseconds response_time{0};
};

/// Interface for sensor validation
class SensorValidator {
public:
    virtual ~SensorValidator() = default;
    
    /// Validate a sensor's health and stability
    virtual SensorHealth validate_sensor() = 0;
    
    /// Get sensor name/type
    virtual std::string get_sensor_name() const = 0;
    
    /// Check if sensor is fundamentally broken (not just temporarily unavailable)
    virtual bool is_fundamentally_broken() const = 0;
    
    /// Get detailed error information
    virtual std::string get_error_details() const = 0;
};

/// PMT-specific sensor validator
class PMTSensorValidator : public SensorValidator {
public:
    explicit PMTSensorValidator(const std::string& sensor_name, 
                               std::unique_ptr<pmt::PMT> sensor);
    
    SensorHealth validate_sensor() override;
    std::string get_sensor_name() const override { return sensor_name_; }
    bool is_fundamentally_broken() const override;
    std::string get_error_details() const override;

private:
    std::string sensor_name_;
    std::unique_ptr<pmt::PMT> sensor_;
    std::string last_error_;
    bool fundamental_failure_ = false;
    
    /// Calculate variance of readings
    double calculate_variance(const std::vector<double>& readings) const;
    
    /// Test sensor with multiple readings
    std::vector<double> perform_stability_test(int num_readings = 5);
    
    /// Check if sensor can provide basic functionality
    bool test_basic_functionality();
};

/// Factory function to create appropriate validator
std::unique_ptr<SensorValidator> CreateSensorValidator(const std::string& sensor_type, 
                                                      std::unique_ptr<pmt::PMT> sensor);

} // namespace codegreen
