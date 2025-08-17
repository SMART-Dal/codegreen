#pragma once

#include <string>
#include <chrono>

namespace codegreen {

/// Represents a single energy measurement
struct Measurement {
    std::string source;           // Source of the measurement
    double joules;                // Energy consumption in joules
    double watts;                 // Power consumption in watts
    double temperature;           // Temperature in Celsius
    std::chrono::system_clock::time_point timestamp; // When the measurement was taken

    Measurement() : joules(0.0), watts(0.0), temperature(0.0) {}
    
    Measurement(const std::string& src, double j, double w, double temp)
        : source(src), joules(j), watts(w), temperature(temp), 
          timestamp(std::chrono::system_clock::now()) {}
};

} // namespace codegreen
