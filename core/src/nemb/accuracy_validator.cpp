#include "nemb/accuracy_validator.hpp"
#include "nemb/codegreen_energy.hpp"
#include "nemb/utils/precision_timer.hpp"

#include <thread>
#include <chrono>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <random>
#include <sstream>
#include <iomanip>
#include <iostream>

namespace codegreen::nemb {

AccuracyValidator::AccuracyValidator(const ValidationConfig& config)
    : config_(config), timer_(utils::PrecisionTimer::ClockSource::TSC_INVARIANT) {}

ValidationResult AccuracyValidator::validate_system_accuracy() {
    ValidationResult result;
    result.timestamp = std::chrono::system_clock::now();
    
    try {
        // Test 1: Basic functionality
        auto basic_test = test_basic_functionality();
        result.tests.emplace_back("basic_functionality", basic_test);
        
        // Test 2: Measurement precision
        auto precision_test = test_measurement_precision();
        result.tests.emplace_back("measurement_precision", precision_test);
        
        // Test 3: Temporal stability
        auto stability_test = test_temporal_stability();
        result.tests.emplace_back("temporal_stability", stability_test);
        
        // Test 4: Load responsiveness
        auto responsiveness_test = test_load_responsiveness();
        result.tests.emplace_back("load_responsiveness", responsiveness_test);
        
        // Test 5: Cross-validation (if multiple providers available)
        auto cross_validation_test = test_cross_validation();
        result.tests.emplace_back("cross_validation", cross_validation_test);
        
        // Test 6: Overhead measurement
        auto overhead_test = measure_measurement_overhead();
        result.tests.emplace_back("measurement_overhead", overhead_test);
        
        // Calculate overall score
        result.overall_score = calculate_overall_score(result.tests);
        result.passed = result.overall_score >= config_.min_acceptable_score;
        
        // Generate recommendations
        result.recommendations = generate_recommendations(result.tests);
        
    } catch (const std::exception& e) {
        result.passed = false;
        result.overall_score = 0.0;
        result.error_message = e.what();
    }
    
    return result;
}

ValidationTest AccuracyValidator::test_basic_functionality() {
    ValidationTest test;
    test.description = "Tests basic energy measurement functionality";
    
    try {
        EnergyMeter meter;
        
        if (!meter.is_available()) {
            test.passed = false;
            test.score = 0.0;
            test.details = "Energy measurement not available";
            return test;
        }
        
        // Take two readings
        auto reading1 = meter.read();
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        auto reading2 = meter.read();
        
        // Validate readings
        bool valid_readings = reading1.is_valid && reading2.is_valid;
        bool energy_progression = reading2.energy_joules >= reading1.energy_joules;
        bool reasonable_values = reading1.energy_joules >= 0 && reading1.power_watts >= 0;
        
        test.passed = valid_readings && energy_progression && reasonable_values;
        test.score = test.passed ? 1.0 : 0.0;
        test.uncertainty_percent = std::max(reading1.uncertainty_percent, reading2.uncertainty_percent);
        
        std::ostringstream details;
        details << "Reading1: " << reading1.summary() << "\n";
        details << "Reading2: " << reading2.summary() << "\n";
        details << "Valid readings: " << (valid_readings ? "✓" : "✗") << "\n";
        details << "Energy progression: " << (energy_progression ? "✓" : "✗") << "\n";
        details << "Reasonable values: " << (reasonable_values ? "✓" : "✗");
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

ValidationTest AccuracyValidator::test_measurement_precision() {
    ValidationTest test;
    test.description = "Tests measurement precision and repeatability";
    
    try {
        EnergyMeter meter;
        std::vector<double> measurements;
        
        // Take multiple quick measurements
        for (int i = 0; i < config_.precision_test_samples; ++i) {
            auto reading = meter.read();
            if (reading.is_valid) {
                measurements.push_back(reading.power_watts);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        
        if (measurements.size() < config_.precision_test_samples / 2) {
            test.passed = false;
            test.score = 0.0;
            test.details = "Insufficient valid measurements for precision test";
            return test;
        }
        
        // Calculate statistics
        double mean = std::accumulate(measurements.begin(), measurements.end(), 0.0) / measurements.size();
        
        double variance = 0.0;
        for (double measurement : measurements) {
            variance += (measurement - mean) * (measurement - mean);
        }
        variance /= measurements.size();
        double stddev = std::sqrt(variance);
        
        double coefficient_of_variation = (mean > 0) ? (stddev / mean) : 1.0;
        test.uncertainty_percent = coefficient_of_variation * 100.0;
        
        // Precision is good if coefficient of variation is low
        test.passed = coefficient_of_variation < config_.max_coefficient_of_variation;
        test.score = std::max(0.0, 1.0 - (coefficient_of_variation / config_.max_coefficient_of_variation));
        
        std::ostringstream details;
        details << "Samples: " << measurements.size() << "\n";
        details << "Mean power: " << energy_utils::format_power(mean) << "\n";
        details << "Std deviation: " << energy_utils::format_power(stddev) << "\n";
        details << "Coefficient of variation: " << std::fixed << std::setprecision(2) << (coefficient_of_variation * 100) << "%\n";
        details << "Target: <" << std::fixed << std::setprecision(1) << (config_.max_coefficient_of_variation * 100) << "%";
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

ValidationTest AccuracyValidator::test_temporal_stability() {
    ValidationTest test;
    test.description = "Tests measurement stability over time";
    
    try {
        EnergyMeter meter;
        std::vector<double> power_readings;
        std::vector<uint64_t> timestamps;
        
        auto start_time = std::chrono::steady_clock::now();
        
        // Collect measurements over time
        while (std::chrono::steady_clock::now() - start_time < config_.stability_test_duration) {
            auto reading = meter.read();
            if (reading.is_valid) {
                power_readings.push_back(reading.power_watts);
                timestamps.push_back(reading.timestamp_ns);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        if (power_readings.size() < 10) {
            test.passed = false;
            test.score = 0.0;
            test.details = "Insufficient measurements for stability test";
            return test;
        }
        
        // Analyze temporal stability using sliding window
        std::vector<double> stability_metrics;
        const size_t window_size = std::min(size_t(10), power_readings.size() / 2);
        
        for (size_t i = 0; i + window_size < power_readings.size(); ++i) {
            double window_mean = 0.0;
            for (size_t j = 0; j < window_size; ++j) {
                window_mean += power_readings[i + j];
            }
            window_mean /= window_size;
            
            double window_variance = 0.0;
            for (size_t j = 0; j < window_size; ++j) {
                window_variance += (power_readings[i + j] - window_mean) * (power_readings[i + j] - window_mean);
            }
            window_variance /= window_size;
            
            if (window_mean > 0) {
                stability_metrics.push_back(std::sqrt(window_variance) / window_mean);
            }
        }
        
        // Calculate average stability metric
        double avg_stability = std::accumulate(stability_metrics.begin(), stability_metrics.end(), 0.0) / stability_metrics.size();
        test.uncertainty_percent = avg_stability * 100.0;
        
        test.passed = avg_stability < config_.max_temporal_variation;
        test.score = std::max(0.0, 1.0 - (avg_stability / config_.max_temporal_variation));
        
        std::ostringstream details;
        details << "Duration: " << std::chrono::duration<double>(config_.stability_test_duration).count() << "s\n";
        details << "Samples: " << power_readings.size() << "\n";
        details << "Average stability metric: " << std::fixed << std::setprecision(3) << (avg_stability * 100) << "%\n";
        details << "Target: <" << std::fixed << std::setprecision(1) << (config_.max_temporal_variation * 100) << "%";
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

ValidationTest AccuracyValidator::test_load_responsiveness() {
    ValidationTest test;
    test.description = "Tests responsiveness to CPU load changes";
    
    try {
        EnergyMeter meter;
        
        // Measure idle power
        std::vector<double> idle_measurements;
        for (int i = 0; i < 5; ++i) {
            auto reading = meter.read();
            if (reading.is_valid) {
                idle_measurements.push_back(reading.power_watts);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
        
        if (idle_measurements.empty()) {
            test.passed = false;
            test.score = 0.0;
            test.details = "Could not measure idle power";
            return test;
        }
        
        double idle_power = std::accumulate(idle_measurements.begin(), idle_measurements.end(), 0.0) / idle_measurements.size();
        
        // Create CPU load and measure
        auto load_energy = meter.measure([&]() {
            auto load_start = std::chrono::steady_clock::now();
            volatile double result = 0.0;
            
            // CPU-intensive workload for 2 seconds
            while (std::chrono::steady_clock::now() - load_start < std::chrono::seconds(2)) {
                for (int i = 0; i < 100000; ++i) {
                    result += std::sqrt(i) * std::sin(i);
                }
            }
        }, "load_test");
        
        if (!load_energy.is_valid || load_energy.duration_seconds < 1.5) {
            test.passed = false;
            test.score = 0.0;
            test.details = "Load test failed or too short";
            return test;
        }
        
        double load_power = load_energy.average_power_watts;
        double power_increase = load_power - idle_power;
        double power_increase_percent = (idle_power > 0) ? (power_increase / idle_power) : 0.0;
        
        // Expect at least 10% power increase during CPU load
        const double MIN_EXPECTED_INCREASE = 0.10;
        test.passed = power_increase_percent >= MIN_EXPECTED_INCREASE;
        test.score = std::min(1.0, power_increase_percent / MIN_EXPECTED_INCREASE);
        test.uncertainty_percent = load_energy.uncertainty_percent;
        
        std::ostringstream details;
        details << "Idle power: " << energy_utils::format_power(idle_power) << "\n";
        details << "Load power: " << energy_utils::format_power(load_power) << "\n";
        details << "Power increase: " << energy_utils::format_power(power_increase) << " (" 
                << std::fixed << std::setprecision(1) << (power_increase_percent * 100) << "%)\n";
        details << "Expected: ≥" << (MIN_EXPECTED_INCREASE * 100) << "% increase\n";
        details << "Energy consumed: " << energy_utils::format_energy(load_energy.energy_joules);
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

ValidationTest AccuracyValidator::test_cross_validation() {
    ValidationTest test;
    test.description = "Tests cross-validation between multiple providers";
    
    try {
        EnergyMeter meter;
        auto providers = meter.get_provider_info();
        
        if (providers.size() < 2) {
            test.passed = true;  // Not applicable with single provider
            test.score = 1.0;
            test.details = "Cross-validation not applicable (single provider)";
            return test;
        }
        
        // Take multiple readings and check consistency
        std::vector<EnergyResult> readings;
        for (int i = 0; i < 10; ++i) {
            auto reading = meter.read();
            if (reading.is_valid && reading.components.size() >= 2) {
                readings.push_back(reading);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        if (readings.empty()) {
            test.passed = false;
            test.score = 0.0;
            test.details = "No multi-component readings available";
            return test;
        }
        
        // Check consistency between component measurements
        std::vector<double> consistency_scores;
        
        for (const auto& reading : readings) {
            if (reading.components.size() >= 2) {
                auto components = reading.components;
                std::vector<double> component_powers;
                
                for (const auto& [name, energy] : components) {
                    // Convert energy to power (this is approximate)
                    component_powers.push_back(energy * 10.0); // Rough conversion
                }
                
                if (component_powers.size() >= 2) {
                    double mean_power = std::accumulate(component_powers.begin(), component_powers.end(), 0.0) / component_powers.size();
                    double max_deviation = 0.0;
                    
                    for (double power : component_powers) {
                        max_deviation = std::max(max_deviation, std::abs(power - mean_power) / mean_power);
                    }
                    
                    consistency_scores.push_back(1.0 - std::min(1.0, max_deviation));
                }
            }
        }
        
        if (consistency_scores.empty()) {
            test.passed = true;
            test.score = 1.0;
            test.details = "Cross-validation not applicable (insufficient component data)";
            return test;
        }
        
        double avg_consistency = std::accumulate(consistency_scores.begin(), consistency_scores.end(), 0.0) / consistency_scores.size();
        test.score = avg_consistency;
        test.passed = avg_consistency >= config_.min_cross_validation_score;
        test.uncertainty_percent = (1.0 - avg_consistency) * 100.0;
        
        std::ostringstream details;
        details << "Providers: " << providers.size() << "\n";
        details << "Readings analyzed: " << consistency_scores.size() << "\n";
        details << "Average consistency: " << std::fixed << std::setprecision(2) << (avg_consistency * 100) << "%\n";
        details << "Target: ≥" << (config_.min_cross_validation_score * 100) << "%";
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

ValidationTest AccuracyValidator::measure_measurement_overhead() {
    ValidationTest test;
    test.description = "Measures the overhead introduced by energy measurements";
    
    try {
        const int NUM_ITERATIONS = 10000;
        
        // Measure time without energy measurement
        auto start_no_measurement = timer_.get_timestamp_ns();
        volatile double result = 0.0;
        for (int i = 0; i < NUM_ITERATIONS; ++i) {
            result += std::sqrt(i);
        }
        auto end_no_measurement = timer_.get_timestamp_ns();
        
        double time_no_measurement = (end_no_measurement - start_no_measurement) / 1e9;
        
        // Measure time with energy measurement
        EnergyMeter meter;
        auto start_with_measurement = timer_.get_timestamp_ns();
        result = 0.0;
        for (int i = 0; i < NUM_ITERATIONS; ++i) {
            if (i % 1000 == 0) {  // Take measurement every 1000 iterations
                meter.read();
            }
            result += std::sqrt(i);
        }
        auto end_with_measurement = timer_.get_timestamp_ns();
        
        double time_with_measurement = (end_with_measurement - start_with_measurement) / 1e9;
        
        double overhead_seconds = time_with_measurement - time_no_measurement;
        double overhead_percent = (time_no_measurement > 0) ? (overhead_seconds / time_no_measurement * 100.0) : 0.0;
        
        test.passed = overhead_percent <= config_.max_acceptable_overhead_percent;
        test.score = std::max(0.0, 1.0 - (overhead_percent / config_.max_acceptable_overhead_percent));
        test.uncertainty_percent = overhead_percent;
        
        std::ostringstream details;
        details << "Iterations: " << NUM_ITERATIONS << "\n";
        details << "Time without measurement: " << std::fixed << std::setprecision(6) << time_no_measurement << "s\n";
        details << "Time with measurement: " << std::fixed << std::setprecision(6) << time_with_measurement << "s\n";
        details << "Overhead: " << std::fixed << std::setprecision(6) << overhead_seconds << "s (" 
                << std::setprecision(2) << overhead_percent << "%)\n";
        details << "Target: ≤" << config_.max_acceptable_overhead_percent << "%";
        test.details = details.str();
        
    } catch (const std::exception& e) {
        test.passed = false;
        test.score = 0.0;
        test.details = std::string("Exception: ") + e.what();
    }
    
    return test;
}

double AccuracyValidator::calculate_overall_score(const std::vector<std::pair<std::string, ValidationTest>>& tests) {
    if (tests.empty()) return 0.0;
    
    double weighted_score = 0.0;
    double total_weight = 0.0;
    
    // Define test weights based on importance
    std::map<std::string, double> weights = {
        {"basic_functionality", 0.3},
        {"measurement_precision", 0.2},
        {"temporal_stability", 0.15},
        {"load_responsiveness", 0.15},
        {"cross_validation", 0.1},
        {"measurement_overhead", 0.1}
    };
    
    for (const auto& [test_name, test] : tests) {
        double weight = weights.count(test_name) ? weights[test_name] : 0.1;
        weighted_score += test.score * weight;
        total_weight += weight;
    }
    
    return total_weight > 0 ? (weighted_score / total_weight) : 0.0;
}

std::vector<std::string> AccuracyValidator::generate_recommendations(const std::vector<std::pair<std::string, ValidationTest>>& tests) {
    std::vector<std::string> recommendations;
    
    for (const auto& [test_name, test] : tests) {
        if (!test.passed) {
            if (test_name == "basic_functionality") {
                recommendations.push_back("Energy measurement hardware may not be properly configured or accessible");
                recommendations.push_back("Check system permissions and hardware drivers");
            } else if (test_name == "measurement_precision") {
                recommendations.push_back("High measurement variability detected - consider enabling noise filtering");
                recommendations.push_back("Check for system background activity affecting measurements");
            } else if (test_name == "temporal_stability") {
                recommendations.push_back("Measurements show temporal instability - enable outlier detection");
                recommendations.push_back("Consider using longer averaging windows for measurements");
            } else if (test_name == "load_responsiveness") {
                recommendations.push_back("Energy measurements may not be responsive to CPU load changes");
                recommendations.push_back("Verify that CPU energy monitoring is enabled and functional");
            } else if (test_name == "cross_validation") {
                recommendations.push_back("Cross-validation between providers failed - check provider configuration");
            } else if (test_name == "measurement_overhead") {
                recommendations.push_back("Measurement overhead is higher than expected");
                recommendations.push_back("Consider reducing measurement frequency or enabling performance mode");
            }
        }
        
        if (test.uncertainty_percent > config_.target_uncertainty_percent * 2.0) {
            recommendations.push_back("High measurement uncertainty detected in " + test_name);
            recommendations.push_back("Consider enabling accuracy optimization features");
        }
    }
    
    if (recommendations.empty()) {
        recommendations.push_back("System validation passed - energy measurements are operating within expected parameters");
    }
    
    return recommendations;
}

ValidationTest AccuracyValidator::run_individual_test(const std::string& test_name) {
    if (test_name == "basic_functionality") {
        return test_basic_functionality();
    } else if (test_name == "measurement_precision") {
        return test_measurement_precision();
    } else if (test_name == "temporal_stability") {
        return test_temporal_stability();
    } else if (test_name == "load_responsiveness") {
        return test_load_responsiveness();
    } else if (test_name == "cross_validation") {
        return test_cross_validation();
    } else if (test_name == "measurement_overhead") {
        return measure_measurement_overhead();
    } else {
        ValidationTest error_test;
        error_test.description = "Unknown test: " + test_name;
        error_test.passed = false;
        error_test.score = 0.0;
        error_test.details = "Test name not recognized";
        return error_test;
    }
}

std::string ValidationResult::generate_report() const {
    std::ostringstream report;
    report << std::fixed << std::setprecision(2);
    
    report << "\n=== CodeGreen Energy Measurement Accuracy Validation Report ===\n";
    report << "Timestamp: " << std::chrono::duration_cast<std::chrono::seconds>(timestamp.time_since_epoch()).count() << "\n";
    report << "Overall Result: " << (passed ? "PASSED" : "FAILED") << "\n";
    report << "Overall Score: " << (overall_score * 100) << "%\n\n";
    
    if (!error_message.empty()) {
        report << "Error: " << error_message << "\n\n";
    }
    
    report << "=== Individual Test Results ===\n";
    for (const auto& [test_name, test] : tests) {
        report << "\n" << test_name << ":\n";
        report << "  Description: " << test.description << "\n";
        report << "  Result: " << (test.passed ? "PASSED" : "FAILED") << "\n";
        report << "  Score: " << (test.score * 100) << "%\n";
        if (test.uncertainty_percent > 0) {
            report << "  Uncertainty: " << test.uncertainty_percent << "%\n";
        }
        if (!test.details.empty()) {
            report << "  Details: " << test.details << "\n";
        }
    }
    
    if (!recommendations.empty()) {
        report << "\n=== Recommendations ===\n";
        for (size_t i = 0; i < recommendations.size(); ++i) {
            report << (i + 1) << ". " << recommendations[i] << "\n";
        }
    }
    
    report << "\n=== End Report ===\n";
    return report.str();
}

} // namespace codegreen::nemb