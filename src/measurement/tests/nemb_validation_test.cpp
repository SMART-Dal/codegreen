#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <memory>
#include <cmath>

#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/drivers/intel_rapl_provider.hpp"
#include "nemb/utils/precision_timer.hpp"

using namespace codegreen::nemb;

class NEMBValidationTest {
public:
    bool run_all_tests() {
        std::cout << "🧪 Starting NEMB Validation Test Suite\n";
        std::cout << "======================================\n\n";
        
        bool all_passed = true;
        
        all_passed &= test_precision_timer();
        all_passed &= test_intel_rapl_provider();
        all_passed &= test_measurement_coordinator();
        all_passed &= test_energy_measurement_accuracy();
        all_passed &= test_performance_overhead();
        
        std::cout << "\n" << (all_passed ? "✅" : "❌") 
                  << " Overall Test Result: " 
                  << (all_passed ? "PASSED" : "FAILED") << "\n\n";
        
        return all_passed;
    }

private:
    bool test_precision_timer() {
        std::cout << "🕒 Testing Precision Timer...\n";
        
        try {
            utils::PrecisionTimer timer;
            if (!timer.initialize()) {
                std::cerr << "  ❌ Failed to initialize precision timer\n";
                return false;
            }
            
            std::cout << "  ✅ Timer initialized\n";
            std::cout << "  Clock source: " << timer.get_clock_source_name() << "\n";
            std::cout << "  Resolution: " << timer.get_resolution_ns() << " ns\n";
            
            // Test timestamp consistency
            uint64_t start_time = timer.get_timestamp_ns();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            uint64_t end_time = timer.get_timestamp_ns();
            
            if (end_time <= start_time) {
                std::cerr << "  ❌ Timestamp not monotonic\n";
                return false;
            }
            
            double elapsed_ms = (end_time - start_time) / 1e6;
            if (elapsed_ms < 9.0 || elapsed_ms > 15.0) {
                std::cerr << "  ❌ Timer accuracy poor: " << elapsed_ms << " ms\n";
                return false;
            }
            
            std::cout << "  ✅ Timer accuracy: " << elapsed_ms << " ms (expected ~10ms)\n";
            
            // Test ScopedTimer
            {
                utils::ScopedTimer scoped("Test operation");
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            } // Should print elapsed time
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_intel_rapl_provider() {
        std::cout << "\n🔋 Testing Intel RAPL Provider...\n";
        
        try {
            auto provider = drivers::create_intel_rapl_provider();
            if (!provider) {
                std::cout << "  ⚠️  Intel RAPL not available on this system\n";
                return true; // Not a failure, just not available
            }
            
            std::cout << "  ✅ RAPL provider created\n";
            
            if (!provider->initialize()) {
                std::cerr << "  ❌ Failed to initialize RAPL provider\n";
                return false;
            }
            
            std::cout << "  ✅ RAPL provider initialized\n";
            
            // Get specification
            auto spec = provider->get_specification();
            std::cout << "  Provider: " << spec.provider_name << "\n";
            std::cout << "  Energy resolution: " << (spec.energy_resolution_joules * 1e6) << " μJ\n";
            std::cout << "  Max frequency: " << spec.max_update_frequency_hz << " Hz\n";
            std::cout << "  Typical accuracy: " << spec.typical_accuracy_percent << "%\n";
            
            // Test reading
            auto reading = provider->get_reading();
            if (!reading.is_valid) {
                std::cerr << "  ❌ Failed to get valid reading: " << reading.error_message << "\n";
                return false;
            }
            
            std::cout << "  ✅ Got valid reading\n";
            std::cout << "    Total energy: " << (reading.total_energy_joules * 1000) << " mJ\n";
            std::cout << "    Total power: " << reading.total_power_watts << " W\n";
            std::cout << "    Components: " << reading.component_breakdown.size() << "\n";
            
            // Run self-test
            if (!provider->self_test()) {
                std::cerr << "  ❌ Provider self-test failed\n";
                return false;
            }
            
            std::cout << "  ✅ Provider self-test passed\n";
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_measurement_coordinator() {
        std::cout << "\n🎛️  Testing Measurement Coordinator...\n";
        
        try {
            MeasurementCoordinator coordinator;
            
            if (!coordinator.initialize()) {
                std::cerr << "  ❌ Failed to initialize coordinator\n";
                return false;
            }
            
            std::cout << "  ✅ Coordinator initialized\n";
            
            // Try to add Intel RAPL provider
            auto provider = drivers::create_intel_rapl_provider();
            if (provider) {
                if (!coordinator.add_provider(std::move(provider))) {
                    std::cerr << "  ❌ Failed to add RAPL provider\n";
                    return false;
                }
                
                std::cout << "  ✅ Added RAPL provider\n";
                
                // Start measurements
                if (!coordinator.start_measurements()) {
                    std::cerr << "  ❌ Failed to start measurements\n";
                    return false;
                }
                
                std::cout << "  ✅ Started measurements\n";
                
                // Take some synchronized readings
                for (int i = 0; i < 5; ++i) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    
                    auto reading = coordinator.get_synchronized_reading();
                    if (!reading.is_valid) {
                        std::cerr << "  ❌ Invalid synchronized reading: " << reading.error_message << "\n";
                        return false;
                    }
                    
                    std::cout << "  📊 Reading " << (i+1) << ": "
                              << reading.total_system_power_watts << " W, "
                              << "providers: " << reading.successful_providers << "/"
                              << reading.total_providers << "\n";
                }
                
                coordinator.stop_measurements();
                std::cout << "  ✅ Stopped measurements\n";
                
                // Print statistics
                auto stats = coordinator.get_measurement_statistics();
                std::cout << "  📈 Statistics:\n";
                std::cout << "    Total readings: " << stats.total_readings << "\n";
                std::cout << "    Success rate: " << (stats.success_rate * 100) << "%\n";
                std::cout << "    Avg overhead: " << (stats.average_coordination_overhead_ns / 1000.0) << " μs\n";
                
            } else {
                std::cout << "  ⚠️  No RAPL provider available, testing coordinator without providers\n";
            }
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_energy_measurement_accuracy() {
        std::cout << "\n⚡ Testing Energy Measurement Accuracy...\n";
        
        try {
            MeasurementCoordinator coordinator;
            if (!coordinator.initialize()) {
                std::cerr << "  ❌ Failed to initialize coordinator\n";
                return false;
            }
            
            auto provider = drivers::create_intel_rapl_provider();
            if (!provider) {
                std::cout << "  ⚠️  No RAPL provider available, skipping accuracy test\n";
                return true;
            }
            
            if (!coordinator.add_provider(std::move(provider))) {
                std::cerr << "  ❌ Failed to add provider\n";
                return false;
            }
            
            if (!coordinator.start_measurements()) {
                std::cerr << "  ❌ Failed to start measurements\n";
                return false;
            }
            
            // Baseline measurement
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            auto baseline = coordinator.get_synchronized_reading();
            if (!baseline.is_valid) {
                std::cerr << "  ❌ Invalid baseline reading\n";
                return false;
            }
            
            std::cout << "  📊 Baseline power: " << baseline.total_system_power_watts << " W\n";
            
            // CPU load test
            std::cout << "  🔥 Starting CPU load test...\n";
            auto load_start_time = std::chrono::steady_clock::now();
            
            // Start CPU load in separate thread
            volatile bool stop_load = false;
            std::thread load_thread([&stop_load]() {
                volatile double result = 0.0;
                while (!stop_load) {
                    for (int i = 0; i < 100000; ++i) {
                        result += std::sqrt(i * 3.14159);
                    }
                }
            });
            
            // Measure during load
            std::vector<double> load_powers;
            for (int i = 0; i < 10; ++i) {
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                auto reading = coordinator.get_synchronized_reading();
                if (reading.is_valid) {
                    load_powers.push_back(reading.total_system_power_watts);
                }
            }
            
            stop_load = true;
            load_thread.join();
            
            auto load_end_time = std::chrono::steady_clock::now();
            auto load_duration = std::chrono::duration_cast<std::chrono::seconds>(
                load_end_time - load_start_time);
            
            if (load_powers.empty()) {
                std::cerr << "  ❌ No valid power readings during load test\n";
                return false;
            }
            
            double avg_load_power = std::accumulate(load_powers.begin(), load_powers.end(), 0.0) / load_powers.size();
            double power_increase = avg_load_power - baseline.total_system_power_watts;
            
            std::cout << "  📊 Load test results:\n";
            std::cout << "    Duration: " << load_duration.count() << " seconds\n";
            std::cout << "    Average load power: " << avg_load_power << " W\n";
            std::cout << "    Power increase: " << power_increase << " W\n";
            
            // Validate results
            if (power_increase < 1.0) {
                std::cout << "  ⚠️  Low power increase detected - may indicate measurement issue\n";
            } else {
                std::cout << "  ✅ Reasonable power increase detected\n";
            }
            
            coordinator.stop_measurements();
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_performance_overhead() {
        std::cout << "\n⚡ Testing Performance Overhead...\n";
        
        try {
            MeasurementCoordinator coordinator;
            if (!coordinator.initialize()) {
                std::cerr << "  ❌ Failed to initialize coordinator\n";
                return false;
            }
            
            auto provider = drivers::create_intel_rapl_provider();
            if (!provider) {
                std::cout << "  ⚠️  No RAPL provider available, skipping overhead test\n";
                return true;
            }
            
            if (!coordinator.add_provider(std::move(provider))) {
                std::cerr << "  ❌ Failed to add provider\n";
                return false;
            }
            
            if (!coordinator.start_measurements()) {
                std::cerr << "  ❌ Failed to start measurements\n";
                return false;
            }
            
            // High-frequency measurement test
            std::cout << "  📊 Measuring coordination overhead...\n";
            
            auto start_time = std::chrono::high_resolution_clock::now();
            const int num_measurements = 1000;
            
            for (int i = 0; i < num_measurements; ++i) {
                auto reading = coordinator.get_synchronized_reading();
                // Don't check validity to avoid extra overhead
            }
            
            auto end_time = std::chrono::high_resolution_clock::now();
            auto total_time = std::chrono::duration_cast<std::chrono::microseconds>(
                end_time - start_time);
            
            double avg_time_us = static_cast<double>(total_time.count()) / num_measurements;
            
            std::cout << "  📈 Overhead results:\n";
            std::cout << "    Total measurements: " << num_measurements << "\n";
            std::cout << "    Total time: " << total_time.count() << " μs\n";
            std::cout << "    Average per measurement: " << avg_time_us << " μs\n";
            
            // Validate overhead is reasonable (target: <100 μs per measurement)
            if (avg_time_us > 100.0) {
                std::cout << "  ⚠️  High overhead detected: " << avg_time_us << " μs\n";
            } else {
                std::cout << "  ✅ Acceptable overhead: " << avg_time_us << " μs\n";
            }
            
            coordinator.stop_measurements();
            
            // Get final statistics
            auto stats = coordinator.get_measurement_statistics();
            std::cout << "  📊 Final coordinator statistics:\n";
            std::cout << "    Max latency: " << (stats.max_reading_latency_ns / 1000.0) << " μs\n";
            std::cout << "    Success rate: " << (stats.success_rate * 100) << "%\n";
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception: " << e.what() << "\n";
            return false;
        }
    }
};

int main(int argc, char* argv[]) {
    std::cout << "NEMB (Native Energy Measurement Backend) Validation Test\n";
    std::cout << "Version: 1.0.0\n";
    std::cout << "Build: " << __DATE__ << " " << __TIME__ << "\n\n";
    
    NEMBValidationTest test_suite;
    bool success = test_suite.run_all_tests();
    
    return success ? 0 : 1;
}