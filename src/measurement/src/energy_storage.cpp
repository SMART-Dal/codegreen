#include "energy_storage.hpp"
#include <sqlite3.h>
#include <iostream>
#include <sstream>
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <set>
#include <cctype>

namespace codegreen {

SQLiteEnergyStorage::SQLiteEnergyStorage(const std::string& db_path) 
    : db_path_(db_path), db_handle_(nullptr) {
    initialize_database();
}

SQLiteEnergyStorage::~SQLiteEnergyStorage() {
    if (db_handle_) {
        sqlite3_close(static_cast<sqlite3*>(db_handle_));
    }
}

bool SQLiteEnergyStorage::initialize_database() {
    if (sqlite3_open(db_path_.c_str(), &db_handle_) != SQLITE_OK) {
        std::cerr << "Failed to open SQLite database: " << db_path_ << std::endl;
        return false;
    }
    
    return create_tables();
}

bool SQLiteEnergyStorage::create_tables() {
    // Enhanced sessions table with metadata for advanced reporting
    const char* create_sessions_sql = R"(
        CREATE TABLE IF NOT EXISTS measurement_sessions (
            session_id TEXT PRIMARY KEY,
            code_version TEXT,
            file_path TEXT,
            language TEXT,
            framework TEXT,
            hardware_info TEXT,
            start_time TEXT,
            end_time TEXT,
            total_joules REAL,
            average_watts REAL,
            peak_watts REAL,
            min_watts REAL,
            checkpoint_count INTEGER,
            duration_seconds REAL,
            cpu_utilization REAL,
            memory_usage_mb REAL,
            git_commit_hash TEXT,
            build_flags TEXT,
            environment_variables TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    )";
    
    // Enhanced measurements table with detailed metrics
    const char* create_measurements_sql = R"(
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            source TEXT,
            joules REAL,
            watts REAL,
            temperature REAL,
            timestamp TEXT,
            checkpoint_id TEXT,
            checkpoint_type TEXT,
            function_name TEXT,
            line_number INTEGER,
            column_number INTEGER,
            file_path TEXT,
            context TEXT,
            duration_ms REAL,
            cpu_time_ms REAL,
            memory_delta_mb REAL,
            sensor_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES measurement_sessions(session_id)
        );
    )";
    
    // Additional reporting tables for dashboard analytics
    const char* create_aggregated_stats_sql = R"(
        CREATE TABLE IF NOT EXISTS function_energy_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            function_name TEXT,
            file_path TEXT,
            total_joules REAL,
            avg_joules REAL,
            max_joules REAL,
            min_joules REAL,
            call_count INTEGER,
            total_duration_ms REAL,
            efficiency_ratio REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES measurement_sessions(session_id)
        );
    )";
    
    const char* create_energy_timeline_sql = R"(
        CREATE TABLE IF NOT EXISTS energy_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp_bucket TEXT,
            avg_watts REAL,
            max_watts REAL,
            total_joules REAL,
            measurement_count INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES measurement_sessions(session_id)
        );
    )";
    
    // Indexes for better query performance
    const char* create_indexes_sql[] = {
        "CREATE INDEX IF NOT EXISTS idx_measurements_session_id ON measurements(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_measurements_checkpoint_type ON measurements(checkpoint_type);",
        "CREATE INDEX IF NOT EXISTS idx_measurements_function_name ON measurements(function_name);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON measurement_sessions(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_language ON measurement_sessions(language);",
        "CREATE INDEX IF NOT EXISTS idx_function_stats_session ON function_energy_stats(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_timeline_session ON energy_timeline(session_id);"
    };
    
    bool success = execute_statement(create_sessions_sql) && 
                  execute_statement(create_measurements_sql) &&
                  execute_statement(create_aggregated_stats_sql) &&
                  execute_statement(create_energy_timeline_sql);
    
    // Create indexes
    for (const char* index_sql : create_indexes_sql) {
        success = success && execute_statement(index_sql);
    }
    
    return success;
}

