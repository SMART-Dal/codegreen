# Energy Measurement Accuracy Best Practices

## Overview

Achieving production-grade accuracy in energy measurement requires careful consideration of hardware limitations, environmental factors, and statistical techniques. This document outlines industry best practices for building high-accuracy energy measurement systems.

## Fundamental Accuracy Principles

### 1. Multi-Source Validation

**Cross-Validation Strategy**
```cpp
class AccuracyValidator {
private:
    std::vector<std::unique_ptr<EnergyProvider>> primary_providers_;
    std::vector<std::unique_ptr<EnergyProvider>> validation_providers_;
    
public:
    struct ValidationResult {
        double mean_absolute_error;
        double root_mean_square_error;
        double correlation_coefficient;
        bool accuracy_acceptable;
        std::string confidence_level;
    };
    
    ValidationResult cross_validate_measurements(std::chrono::seconds duration) {
        auto primary_measurements = collect_synchronized_measurements(
            primary_providers_, duration);
        auto validation_measurements = collect_synchronized_measurements(
            validation_providers_, duration);
        
        return statistical_comparison(primary_measurements, validation_measurements);
    }
};
```

### 2. Statistical Uncertainty Quantification

**Measurement Uncertainty Calculation**
```cpp
class UncertaintyQuantification {
public:
    struct UncertaintyAnalysis {
        double systematic_error;      // Bias in measurement system
        double random_error;          // Statistical uncertainty  
        double resolution_error;      // Limited by hardware resolution
        double total_uncertainty;     // Combined uncertainty
        double confidence_interval_95; // 95% confidence bounds
    };
    
    UncertaintyAnalysis analyze_measurement_uncertainty(
        const std::vector<EnergyReading>& readings) {
        
        UncertaintyAnalysis analysis{};
        
        // Calculate systematic error through calibration standards
        analysis.systematic_error = calculate_systematic_bias(readings);
        
        // Calculate random error through repeated measurements
        analysis.random_error = calculate_random_uncertainty(readings);
        
        // Resolution error from hardware specifications
        analysis.resolution_error = get_hardware_resolution_limit();
        
        // Combine uncertainties using root sum of squares
        analysis.total_uncertainty = std::sqrt(
            std::pow(analysis.systematic_error, 2) +
            std::pow(analysis.random_error, 2) +
            std::pow(analysis.resolution_error, 2)
        );
        
        // Calculate 95% confidence interval
        analysis.confidence_interval_95 = 1.96 * analysis.total_uncertainty;
        
        return analysis;
    }
    
private:
    double calculate_systematic_bias(const std::vector<EnergyReading>& readings) {
        // Compare against known reference standards
        // Implementation requires external calibration source
        return 0.0; // Placeholder
    }
    
    double calculate_random_uncertainty(const std::vector<EnergyReading>& readings) {
        if (readings.size() < 2) return 1.0;
        
        // Calculate standard deviation of repeated measurements
        double mean = calculate_mean_power(readings);
        double variance = 0.0;
        
        for (const auto& reading : readings) {
            variance += std::pow(reading.instantaneous_power_watts - mean, 2);
        }
        
        variance /= (readings.size() - 1);
        return std::sqrt(variance) / mean;  // Coefficient of variation
    }
};
```

## Environmental Compensation

### Temperature Impact Compensation

**Thermal Models for Accuracy**
```cpp
class ThermalCompensation {
private:
    struct ThermalModel {
        double reference_temperature;    // Celsius  
        double temp_coefficient;         // Power change per degree
        double thermal_time_constant;    // Thermal response time
        double max_operating_temp;       // Thermal throttling threshold
    };
    
    std::map<std::string, ThermalModel> cpu_thermal_models_ = {
        {"intel_skylake", {65.0, 0.005, 2.0, 100.0}},
        {"intel_ice_lake", {70.0, 0.004, 1.8, 105.0}},
        {"amd_zen3", {65.0, 0.006, 2.2, 95.0}},
        {"amd_zen4", {70.0, 0.005, 2.0, 100.0}}
    };
    
public:
    double compensate_for_temperature(double raw_power_watts,
                                    double current_temp_celsius,
                                    const std::string& processor_model) {
        auto& model = cpu_thermal_models_[processor_model];
        
        // Linear compensation model (can be enhanced with polynomial)
        double temp_delta = current_temp_celsius - model.reference_temperature;
        double compensation_factor = 1.0 - (model.temp_coefficient * temp_delta);
        
        // Ensure compensation factor stays within reasonable bounds
        compensation_factor = std::clamp(compensation_factor, 0.8, 1.2);
        
        return raw_power_watts * compensation_factor;
    }
    
    bool is_thermal_throttling(double current_temp_celsius,
                             const std::string& processor_model) {
        auto& model = cpu_thermal_models_[processor_model];
        return current_temp_celsius > (model.max_operating_temp - 5.0);
    }
};
```

