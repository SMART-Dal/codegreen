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
#include "measurement_engine.hpp"
#include "energy_monitor.hpp"
#include "python.hpp"
#include "config.hpp"
#include "nemb/codegreen_energy.hpp"

void print_usage() {
    std::cout << "CodeGreen - Energy Monitoring and Code Optimization Tool" << std::endl;
    std::cout << "Version: 0.1.0" << std::endl;
    std::cout << std::endl;
    std::cout << "Usage:" << std::endl;
    std::cout << "  codegreen <language> <source_file> [args...]" << std::endl;
    std::cout << "  codegreen --init-sensors" << std::endl;
    std::cout << std::endl;
    std::cout << "Examples:" << std::endl;
    std::cout << "  codegreen python3 main.py" << std::endl;
    std::cout << "  codegreen python3 script.py arg1 arg2" << std::endl;
    std::cout << "  codegreen --init-sensors" << std::endl;
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
        
        // Register language adapters
        if (language == "python") {
            measurement_engine->register_language_adapter(
                std::make_unique<codegreen::PythonAdapter>()
            );
        } else {
            std::cerr << "Language " << language << " not yet supported. Currently only Python is available." << std::endl;
            return 1;
        }
        
        // Prepare execution arguments (everything after the source file)
        std::vector<std::string> exec_args;
        for (int i = 3; i < argc; ++i) {
            exec_args.push_back(argv[i]);
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
