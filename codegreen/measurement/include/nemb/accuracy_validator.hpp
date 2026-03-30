#pragma once

#include <string>
#include <vector>
#include <chrono>
#include <map>

#include "nemb/utils/precision_timer.hpp"

namespace codegreen::nemb {

/**
 * @brief Configuration for accuracy validation tests
 */
struct ValidationConfig {
    // Precision testing
    int precision_test_samples{50};
    double max_coefficient_of_variation{0.05}; // 5% max variation
    
    // Stability testing
    std::chrono::seconds stability_test_duration{10};
    double max_temporal_variation{0.03}; // 3% max temporal variation
    
    // Cross-validation
    double min_cross_validation_score{0.85}; // 85% minimum consistency
    
    // Performance
    double max_acceptable_overhead_percent{1.0}; // 1% max overhead
    
    // Overall requirements
    double target_uncertainty_percent{1.0}; // Target 1% uncertainty
    double min_acceptable_score{0.7}; // 70% minimum overall score
};

/**
 * @brief Result of a single validation test
 */
struct ValidationTest {
    std::string description;
    bool passed{false};
    double score{0.0}; // 0.0 to 1.0
    double uncertainty_percent{0.0};
    std::string details;
};

/**
 * @brief Complete validation result
 */
struct ValidationResult {
    std::chrono::system_clock::time_point timestamp;
    bool passed{false};
    double overall_score{0.0};
    std::string error_message;
    
    std::vector<std::pair<std::string, ValidationTest>> tests;
    std::vector<std::string> recommendations;
    
    /**
     * @brief Generate a human-readable summary report
     */
    std::string generate_report() const;
};

/**
 * @brief Comprehensive accuracy validation system
 * 
 * Validates energy measurement accuracy through multiple independent tests:
 * - Basic functionality verification
 * - Measurement precision and repeatability
 * - Temporal stability analysis
 * - Load responsiveness testing
 * - Cross-validation between providers
 * - Measurement overhead analysis
 */
class AccuracyValidator {
public:
    /**
     * @brief Create validator with default configuration
     */
    AccuracyValidator() : AccuracyValidator(ValidationConfig{}) {}
    
    /**
     * @brief Create validator with custom configuration
     */
    explicit AccuracyValidator(const ValidationConfig& config);
    
    /**
     * @brief Run complete system accuracy validation
     * @return Comprehensive validation results
     */
    ValidationResult validate_system_accuracy();
    
    /**
     * @brief Run individual test by name
     * @param test_name Name of test to run
     * @return Individual test result
     */
    ValidationTest run_individual_test(const std::string& test_name);
    
    /**
     * @brief Get current validation configuration
     */
    const ValidationConfig& get_config() const { return config_; }
    
private:
    ValidationConfig config_;
    utils::PrecisionTimer timer_;
    
    // Individual test implementations
    ValidationTest test_basic_functionality();
    ValidationTest test_measurement_precision();
    ValidationTest test_temporal_stability();
    ValidationTest test_load_responsiveness();
    ValidationTest test_cross_validation();
    ValidationTest measure_measurement_overhead();
    
    // Analysis helpers
    double calculate_overall_score(const std::vector<std::pair<std::string, ValidationTest>>& tests);
    std::vector<std::string> generate_recommendations(const std::vector<std::pair<std::string, ValidationTest>>& tests);
};

} // namespace codegreen::nemb