bool SQLiteEnergyStorage::execute_statement(const std::string& sql) {
    // Whitelist of safe SQL statements to prevent SQL injection
    static const std::set<std::string> safe_statements = {
        "BEGIN TRANSACTION",
        "COMMIT", 
        "ROLLBACK",
        "VACUUM",
        "ANALYZE"
    };
    
    // Check if it's a safe DDL statement (allow for whitespace and case insensitivity)
    std::string trimmed_sql = sql;
    trimmed_sql.erase(0, trimmed_sql.find_first_not_of(" \t\n\r"));
    std::transform(trimmed_sql.begin(), trimmed_sql.end(), trimmed_sql.begin(), ::toupper);
    
    bool is_safe_ddl = (trimmed_sql.substr(0, 12) == "CREATE TABLE" || 
                       trimmed_sql.substr(0, 18) == "CREATE TABLE IF NO" ||
                       trimmed_sql.substr(0, 12) == "CREATE INDEX" ||
                       trimmed_sql.substr(0, 18) == "CREATE INDEX IF NO" ||
                       trimmed_sql.substr(0, 6) == "INSERT" ||
                       trimmed_sql.substr(0, 6) == "UPDATE" ||
                       trimmed_sql.substr(0, 6) == "DELETE" ||
                       trimmed_sql.substr(0, 6) == "SELECT");
    
    // Only allow whitelisted statements or safe DDL/DML statements
    if (!is_safe_ddl && safe_statements.find(sql) == safe_statements.end()) {
        std::cerr << "SQL Security Error: Attempted to execute non-whitelisted statement" << std::endl;
        return false;
    }
    
    char* error_msg = nullptr;
    if (sqlite3_exec(static_cast<sqlite3*>(db_handle_), sql.c_str(), nullptr, nullptr, &error_msg) != SQLITE_OK) {
        std::cerr << "SQL error: " << error_msg << std::endl;
        sqlite3_free(error_msg);
        return false;
    }
    return true;
}

bool SQLiteEnergyStorage::store_measurement(const Measurement& measurement) {
    // This method is mainly for individual measurements
    // Usually we store complete sessions instead
    return true;
}

bool SQLiteEnergyStorage::store_session(const std::string& session_id, 
                                       const std::vector<Measurement>& measurements,
                                       const std::string& code_version,
                                       const std::string& file_path) {
    if (measurements.empty()) {
        return false;
    }
    
    // Calculate session summary
    auto start_time = measurements.front().timestamp;
    auto end_time = measurements.back().timestamp;
    double total_joules = 0.0;
    double total_watts = 0.0;
    double peak_watts = 0.0;
    
    for (const auto& m : measurements) {
        total_joules += m.joules;
        total_watts += m.watts;
        peak_watts = std::max(peak_watts, m.watts);
    }
    
    double avg_watts = total_watts / measurements.size();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(end_time - start_time);
    
    // Store session summary using parameterized query
    const char* session_sql = R"(
        INSERT OR REPLACE INTO measurement_sessions 
        (session_id, code_version, file_path, start_time, end_time, total_joules, average_watts, peak_watts, checkpoint_count, duration_seconds) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    )";
    
    sqlite3_stmt* session_stmt;
    if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), session_sql, -1, &session_stmt, nullptr) != SQLITE_OK) {
        return false;
    }
    
    // Bind parameters safely
    sqlite3_bind_text(session_stmt, 1, session_id.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(session_stmt, 2, code_version.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(session_stmt, 3, file_path.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(session_stmt, 4, std::chrono::duration_cast<std::chrono::seconds>(start_time.time_since_epoch()).count());
    sqlite3_bind_int64(session_stmt, 5, std::chrono::duration_cast<std::chrono::seconds>(end_time.time_since_epoch()).count());
    sqlite3_bind_double(session_stmt, 6, total_joules);
    sqlite3_bind_double(session_stmt, 7, avg_watts);
    sqlite3_bind_double(session_stmt, 8, peak_watts);
    sqlite3_bind_int(session_stmt, 9, static_cast<int>(measurements.size()));
    sqlite3_bind_int(session_stmt, 10, static_cast<int>(duration.count()));
    
    bool session_success = (sqlite3_step(session_stmt) == SQLITE_DONE);
    sqlite3_finalize(session_stmt);
    
    if (!session_success) {
        return false;
    }
    
    // Store individual measurements using batch operations
    return store_measurements_batch(session_id, measurements);
    
    return true;
}

std::vector<Measurement> SQLiteEnergyStorage::get_session_measurements(const std::string& session_id) {
    std::vector<Measurement> measurements;
    
    const char* sql = "SELECT source, joules, watts, temperature, timestamp FROM measurements WHERE session_id = ?;";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return measurements;
    }
    
    sqlite3_bind_text(stmt, 1, session_id.c_str(), -1, SQLITE_STATIC);
    
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        Measurement m;
        m.source = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        m.joules = sqlite3_column_double(stmt, 1);
        m.watts = sqlite3_column_double(stmt, 2);
        m.temperature = sqlite3_column_double(stmt, 3);
        
        // Convert timestamp back
        int64_t timestamp_seconds = sqlite3_column_int64(stmt, 4);
        m.timestamp = std::chrono::system_clock::from_time_t(timestamp_seconds);
        
        measurements.push_back(m);
    }
    
    sqlite3_finalize(stmt);
    return measurements;
}

