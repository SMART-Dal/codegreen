#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>
#include <string>
#include <filesystem>
#include "measurement_engine.hpp"
#include "energy_monitor.hpp"
#include "python.hpp"
#include "config.hpp"
#include "pmt_manager.hpp"

void print_usage() {
    std::cout << "CodeGreen - Energy Monitoring and Code Optimization Tool" << std::endl;
    std::cout << "Version: 0.1.0" << std::endl;
    std::cout << std::endl;
    std::cout << "Usage:" << std::endl;
    std::cout << "  codegreen <language> <source_file> [args...]" << std::endl;
    std::cout << std::endl;
    std::cout << "Examples:" << std::endl;
    std::cout << "  codegreen python3 main.py" << std::endl;
    std::cout << "  codegreen python3 script.py arg1 arg2" << std::endl;
    std::cout << std::endl;
    std::cout << "Supported languages:" << std::endl;
    std::cout << "  python3, python - Python 3.x" << std::endl;
    std::cout << "  g++, gcc - C++ and C" << std::endl;
    std::cout << "  javac, java - Java" << std::endl;
}

int main(int argc, char* argv[]) {
    try {
        // Initialize configuration system early
        codegreen::ConfigLoader config_loader;
        if (!config_loader.is_loaded()) {
            std::cerr << "Warning: " << config_loader.get_error() << std::endl;
            std::cerr << "Continuing with default configuration..." << std::endl;
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
        
        // Cleanup resources before exit
        codegreen::PMTManager::destroy_instance();
        
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        
        // Ensure cleanup even on exceptions
        try {
            codegreen::PMTManager::destroy_instance();
        } catch (...) {
            // Ignore cleanup failures in exception handler
        }
        
        return 1;
    }
}
