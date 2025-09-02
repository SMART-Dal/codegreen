#pragma once

#include "measurement.hpp"
#include "adapters/language_adapter.hpp"
#include "energy_storage.hpp"
#include <memory>
#include <vector>
#include <chrono>
#include <unordered_map>
#include <mutex>

/// Forward declarations for PMT library
namespace pmt { class PMT; class State; }

namespace codegreen {

/// Forward declarations 
class EnergyStorage;

/// Source line energy mapping for fine-grained attribution
struct SourceLineEnergy {
    size_t line_number;
    std::string line_content;
    double total_energy_joules = 0.0;
    size_t execution_count = 0;
    double avg_energy_per_execution = 0.0;
    std::vector<std::string> associated_checkpoints;
};

/// Represents a timed checkpoint measurement with energy correlation
struct TimedCheckpoint {
    CodeCheckpoint checkpoint;
    std::chrono::system_clock::time_point timestamp;
    std::unique_ptr<Measurement> energy_before;
    std::unique_ptr<Measurement> energy_after;
    double energy_consumed_joules = 0.0;
    double power_consumed_watts = 0.0;
    double duration_seconds = 0.0;
    bool has_energy_data = false;
    
    // Enhanced source mapping
    std::vector<size_t> source_lines_covered;  // Lines this checkpoint covers
    std::string original_source_context;       // Original source code context
};

/// Represents a complete measurement session with fine-grained energy data
struct EnergyMeasurementSession {
    std::string session_id;
    std::string source_file_path;
    std::string language;
    std::chrono::system_clock::time_point start_time;
    std::chrono::system_clock::time_point end_time;
    std::vector<std::unique_ptr<TimedCheckpoint>> checkpoints;
    double total_energy_joules = 0.0;
    double average_power_watts = 0.0;
    double peak_power_watts = 0.0;
    
    // Enhanced source-level energy tracking
    std::unordered_map<size_t, SourceLineEnergy> line_energy_map;  // Line → Energy mapping
    std::vector<std::string> original_source_lines;               // Original source code
    
    /// Get energy breakdown by function/method
    std::unordered_map<std::string, double> get_function_energy_breakdown() const;
    
    /// Get energy breakdown by checkpoint type
    std::unordered_map<std::string, double> get_type_energy_breakdown() const;
    
    /// Get energy breakdown by source line
    std::unordered_map<size_t, double> get_line_energy_breakdown() const;
    
    /// Get most energy-consuming source lines
    std::vector<std::pair<size_t, double>> get_top_energy_lines(size_t count = 10) const;
    
    /// Get most energy-intensive checkpoints
    std::vector<const TimedCheckpoint*> get_top_energy_consumers(size_t count = 10) const;
};

/// Core class responsible for mapping energy measurements to code checkpoints
class EnergyCodeMapper {
public:
    explicit EnergyCodeMapper(std::unique_ptr<EnergyStorage> storage = nullptr);
    ~EnergyCodeMapper();

    /// Start a new measurement session
    std::string start_session(const std::string& source_file_path, 
                             const std::string& language);

    /// Record a checkpoint during execution
    bool record_checkpoint(const std::string& session_id, 
                          const CodeCheckpoint& checkpoint);

    /// End measurement session and finalize energy calculations
    std::unique_ptr<EnergyMeasurementSession> end_session(const std::string& session_id);

    /// Add PMT sensor for energy measurement
    bool add_pmt_sensor(std::unique_ptr<pmt::PMT> sensor, const std::string& sensor_name);

    /// Get current energy measurement from all sensors
    std::unique_ptr<Measurement> get_current_energy_measurement();

    /// Generate detailed energy report
    std::string generate_energy_report(const EnergyMeasurementSession& session);

    /// Export session data to various formats
    bool export_session_csv(const EnergyMeasurementSession& session, const std::string& filepath);
    bool export_session_json(const EnergyMeasurementSession& session, const std::string& filepath);

private:
    std::unique_ptr<EnergyStorage> storage_;
    
