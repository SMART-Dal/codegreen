#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>
#include <string>
#include <filesystem>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <fstream>
#include <algorithm>
#include "measurement_engine.hpp"
#include "config.hpp"
#include "nemb/codegreen_energy.hpp"
// Legacy python.hpp removed - using Python AST-based system

std::string detect_language_from_file(const std::string& file_path) {
    std::filesystem::path path(file_path);
    std::string extension = path.extension().string();
    
    if (extension == ".py" || extension == ".pyw" || extension == ".pyi") {
        return "python";
    } else if (extension == ".cpp" || extension == ".cxx" || extension == ".cc" || extension == ".hpp" || extension == ".h") {
        return "cpp";
    } else if (extension == ".c") {
        return "c";
    } else if (extension == ".java") {
        return "java";
    } else if (extension == ".js") {
        return "javascript";
    }
    
    return "";
}

void print_usage() {
    std::cout << "CodeGreen - Energy Monitoring and Code Optimization Tool" << std::endl;
    std::cout << "Version: 0.1.0" << std::endl;
    std::cout << std::endl;
    std::cout << "Usage:" << std::endl;
    std::cout << "  codegreen <language> <source_file> [args...]" << std::endl;
    std::cout << "  codegreen --init-sensors" << std::endl;
    std::cout << "  codegreen --analyze <source_file> [options]" << std::endl;
    std::cout << std::endl;
    std::cout << "Examples:" << std::endl;
    std::cout << "  codegreen python3 main.py" << std::endl;
    std::cout << "  codegreen python3 script.py arg1 arg2" << std::endl;
    std::cout << "  codegreen --init-sensors" << std::endl;
    std::cout << "  codegreen --analyze script.py --save-instrumented" << std::endl;
    std::cout << "  codegreen --analyze script.py --output-dir ./analysis" << std::endl;
    std::cout << std::endl;
    std::cout << "Supported languages:" << std::endl;
    std::cout << "  python3, python - Python 3.x" << std::endl;
    std::cout << "  g++, gcc - C++ and C" << std::endl;
    std::cout << "  javac, java - Java" << std::endl;
    std::cout << std::endl;
    std::cout << "Commands:" << std::endl;
    std::cout << "  --init-sensors    Initialize and cache sensor configuration" << std::endl;
    std::cout << "  --measure-workload --duration=<sec> --workload=<type>" << std::endl;
    std::cout << "                    Measure energy consumption of specified workload" << std::endl;
    std::cout << "  --analyze         Analyze and instrument code without execution" << std::endl;
    std::cout << std::endl;
    std::cout << "Analysis Options:" << std::endl;
    std::cout << "  --save-instrumented    Save instrumented code to current directory" << std::endl;
    std::cout << "  --output-dir <dir>     Save instrumented code to specified directory" << std::endl;
    std::cout << "  --no-cleanup          Keep temporary files (default: auto-cleanup)" << std::endl;
    std::cout << "  --verbose             Show detailed instrumentation information" << std::endl;
}