std::vector<std::string> SQLiteEnergyStorage::get_all_sessions() {
    std::vector<std::string> sessions;
    
    const char* sql = "SELECT session_id FROM measurement_sessions ORDER BY start_time DESC;";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return sessions;
    }
    
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sessions.push_back(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    }
    
    sqlite3_finalize(stmt);
    return sessions;
}

EnergySummary SQLiteEnergyStorage::get_session_summary(const std::string& session_id) {
    EnergySummary summary;
    summary.session_id = session_id;
    
    const char* sql = "SELECT * FROM measurement_sessions WHERE session_id = ?;";
    sqlite3_stmt* stmt;
    
    if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return summary;
    }
    
    sqlite3_bind_text(stmt, 1, session_id.c_str(), -1, SQLITE_STATIC);
    
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        summary.code_version = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        summary.file_path = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        
        int64_t start_seconds = sqlite3_column_int64(stmt, 3);
        int64_t end_seconds = sqlite3_column_int64(stmt, 4);
        
        summary.start_time = std::chrono::system_clock::from_time_t(start_seconds);
        summary.end_time = std::chrono::system_clock::from_time_t(end_seconds);
        
        summary.total_joules = sqlite3_column_double(stmt, 5);
        summary.average_watts = sqlite3_column_double(stmt, 6);
        summary.peak_watts = sqlite3_column_double(stmt, 7);
        summary.checkpoint_count = sqlite3_column_int(stmt, 8);
        summary.duration_seconds = sqlite3_column_double(stmt, 9);
    }
    
    sqlite3_finalize(stmt);
    return summary;
}

ComparisonResult SQLiteEnergyStorage::compare_sessions(const std::string& session1, const std::string& session2) {
    ComparisonResult result;
    result.session1_id = session1;
    result.session2_id = session2;
    
    auto summary1 = get_session_summary(session1);
    auto summary2 = get_session_summary(session2);
    
    result.energy_difference_joules = summary2.total_joules - summary1.total_joules;
    result.power_difference_watts = summary2.average_watts - summary1.average_watts;
    result.time_difference_seconds = summary2.duration_seconds - summary1.duration_seconds;
    
    if (summary1.total_joules > 0) {
        result.efficiency_improvement = ((summary1.total_joules - summary2.total_joules) / summary1.total_joules) * 100.0;
    }
    
    // Generate insights
    if (result.energy_difference_joules < 0) {
        result.insights.push_back("Session 2 is more energy efficient");
    } else {
        result.insights.push_back("Session 1 is more energy efficient");
    }
    
    if (result.power_difference_watts < 0) {
        result.insights.push_back("Session 2 has lower average power consumption");
    }
    
    if (result.time_difference_seconds < 0) {
        result.insights.push_back("Session 2 completed faster");
    }
    
    return result;
}

