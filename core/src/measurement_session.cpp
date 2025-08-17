#include "measurement_session.hpp"
#include <algorithm>

namespace codegreen {

MeasurementSession::MeasurementSession()
    : start_(std::chrono::system_clock::now()),
      end_(std::chrono::system_clock::now()),
      duration_(0.0),
      total_energy_(0.0) {
}

void MeasurementSession::add_start_measurement(const std::string& source, const Measurement& measurement) {
    start_measurements_[source] = measurement;
}

void MeasurementSession::add_end_measurement(const std::string& source, const Measurement& measurement) {
    end_measurements_[source] = measurement;
    end_ = measurement.timestamp;
    
    auto duration = std::chrono::duration_cast<std::chrono::duration<double>>(end_ - start_);
    duration_ = duration;
    
    calculate_total_energy();
}

std::chrono::duration<double> MeasurementSession::get_duration() const {
    return duration_;
}

double MeasurementSession::get_total_energy() const {
    return total_energy_;
}

std::pair<Measurement, Measurement> MeasurementSession::get_measurements(const std::string& source) const {
    auto start_it = start_measurements_.find(source);
    auto end_it = end_measurements_.find(source);
    
    if (start_it != start_measurements_.end() && end_it != end_measurements_.end()) {
        return {start_it->second, end_it->second};
    }
    
    // Return default measurements if not found
    return {Measurement{}, Measurement{}};
}

void MeasurementSession::calculate_total_energy() {
    total_energy_ = 0.0;
    
    for (const auto& [source, end_measurement] : end_measurements_) {
        auto start_it = start_measurements_.find(source);
        if (start_it != start_measurements_.end()) {
            total_energy_ += end_measurement.joules - start_it->second.joules;
        }
    }
}

} // namespace codegreen