### Frequency Scaling Compensation

**Dynamic Voltage/Frequency Scaling (DVFS) Models**
```cpp
class DVFSCompensation {
private:
    struct FrequencyPowerModel {
        double base_frequency_mhz;
        double base_voltage_v;
        double frequency_voltage_slope;   // V/MHz
        double power_voltage_exponent;    // Typically ~2.5-3.0
    };
    
public:
    double compensate_for_frequency_scaling(double base_power_watts,
                                          uint32_t current_freq_mhz,
                                          uint32_t base_freq_mhz,
                                          const FrequencyPowerModel& model) {
        // Calculate voltage scaling
        double freq_ratio = static_cast<double>(current_freq_mhz) / base_freq_mhz;
        double voltage_ratio = 1.0 + model.frequency_voltage_slope * (freq_ratio - 1.0);
        
        // Power scales as: P ∝ V^α × f (where α ≈ 2.5-3.0)
        double power_scaling_factor = std::pow(voltage_ratio, model.power_voltage_exponent) * freq_ratio;
        
        return base_power_watts * power_scaling_factor;
    }
    
    FrequencyPowerModel detect_processor_power_model(const std::string& processor_name) {
        // Database of processor-specific power models
        static const std::map<std::string, FrequencyPowerModel> models = {
            {"Intel Core i7-12700K", {3600, 1.2, 0.0001, 2.8}},
            {"AMD Ryzen 9 5950X", {3400, 1.25, 0.00012, 2.6}},
            {"Intel Xeon Gold 6348", {2600, 1.1, 0.00008, 2.9}}
        };
        
        auto it = models.find(processor_name);
        return (it != models.end()) ? it->second : FrequencyPowerModel{3000, 1.2, 0.0001, 2.7};
    }
};
```

## Noise Reduction Techniques

### Real-Time Filtering

**Adaptive Kalman Filter**
```cpp
class AdaptiveKalmanFilter {
private:
    // State variables
    double filtered_power_;           // Current power estimate
    double prediction_uncertainty_;   // P: Error covariance
    double process_noise_;           // Q: Process noise
    double measurement_noise_;       // R: Measurement noise  
    
    // Adaptive parameters
    double innovation_threshold_;    // For outlier detection
    uint32_t adaptation_window_;     // Samples for noise estimation
    
public:
    double filter_power_measurement(double raw_power, 
                                  double measurement_uncertainty) {
        // Prediction step
        double predicted_power = filtered_power_;  // Assume constant power
        double predicted_uncertainty = prediction_uncertainty_ + process_noise_;
        
        // Innovation (measurement residual)
        double innovation = raw_power - predicted_power;
        double innovation_covariance = predicted_uncertainty + measurement_uncertainty;
        
        // Outlier detection
        if (std::abs(innovation) > innovation_threshold_ * std::sqrt(innovation_covariance)) {
            // Suspected outlier - reduce Kalman gain
            measurement_uncertainty *= 10.0;
            innovation_covariance = predicted_uncertainty + measurement_uncertainty;
        }
        
        // Update step
        double kalman_gain = predicted_uncertainty / innovation_covariance;
        filtered_power_ = predicted_power + kalman_gain * innovation;
        prediction_uncertainty_ = (1.0 - kalman_gain) * predicted_uncertainty;
        
        // Adaptive noise estimation
        adapt_noise_parameters(innovation, innovation_covariance);
        
        return filtered_power_;
    }
    
private:
    void adapt_noise_parameters(double innovation, double innovation_covariance) {
        // Adaptive noise estimation using innovation sequence
        static std::vector<double> innovation_history;
        innovation_history.push_back(innovation);
        
        if (innovation_history.size() > adaptation_window_) {
            innovation_history.erase(innovation_history.begin());
            
            // Update process noise based on innovation statistics
            double innovation_variance = calculate_variance(innovation_history);
            process_noise_ = 0.1 * innovation_variance;  // 10% of innovation variance
        }
    }
};
```