bool SQLiteEnergyStorage::export_to_csv(const std::string& filepath, const std::string& session_id) {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        return false;
    }
    
    // Write header
    file << "session_id,source,joules,watts,temperature,timestamp,checkpoint_id,checkpoint_type,name,line_number,context\n";
    
    const char* sql = "SELECT * FROM measurements ORDER BY timestamp;";
    const char* sql_with_filter = "SELECT * FROM measurements WHERE session_id = ? ORDER BY timestamp;";
    
    sqlite3_stmt* stmt;
    if (!session_id.empty()) {
        if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), sql_with_filter, -1, &stmt, nullptr) != SQLITE_OK) {
            return false;
        }
        sqlite3_bind_text(stmt, 1, session_id.c_str(), -1, SQLITE_STATIC);
    } else {
        if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), sql, -1, &stmt, nullptr) != SQLITE_OK) {
            return false;
        }
    }
    
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        file << sqlite3_column_text(stmt, 1) << ","  // session_id
             << sqlite3_column_text(stmt, 2) << ","  // source
             << sqlite3_column_double(stmt, 3) << "," // joules
             << sqlite3_column_double(stmt, 4) << "," // watts
             << sqlite3_column_double(stmt, 5) << "," // temperature
             << sqlite3_column_text(stmt, 6) << ","  // timestamp
             << sqlite3_column_text(stmt, 7) << ","  // checkpoint_id
             << sqlite3_column_text(stmt, 8) << ","  // checkpoint_type
             << sqlite3_column_text(stmt, 9) << ","  // name
             << sqlite3_column_int(stmt, 10) << ","  // line_number
             << sqlite3_column_text(stmt, 11) << "\n"; // context
    }
    
    sqlite3_finalize(stmt);
    file.close();
    return true;
}

bool SQLiteEnergyStorage::store_measurements_batch(const std::string& session_id, const std::vector<Measurement>& measurements) {
    if (measurements.empty()) return true;

    // Begin transaction for better performance
    if (!execute_statement("BEGIN TRANSACTION")) {
        return false;
    }

    const char* insert_sql = R"(
        INSERT INTO measurements 
        (session_id, source, joules, watts, temperature, timestamp, checkpoint_id, checkpoint_type, name, line_number, context) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    )";

    sqlite3_stmt* stmt;
    if (sqlite3_prepare_v2(static_cast<sqlite3*>(db_handle_), insert_sql, -1, &stmt, nullptr) != SQLITE_OK) {
        execute_statement("ROLLBACK");
        return false;
    }

    // Batch insert all measurements
    for (const auto& m : measurements) {
        sqlite3_bind_text(stmt, 1, session_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, m.source.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 3, m.joules);
        sqlite3_bind_double(stmt, 4, m.watts);
        sqlite3_bind_double(stmt, 5, m.temperature);
        sqlite3_bind_int64(stmt, 6, std::chrono::duration_cast<std::chrono::seconds>(m.timestamp.time_since_epoch()).count());
        
        // Generate checkpoint ID and type
        std::string checkpoint_id = "checkpoint_" + std::to_string(std::chrono::duration_cast<std::chrono::milliseconds>(m.timestamp.time_since_epoch()).count());
        sqlite3_bind_text(stmt, 7, checkpoint_id.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 8, "measurement", -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 9, "energy_measurement", -1, SQLITE_STATIC);
        sqlite3_bind_int(stmt, 10, 0);
        sqlite3_bind_text(stmt, 11, "NEMB measurement", -1, SQLITE_STATIC);

        if (sqlite3_step(stmt) != SQLITE_DONE) {
            sqlite3_finalize(stmt);
            execute_statement("ROLLBACK");
            return false;
        }

        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    return execute_statement("COMMIT");
}

std::unique_ptr<EnergyStorage> CreateEnergyStorage(const std::string& type, const std::string& path) {
    if (type == "sqlite" || type.empty()) {
        return std::make_unique<SQLiteEnergyStorage>(path.empty() ? "energy_data.db" : path);
    }
    
    // Future: Add other storage backends (InfluxDB, TimescaleDB, etc.)
    std::cerr << "Unknown storage type: " << type << ", falling back to SQLite" << std::endl;
    return std::make_unique<SQLiteEnergyStorage>(path.empty() ? "energy_data.db" : path);
}

} // namespace codegreen
