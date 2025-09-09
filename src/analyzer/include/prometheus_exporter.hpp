#pragma once

#include <string>
#include <unordered_map>
#include <vector>
#include <chrono>
#include <fstream>
#include <memory>
#include "energy_code_mapper.hpp"

namespace codegreen {

/// Prometheus metrics data structure
struct PrometheusMetric {
    std::string name;
    std::string type;  // counter, gauge, histogram, summary
    std::string help;
    std::unordered_map<std::string, std::string> labels;
    double value;
    std::chrono::system_clock::time_point timestamp;
};

/// Prometheus metrics exporter for CodeGreen energy measurements
class PrometheusExporter {
public:
    PrometheusExporter(int port = 8080);
    ~PrometheusExporter() = default;

    /// Export energy session to Prometheus format
    bool export_session_metrics(const EnergyMeasurementSession& session);
    
    /// Export real-time energy metrics
    bool export_realtime_metrics(const std::vector<TimedCheckpoint>& checkpoints);
    
    /// Start Prometheus HTTP server for metrics scraping
    bool start_metrics_server();
    
    /// Stop Prometheus HTTP server
    void stop_metrics_server();
    
    /// Generate Prometheus text format output
    std::string generate_prometheus_output() const;
    
    /// Write metrics to file (for file-based scraping)
    bool write_metrics_file(const std::string& file_path) const;
    
    /// Add custom metric
    void add_metric(const PrometheusMetric& metric);
    
    /// Clear all metrics
    void clear_metrics();

private:
    int server_port_;
    bool server_running_;
    std::vector<PrometheusMetric> metrics_;
    
    /// Convert energy measurement to Prometheus metrics
    std::vector<PrometheusMetric> convert_session_to_metrics(const EnergyMeasurementSession& session);
    
    /// Convert checkpoint to Prometheus metric
    PrometheusMetric convert_checkpoint_to_metric(const TimedCheckpoint& checkpoint, 
                                                const std::string& session_id);
    
    /// Generate metric labels from checkpoint context
    std::unordered_map<std::string, std::string> generate_labels(const TimedCheckpoint& checkpoint,
                                                               const std::string& session_id);
    
    /// Sanitize metric name for Prometheus format
    std::string sanitize_metric_name(const std::string& name) const;
    
    /// Format metric for Prometheus text output
    std::string format_metric(const PrometheusMetric& metric) const;
};

/// Factory function to create Prometheus exporter
std::unique_ptr<PrometheusExporter> CreatePrometheusExporter(int port = 8080);

} // namespace codegreen