### Outlier Detection and Removal

**Modified Z-Score Method**
```cpp
class RobustOutlierDetection {
private:
    static constexpr double OUTLIER_THRESHOLD = 3.5;
    static constexpr size_t MIN_HISTORY_SIZE = 10;
    
public:
    bool is_outlier(double value, const std::vector<double>& history) {
        if (history.size() < MIN_HISTORY_SIZE) {
            return false;  // Insufficient data for outlier detection
        }
        
        // Use median and MAD for robustness
        double median_value = calculate_median(history);
        double mad = calculate_median_absolute_deviation(history);
        
        // Modified Z-score (more robust than standard Z-score)
        double modified_z_score = 0.6745 * (value - median_value) / mad;
        
        return std::abs(modified_z_score) > OUTLIER_THRESHOLD;
    }
    
    std::vector<double> remove_outliers(const std::vector<double>& data) {
        std::vector<double> filtered_data;
        
        for (size_t i = 0; i < data.size(); ++i) {
            std::vector<double> context(data.begin(), data.begin() + i + 1);
            
            if (!is_outlier(data[i], context)) {
                filtered_data.push_back(data[i]);
            }
        }
        
        return filtered_data;
    }
    
private:
    double calculate_median_absolute_deviation(const std::vector<double>& data) {
        std::vector<double> sorted_data = data;
        std::sort(sorted_data.begin(), sorted_data.end());
        
        double median = calculate_median(sorted_data);
        
        std::vector<double> absolute_deviations;
        for (double value : sorted_data) {
            absolute_deviations.push_back(std::abs(value - median));
        }
        
        return calculate_median(absolute_deviations);
    }
};
```

## Measurement Timing Best Practices

### High-Resolution Timestamping

**Clock Selection Strategy**
```cpp
class PrecisionClock {
private:
    enum class ClockType {
        TSC_INVARIANT,      // Time Stamp Counter (best precision)
        CLOCK_MONOTONIC_RAW, // Raw monotonic clock
        CLOCK_MONOTONIC,     // Standard monotonic clock
        HPET               // High Precision Event Timer
    };
    
    ClockType selected_clock_;
    uint64_t tsc_frequency_;
    bool tsc_invariant_available_;
    
public:
    bool initialize() {
        // Detect best available clock source
        if (detect_tsc_invariant()) {
            selected_clock_ = ClockType::TSC_INVARIANT;
            tsc_frequency_ = measure_tsc_frequency();
            return true;
        } else if (check_clock_resolution(CLOCK_MONOTONIC_RAW) < 100) {  // <100ns resolution
            selected_clock_ = ClockType::CLOCK_MONOTONIC_RAW;
            return true;
        } else {
            selected_clock_ = ClockType::CLOCK_MONOTONIC;
            return true;
        }
    }
    
    uint64_t get_timestamp_ns() {
        switch (selected_clock_) {
            case ClockType::TSC_INVARIANT: {
                uint64_t tsc = __rdtsc();
                return (tsc * 1000000000ULL) / tsc_frequency_;
            }
            
            case ClockType::CLOCK_MONOTONIC_RAW:
            case ClockType::CLOCK_MONOTONIC: {
                struct timespec ts;
                clock_gettime((selected_clock_ == ClockType::CLOCK_MONOTONIC_RAW) ? 
                             CLOCK_MONOTONIC_RAW : CLOCK_MONOTONIC, &ts);
                return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
            }
            
            default:
                return 0;
        }
    }
    
private:
    bool detect_tsc_invariant() {
        // Check CPUID for invariant TSC support
        uint32_t eax, ebx, ecx, edx;
        __cpuid_count(0x80000007, 0, eax, ebx, ecx, edx);
        return (edx & (1 << 8)) != 0;  // Invariant TSC bit
    }
    
    uint64_t measure_tsc_frequency() {
        auto start_time = std::chrono::high_resolution_clock::now();
        uint64_t start_tsc = __rdtsc();
        
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        
        auto end_time = std::chrono::high_resolution_clock::now();
        uint64_t end_tsc = __rdtsc();
        
        auto duration_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            end_time - start_time).count();
        
        return ((end_tsc - start_tsc) * 1000000000ULL) / duration_ns;
    }
};
```

