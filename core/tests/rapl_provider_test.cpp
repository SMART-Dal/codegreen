#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <memory>
#include <iomanip>

#include "nemb/drivers/intel_rapl_provider.hpp"

using namespace codegreen::nemb::drivers;

class RAPLProviderTest {
public:
    bool run_all_tests() {
        std::cout << "🔋 Intel RAPL Provider Test Suite\n";
        std::cout << "=================================\n\n";
        
        bool all_passed = true;
        
        all_passed &= test_provider_availability();
        all_passed &= test_provider_initialization();
        all_passed &= test_reading_validity();
        all_passed &= test_energy_accumulation();
        all_passed &= test_load_response();
        all_passed &= test_counter_wraparound_handling();
        
        std::cout << "\n" << (all_passed ? "✅" : "❌") 
                  << " Overall RAPL Test Result: " 
                  << (all_passed ? "PASSED" : "FAILED") << "\n\n";
        
        return all_passed;
    }

private:
    bool test_provider_availability() {
        std::cout << "🔍 Testing RAPL Provider Availability...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider) {
            std::cout << "  ⚠️  Intel RAPL not available on this system\n";
            std::cout << "  This may be due to:\n";
            std::cout << "    - Non-Intel CPU\n";
            std::cout << "    - Unsupported CPU model\n";
            std::cout << "    - Missing MSR access permissions\n";
            std::cout << "    - Missing sysfs RAPL interface\n";
            return true; // Not a test failure, just not available
        }
        
        std::cout << "  ✅ RAPL provider created successfully\n";
        
        // Test availability check
        bool available = provider->is_available();
        std::cout << "  Available: " << (available ? "Yes" : "No") << "\n";
        
