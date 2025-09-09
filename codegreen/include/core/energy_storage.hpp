#pragma once

#include "measurement.hpp"
#include <sqlite3.h>
#include <string>
#include <vector>
#include <memory>
#include <chrono>

namespace codegreen {

/// Energy storage interface for persistent data storage
class EnergyStorage {
public:
    virtual ~EnergyStorage() = default;
    
    /// Store energy measurement data
    virtual bool store_measurement(const Measurement& measurement) = 0;
    
    /// Store a complete measurement session
    virtual bool store_session(const std::string& session_id, 
                             const std::vector<Measurement>& measurements,
                             const std::string& code_version = "",
                             const std::string& file_path = "") = 0;
    
    /// Retrieve measurements for a specific session
    virtual std::vector<Measurement> get_session_measurements(const std::string& session_id) = 0;
    
    /// Get all sessions for comparison
    virtual std::vector<std::string> get_all_sessions() = 0;
    
    /// Get energy consumption summary for a session
    virtual struct EnergySummary get_session_summary(const std::string& session_id) = 0;
    
    /// Compare two sessions
    virtual struct ComparisonResult compare_sessions(const std::string& session1, 
                                                   const std::string& session2) = 0;
    
    /// Export data to CSV format
    virtual bool export_to_csv(const std::string& filepath, const std::string& session_id = "") = 0;
};

/// Energy consumption summary for a session
struct EnergySummary {
    std::string session_id;
    std::string code_version;
    std::string file_path;
    std::chrono::system_clock::time_point start_time;
    std::chrono::system_clock::time_point end_time;
    double total_joules;
    double average_watts;
    double peak_watts;
    size_t checkpoint_count;
    double duration_seconds;
};

/// Comparison result between two sessions
struct ComparisonResult {
    std::string session1_id;
    std::string session2_id;
    double energy_difference_joules;  // session2 - session1
    double power_difference_watts;    // session2 - session1
    double time_difference_seconds;   // session2 - session1
    double efficiency_improvement;    // percentage improvement
    std::vector<std::string> insights;
};

/// SQLite implementation of energy storage
class SQLiteEnergyStorage : public EnergyStorage {
public:
    explicit SQLiteEnergyStorage(const std::string& db_path = "energy_data.db");
    ~SQLiteEnergyStorage() override;
    
    // EnergyStorage interface implementation
    bool store_measurement(const Measurement& measurement) override;
    bool store_session(const std::string& session_id, 
                      const std::vector<Measurement>& measurements,
                      const std::string& code_version = "",
                      const std::string& file_path = "") override;
    std::vector<Measurement> get_session_measurements(const std::string& session_id) override;
    std::vector<std::string> get_all_sessions() override;
    EnergySummary get_session_summary(const std::string& session_id) override;
    ComparisonResult compare_sessions(const std::string& session1, 
                                    const std::string& session2) override;
    
    /// Initialize database tables
    bool initialize_database();
    
    /// Export data for Grafana/other tools
    bool export_to_csv(const std::string& filepath, const std::string& session_id = "");
    
    /// Get database path
    std::string get_database_path() const { return db_path_; }
    
    /// Store measurements in batch for better performance
    bool store_measurements_batch(const std::string& session_id, const std::vector<Measurement>& measurements);

private:
    std::string db_path_;
    sqlite3* db_handle_;  // SQLite database handle
    
    /// Create tables if they don't exist
    bool create_tables();
    
    /// Helper to execute SQL statements
    bool execute_statement(const std::string& sql);
};

/// Factory function to create energy storage
std::unique_ptr<EnergyStorage> CreateEnergyStorage(const std::string& type = "sqlite", 
                                                  const std::string& path = "");

} // namespace codegreen