### Temporal Alignment and Synchronization

**Multi-Source Time Alignment**
```cpp
class TemporalAligner {
private:
    struct MeasurementPoint {
        uint64_t timestamp_ns;
        double power_watts;
        std::string source_id;
        double latency_compensation_ns;
    };
    
public:
    std::vector<MeasurementPoint> align_measurements(
        const std::map<std::string, std::vector<EnergyReading>>& multi_source_data) {
        
        std::vector<MeasurementPoint> aligned_points;
        
        // Find common time base
        uint64_t earliest_timestamp = find_earliest_timestamp(multi_source_data);
        uint64_t latest_timestamp = find_latest_timestamp(multi_source_data);
        
        // Create aligned time grid
        const uint64_t time_step_ns = 1000000;  // 1ms intervals
        
        for (uint64_t t = earliest_timestamp; t <= latest_timestamp; t += time_step_ns) {
            // Interpolate measurements from all sources at time t
            for (const auto& [source_id, readings] : multi_source_data) {
                double interpolated_power = interpolate_power_at_time(readings, t);
                
                MeasurementPoint point{};
                point.timestamp_ns = t;
                point.power_watts = interpolated_power;
                point.source_id = source_id;
                point.latency_compensation_ns = get_source_latency_compensation(source_id);
                
                aligned_points.push_back(point);
            }
        }
        
        return aligned_points;
    }
    
private:
    double interpolate_power_at_time(const std::vector<EnergyReading>& readings, 
                                   uint64_t target_time_ns) {
        // Linear interpolation between adjacent measurements
        auto it_after = std::lower_bound(readings.begin(), readings.end(), target_time_ns,
            [](const EnergyReading& reading, uint64_t time) {
                return reading.timestamp_ns < time;
            });
        
        if (it_after == readings.begin()) {
            return readings.front().instantaneous_power_watts;
        }
        if (it_after == readings.end()) {
            return readings.back().instantaneous_power_watts;
        }
        
        auto it_before = it_after - 1;
        
        // Linear interpolation
        double time_fraction = static_cast<double>(target_time_ns - it_before->timestamp_ns) /
                              (it_after->timestamp_ns - it_before->timestamp_ns);
        
        return it_before->instantaneous_power_watts + 
               time_fraction * (it_after->instantaneous_power_watts - 
                              it_before->instantaneous_power_watts);
    }
};
```

## Hardware Counter Management

### Counter Wraparound Handling

**Robust Wraparound Detection**
```cpp
class CounterManager {
private:
    struct CounterState {
        uint64_t last_raw_value;
        uint64_t accumulated_value;
        uint32_t wraparound_count;
        uint64_t counter_mask;
        std::chrono::steady_clock::time_point last_update;
    };
    
    std::map<std::string, CounterState> counter_states_;
    
public:
    uint64_t handle_counter_update(const std::string& counter_id,
                                  uint64_t current_raw_value,
                                  uint32_t counter_bits) {
        auto& state = counter_states_[counter_id];
        
        // Initialize on first use
        if (state.counter_mask == 0) {
            state.counter_mask = (1ULL << counter_bits) - 1;
            state.last_raw_value = current_raw_value;
            state.accumulated_value = 0;
            state.last_update = std::chrono::steady_clock::now();
            return 0;
        }
        
        auto current_time = std::chrono::steady_clock::now();
        auto time_since_last = std::chrono::duration_cast<std::chrono::milliseconds>(
            current_time - state.last_update);
        
        // Detect wraparound
        if (current_raw_value < state.last_raw_value) {
            // Verify this is actually a wraparound, not a counter reset
            if (time_since_last.count() < COUNTER_RESET_THRESHOLD_MS) {
                uint64_t increment = (state.counter_mask - state.last_raw_value) + 
                                   current_raw_value + 1;
                state.accumulated_value += increment;
                state.wraparound_count++;
                
                log_wraparound_event(counter_id, state.wraparound_count, increment);
            } else {
                // Likely a counter reset - restart accumulation
                state.accumulated_value = 0;
                log_counter_reset_event(counter_id);
            }
        } else {
            // Normal increment
            state.accumulated_value += (current_raw_value - state.last_raw_value);
        }
        
        state.last_raw_value = current_raw_value;
        state.last_update = current_time;
        
        return state.accumulated_value;
    }
    
private:
    static constexpr uint32_t COUNTER_RESET_THRESHOLD_MS = 1000;
    
    void log_wraparound_event(const std::string& counter_id, 
                            uint32_t wraparound_count, 
                            uint64_t increment) {
        // Log for diagnostics and validation
        std::cout << "Counter " << counter_id << " wraparound #" << wraparound_count
                  << " increment=" << increment << std::endl;
    }
};
```

