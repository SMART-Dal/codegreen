#pragma once

#include <string>
#include <unordered_map>
#include <chrono>
#include "measurement.hpp"

namespace codegreen {

/// Represents a measurement session with start and end measurements
class MeasurementSession {
public:
    MeasurementSession();
    ~MeasurementSession() = default;

    // Add a start measurement
    void add_start_measurement(const std::string& source, const Measurement& measurement);

    // Add an end measurement
    void add_end_measurement(const std::string& source, const Measurement& measurement);

    // Get the duration of the measurement session
    std::chrono::duration<double> get_duration() const;

    // Get the total energy consumption
    double get_total_energy() const;

    // Get all measurements for a specific source
    std::pair<Measurement, Measurement> get_measurements(const std::string& source) const;

private:
    // Calculate total energy consumption
    void calculate_total_energy();

    std::unordered_map<std::string, Measurement> start_measurements_;
    std::unordered_map<std::string, Measurement> end_measurements_;
    std::chrono::system_clock::time_point start_;
    std::chrono::system_clock::time_point end_;
    std::chrono::duration<double> duration_;
    double total_energy_;
};

} // namespace codegreen