    // Active measurement sessions
    std::unordered_map<std::string, std::unique_ptr<EnergyMeasurementSession>> active_sessions_;
    
    // PMT sensors for energy measurement
    std::vector<std::unique_ptr<pmt::PMT>> pmt_sensors_;
    std::vector<std::string> sensor_names_;
    
    // Thread safety
    std::mutex session_mutex_;
    std::mutex sensor_mutex_;
    
    // Runtime overhead compensation data
    std::unordered_map<std::string, double> language_overheads_;  // language -> baseline overhead (J)
    std::unordered_map<std::string, std::unordered_map<std::string, double>> checkpoint_overheads_;  // language -> {checkpoint_type -> overhead}
    bool overhead_calibrated_ = false;
    
    // Statistical filtering configuration
    static constexpr double STATISTICAL_NOISE_THRESHOLD_MS = 1.0;  // 1 ms
    static constexpr size_t MIN_MEASUREMENTS_FOR_STATISTICS = 5;
    static constexpr double OUTLIER_THRESHOLD_SIGMA = 2.5;  // 2.5 standard deviations
    
    /// Generate unique session ID
    std::string generate_session_id() const;
    
    /// Correlate energy measurements with checkpoints
    void correlate_energy_measurements(EnergyMeasurementSession& session);
    
    /// Calculate energy deltas between checkpoints
    void calculate_energy_deltas(EnergyMeasurementSession& session);
    
    /// Aggregate energy data by functions/types
    void aggregate_energy_data(EnergyMeasurementSession& session);
    
    /// Helper to get energy measurement from PMT sensors
    std::unique_ptr<Measurement> collect_pmt_measurements();
    
    /// Get estimated instrumentation overhead for a language
    double get_instrumentation_overhead(const std::string& language, 
                                       const std::string& checkpoint_type) const;
    
    /// Calibrate runtime overhead for different languages
    void calibrate_runtime_overhead(const std::string& language);
    
    /// Apply runtime overhead compensation to energy measurements
    void apply_overhead_compensation(EnergyMeasurementSession& session);
    
    /// Apply statistical filtering for noise reduction
    void apply_statistical_filtering(EnergyMeasurementSession& session);
    
    /// Calculate moving average for energy measurements
    double calculate_moving_average_energy(const std::vector<double>& recent_measurements, 
                                         size_t window_size = 5) const;
    
    /// Detect and handle measurement outliers
    bool is_measurement_outlier(double measurement, const std::vector<double>& baseline_measurements) const;
    
    /// Load original source code for energy mapping
    void load_original_source_code(EnergyMeasurementSession& session);
    
    /// Build source-line to energy mapping
    void build_source_energy_mapping(EnergyMeasurementSession& session);
    
    /// Validate session exists and return reference
    EnergyMeasurementSession* get_session(const std::string& session_id);
};

/// Factory function to create energy-code mapper with auto-configured storage
std::unique_ptr<EnergyCodeMapper> CreateEnergyCodeMapper(const std::string& storage_type = "sqlite");

/// Utility functions for energy analysis
namespace energy_analysis {
    /// Find energy hotspots in code
    std::vector<std::string> find_energy_hotspots(const EnergyMeasurementSession& session, 
                                                  double threshold_percentage = 10.0);
    
    /// Compare two measurement sessions
    struct SessionComparison {
        double energy_difference_joules;
        double power_difference_watts;
        double time_difference_seconds;
        std::vector<std::string> performance_insights;
    };
    
    SessionComparison compare_sessions(const EnergyMeasurementSession& session1,
                                      const EnergyMeasurementSession& session2);
    
    /// Generate optimization suggestions based on energy patterns
    std::vector<std::string> generate_optimization_suggestions(const EnergyMeasurementSession& session);
}

} // namespace codegreen