## Calibration and Validation Framework

### Self-Calibration System

**Automated Calibration Routines**
```cpp
class CalibrationFramework {
private:
    struct CalibrationData {
        double idle_power_baseline;
        double measurement_noise_floor;
        std::map<double, double> known_load_calibration;  // Load -> Expected Power
        double calibration_confidence;
    };
    
public:
    CalibrationData perform_system_calibration() {
        CalibrationData calibration{};
        
        // Phase 1: Idle baseline characterization
        calibration.idle_power_baseline = measure_idle_baseline();
        
        // Phase 2: Noise floor determination
        calibration.measurement_noise_floor = measure_noise_floor();
        
        // Phase 3: Known load calibration
        calibration.known_load_calibration = perform_known_load_tests();
        
        // Phase 4: Confidence assessment
        calibration.calibration_confidence = assess_calibration_quality(calibration);
        
        return calibration;
    }
    
private:
    double measure_idle_baseline() {
        std::cout << "Measuring idle power baseline..." << std::endl;
        
        // Ensure system is idle
        std::this_thread::sleep_for(std::chrono::seconds(2));
        
        std::vector<double> idle_measurements;
        auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(30);
        
        while (std::chrono::steady_clock::now() < end_time) {
            auto reading = energy_provider_->get_reading();
            idle_measurements.push_back(reading.instantaneous_power_watts);
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        // Remove outliers and calculate stable baseline
        auto filtered_measurements = outlier_detector_.remove_outliers(idle_measurements);
        return calculate_mean(filtered_measurements);
    }
    
    std::map<double, double> perform_known_load_tests() {
        std::map<double, double> calibration_points;
        
        // Test various CPU loads: 25%, 50%, 75%, 100%
        std::vector<double> load_levels = {0.25, 0.5, 0.75, 1.0};
        
        for (double load : load_levels) {
            std::cout << "Calibrating " << (load * 100) << "% CPU load..." << std::endl;
            
            double measured_power = measure_power_under_load(load);
            calibration_points[load] = measured_power;
            
            // Cool down between tests
            std::this_thread::sleep_for(std::chrono::seconds(10));
        }
        
        return calibration_points;
    }
    
    double measure_power_under_load(double cpu_load_fraction) {
        // Generate precise CPU load
        auto load_generator = std::make_unique<CPULoadGenerator>();
        load_generator->start_load(cpu_load_fraction);
        
        // Measure power for 10 seconds
        std::vector<double> power_measurements;
        auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        
        while (std::chrono::steady_clock::now() < end_time) {
            auto reading = energy_provider_->get_reading();
            power_measurements.push_back(reading.instantaneous_power_watts);
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        load_generator->stop_load();
        
        // Return stable power measurement
        auto filtered_measurements = outlier_detector_.remove_outliers(power_measurements);
        return calculate_mean(filtered_measurements);
    }
};
```

### Cross-Platform Validation

