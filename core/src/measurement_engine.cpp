#include "measurement_engine.hpp"
#include "plugin/plugin_registry.hpp"
#include "adapters/pmt_adapter.hpp"
#include "energy_storage.hpp"
#include "config.hpp"
#include "pmt_manager.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <sstream>
#include <sys/wait.h>
#include <unistd.h>

namespace codegreen {

MeasurementEngine::MeasurementEngine()
    : plugin_registry_(std::make_unique<PluginRegistry>()) {
    
    // Load configuration
    auto& config = Config::instance();
    
    // Initialize centralized PMT manager (replaces duplicate initialization)
    auto& pmt_manager = PMTManager::get_instance();
    if (!pmt_manager.is_initialized()) {
        pmt_manager.initialize_from_config();
    }
    
    // Initialize energy storage with configured path
    std::string db_path = config.get_database_path().string();
    energy_storage_ = CreateEnergyStorage("sqlite", db_path);
}

void MeasurementEngine::register_language_adapter(std::unique_ptr<LanguageAdapter> adapter) {
    language_adapters_.push_back(std::move(adapter));
}

const std::vector<std::unique_ptr<LanguageAdapter>>& MeasurementEngine::language_adapters() const {
    return language_adapters_;
}

bool MeasurementEngine::analyze_code(const std::string& source_code, const std::string& language_id) {
    auto it = std::find_if(language_adapters_.begin(), language_adapters_.end(),
        [&language_id](const std::unique_ptr<LanguageAdapter>& adapter) {
            return adapter->get_language_id() == language_id;
        });
    
    if (it != language_adapters_.end()) {
        auto ast = (*it)->parse(source_code);
        return (*it)->analyze(source_code);
    }
    
    return false;
}

InstrumentationResult MeasurementEngine::instrument_and_execute(const MeasurementConfig& config) {
    InstrumentationResult result;
    result.success = false;
    
    try {
        // PHASE 1: Instrumentation (no energy measurement)
        std::cout << "Phase 1: Code analysis and instrumentation..." << std::endl;
        
        // 1. Read source file
        std::string source_code = read_source_file(config.source_file);
        if (source_code.empty()) {
            result.error_message = "Failed to read source file: " + config.source_file;
            return result;
        }
        
        // 2. Detect language if not specified
        std::string language = config.language;
        if (language.empty()) {
            language = detect_language_from_file(config.source_file);
        }
        
        // 3. Get appropriate language adapter
        LanguageAdapter* adapter = get_adapter_by_language(language);
        if (!adapter) {
            result.error_message = "No language adapter found for: " + language;
            return result;
        }
        
        // 4. Generate checkpoints
        result.checkpoints = adapter->generate_checkpoints(source_code);
        if (result.checkpoints.empty()) {
            result.error_message = "No checkpoints generated for source code";
            return result;
        }
        
        // 5. Instrument code with checkpoints
        result.instrumented_code = adapter->instrument_code(source_code, result.checkpoints);
        
        // 6. Create temporary directory
        std::string temp_dir = create_temp_directory();
        
        // 7. Write instrumented code to temporary file
        std::filesystem::path source_path(config.source_file);
        std::string temp_filename = source_path.stem().string() + "_instrumented" + source_path.extension().string();
        result.temp_file_path = temp_dir + "/" + temp_filename;
        
        if (!write_instrumented_file(result.instrumented_code, result.temp_file_path)) {
            result.error_message = "Failed to write instrumented file";
            return result;
        }
        
        // Set up automatic cleanup of temporary file
        TempFileGuard temp_guard(result.temp_file_path);
        
        // 8. Copy runtime module for Python using configuration
        if (language == "python") {
            auto& config = Config::instance();
            auto runtime_source = config.get_runtime_module_path("python");
            auto runtime_dest = std::filesystem::path(temp_dir) / "codegreen_runtime.py";
            
            try {
                // Atomic copy operation - no TOCTOU race condition
                std::filesystem::copy_file(runtime_source, runtime_dest, 
                                         std::filesystem::copy_options::overwrite_existing);
            } catch (const std::filesystem::filesystem_error& e) {
                result.error_message = "Failed to copy runtime module: " + std::string(e.what());
                return result;
            }
        }
        
        // PHASE 2: Clean execution with energy measurement ONLY
        // No more file I/O after this point!
        std::cout << "Phase 2: Clean execution with energy measurement..." << std::endl;
        
        std::vector<std::string> exec_args = config.execution_args;
        exec_args.insert(exec_args.begin(), result.temp_file_path);
        
        // Start energy monitoring using centralized PMT manager
        std::vector<codegreen::Measurement> energy_measurements;
        auto start_time = std::chrono::system_clock::now();
        
        // Collect initial energy reading from PMT manager
        auto& pmt_manager = PMTManager::get_instance();
        auto start_measurement = pmt_manager.collect_measurement();
        if (start_measurement) {
            start_measurement->timestamp = start_time;
            energy_measurements.push_back(*start_measurement);
        }
        
        if (!execute_instrumented_code(result.temp_file_path, exec_args)) {
            result.error_message = "Failed to execute instrumented code";
            return result;
        }
        
        // Collect final energy reading from PMT manager
        auto end_time = std::chrono::system_clock::now();
        auto end_measurement = pmt_manager.collect_measurement();
        if (end_measurement) {
            end_measurement->timestamp = end_time;
            energy_measurements.push_back(*end_measurement);
        }
        
        // Store energy measurements if we have any
        if (!energy_measurements.empty() && energy_storage_) {
            std::string session_id = "session_" + std::to_string(std::time(nullptr));
            std::string code_version = "v1.0"; // Could be extracted from git or config
            std::string file_path = config.source_file;
            
            if (energy_storage_->store_session(session_id, energy_measurements, code_version, file_path)) {
                std::cout << "✓ Energy measurements stored in session: " << session_id << std::endl;
            } else {
                std::cout << "⚠️  Failed to store energy measurements" << std::endl;
            }
        }
        
        result.success = true;
        
    } catch (const std::exception& e) {
        result.error_message = std::string("Exception during instrumentation: ") + e.what();
    }
    
    return result;
}

LanguageAdapter* MeasurementEngine::get_adapter_for_file(const std::string& file_path) {
    std::filesystem::path path(file_path);
    std::string extension = path.extension().string();
    
    for (auto& adapter : language_adapters_) {
        auto extensions = adapter->get_file_extensions();
        if (std::find(extensions.begin(), extensions.end(), extension) != extensions.end()) {
            return adapter.get();
        }
    }
    
    return nullptr;
}

LanguageAdapter* MeasurementEngine::get_adapter_by_language(const std::string& language_id) {
    auto it = std::find_if(language_adapters_.begin(), language_adapters_.end(),
        [&language_id](const std::unique_ptr<LanguageAdapter>& adapter) {
            return adapter->get_language_id() == language_id;
        });
    
    return (it != language_adapters_.end()) ? it->get() : nullptr;
}

std::string MeasurementEngine::read_source_file(const std::string& file_path) {
    std::ifstream file(file_path);
    if (!file.is_open()) {
        return "";
    }
    
    std::ostringstream content_stream;
    content_stream << file.rdbuf();
    return content_stream.str();
}

bool MeasurementEngine::write_instrumented_file(const std::string& content, const std::string& file_path) {
    std::ofstream file(file_path);
    if (!file.is_open()) {
        return false;
    }
    
    file << content;
    bool success = file.good();
    file.close();
    
    if (success) {
        try {
            // Set secure permissions on temporary file (owner read/write only)
            std::filesystem::permissions(file_path,
                                       std::filesystem::perms::owner_read |
                                       std::filesystem::perms::owner_write,
                                       std::filesystem::perm_options::replace);
        } catch (const std::filesystem::filesystem_error& e) {
            std::cerr << "Warning: Could not set secure permissions on temp file: " << e.what() << std::endl;
            // Continue anyway - file was created successfully
        }
    }
    
    return success;
}

std::string MeasurementEngine::create_temp_directory() {
    auto& config = Config::instance();
    auto temp_dir = config.get_temp_directory();
    
    std::filesystem::create_directories(temp_dir);
    return temp_dir.string();
}

std::string MeasurementEngine::detect_language_from_file(const std::string& file_path) {
    std::filesystem::path path(file_path);
    std::string extension = path.extension().string();
    
    if (extension == ".py" || extension == ".pyw" || extension == ".pyi") {
        return "python";
    } else if (extension == ".cpp" || extension == ".cxx" || extension == ".cc") {
        return "cpp";
    } else if (extension == ".js" || extension == ".jsx") {
        return "javascript";
    } else if (extension == ".java") {
        return "java";
    }
    
    return "";
}

bool MeasurementEngine::execute_instrumented_code(const std::string& temp_file, const std::vector<std::string>& args) {
    // Determine execution command based on file extension
    std::filesystem::path path(temp_file);
    std::string extension = path.extension().string();
    
    const char* interpreter = nullptr;
    if (extension == ".py") {
        interpreter = "python3";
    } else if (extension == ".js") {
        interpreter = "node";
    } else {
        return false; // Unsupported file type for execution
    }
    
    // Create argument vector for execvp (safe execution)
    std::vector<const char*> exec_args;
    exec_args.push_back(interpreter);
    exec_args.push_back(temp_file.c_str());
    
    // Add any additional arguments (skip the first one as it's the file path)
    for (size_t i = 1; i < args.size(); ++i) {
        exec_args.push_back(args[i].c_str());
    }
    exec_args.push_back(nullptr); // execvp requires null termination
    
    // Safe process execution using fork and execvp
    pid_t pid = fork();
    if (pid == 0) {
        // Child process - execute the instrumented code
        execvp(interpreter, const_cast<char* const*>(exec_args.data()));
        // If we reach here, execvp failed
        _exit(1);
    } else if (pid > 0) {
        // Parent process - wait for child to complete
        int status;
        waitpid(pid, &status, 0);
        return WIFEXITED(status) && WEXITSTATUS(status) == 0;
    } else {
        // Fork failed
        return false;
    }
}

} // namespace codegreen
