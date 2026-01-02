/**
 * @file simple_usage.cpp
 * @brief Simple example demonstrating CodeGreen NEMB energy measurement API
 * 
 * This example shows the basic usage of the CodeGreen Native Energy Measurement
 * Backend (NEMB) for measuring energy consumption of code workloads.
 */

#include "nemb/codegreen_energy.hpp"
#include "nemb/accuracy_validator.hpp"

#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <cmath>

using namespace codegreen;

/**
 * @brief CPU-intensive workload for demonstration
 */
void cpu_intensive_workload(int iterations = 1000000) {
    volatile double result = 0.0;
    for (int i = 0; i < iterations; ++i) {
        result += std::sqrt(i) * std::sin(i / 1000.0);
    }
}

/**
 * @brief Memory-intensive workload for demonstration
 */
void memory_intensive_workload(size_t size_mb = 100) {
    std::vector<double> large_array(size_mb * 1024 * 1024 / sizeof(double));
    
    // Fill array with computed values
    for (size_t i = 0; i < large_array.size(); ++i) {
        large_array[i] = std::sin(i) + std::cos(i);
    }
    
    // Sum all values to prevent optimization
    volatile double sum = 0.0;
    for (double value : large_array) {
        sum += value;
    }
}

/**
 * @brief Demonstrate basic energy measurement
 */
