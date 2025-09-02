#include "prometheus_exporter.hpp"
#include <sstream>
#include <iomanip>
#include <regex>
#include <thread>
#include <future>

namespace codegreen {

PrometheusExporter::PrometheusExporter(int port) 
    : server_port_(port), server_running_(false) {}

bool PrometheusExporter::export_session_metrics(const EnergyMeasurementSession& session) {
    auto session_metrics = convert_session_to_metrics(session);
    
    for (const auto& metric : session_metrics) {
        add_metric(metric);
    }
    
    return true;
}

bool PrometheusExporter::export_realtime_metrics(const std::vector<TimedCheckpoint>& checkpoints) {
    std::string session_id = "realtime_" + std::to_string(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count());
    
    for (const auto& checkpoint : checkpoints) {
        auto metric = convert_checkpoint_to_metric(checkpoint, session_id);
        add_metric(metric);
    }
    
    return true;
}

bool PrometheusExporter::start_metrics_server() {
    if (server_running_) {
        return true;
    }
    
    // Simple HTTP server implementation for Prometheus scraping endpoint
    // In production, consider using a proper HTTP library like cpp-httplib
    server_running_ = true;
    
    std::thread server_thread([this]() {
        // Simplified server implementation
        // This would normally bind to port and serve HTTP requests
        while (server_running_) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    });
    
    server_thread.detach();
    return true;
}

void PrometheusExporter::stop_metrics_server() {
    server_running_ = false;
}

std::string PrometheusExporter::generate_prometheus_output() const {
    std::ostringstream output;
    
    // Group metrics by name for proper Prometheus format
    std::unordered_map<std::string, std::vector<const PrometheusMetric*>> grouped_metrics;
    
    for (const auto& metric : metrics_) {
        grouped_metrics[metric.name].push_back(&metric);
    }
    
    for (const auto& [name, metric_group] : grouped_metrics) {
        if (!metric_group.empty()) {
            // Add HELP and TYPE declarations
            output << "# HELP " << name << " " << metric_group[0]->help << "\n";
            output << "# TYPE " << name << " " << metric_group[0]->type << "\n";
            
            // Add metric values
            for (const auto* metric : metric_group) {
                output << format_metric(*metric) << "\n";
            }
            output << "\n";
        }
    }
    
    return output.str();
}

bool PrometheusExporter::write_metrics_file(const std::string& file_path) const {
    std::ofstream file(file_path);
    if (!file.is_open()) {
        return false;
    }
    
    file << generate_prometheus_output();
    file.close();
    
    return true;
}

void PrometheusExporter::add_metric(const PrometheusMetric& metric) {
    metrics_.push_back(metric);
}

void PrometheusExporter::clear_metrics() {
    metrics_.clear();
}

std::vector<PrometheusMetric> PrometheusExporter::convert_session_to_metrics(const EnergyMeasurementSession& session) {
    std::vector<PrometheusMetric> metrics;
    
    // Session-level metrics
    PrometheusMetric total_energy_metric;
    total_energy_metric.name = "codegreen_session_total_energy_joules";
    total_energy_metric.type = "gauge";
    total_energy_metric.help = "Total energy consumption for the session in joules";
    total_energy_metric.labels["session_id"] = session.get_session_id();
    total_energy_metric.labels["language"] = session.get_language();
    total_energy_metric.value = session.get_total_energy();
    total_energy_metric.timestamp = std::chrono::system_clock::now();
    metrics.push_back(total_energy_metric);
    
    PrometheusMetric duration_metric;
    duration_metric.name = "codegreen_session_duration_seconds";
    duration_metric.type = "gauge";
    duration_metric.help = "Session duration in seconds";
    duration_metric.labels["session_id"] = session.get_session_id();
    duration_metric.labels["language"] = session.get_language();
    duration_metric.value = std::chrono::duration<double>(session.get_duration()).count();
    duration_metric.timestamp = std::chrono::system_clock::now();
    metrics.push_back(duration_metric);
    
    // Checkpoint-level metrics
    auto checkpoints = session.get_checkpoints();
    for (const auto& checkpoint : checkpoints) {
        auto checkpoint_metric = convert_checkpoint_to_metric(checkpoint, session.get_session_id());
        metrics.push_back(checkpoint_metric);
    }
    
    return metrics;
}

PrometheusMetric PrometheusExporter::convert_checkpoint_to_metric(const TimedCheckpoint& checkpoint, 
                                                                const std::string& session_id) {
    PrometheusMetric metric;
    
    metric.name = "codegreen_checkpoint_energy_joules";
    metric.type = "gauge";
    metric.help = "Energy consumption at checkpoint in joules";
    
    // Generate labels from checkpoint context
    metric.labels = generate_labels(checkpoint, session_id);
    
    metric.value = checkpoint.energy_consumed_joules;
    metric.timestamp = checkpoint.timestamp;
    
    return metric;
}

std::unordered_map<std::string, std::string> PrometheusExporter::generate_labels(const TimedCheckpoint& checkpoint,
                                                                               const std::string& session_id) {
    std::unordered_map<std::string, std::string> labels;
    
    labels["session_id"] = session_id;
    labels["checkpoint_type"] = checkpoint.checkpoint.type;
    labels["file_path"] = checkpoint.checkpoint.file_path;
    labels["function_name"] = checkpoint.checkpoint.function_name;
    labels["line_number"] = std::to_string(checkpoint.checkpoint.line_number);
    labels["column_number"] = std::to_string(checkpoint.checkpoint.column_number);
    
    return labels;
}

std::string PrometheusExporter::sanitize_metric_name(const std::string& name) const {
    std::regex invalid_chars("[^a-zA-Z0-9_:]");
    std::string sanitized = std::regex_replace(name, invalid_chars, "_");
    
    // Ensure metric name starts with letter or underscore
    if (!sanitized.empty() && !std::isalpha(sanitized[0]) && sanitized[0] != '_') {
        sanitized = "_" + sanitized;
    }
    
    return sanitized;
}

std::string PrometheusExporter::format_metric(const PrometheusMetric& metric) const {
    std::ostringstream formatted;
    
    formatted << metric.name;
    
    // Add labels if any exist
    if (!metric.labels.empty()) {
        formatted << "{";
        bool first = true;
        for (const auto& [key, value] : metric.labels) {
            if (!first) {
                formatted << ",";
            }
            formatted << key << "=\"" << value << "\"";
            first = false;
        }
        formatted << "}";
    }
    
    // Add value with proper precision
    formatted << " " << std::fixed << std::setprecision(6) << metric.value;
    
    // Add timestamp (optional for Prometheus)
    auto timestamp_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        metric.timestamp.time_since_epoch()).count();
    formatted << " " << timestamp_ms;
    
    return formatted.str();
}

std::unique_ptr<PrometheusExporter> CreatePrometheusExporter(int port) {
    return std::make_unique<PrometheusExporter>(port);
}

} // namespace codegreen