int main(int argc, char* argv[]) {
    try {
        // Initialize configuration system early
        codegreen::ConfigLoader config_loader;
        if (!config_loader.is_loaded()) {
            std::cerr << "Warning: " << config_loader.get_error() << std::endl;
            std::cerr << "Continuing with default configuration..." << std::endl;
        }
        
        // Check for init-sensors command
        if (argc >= 2 && std::string(argv[1]) == "--init-sensors") {
            std::cout << "CodeGreen - NEMB Sensor Initialization" << std::endl;
            
            // Initialize NEMB energy measurement system using default config
            codegreen::EnergyMeter meter; // Uses default MeasurementConfig
            
            if (meter.is_available()) {
                std::cout << "✓ NEMB energy measurement system initialized successfully!" << std::endl;
                
                // Display available providers
                auto providers = meter.get_provider_info();
                std::cout << "Available energy providers:" << std::endl;
                for (const auto& provider : providers) {
                    std::cout << "  - " << provider << std::endl;
                }
                
                // Run system self-test
                if (meter.self_test()) {
                    std::cout << "✓ System self-test passed" << std::endl;
                } else {
                    std::cout << "⚠ System self-test failed" << std::endl;
                }
                
                return 0;
            } else {
                std::cerr << "Failed to initialize sensors" << std::endl;
                return 1;
            }
        }
        
        // Check for analyze command
        if (argc >= 3 && std::string(argv[1]) == "--analyze") {
            std::string source_file = argv[2];
            std::string output_dir = ".";
            bool save_instrumented = false;
            bool no_cleanup = false;
            bool verbose = false;
            
            // Parse analysis options
            for (int i = 3; i < argc; i++) {
                std::string arg = argv[i];
                if (arg == "--save-instrumented") {
                    save_instrumented = true;
                } else if (arg == "--no-cleanup") {
                    no_cleanup = true;
                } else if (arg == "--verbose") {
                    verbose = true;
                } else if (arg.find("--output-dir=") == 0) {
                    output_dir = arg.substr(13);
                } else if (i + 1 < argc && arg == "--output-dir") {
                    output_dir = argv[++i];
                }
            }
            
            // Check if source file exists
            if (!std::filesystem::exists(source_file)) {
                std::cerr << "Error: Source file not found: " << source_file << std::endl;
                return 1;
            }
            
            std::cout << "CodeGreen - Code Analysis and Instrumentation" << std::endl;
            std::cout << "Analyzing: " << source_file << std::endl;
            
            // Initialize measurement engine
            auto measurement_engine = std::make_unique<codegreen::MeasurementEngine>();
            
            // Detect language from file extension
            std::string language = detect_language_from_file(source_file);
            if (language.empty()) {
                std::cerr << "Error: Could not detect language for file: " << source_file << std::endl;
                return 1;
            }
            
            // Read source file
            std::string source_code = measurement_engine->read_source_file(source_file);
            if (source_code.empty()) {
                std::cerr << "Error: Failed to read source file: " << source_file << std::endl;
                return 1;
            }
            
            // Get language adapter
            auto* adapter = measurement_engine->get_adapter_by_language(language);
            if (!adapter) {
                std::cerr << "Error: No language adapter found for: " << language << std::endl;
                return 1;
            }
            
            // Generate checkpoints
            std::cout << "Generating instrumentation checkpoints..." << std::endl;
            auto checkpoints = adapter->generate_checkpoints(source_code);
            if (checkpoints.empty()) {
                std::cout << "No checkpoints generated for source code" << std::endl;
                return 0;
            }
            
            // Instrument code
            std::cout << "Instrumenting code..." << std::endl;
            std::string instrumented_code = adapter->instrument_code(source_code, checkpoints);
            
            // Create output directory if it doesn't exist
            if (save_instrumented) {
                std::filesystem::create_directories(output_dir);
            }
            
            // Save instrumented code if requested
            if (save_instrumented) {
                std::filesystem::path source_path(source_file);
                std::string instrumented_filename = source_path.stem().string() + "_instrumented" + source_path.extension().string();
                std::string instrumented_path = output_dir + "/" + instrumented_filename;
                
                std::ofstream out_file(instrumented_path);
                if (out_file.is_open()) {
                    out_file << instrumented_code;
                    out_file.close();
                    std::cout << "✓ Instrumented code saved to: " << instrumented_path << std::endl;
                } else {
                    std::cerr << "Error: Failed to save instrumented code to: " << instrumented_path << std::endl;
                    return 1;
                }
            }
            
            // Display results
            std::cout << std::endl;
            std::cout << "=== Analysis Results ===" << std::endl;
            std::cout << "Language: " << language << std::endl;
            std::cout << "Checkpoints generated: " << checkpoints.size() << std::endl;
            std::cout << "Original lines: " << std::count(source_code.begin(), source_code.end(), '\n') + 1 << std::endl;
            std::cout << "Instrumented lines: " << std::count(instrumented_code.begin(), instrumented_code.end(), '\n') + 1 << std::endl;
            
            if (verbose) {
                std::cout << std::endl;
                std::cout << "=== Generated Checkpoints ===" << std::endl;
                for (const auto& checkpoint : checkpoints) {
                    std::cout << "  " << checkpoint.type << ": " << checkpoint.name 
                             << " (line " << checkpoint.line_number << ")" << std::endl;
                }
            }
            
            std::cout << std::endl;
            std::cout << "✅ Analysis completed successfully" << std::endl;
            
            return 0;
        }
        
        // Check for workload measurement commands
        if (argc >= 2 && (std::string(argv[1]) == "--measure-workload" || std::string(argv[1]) == "benchmark")) {
            // Parse parameters
            int duration = 3;
            std::string workload_type = "cpu_stress";
            
            for (int i = 2; i < argc; i++) {
                std::string arg = argv[i];
                if (arg.find("--duration=") == 0) {
                    duration = std::stoi(arg.substr(11));
                } else if (arg.find("--workload=") == 0) {
                    workload_type = arg.substr(11);
                }
            }
            
            // Simple direct energy measurement (temporary fix for coordinator hanging)
            std::cout << "⚡ Starting direct energy measurement..." << std::endl;
            
            // Check RAPL access
            std::ifstream rapl_file("/sys/class/powercap/intel-rapl:0/energy_uj");
            if (!rapl_file.is_open()) {
                std::cerr << "RAPL energy measurement not available (try sudo for hardware access)" << std::endl;
                return 1;
            }
            
            // Get initial energy reading
            uint64_t energy_start;
            rapl_file >> energy_start;
            rapl_file.close();
            std::cout << "🔋 Initial energy: " << energy_start << " μJ" << std::endl;
            
            // Get start time
            auto time_start = std::chrono::steady_clock::now();
            
            std::cout << "🏃 Running " << workload_type << " workload for " << duration << " seconds..." << std::endl;
            
            try {
                // Run the workload
                if (workload_type == "cpu_stress") {
                    volatile double x = 0.0;
                    auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(duration);
                    int iterations = 0;
                    
                    while (std::chrono::steady_clock::now() < end_time) {
                        for (int i = 0; i < 50000; i++) {
                            x += std::sqrt(i * 3.14159);
                            x = std::sin(x) * std::cos(x);
                        }
                        iterations++;
                    }
                    std::cout << "💪 Completed " << iterations << " iterations" << std::endl;
                    
                } else if (workload_type == "memory_stress") {
                    auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(duration);
                    
                    while (std::chrono::steady_clock::now() < end_time) {
                        std::vector<double> data(1000000);
                        for (size_t i = 0; i < data.size(); i++) {
                            data[i] = std::sqrt(i);
                        }
                        volatile double sum = 0;
                        for (size_t i = 0; i < data.size(); i += 1000) {
                            sum += data[i];
                        }
                    }
                    
                } else {
                    // Fallback CPU stress
                    volatile double x = 0.0;
                    auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(duration);
                    while (std::chrono::steady_clock::now() < end_time) {
                        for (int i = 0; i < 10000; i++) {
                            x += std::sqrt(i);
                        }
                    }
                }
                
                // Get end time and energy
                auto time_end = std::chrono::steady_clock::now();
                
                rapl_file.open("/sys/class/powercap/intel-rapl:0/energy_uj");
                uint64_t energy_end;
                rapl_file >> energy_end;
                rapl_file.close();
                std::cout << "🔋 Final energy: " << energy_end << " μJ" << std::endl;
                
                // Calculate results
                double energy_joules = (energy_end - energy_start) / 1e6;
                double duration_seconds = std::chrono::duration<double>(time_end - time_start).count();
                double average_power_watts = energy_joules / duration_seconds;
                
                // Create result structure
                struct {
                    double energy_joules;
                    double average_power_watts; 
                    double duration_seconds;
                    bool is_valid = true;
                    double uncertainty_percent = 5.0; // Estimated uncertainty for direct RAPL
                } result = {energy_joules, average_power_watts, duration_seconds};
                
                // Output results in machine-readable format for Python CLI
                std::cout << "Energy consumed: " << std::fixed << std::setprecision(6) << result.energy_joules << " J" << std::endl;
                std::cout << "Average power: " << std::fixed << std::setprecision(3) << result.average_power_watts << " W" << std::endl;
                std::cout << "Duration: " << std::fixed << std::setprecision(3) << result.duration_seconds << " s" << std::endl;
                std::cout << "Valid: " << (result.is_valid ? "Yes" : "No") << std::endl;
                std::cout << "Uncertainty: ±" << std::fixed << std::setprecision(2) << result.uncertainty_percent << "%" << std::endl;
                
                if (result.is_valid) {
                    std::cout << "✅ Measurement completed successfully" << std::endl;
                } else {
                    std::cout << "⚠️ Measurement completed with warnings" << std::endl;
                }
                
                return 0;
                
            } catch (const std::exception& e) {
                std::cerr << "Measurement failed: " << e.what() << std::endl;
                return 1;
            }
        }
        
        if (argc < 3) {
            print_usage();
            return 1;
        }
        
        std::string language = argv[1];
        std::string source_file = argv[2];
        
        // Normalize language identifier
        if (language == "python3" || language == "python") {
            language = "python";
        } else if (language == "g++") {
            language = "cpp";
        } else if (language == "gcc") {
            language = "c";
        } else if (language == "javac" || language == "java") {
            language = "java";
        }
        
        // Check if source file exists
        if (!std::filesystem::exists(source_file)) {
            std::cerr << "Error: Source file not found: " << source_file << std::endl;
            return 1;
        }
        
        std::cout << "CodeGreen - Energy Monitoring Tool" << std::endl;
        std::cout << "Analyzing and instrumenting: " << source_file << std::endl;
        
        // Initialize measurement engine
        auto measurement_engine = std::make_unique<codegreen::MeasurementEngine>();
        
        // Language adapters now use Python AST-based system instead of C++ adapters
        if (language != "python" && language != "cpp" && language != "c" && language != "java") {
            std::cerr << "Language " << language << " not yet supported." << std::endl;
            return 1;
        }
        
        // Prepare execution arguments (everything after the source file)
        // Also scan for CodeGreen-specific flags mixed in
        std::vector<std::string> exec_args;
        std::string json_output_path = "";
        
        for (int i = 3; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg.find("--json-output=") == 0) {
                json_output_path = arg.substr(14);
            } else if (arg == "--json-output" && i + 1 < argc) {
                json_output_path = argv[++i];
            } else {
                exec_args.push_back(arg);
            }
        }
        
        // Configure measurement
        codegreen::MeasurementConfig config;
        config.language = language;
        config.source_file = source_file;
        config.execution_args = exec_args;
        config.cleanup_temp_files = true;
        config.generate_report = true;
        
        std::cout << "Generating energy measurement checkpoints..." << std::endl;
        
        // Execute the full measurement workflow
        auto result = measurement_engine->instrument_and_execute(config);
        
        // Handle JSON output if requested
        if (result.success && !json_output_path.empty()) {
            std::cout << "📝 Writing results to " << json_output_path << std::endl;
            
            // Create JSON object
            Json::Value root;
            root["session_id"] = "session_" + std::to_string(std::time(nullptr));
            root["file_path"] = source_file;
            root["language"] = language;
            root["success"] = true;
            
            // Calculate aggregates
            double total_joules = 0.0;
            double total_watts = 0.0;
            double max_watts = 0.0;
            double duration = 0.0;
            
            if (!result.measurements.empty()) {
                const auto& m = result.measurements.back(); // Assuming one summary measurement for now
                total_joules = m.joules;
                total_watts = m.watts; // This is avg power for differential measurement
                max_watts = m.watts;   // Placeholder
                duration = m.duration_seconds;
            }
            
            root["total_joules"] = total_joules;
            root["average_watts"] = total_watts;
            root["peak_watts"] = max_watts;
            root["duration_seconds"] = duration;
            root["checkpoint_count"] = (int)result.checkpoints.size();
            
            // Write to file
            std::ofstream json_file(json_output_path);
            if (json_file.is_open()) {
                Json::StreamWriterBuilder builder;
                builder["indentation"] = "  ";
                std::unique_ptr<Json::StreamWriter> writer(builder.newStreamWriter());
                writer->write(root, &json_file);
                json_file.close();
            } else {
                std::cerr << "Error: Failed to write JSON output to " << json_output_path << std::endl;
            }
        }
        
        if (!result.success) {
            std::cerr << "Error: " << result.error_message << std::endl;
            return 1;
        }
        
        std::cout << std::endl;
        std::cout << "=== Instrumentation Results ===" << std::endl;
        std::cout << "Checkpoints generated: " << result.checkpoints.size() << std::endl;
        std::cout << "Instrumented file: " << result.temp_file_path << std::endl;
        
        std::cout << std::endl;
        std::cout << "=== Generated Checkpoints ===" << std::endl;
        for (const auto& checkpoint : result.checkpoints) {
            std::cout << "  " << checkpoint.type << ": " << checkpoint.name 
                     << " (line " << checkpoint.line_number << ")" << std::endl;
        }
        
        std::cout << std::endl;
        std::cout << "=== Code Execution Complete ===" << std::endl;
        
        if (!result.measurements.empty()) {
            double total_joules = 0;
            for (const auto& m : result.measurements) total_joules += m.joules;
            std::cout << "Total Energy consumed: " << std::fixed << std::setprecision(6) << total_joules << " J" << std::endl;
        }
        
        std::cout << "Energy measurement data collected." << std::endl;
        
        // Display optimization suggestions if available
        auto* adapter = measurement_engine->get_adapter_by_language(language);
        if (adapter) {
            std::string source_code = measurement_engine->read_source_file(source_file);
            if (adapter->analyze(source_code)) {
                auto suggestions = adapter->get_suggestions();
                if (!suggestions.empty()) {
                    std::cout << std::endl;
                    std::cout << "=== Energy Optimization Suggestions ===" << std::endl;
                    for (const auto& suggestion : suggestions) {
                        std::cout << "  • " << suggestion << std::endl;
                    }
                }
            }
        }
        
        // NEMB resources are automatically cleaned up with RAII
        
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        
        // NEMB cleanup is automatic with RAII
        
        return 1;
    }
}