void demonstrate_basic_measurement() {
    std::cout << "\n=== Basic Energy Measurement Demo ===\n";
    
    try {
        // Create energy meter with default (accuracy-optimized) configuration
        EnergyMeter meter;
        
        // Check if energy measurement is available
        if (!meter.is_available()) {
            std::cout << "⚠ Energy measurement not available on this system\n";
            std::cout << "This could be due to:\n";
            std::cout << "  - Insufficient permissions (try running as root)\n";
            std::cout << "  - No supported hardware detected\n";
            std::cout << "  - Missing drivers or kernel modules\n";
            return;
        }
        
        std::cout << "✓ Energy measurement available\n";
        
        // Show available providers
        auto providers = meter.get_provider_info();
        std::cout << \"Detected providers: \";
        for (size_t i = 0; i < providers.size(); ++i) {
            if (i > 0) std::cout << \", \";
            std::cout << providers[i];
        }
        std::cout << \"\\n\\n\";
        
        // Method 1: Manual baseline/end measurement
        std::cout << \"Method 1: Manual measurement\\n\";
        auto baseline = meter.read();
        std::cout << \"Baseline: \" << baseline.summary() << \"\\n\";
        
        // Run workload
        std::cout << \"Running CPU workload...\\n\";
        cpu_intensive_workload(500000);
        
        auto end_reading = meter.read();
        std::cout << \"End reading: \" << end_reading.summary() << \"\\n\";
        
        // Calculate difference
        auto energy_consumed = energy_utils::calculate_difference(end_reading, baseline);
        std::cout << \"Energy consumed: \" << energy_consumed.summary() << \"\\n\\n\";
        
        // Method 2: Automatic measurement with lambda
        std::cout << \"Method 2: Automatic lambda measurement\\n\";
        auto lambda_result = meter.measure([&]() {
            std::cout << \"  Running memory workload...\\n\";
            memory_intensive_workload(50);
        }, \"memory_workload\");
        
        std::cout << \"Lambda result: \" << lambda_result.summary() << \"\\n\\n\";
        
        // Method 3: Scoped measurement (RAII-style)
        std::cout << \"Method 3: Scoped measurement\\n\";
        {
            ScopedEnergyMeter scoped_meter(\"mixed_workload\");
            
            std::cout << \"  Running mixed CPU+memory workload...\\n\";
            cpu_intensive_workload(200000);
            memory_intensive_workload(25);
            
            // Optionally get intermediate results
            auto intermediate = scoped_meter.current();
            std::cout << \"  Intermediate: \" << intermediate.summary() << \"\\n\";
            
            // Results automatically printed on scope exit
        }
        
    } catch (const std::exception& e) {
        std::cerr << \"Error: \" << e.what() << \"\\n\";
    }
}

/**
 * @brief Demonstrate session-based measurement
 */
void demonstrate_session_measurement() {
    std::cout << \"\\n=== Session-Based Measurement Demo ===\\n\";
    
    try {
        EnergyMeter meter;
        
        if (!meter.is_available()) {
            std::cout << \"⚠ Energy measurement not available\\n\";
            return;
        }
        
        // Start a measurement session
        auto session_id = meter.start_session(\"long_running_session\");
        std::cout << \"Started session: \" << session_id << \"\\n\";
        
        // Simulate long-running process with multiple phases
        std::cout << \"Phase 1: Initialization...\\n\";
        cpu_intensive_workload(100000);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        std::cout << \"Phase 2: Processing...\\n\";
        memory_intensive_workload(30);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        std::cout << \"Phase 3: Cleanup...\\n\";
        cpu_intensive_workload(50000);
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        
        // End session and get total energy consumption
        auto session_result = meter.end_session(session_id);
        std::cout << \"Session total: \" << session_result.summary() << \"\\n\\n\";
        
        // Show component breakdown if available
        if (!session_result.component_energy.empty()) {
            std::cout << \"Component breakdown:\\n\";
            for (const auto& [component, energy] : session_result.component_energy) {
                std::cout << \"  \" << component << \": \" 
                         << energy_utils::format_energy(energy) << \"\\n\";
            }
        }
        
    } catch (const std::exception& e) {
        std::cerr << \"Error: \" << e.what() << \"\\n\";
    }
}

/**
 * @brief Demonstrate accuracy validation
 */
void demonstrate_accuracy_validation() {
    std::cout << \"\\n=== Accuracy Validation Demo ===\\n\";
    
    try {
        // Create validator with default configuration
        nemb::AccuracyValidator validator;
        
        std::cout << \"Running comprehensive accuracy validation...\\n\";
        std::cout << \"This may take 10-15 seconds...\\n\\n\";
        
        // Run full validation suite
        auto validation_result = validator.validate_system_accuracy();
        
        // Print detailed report
        std::cout << validation_result.generate_report();
        
        // Summary
        if (validation_result.passed) {
            std::cout << \"\\n✅ System validation PASSED\\n\";
            std::cout << \"Energy measurements are operating within acceptable parameters.\\n\";
        } else {
            std::cout << \"\\n❌ System validation FAILED\\n\";
            std::cout << \"Energy measurements may not be sufficiently accurate.\\n\";
        }
        
    } catch (const std::exception& e) {
        std::cerr << \"Validation error: \" << e.what() << \"\\n\";
    }
}

/**
 * @brief Demonstrate configuration options
 */
void demonstrate_configuration() {
    std::cout << \"\\n=== Configuration Demo ===\\n\";
    
    // Example 1: Accuracy-optimized configuration
    std::cout << \"Accuracy-optimized meter:\\n\";
    try {
        auto accuracy_config = MeasurementConfig::accuracy_optimized();
        EnergyMeter accuracy_meter(accuracy_config);
        
        if (accuracy_meter.is_available()) {
            auto result = accuracy_meter.measure([&]() {
                cpu_intensive_workload(100000);
            }, \"accuracy_test\");
            std::cout << \"  Result: \" << result.summary() << \"\\n\";
        }
    } catch (const std::exception& e) {
        std::cout << \"  Error: \" << e.what() << \"\\n\";
    }
    
    // Example 2: Performance-optimized configuration
    std::cout << \"\\nPerformance-optimized meter:\\n\";
    try {
        auto perf_config = MeasurementConfig::performance_optimized();
        EnergyMeter perf_meter(perf_config);
        
        if (perf_meter.is_available()) {
            auto result = perf_meter.measure([&]() {
                cpu_intensive_workload(100000);
            }, \"performance_test\");
            std::cout << \"  Result: \" << result.summary() << \"\\n\";
        }
    } catch (const std::exception& e) {
        std::cout << \"  Error: \" << e.what() << \"\\n\";
    }
    
    // Example 3: Configuration from file
    std::cout << \"\\nFile-based configuration:\\n\";
    try {
        auto file_config = MeasurementConfig::from_config_file();
        EnergyMeter file_meter(file_config);
        
        if (file_meter.is_available()) {
            std::cout << \"  ✓ Loaded configuration from codegreen.json\\n\";
            
            // Show diagnostics
            auto diagnostics = file_meter.get_diagnostics();
            for (const auto& [key, value] : diagnostics) {
                std::cout << \"  \" << key << \": \" << value << \"\\n\";
            }
        }
    } catch (const std::exception& e) {
        std::cout << \"  Error: \" << e.what() << \"\\n\";
    }
}

/**
 * @brief Demonstrate utility functions
 */
void demonstrate_utilities() {
    std::cout << \"\\n=== Utility Functions Demo ===\\n\";
    
    // Check system support
    if (energy_utils::is_energy_measurement_supported()) {
        std::cout << \"✓ Energy measurement is supported on this system\\n\";
        
        // List available providers
        auto providers = energy_utils::get_available_providers();
        std::cout << \"Available providers: \";
        for (size_t i = 0; i < providers.size(); ++i) {
            if (i > 0) std::cout << \", \";
            std::cout << providers[i];
        }
        std::cout << \"\\n\";
        
        // Validate measurement accuracy
        std::cout << \"\\nValidating measurement accuracy (5 second test)...\\n\";
        double accuracy = energy_utils::validate_measurement_accuracy(5.0);
        if (accuracy >= 0) {
            std::cout << \"Estimated measurement uncertainty: \" 
                     << std::fixed << std::setprecision(1) << accuracy << \"%\\n\";
        } else {
            std::cout << \"Unable to validate accuracy\\n\";
        }
        
    } else {
        std::cout << \"⚠ Energy measurement is not supported on this system\\n\";
    }
    
    // Demonstrate unit conversions
    std::cout << \"\\nUnit conversion examples:\\n\";
    double test_energy = 0.012345; // 12.345 mJ
    std::cout << \"  \" << test_energy << \" J = \" 
             << energy_utils::convert_energy(test_energy, \"mJ\") << \" mJ\\n\";
    std::cout << \"  \" << test_energy << \" J = \" 
             << energy_utils::convert_energy(test_energy, \"Wh\") << \" Wh\\n\";
    
    // Demonstrate formatting
    std::cout << \"\\nFormatting examples:\\n\";
    std::cout << \"  Energy: \" << energy_utils::format_energy(test_energy) << \"\\n\";
    std::cout << \"  Power: \" << energy_utils::format_power(15.678) << \"\\n\";
}

int main() {
    std::cout << \"CodeGreen NEMB (Native Energy Measurement Backend)\\n\";
    std::cout << \"Simple Usage Examples\\n\";
    std::cout << \"=====================\\n\";
    
    // Run all demonstrations
    demonstrate_basic_measurement();
    demonstrate_session_measurement(); 
    demonstrate_accuracy_validation();
    demonstrate_configuration();
    demonstrate_utilities();
    
    std::cout << \"\\n=== Demo Complete ===\\n\";
    std::cout << \"For more advanced usage, see the API documentation and configuration guide.\\n\";
    
    return 0;
}