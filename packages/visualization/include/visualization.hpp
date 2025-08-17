#pragma once

#include <string>
#include <vector>
#include <memory>
#include "core/measurement_session.hpp"

namespace codegreen {

/// Main visualization class for energy data visualization
class Visualization {
public:
    Visualization();
    ~Visualization() = default;

    /// Generate energy consumption charts
    bool generate_charts(const MeasurementSession& session);

    /// Generate energy reports
    std::string generate_report(const MeasurementSession& session);

    /// Export data to various formats
    bool export_data(const MeasurementSession& session, const std::string& format);

    /// Set chart type
    void set_chart_type(const std::string& chart_type);

private:
    std::string chart_type_;
};

} // namespace codegreen