        return true;
    }
    
    bool test_provider_initialization() {
        std::cout << "\n🚀 Testing RAPL Provider Initialization...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider) {
            std::cout << "  ⚠️  RAPL provider not available, skipping initialization test\n";
            return true;
        }
        
        try {
            bool initialized = provider->initialize();
            if (!initialized) {
                std::cout << "  ❌ Provider initialization failed\n";
                return false;
            }
            
            std::cout << "  ✅ Provider initialized successfully\n";
            
            // Get and display specification
            auto spec = provider->get_specification();
            std::cout << "  📋 Provider Specification:\n";
            std::cout << "    Name: " << spec.provider_name << "\n";
            std::cout << "    Type: " << spec.provider_type << "\n";
            std::cout << "    Vendor: " << spec.hardware_vendor << "\n";
            std::cout << "    Energy resolution: " << (spec.energy_resolution_joules * 1e6) << " μJ\n";
            std::cout << "    Power resolution: " << (spec.power_resolution_watts * 1000) << " mW\n";
            std::cout << "    Max frequency: " << spec.max_update_frequency_hz << " Hz\n";
            std::cout << "    Typical accuracy: " << spec.typical_accuracy_percent << "%\n";
            std::cout << "    Requires root: " << (spec.requires_root_access ? "Yes" : "No") << "\n";
            
            std::cout << "    Measurement domains:\n";
            for (const auto& domain : spec.measurement_domains) {
                std::cout << "      - " << domain << "\n";
            }
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception during initialization: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_reading_validity() {
        std::cout << "\n📊 Testing RAPL Reading Validity...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider || !provider->initialize()) {
            std::cout << "  ⚠️  RAPL provider not available, skipping reading test\n";
            return true;
        }
        
        try {
            // Take multiple readings
            std::vector<EnergyReading> readings;
            
            for (int i = 0; i < 5; ++i) {
                auto reading = provider->get_reading();
                readings.push_back(reading);
                
                std::cout << "  📈 Reading " << (i+1) << ":\n";
                std::cout << "    Valid: " << (reading.is_valid ? "Yes" : "No") << "\n";
                
                if (reading.is_valid) {
                    std::cout << std::fixed << std::setprecision(6);
                    std::cout << "    Total energy: " << reading.total_energy_joules << " J\n";
                    std::cout << "    Total power: " << reading.total_power_watts << " W\n";
                    std::cout << "    Components: " << reading.component_breakdown.size() << "\n";
                    std::cout << "    Temperature: " << reading.temperature_celsius << " °C\n";
                    std::cout << "    Frequency: " << reading.frequency_mhz << " MHz\n";
                    std::cout << "    Uncertainty: " << reading.measurement_uncertainty_percent << "%\n";
                    
                    // Display component breakdown
                    for (const auto& component : reading.component_breakdown) {
                        if (component.is_valid) {
                            std::cout << "      " << component.component_name 
                                      << ": " << (component.energy_joules * 1000) << " mJ\n";
                        }
                    }
                } else {
                    std::cout << "    Error: " << reading.error_message << "\n";
                }
                
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
            }
            
            // Validate that we got at least some valid readings
            int valid_count = 0;
            for (const auto& reading : readings) {
                if (reading.is_valid) valid_count++;
            }
            
            if (valid_count == 0) {
                std::cerr << "  ❌ No valid readings obtained\n";
                return false;
            }
            
            std::cout << "  ✅ Got " << valid_count << "/" << readings.size() << " valid readings\n";
            
            // Check for energy monotonicity (energy should generally increase)
            bool monotonic = true;
            for (size_t i = 1; i < readings.size(); ++i) {
                if (readings[i].is_valid && readings[i-1].is_valid) {
                    if (readings[i].total_energy_joules < readings[i-1].total_energy_joules) {
                        monotonic = false;
                        break;
                    }
                }
            }
            
            if (monotonic) {
                std::cout << "  ✅ Energy readings are monotonic\n";
            } else {
                std::cout << "  ⚠️  Energy readings are not monotonic (may indicate counter wraparound)\n";
            }
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception during reading: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_energy_accumulation() {
        std::cout << "\n⚡ Testing Energy Accumulation...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider || !provider->initialize()) {
            std::cout << "  ⚠️  RAPL provider not available, skipping accumulation test\n";
            return true;
        }
        
        try {
            // Reset and take baseline
            auto baseline = provider->get_reading();
            if (!baseline.is_valid) {
                std::cerr << "  ❌ Failed to get baseline reading\n";
                return false;
            }
            
            double baseline_energy = baseline.total_energy_joules;
            std::cout << "  📊 Baseline energy: " << (baseline_energy * 1000) << " mJ\n";
            
            // Wait and measure accumulation
            std::cout << "  ⏱️  Measuring energy accumulation over 2 seconds...\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(2000));
            
            auto final_reading = provider->get_reading();
            if (!final_reading.is_valid) {
                std::cerr << "  ❌ Failed to get final reading\n";
                return false;
            }
            
            double final_energy = final_reading.total_energy_joules;
            double energy_delta = final_energy - baseline_energy;
            double average_power = energy_delta / 2.0; // 2 seconds
            
            std::cout << "  📊 Results:\n";
            std::cout << "    Final energy: " << (final_energy * 1000) << " mJ\n";
            std::cout << "    Energy delta: " << (energy_delta * 1000) << " mJ\n";
            std::cout << "    Average power: " << average_power << " W\n";
            
            // Validate results
            if (energy_delta < 0) {
                std::cerr << "  ❌ Negative energy delta - possible counter issue\n";
                return false;
            }
            
            if (energy_delta < 0.001) { // Less than 1mJ over 2 seconds
                std::cout << "  ⚠️  Very low energy delta - system may be idle\n";
            } else {
                std::cout << "  ✅ Reasonable energy accumulation detected\n";
            }
            
            if (average_power > 500.0) { // Sanity check
                std::cout << "  ⚠️  Very high power consumption - check readings\n";
            }
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception during accumulation test: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_load_response() {
        std::cout << "\n🔥 Testing Load Response...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider || !provider->initialize()) {
            std::cout << "  ⚠️  RAPL provider not available, skipping load test\n";
            return true;
        }
        
        try {
            // Measure idle power
            std::cout << "  😴 Measuring idle power...\n";
            std::vector<double> idle_powers;
            for (int i = 0; i < 5; ++i) {
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                auto reading = provider->get_reading();
                if (reading.is_valid) {
                    idle_powers.push_back(reading.total_power_watts);
                }
            }
            
            if (idle_powers.empty()) {
                std::cerr << "  ❌ No valid idle power readings\n";
                return false;
            }
            
            double avg_idle_power = std::accumulate(idle_powers.begin(), idle_powers.end(), 0.0) / idle_powers.size();
            std::cout << "  📊 Average idle power: " << avg_idle_power << " W\n";
            
            // Create CPU load
            std::cout << "  🔥 Creating CPU load...\n";
            volatile bool stop_load = false;
            std::thread load_thread([&stop_load]() {
                volatile double result = 0.0;
                while (!stop_load) {
                    for (int i = 0; i < 100000; ++i) {
                        result += std::sqrt(i * 3.14159);
                    }
                }
            });
            
            // Wait for load to ramp up
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            
            // Measure load power
            std::vector<double> load_powers;
            for (int i = 0; i < 5; ++i) {
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                auto reading = provider->get_reading();
                if (reading.is_valid) {
                    load_powers.push_back(reading.total_power_watts);
                }
            }
            
            stop_load = true;
            load_thread.join();
            
            if (load_powers.empty()) {
                std::cerr << "  ❌ No valid load power readings\n";
                return false;
            }
            
            double avg_load_power = std::accumulate(load_powers.begin(), load_powers.end(), 0.0) / load_powers.size();
            double power_increase = avg_load_power - avg_idle_power;
            
            std::cout << "  📊 Load test results:\n";
            std::cout << "    Average load power: " << avg_load_power << " W\n";
            std::cout << "    Power increase: " << power_increase << " W\n";
            std::cout << "    Relative increase: " << (power_increase / avg_idle_power * 100) << "%\n";
            
            // Validate response
            if (power_increase < 0.5) {
                std::cout << "  ⚠️  Low power increase - may indicate measurement issues\n";
            } else {
                std::cout << "  ✅ CPU load detected by power measurements\n";
            }
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception during load test: " << e.what() << "\n";
            return false;
        }
    }
    
    bool test_counter_wraparound_handling() {
        std::cout << "\n🔄 Testing Counter Wraparound Handling...\n";
        
        auto provider = create_intel_rapl_provider();
        if (!provider || !provider->initialize()) {
            std::cout << "  ⚠️  RAPL provider not available, skipping wraparound test\n";
            return true;
        }
        
        try {
            // This is a conceptual test - actual wraparound would take hours
            std::cout << "  📊 Testing counter consistency over time...\n";
            
            std::vector<double> energy_values;
            uint64_t start_time = 0;
            
            for (int i = 0; i < 20; ++i) {
                auto reading = provider->get_reading();
                if (reading.is_valid) {
                    energy_values.push_back(reading.total_energy_joules);
                    if (start_time == 0) {
                        start_time = reading.timestamp_ns;
                    }
                    
                    std::cout << "    Sample " << (i+1) << ": " 
                              << (reading.total_energy_joules * 1000) << " mJ\n";
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            
            if (energy_values.size() < 10) {
                std::cerr << "  ❌ Insufficient valid samples for wraparound test\n";
                return false;
            }
            
            // Check for monotonicity (allowing for small decreases due to measurement noise)
            int non_monotonic_count = 0;
            for (size_t i = 1; i < energy_values.size(); ++i) {
                if (energy_values[i] < energy_values[i-1] - 0.001) { // Allow 1mJ tolerance
                    non_monotonic_count++;
                }
            }
            
            double non_monotonic_rate = static_cast<double>(non_monotonic_count) / (energy_values.size() - 1);
            
            std::cout << "  📊 Monotonicity analysis:\n";
            std::cout << "    Samples: " << energy_values.size() << "\n";
            std::cout << "    Non-monotonic: " << non_monotonic_count << "\n";
            std::cout << "    Non-monotonic rate: " << (non_monotonic_rate * 100) << "%\n";
            
            if (non_monotonic_rate > 0.2) { // More than 20%
                std::cout << "  ⚠️  High non-monotonic rate - possible counter issues\n";
            } else {
                std::cout << "  ✅ Counter behavior appears consistent\n";
            }
            
            // Calculate total energy range
            double min_energy = *std::min_element(energy_values.begin(), energy_values.end());
            double max_energy = *std::max_element(energy_values.begin(), energy_values.end());
            double energy_range = max_energy - min_energy;
            
            std::cout << "    Energy range: " << (energy_range * 1000) << " mJ\n";
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "  ❌ Exception during wraparound test: " << e.what() << "\n";
            return false;
        }
    }
};

int main(int argc, char* argv[]) {
    std::cout << "Intel RAPL Provider Validation Test\n";
    std::cout << "Version: 1.0.0\n";
    std::cout << "Build: " << __DATE__ << " " << __TIME__ << "\n\n";
    
    RAPLProviderTest test_suite;
    bool success = test_suite.run_all_tests();
    
    return success ? 0 : 1;
}