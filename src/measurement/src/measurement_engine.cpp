#include "measurement_engine.hpp"
#include "energy_storage.hpp"
#include "config.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/config_loader.hpp"
#include "adapters/python_bridge_adapter.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <sstream>
#include <sys/wait.h>
#include <unistd.h>
#include <thread>
#include <chrono>
#include <cstring>

namespace codegreen {

MeasurementEngine::MeasurementEngine() {
    
    // Load configuration
    auto& config = Config::instance();
    
    // Initialize NEMB (Native Energy Measurement Backend)
    auto nemb_config = nemb::ConfigLoader::load_config();
    
    // Convert to coordinator config
    nemb::CoordinatorConfig coordinator_config;
    coordinator_config.temporal_alignment_tolerance_ms = nemb_config.coordinator.temporal_alignment_tolerance_ms;
    coordinator_config.cross_validation_threshold = nemb_config.coordinator.cross_validation_threshold;
    coordinator_config.measurement_buffer_size = nemb_config.coordinator.measurement_buffer_size;
    coordinator_config.auto_restart_failed_providers = nemb_config.coordinator.auto_restart_failed_providers;
    coordinator_config.provider_restart_interval = nemb_config.coordinator.provider_restart_interval;
    
    nemb_coordinator_ = std::make_unique<nemb::MeasurementCoordinator>(coordinator_config);
    
    // Initialize energy storage with configured path
    std::string db_path = config.get_database_path().string();
    energy_storage_ = CreateEnergyStorage("sqlite", db_path);
    
    // Register Python bridge adapter for supported languages
    register_language_adapter(std::make_unique<PythonBridgeAdapter>("python"));
    register_language_adapter(std::make_unique<PythonBridgeAdapter>("c"));
    register_language_adapter(std::make_unique<PythonBridgeAdapter>("cpp"));
    register_language_adapter(std::make_unique<PythonBridgeAdapter>("java"));
    register_language_adapter(std::make_unique<PythonBridgeAdapter>("javascript"));
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

// Helper to compile code
bool compile_code(const std::string& source_file, std::string& out_binary, const std::string& language) {
    auto& config = Config::instance();
    std::filesystem::path exe_dir = config.get_executable_directory();
    std::filesystem::path lib_dir = exe_dir / "../lib";
    
    std::string cmd;
    if (language == "c") {
        std::filesystem::path include_dir = exe_dir / "../src/instrumentation/language_runtimes/c";
        out_binary = source_file.substr(0, source_file.find_last_of('.')) + ".bin";
        cmd = "gcc -O2 -o " + out_binary + " " + source_file + " -I" + include_dir.string() + " -L" + lib_dir.string() + " -lcodegreen-nemb -Wl,-rpath," + lib_dir.string() + " -lm";
    } else if (language == "cpp") {
        std::filesystem::path include_dir = exe_dir / "../src/instrumentation/language_runtimes/cpp";
        out_binary = source_file.substr(0, source_file.find_last_of('.')) + ".bin";
        cmd = "g++ -O2 -std=c++17 -o " + out_binary + " " + source_file + " -I" + include_dir.string() + " -L" + lib_dir.string() + " -lcodegreen-nemb -Wl,-rpath," + lib_dir.string() + " -lm";
    } else if (language == "java") {
        std::filesystem::path src_dir = exe_dir.parent_path() / "src/instrumentation/language_runtimes/java";
        std::filesystem::path runtime_java = src_dir / "codegreen/runtime/CodeGreenRuntime.java";
        out_binary = source_file.substr(0, source_file.find_last_of('.')) + ".class";
        // Compile both runtime and source
        cmd = "javac -cp " + src_dir.string() + " " + runtime_java.string() + " " + source_file;
    } else {
        return false;
    }
    
    // std::cout << "Compiling: " << cmd << std::endl;
    return system(cmd.c_str()) == 0;
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
        std::filesystem::path source_path(config.source_file);
        std::string temp_filename;
        if (language == "java") {
            temp_filename = source_path.filename().string();
        } else {
            temp_filename = source_path.stem().string() + "_instrumented" + source_path.extension().string();
        }
        result.temp_file_path = temp_dir + "/" + temp_filename;
        
        if (!write_instrumented_file(result.instrumented_code, result.temp_file_path)) {
            result.error_message = "Failed to write instrumented file";
            return result;
        }
        
        // Set up automatic cleanup of temporary file (only if cleanup is enabled)
        std::unique_ptr<TempFileGuard> temp_guard;
        if (config.cleanup_temp_files) {
            temp_guard = std::make_unique<TempFileGuard>(result.temp_file_path);
        }
        
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
        
        // Compilation for compiled languages
        if (language == "c" || language == "cpp" || language == "java") {
            std::cout << "Compiling instrumented code..." << std::endl;
            std::string binary_path;
            if (!compile_code(result.temp_file_path, binary_path, language)) {
                result.error_message = "Compilation failed";
                return result;
            }
            result.temp_file_path = binary_path; // Execute the binary/class
        }
        
        // PHASE 2: Clean execution with energy measurement ONLY
        // No more file I/O after this point!
        std::cout << "Phase 2: Clean execution with energy measurement..." << std::endl;
        
        std::vector<std::string> exec_args = config.execution_args;
        exec_args.insert(exec_args.begin(), result.temp_file_path);
        
        // Start energy monitoring using NEMB coordinator
        std::vector<codegreen::Measurement> energy_measurements;
        auto start_time = std::chrono::system_clock::now();
        
        // Take baseline reading before execution
        nemb::SynchronizedReading baseline_reading;
        if (nemb_coordinator_ && !nemb_coordinator_->get_active_providers().empty()) {
            baseline_reading = nemb_coordinator_->get_synchronized_reading();
        }
        
        if (!execute_instrumented_code(result.temp_file_path, exec_args)) {
            result.error_message = "Failed to execute instrumented code";
            return result;
        }
        
        // Collect final energy measurement and calculate difference
        std::unique_ptr<Measurement> energy_measurement;
        if (nemb_coordinator_ && !nemb_coordinator_->get_active_providers().empty()) {
            auto final_reading = nemb_coordinator_->get_synchronized_reading();
            energy_measurement = convert_nemb_difference_to_measurement(final_reading, baseline_reading);
        }
        if (energy_measurement) {
            energy_measurement->timestamp = start_time;
            energy_measurements.push_back(*energy_measurement);
        }
        
        result.measurements = energy_measurements; // Export measurements
        
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
    
    std::string cmd;
    std::vector<const char*> exec_args;
    
    if (extension == ".py") {
        cmd = "python3";
        exec_args.push_back(cmd.c_str());
        exec_args.push_back(temp_file.c_str());
    } else if (extension == ".js") {
        cmd = "node";
        exec_args.push_back(cmd.c_str());
        exec_args.push_back(temp_file.c_str());
    } else if (extension == ".class") {
        cmd = "java";
        exec_args.push_back(cmd.c_str());
        
        // Setup classpath and library path
        auto& config = Config::instance();
        std::filesystem::path exe_dir = config.get_executable_directory();
        std::filesystem::path lib_dir = exe_dir / "../lib";
        std::string lib_path = "-Djava.library.path=" + lib_dir.string();
        
        // Classpath: current temp dir + runtime dir
        std::string classpath = "-cp " + path.parent_path().string() + ":" + (exe_dir / "../src/instrumentation/language_runtimes/java").string();
        
        // Split classpath args (hacky, better to add to exec_args individually if no spaces)
        // For safety, let's just assume we need to run it properly
        // execvp requires individual args
        
        // Simplified: set CLASSPATH env var? No, passed as args.
        // We'll just construct the args for java
        exec_args.push_back("-cp");
        std::string cp_str = path.parent_path().string() + ":" + (exe_dir / "../src/instrumentation/language_runtimes/java").string();
        // Leak memory for safety in execvp (execvp replaces process anyway)
        exec_args.push_back(strdup(cp_str.c_str())); 
        
        exec_args.push_back(strdup(lib_path.c_str()));
        
        // Add absolute library path for Java System.load()
        std::string codegreen_lib_prop = "-Dcodegreen.lib.path=" + (lib_dir / "libcodegreen-nemb.so").string();
        exec_args.push_back(strdup(codegreen_lib_prop.c_str()));
        
        exec_args.push_back(strdup(path.stem().c_str())); // Class name
        
    } else if (extension == "" || extension == ".exe" || extension == ".bin") {
        // Compiled binary
        cmd = temp_file;
        exec_args.push_back(cmd.c_str());
    } else {
        return false; // Unsupported file type
    }
    
    // Add any additional arguments
    for (size_t i = 1; i < args.size(); ++i) {
        exec_args.push_back(args[i].c_str());
    }
    exec_args.push_back(nullptr);
    
    // Safe process execution
    pid_t pid = fork();
    if (pid == 0) {
        // Set LD_LIBRARY_PATH for C/C++ binaries and Java native libraries
        auto& config = Config::instance();
        std::filesystem::path exe_dir = config.get_executable_directory();
        std::filesystem::path lib_dir = exe_dir.parent_path() / "lib";
        
        std::string current_ld = getenv("LD_LIBRARY_PATH") ? getenv("LD_LIBRARY_PATH") : "";
        std::string new_ld = "LD_LIBRARY_PATH=" + lib_dir.string();
        if (!current_ld.empty()) {
            new_ld += ":" + current_ld;
        }
        putenv(strdup(new_ld.c_str()));
        
        execvp(cmd.c_str(), const_cast<char* const*>(exec_args.data()));
        _exit(1);
    } else if (pid > 0) {
        int status;
        waitpid(pid, &status, 0);
        return WIFEXITED(status) && WEXITSTATUS(status) == 0;
    }
    return false;
}

std::unique_ptr<Measurement> MeasurementEngine::convert_nemb_difference_to_measurement(
    const nemb::SynchronizedReading& final_reading,
    const nemb::SynchronizedReading& baseline_reading) {
    
    auto measurement = std::make_unique<Measurement>();
    measurement->timestamp = std::chrono::system_clock::now();
    bool measurement_valid = final_reading.temporal_alignment_valid && baseline_reading.temporal_alignment_valid;
    
    if (!measurement_valid) {
        // Set source to indicate error
        measurement->source = "NEMB_ERROR: Invalid readings";
        return measurement;
    }
    
    // Calculate energy difference from all providers
    double total_energy_joules = 0.0;
    double total_power_watts = 0.0;
    
    for (const auto& final_provider : final_reading.provider_readings) {
        // Find corresponding baseline reading
        auto baseline_it = std::find_if(baseline_reading.provider_readings.begin(), baseline_reading.provider_readings.end(),
            [&final_provider](const nemb::EnergyReading& baseline) {
                return baseline.provider_id == final_provider.provider_id;
            });
        
        if (baseline_it != baseline_reading.provider_readings.end()) {
            double energy_diff = final_provider.energy_joules - baseline_it->energy_joules;
            if (energy_diff >= 0) { // Ensure monotonic energy
                total_energy_joules += energy_diff;
                total_power_watts += final_provider.average_power_watts;
            }
        }
    }
    
    measurement->joules = total_energy_joules;
    measurement->watts = total_power_watts;
    measurement->source = "NEMB";
    measurement->sensor_name = "NEMB";
    measurement->measurement_type = "differential";
    measurement->valid = true;
    
    // Calculate duration
    double duration_ns = static_cast<double>(final_reading.common_timestamp_ns - baseline_reading.common_timestamp_ns);
    measurement->duration_seconds = duration_ns / 1e9;
    
    // Temperature not available from NEMB, set to 0
    measurement->temperature = 0.0;
    
    // Set component breakdown for quality preservation
    for (const auto& final_provider : final_reading.provider_readings) {
        auto baseline_it = std::find_if(baseline_reading.provider_readings.begin(), baseline_reading.provider_readings.end(),
            [&final_provider](const nemb::EnergyReading& baseline) {
                return baseline.provider_id == final_provider.provider_id;
            });
        
        if (baseline_it != baseline_reading.provider_readings.end()) {
            double component_energy = final_provider.energy_joules - baseline_it->energy_joules;
            double component_power = final_provider.average_power_watts;
            if (component_energy >= 0) {
                measurement->component_joules[final_provider.provider_id] = component_energy;
                measurement->component_watts[final_provider.provider_id] = component_power;
                
                // Include per-domain breakdown if available
                for (const auto& [domain, domain_energy] : final_provider.domain_energy_joules) {
                    auto baseline_domain_it = baseline_it->domain_energy_joules.find(domain);
                    if (baseline_domain_it != baseline_it->domain_energy_joules.end()) {
                        double domain_diff = domain_energy - baseline_domain_it->second;
                        if (domain_diff >= 0) {
                            std::string component_key = final_provider.provider_id + ":" + domain;
                            measurement->component_joules[component_key] = domain_diff;
                        }
                    }
                }
            }
        }
    }
    
    // Set quality metrics from synchronized reading
    measurement->uncertainty_percent = final_reading.max_provider_uncertainty;
    measurement->confidence = final_reading.measurement_confidence;
    
    return measurement;
}

} // namespace codegreen