**Reference Measurement Comparison**
```cpp
class CrossPlatformValidator {
public:
    struct ValidationReport {
        std::map<std::string, double> provider_accuracy;  // Provider -> % error
        std::vector<std::string> failed_providers;
        std::string recommended_primary_provider;
        double system_measurement_confidence;
    };
    
    ValidationReport validate_all_providers(
        const std::vector<std::unique_ptr<EnergyProvider>>& providers) {
        
        ValidationReport report;
        
        // Collect measurements from all providers simultaneously
        auto measurement_matrix = collect_parallel_measurements(providers);
        
        // Cross-validate each provider against others
        for (size_t i = 0; i < providers.size(); ++i) {
            double accuracy = calculate_provider_accuracy(measurement_matrix, i);
            
            if (accuracy > ACCEPTABLE_ACCURACY_THRESHOLD) {
                report.provider_accuracy[providers[i]->get_name()] = accuracy;
            } else {
                report.failed_providers.push_back(providers[i]->get_name());
            }
        }
        
        // Select most accurate provider as primary
        if (!report.provider_accuracy.empty()) {
            auto best_provider = std::min_element(report.provider_accuracy.begin(),
                                                report.provider_accuracy.end(),
                                                [](const auto& a, const auto& b) {
                                                    return a.second < b.second;
                                                });
            report.recommended_primary_provider = best_provider->first;
        }
        
        // Calculate overall system confidence
        report.system_measurement_confidence = calculate_system_confidence(report);
        
        return report;
    }
    
private:
    static constexpr double ACCEPTABLE_ACCURACY_THRESHOLD = 0.05;  // 5%
    
    double calculate_provider_accuracy(
        const std::vector<std::vector<EnergyReading>>& measurement_matrix,
        size_t provider_index) {
        
        // Compare against ensemble average of other providers
        std::vector<double> provider_readings;
        std::vector<double> reference_readings;
        
        for (size_t sample = 0; sample < measurement_matrix.size(); ++sample) {
            provider_readings.push_back(
                measurement_matrix[sample][provider_index].instantaneous_power_watts);
            
            // Calculate reference from other providers
            double reference_power = 0.0;
            size_t valid_providers = 0;
            
            for (size_t p = 0; p < measurement_matrix[sample].size(); ++p) {
                if (p != provider_index) {
                    reference_power += measurement_matrix[sample][p].instantaneous_power_watts;
                    valid_providers++;
                }
            }
            
            if (valid_providers > 0) {
                reference_readings.push_back(reference_power / valid_providers);
            }
        }
        
        // Calculate mean absolute percentage error
        double total_error = 0.0;
        for (size_t i = 0; i < provider_readings.size() && i < reference_readings.size(); ++i) {
            if (reference_readings[i] > 0.1) {  // Avoid division by very small numbers
                double error = std::abs(provider_readings[i] - reference_readings[i]) / 
                              reference_readings[i];
                total_error += error;
            }
        }
        
        return total_error / std::min(provider_readings.size(), reference_readings.size());
    }
};
```

## Industry Standard Compliance

### IEEE 1459-2010 Power Measurement Standards

```cpp
class IEEE1459Compliance {
public:
    struct PowerQualityMetrics {
        double active_power;           // Real power (Watts)
        double reactive_power;         // Reactive power (VAR)
        double apparent_power;         // Apparent power (VA)
        double power_factor;           // cos(φ)
        double total_harmonic_distortion;
        double measurement_accuracy_class;  // IEEE accuracy class
    };
    
    PowerQualityMetrics analyze_power_quality(
        const std::vector<EnergyReading>& readings) {
        
        PowerQualityMetrics metrics{};
        
        // For DC systems (most computer components), reactive power is minimal
        metrics.active_power = calculate_mean_power(readings);
        metrics.reactive_power = 0.0;  // DC systems
        metrics.apparent_power = metrics.active_power;
        metrics.power_factor = 1.0;    // Unity power factor for DC
        
        // Calculate measurement accuracy class per IEEE 1459
        double measurement_uncertainty = calculate_measurement_uncertainty(readings);
        metrics.measurement_accuracy_class = classify_accuracy(measurement_uncertainty);
        
        return metrics;
    }
    
private:
    double classify_accuracy(double uncertainty) {
        // IEEE 1459 accuracy classes
        if (uncertainty < 0.002) return 0.2;      // Class 0.2 (0.2% accuracy)
        if (uncertainty < 0.005) return 0.5;      // Class 0.5 (0.5% accuracy)
        if (uncertainty < 0.01) return 1.0;       // Class 1.0 (1.0% accuracy)
        if (uncertainty < 0.02) return 2.0;       // Class 2.0 (2.0% accuracy)
        return 5.0;                               // Class 5.0 (5.0% accuracy)
    }
};
```

This comprehensive accuracy guide ensures that NEMB meets industry standards for energy measurement precision and reliability.