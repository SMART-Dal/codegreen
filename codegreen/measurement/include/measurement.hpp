#pragma once

#include <string>
#include <chrono>
#include <map>
#include <vector>

namespace codegreen {

/// Represents a single energy measurement with detailed component breakdown
struct Measurement {
    std::string source;           // Source of the measurement
    double joules;                // Total energy consumption in joules
    double watts;                 // Total power consumption in watts
    double temperature;           // Temperature in Celsius
    std::chrono::system_clock::time_point timestamp; // When the measurement was taken
    
    // Enhanced fields for NEMB quality preservation
    std::map<std::string, double> component_joules;    // Per-component energy breakdown (package, core, dram, etc.)
    std::map<std::string, double> component_watts;     // Per-component power breakdown
    std::string sensor_name;                           // Specific sensor/provider name
    std::string measurement_type;                      // Type of measurement (differential, absolute, etc.)
    double duration_seconds{0.0};                     // Duration of measurement
    double uncertainty_percent{0.0};                  // Measurement uncertainty
    double confidence{1.0};                           // Measurement confidence (0-1)
    bool valid{true};                                  // Whether measurement is valid
    std::string error_message;                         // Error details if invalid
    
    // Provider-specific metadata
    std::vector<std::string> active_providers;        // List of active measurement providers
    std::map<std::string, std::string> provider_metadata; // Provider-specific information

    Measurement() : joules(0.0), watts(0.0), temperature(0.0) {}
    
    Measurement(const std::string& src, double j, double w, double temp)
        : source(src), joules(j), watts(w), temperature(temp), 
          timestamp(std::chrono::system_clock::now()) {}
};

} // namespace codegreen
