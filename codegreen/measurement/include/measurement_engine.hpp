#pragma once

#include <memory>
#include <vector>
#include <string>
#include <chrono>
#include <unordered_map>
#include <filesystem>
#include "measurement_session.hpp"
#include "adapters/language_adapter.hpp"
#include "energy_storage.hpp"
#include "energy_code_mapper.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include <iostream>

namespace codegreen {

// RAII helper for automatic temporary file cleanup
class TempFileGuard {
public:
    explicit TempFileGuard(const std::string& filepath) : filepath_(filepath) {}
    ~TempFileGuard() {
        try {
            if (!filepath_.empty() && std::filesystem::exists(filepath_)) {
                std::filesystem::remove(filepath_);
            }
        } catch (const std::exception& e) {
            // Don't throw in destructor, just log
            std::cerr << "Warning: Failed to cleanup temp file " << filepath_ << ": " << e.what() << std::endl;
        }
    }
    
    // Non-copyable, movable
    TempFileGuard(const TempFileGuard&) = delete;
    TempFileGuard& operator=(const TempFileGuard&) = delete;
    TempFileGuard(TempFileGuard&& other) noexcept : filepath_(std::move(other.filepath_)) {
        other.filepath_.clear();
    }
    TempFileGuard& operator=(TempFileGuard&& other) noexcept {
        if (this != &other) {
            filepath_ = std::move(other.filepath_);
            other.filepath_.clear();
        }
        return *this;
    }

private:
    std::string filepath_;
};

/// Result of code instrumentation process
struct InstrumentationResult {
    bool success;
    std::string instrumented_code;
    std::vector<CodeCheckpoint> checkpoints;
    std::string temp_file_path;
    std::string error_message;
    std::vector<Measurement> measurements;
};

/// Configuration for measurement execution
struct MeasurementConfig {
    std::string language;
    std::string source_file;
    std::string output_dir = "/tmp/codegreen";
    bool cleanup_temp_files = true;
    bool generate_report = true;
    std::vector<std::string> execution_args;
};

class MeasurementEngine {
public:
    MeasurementEngine();
    ~MeasurementEngine() = default;

    // Register a language adapter
    void register_language_adapter(std::unique_ptr<LanguageAdapter> adapter);

    // Get all registered language adapters
    const std::vector<std::unique_ptr<LanguageAdapter>>& language_adapters() const;

    // Analyze code with language adapters
    bool analyze_code(const std::string& source_code, const std::string& language_id);

    // Full measurement workflow with energy mapping
    InstrumentationResult instrument_and_execute(const MeasurementConfig& config);
    
    // Advanced measurement workflow with fine-grained energy mapping
    std::unique_ptr<EnergyMeasurementSession> measure_with_energy_mapping(const MeasurementConfig& config);

    // Get language adapter by file extension
    LanguageAdapter* get_adapter_for_file(const std::string& file_path);

    // Get language adapter by language ID
    LanguageAdapter* get_adapter_by_language(const std::string& language_id);

        // Helper methods
        std::string read_source_file(const std::string& file_path);

    private:
        std::vector<std::unique_ptr<LanguageAdapter>> language_adapters_;
        std::unique_ptr<EnergyStorage> energy_storage_;

        // Private helper methods
        bool write_instrumented_file(const std::string& content, const std::string& file_path);
        std::string create_temp_directory();
        std::string detect_language_from_file(const std::string& file_path);
        bool execute_instrumented_code(const std::string& temp_file, const std::vector<std::string>& args);
        
        
        // NEMB (Native Energy Measurement Backend)
        std::unique_ptr<nemb::MeasurementCoordinator> nemb_coordinator_;
        
        // NEMB conversion helpers
        std::unique_ptr<Measurement> convert_nemb_difference_to_measurement(
            const nemb::SynchronizedReading& final_reading,
            const nemb::SynchronizedReading& baseline_reading);
};

} // namespace codegreen
