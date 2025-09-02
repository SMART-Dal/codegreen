#pragma once

#include <string>
#include <vector>
#include <memory>
#include "measurement_session.hpp"

namespace codegreen {

/// Main instrumenter class for code instrumentation
class Instrumenter {
public:
    Instrumenter();
    ~Instrumenter() = default;

    /// Instrument code for energy monitoring
    std::string instrument_code(const std::string& source_code, const std::string& language);

    /// Start monitoring a process
    std::unique_ptr<MeasurementSession> start_monitoring(int process_id);

    /// Stop monitoring a process
    std::unique_ptr<MeasurementSession> stop_monitoring(std::unique_ptr<MeasurementSession> session);

    /// Get instrumentation metrics
    std::vector<std::pair<std::string, double>> get_metrics() const;

private:
    std::vector<std::pair<std::string, double>> metrics_;
};

} // namespace codegreen
