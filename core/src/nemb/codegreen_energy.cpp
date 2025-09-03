#include "nemb/codegreen_energy.hpp"
#include "nemb/config_loader.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/core/energy_provider.hpp"
#include "nemb/utils/precision_timer.hpp"

#include <sstream>
#include <iomanip>
#include <thread>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <iostream>

namespace codegreen {

// Implementation details hidden using PIMPL pattern
class EnergyMeter::Impl {
public:
    explicit Impl(const NEMBConfig& config);
    ~Impl();
    
    bool is_available() const;
    std::vector<std::string> get_provider_info() const;
    EnergyResult read();
    uint64_t start_session(const std::string& name);
    EnergyDifference end_session(uint64_t session_id);
    const NEMBConfig& get_config() const;
    bool self_test();
    std::map<std::string, std::string> get_diagnostics() const;
    
private:
    struct Session {
        std::string name;
        EnergyResult baseline;
        uint64_t start_time_ns;
        bool active{true};
    };
    
    NEMBConfig config_;
    std::unique_ptr<nemb::MeasurementCoordinator> coordinator_;
    nemb::utils::PrecisionTimer timer_;
    std::map<uint64_t, Session> active_sessions_;
    std::atomic<uint64_t> next_session_id_{1};
    mutable std::mutex sessions_mutex_;
    
    // Accuracy optimization features
    void apply_noise_minimization();
    void prefault_memory();
    void set_cpu_affinity();
    bool validate_reading_accuracy(const EnergyResult& reading) const;
    EnergyResult apply_noise_filtering(const EnergyResult& reading) const;
    
    // Cross-validation and error detection
    bool cross_validate_providers(const nemb::SynchronizedReading& reading) const;
    void detect_and_handle_outliers(EnergyResult& result) const;
    
    // Conversion helpers
    EnergyResult convert_synchronized_reading(const nemb::SynchronizedReading& sync_reading) const;
};

EnergyMeter::Impl::Impl(const NEMBConfig& config) 
    : config_(config), timer_() {
    
    // Load NEMB configuration based on user settings
    auto nemb_config = nemb::ConfigLoader::load_config();
    
    // Apply user preferences to NEMB config
    if (config.target_uncertainty_percent != 1.0) {
        nemb_config.accuracy.target_uncertainty_percent = config.target_uncertainty_percent;
    }
    nemb_config.accuracy.measurement_validation = config.enable_cross_validation;
    nemb_config.accuracy.outlier_detection = config.enable_outlier_detection;
    nemb_config.accuracy.noise_filtering = config.enable_noise_filtering ? "adaptive" : "none";
    
    // Override timing source if specified
    if (config.force_clock_source.has_value()) {
        nemb_config.timing.clock_source = *config.force_clock_source;
    }
    
    // Apply accuracy optimizations
    if (config.prefer_accuracy_over_speed) {
        apply_noise_minimization();
    }
    
    // Initialize measurement coordinator with providers
    // Convert ConfigLoader::CoordinatorConfig to nemb::CoordinatorConfig
    nemb::CoordinatorConfig coordinator_config;
    coordinator_config.temporal_alignment_tolerance_ms = nemb_config.coordinator.temporal_alignment_tolerance_ms;
    coordinator_config.cross_validation_threshold = nemb_config.coordinator.cross_validation_threshold;
    coordinator_config.measurement_buffer_size = nemb_config.coordinator.measurement_buffer_size;
    coordinator_config.auto_restart_failed_providers = nemb_config.coordinator.auto_restart_failed_providers;
    coordinator_config.provider_restart_interval = nemb_config.coordinator.provider_restart_interval;
    
    coordinator_ = std::make_unique<nemb::MeasurementCoordinator>(coordinator_config);
    
    // Add available providers to the coordinator
    auto providers = nemb::detect_available_providers();
    for (auto& provider : providers) {
        if (!coordinator_->add_provider(std::move(provider))) {
            std::cerr << "Failed to add energy provider to coordinator" << std::endl;
        }
    }
    
    // Start measurements
    if (!coordinator_->start_measurements()) {
        std::cerr << "Failed to start energy measurements" << std::endl;
    }
    
    // Wait for initialization with timeout
    auto start_time = std::chrono::steady_clock::now();
    while (coordinator_->get_active_providers().empty() && 
           std::chrono::steady_clock::now() - start_time < config.timeout) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    
    if (coordinator_->get_active_providers().empty()) {
        throw std::runtime_error("Energy measurement initialization timed out");
    }
}

EnergyMeter::Impl::~Impl() {
    // Ensure clean shutdown of all sessions
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    active_sessions_.clear();
}

void EnergyMeter::Impl::apply_noise_minimization() {
    if (config_.minimize_overhead) {
        // Prefault memory to avoid page faults during measurement
        prefault_memory();
        
        // Set CPU affinity to reduce scheduling noise
        set_cpu_affinity();
    }
}

void EnergyMeter::Impl::prefault_memory() {
    // Allocate and touch pages that will be used during measurement
    // This prevents page faults from adding noise to measurements
    constexpr size_t PREFAULT_SIZE = 1024 * 1024; // 1MB
    static thread_local std::vector<char> prefault_buffer(PREFAULT_SIZE);
    
    // Touch all pages to ensure they're resident
    for (size_t i = 0; i < PREFAULT_SIZE; i += 4096) {
        prefault_buffer[i] = 1;
    }
}

void EnergyMeter::Impl::set_cpu_affinity() {
    // Set CPU affinity to reduce measurement noise from thread migration
    // This is platform-specific and could be implemented using sched_setaffinity on Linux
    // For now, we'll use a portable approach with thread priorities
    
#ifdef __linux__
    // On Linux, we could implement CPU affinity here
    // pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);
#endif
}

bool EnergyMeter::Impl::is_available() const {
    return coordinator_ && !coordinator_->get_active_providers().empty();
}

std::vector<std::string> EnergyMeter::Impl::get_provider_info() const {
    if (!coordinator_) {
        return {};
    }
    
    std::vector<std::string> info;
    auto providers = coordinator_->get_active_providers();
    
    for (const auto& provider_id : providers) {
        std::ostringstream details;
        details << provider_id << " (active)";
        info.push_back(details.str());
    }
    
    return info;
}

EnergyResult EnergyMeter::Impl::read() {
    if (!coordinator_ || coordinator_->get_active_providers().empty()) {
        EnergyResult error_result;
        error_result.is_valid = false;
        error_result.error_message = "Energy measurement not available";
        return error_result;
    }
    
    try {
        // Get synchronized reading from all providers
        auto sync_reading = coordinator_->get_synchronized_reading();
        
        // Convert to public API format
        EnergyResult result = convert_synchronized_reading(sync_reading);
        
        // Apply accuracy validation and filtering
        if (config_.enable_cross_validation && !cross_validate_providers(sync_reading)) {
            result.confidence *= 0.5; // Reduce confidence if cross-validation fails
            result.uncertainty_percent = std::max(result.uncertainty_percent, 5.0);
        }
        
        if (config_.enable_outlier_detection) {
            detect_and_handle_outliers(result);
        }
        
        if (config_.enable_noise_filtering) {
            result = apply_noise_filtering(result);
        }
        
        // Final accuracy validation
        result.is_valid = validate_reading_accuracy(result);
        
        return result;
        
    } catch (const std::exception& e) {
        EnergyResult error_result;
        error_result.is_valid = false;
        error_result.error_message = std::string("Measurement error: ") + e.what();
        return error_result;
    }
}

EnergyResult EnergyMeter::Impl::convert_synchronized_reading(const nemb::SynchronizedReading& sync_reading) const {
    EnergyResult result;
    
    if (sync_reading.provider_readings.empty()) {
        result.is_valid = false;
        result.error_message = "No provider readings available";
        return result;
    }
    
    // Aggregate energy from all providers
    double total_energy = 0.0;
    double total_power = 0.0;
    double max_uncertainty = 0.0;
    double min_confidence = 1.0;
    
    for (const auto& reading : sync_reading.provider_readings) {
        total_energy += reading.energy_joules;
        total_power += reading.average_power_watts;
        max_uncertainty = std::max(max_uncertainty, reading.uncertainty_percent);
        min_confidence = std::min(min_confidence, reading.confidence);
        
        // Populate component breakdown
        std::string component_name = reading.provider_id;
        if (reading.component_name && !reading.component_name->empty()) {
            component_name += "_" + *reading.component_name;
        }
        result.components[component_name] = reading.energy_joules;
    }
    
    result.energy_joules = total_energy;
    result.power_watts = total_power;
    result.timestamp_ns = sync_reading.common_timestamp_ns;
    result.uncertainty_percent = max_uncertainty;
    result.confidence = min_confidence;
    result.is_valid = sync_reading.temporal_alignment_valid && sync_reading.cross_validation_passed;
    
    // Add provider information
    std::ostringstream provider_info;
    for (size_t i = 0; i < sync_reading.provider_readings.size(); ++i) {
        if (i > 0) provider_info << ", ";
        provider_info << sync_reading.provider_readings[i].provider_id;
    }
    result.provider_info = provider_info.str();
    
    return result;
}

bool EnergyMeter::Impl::cross_validate_providers(const nemb::SynchronizedReading& reading) const {
    if (reading.provider_readings.size() < 2) {
        return true; // Can't cross-validate with single provider
    }
    
    // Check for consistency between providers
    double avg_power = 0.0;
    for (const auto& r : reading.provider_readings) {
        avg_power += r.average_power_watts;
    }
    avg_power /= reading.provider_readings.size();
    
    // Check if all providers are within reasonable range
    const double VALIDATION_THRESHOLD = config_.target_uncertainty_percent / 100.0 * 2.0;
    for (const auto& r : reading.provider_readings) {
        double deviation = std::abs(r.average_power_watts - avg_power) / avg_power;
        if (deviation > VALIDATION_THRESHOLD) {
            return false;
        }
    }
    
    return true;
}

void EnergyMeter::Impl::detect_and_handle_outliers(EnergyResult& result) const {
    // Simple outlier detection based on historical readings
    // In a full implementation, this would maintain a rolling buffer of recent readings
    
    static thread_local std::vector<double> recent_powers;
    static thread_local const size_t MAX_HISTORY = 10;
    
    recent_powers.push_back(result.power_watts);
    if (recent_powers.size() > MAX_HISTORY) {
        recent_powers.erase(recent_powers.begin());
    }
    
    if (recent_powers.size() >= 3) {
        double mean = 0.0;
        for (double p : recent_powers) mean += p;
        mean /= recent_powers.size();
        
        double stddev = 0.0;
        for (double p : recent_powers) {
            stddev += (p - mean) * (p - mean);
        }
        stddev = std::sqrt(stddev / recent_powers.size());
        
        // Mark as potential outlier if more than 2 standard deviations from mean
        if (std::abs(result.power_watts - mean) > 2.0 * stddev) {
            result.confidence *= 0.7; // Reduce confidence for potential outliers
            result.uncertainty_percent = std::max(result.uncertainty_percent, 3.0);
        }
    }
}

EnergyResult EnergyMeter::Impl::apply_noise_filtering(const EnergyResult& reading) const {
    EnergyResult filtered = reading;
    
    // Apply adaptive noise filtering based on configuration
    // This could include temporal smoothing, statistical filtering, etc.
    
    // For now, apply simple confidence-based filtering
    if (filtered.confidence < 0.8) {
        filtered.uncertainty_percent = std::max(filtered.uncertainty_percent, 2.0);
    }
    
    return filtered;
}

bool EnergyMeter::Impl::validate_reading_accuracy(const EnergyResult& reading) const {
    // Validate that the reading meets our accuracy requirements
    return reading.uncertainty_percent <= config_.target_uncertainty_percent * 2.0 &&
           reading.confidence >= 0.7 &&
           reading.energy_joules >= 0.0 &&
           reading.power_watts >= 0.0;
}

uint64_t EnergyMeter::Impl::start_session(const std::string& name) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    
    uint64_t session_id = next_session_id_++;
    Session session;
    session.name = name.empty() ? ("session_" + std::to_string(session_id)) : name;
    session.baseline = read();
    session.start_time_ns = timer_.get_timestamp_ns();
    session.active = true;
    
    active_sessions_[session_id] = std::move(session);
    return session_id;
}

EnergyDifference EnergyMeter::Impl::end_session(uint64_t session_id) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    
    auto it = active_sessions_.find(session_id);
    if (it == active_sessions_.end() || !it->second.active) {
        EnergyDifference error_result;
        error_result.is_valid = false;
        return error_result;
    }
    
    EnergyResult end_reading = read();
    Session& session = it->second;
    session.active = false;
    
    EnergyDifference result = energy_utils::calculate_difference(end_reading, session.baseline);
    
    // Clean up finished session
    active_sessions_.erase(it);
    
    return result;
}

const NEMBConfig& EnergyMeter::Impl::get_config() const {
    return config_;
}

bool EnergyMeter::Impl::self_test() {
    if (!is_available()) {
        return false;
    }
    
    try {
        // Perform basic functionality test
        auto reading1 = read();
        if (!reading1.is_valid) {
            return false;
        }
        
        // Wait a short time and take another reading
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        
        auto reading2 = read();
        if (!reading2.is_valid) {
            return false;
        }
        
        // Verify readings are progressing (energy is cumulative)
        if (reading2.energy_joules < reading1.energy_joules) {
            return false;
        }
        
        // Test basic read functionality
        auto baseline = read();
        if (!baseline.is_valid) {
            return false;
        }
        
        // Simple workload for testing
        volatile double x = 0.0;
        for (int i = 0; i < 1000000; ++i) {
            x += std::sqrt(i);
        }
        
        auto after_work = read();
        if (!after_work.is_valid) {
            return false;
        }
        
        return after_work.energy_joules >= baseline.energy_joules;
        
    } catch (...) {
        return false;
    }
}

std::map<std::string, std::string> EnergyMeter::Impl::get_diagnostics() const {
    std::map<std::string, std::string> diagnostics;
    
    diagnostics["available"] = is_available() ? "true" : "false";
    diagnostics["providers"] = std::to_string(get_provider_info().size());
    diagnostics["accuracy_mode"] = config_.prefer_accuracy_over_speed ? "accuracy" : "performance";
    diagnostics["target_uncertainty"] = std::to_string(config_.target_uncertainty_percent) + "%";
    
    if (coordinator_) {
        diagnostics["coordinator_ready"] = !coordinator_->get_active_providers().empty() ? "true" : "false";
        auto providers = coordinator_->get_active_providers();
        diagnostics["active_providers"] = std::to_string(providers.size());
    }
    
    {
        std::lock_guard<std::mutex> lock(sessions_mutex_);
        diagnostics["active_sessions"] = std::to_string(active_sessions_.size());
    }
    
    return diagnostics;
}

// Public API Implementation

EnergyMeter::EnergyMeter() : EnergyMeter(NEMBConfig::accuracy_optimized()) {}

EnergyMeter::EnergyMeter(const NEMBConfig& config) 
    : impl_(std::make_unique<Impl>(config)) {}

EnergyMeter::~EnergyMeter() = default;

EnergyMeter::EnergyMeter(EnergyMeter&&) noexcept = default;
EnergyMeter& EnergyMeter::operator=(EnergyMeter&&) noexcept = default;

bool EnergyMeter::is_available() const {
    return impl_->is_available();
}

std::vector<std::string> EnergyMeter::get_provider_info() const {
    return impl_->get_provider_info();
}

EnergyResult EnergyMeter::read() {
    return impl_->read();
}

uint64_t EnergyMeter::start_session(const std::string& name) {
    return impl_->start_session(name);
}

EnergyDifference EnergyMeter::end_session(uint64_t session_id) {
    return impl_->end_session(session_id);
}

const NEMBConfig& EnergyMeter::get_config() const {
    return impl_->get_config();
}

bool EnergyMeter::self_test() {
    return impl_->self_test();
}

std::map<std::string, std::string> EnergyMeter::get_diagnostics() const {
    return impl_->get_diagnostics();
}

// Configuration implementations

NEMBConfig NEMBConfig::accuracy_optimized() {
    NEMBConfig config;
    config.target_uncertainty_percent = 0.5;
    config.enable_cross_validation = true;
    config.enable_outlier_detection = true;
    config.enable_noise_filtering = true;
    config.minimize_overhead = true;
    config.prefer_accuracy_over_speed = true;
    config.timeout = std::chrono::milliseconds(10000);
    config.allow_fallback_providers = true;
    config.enable_debug_logging = false;
    return config;
}

NEMBConfig NEMBConfig::performance_optimized() {
    NEMBConfig config;
    config.target_uncertainty_percent = 2.0;
    config.enable_cross_validation = false;
    config.enable_outlier_detection = false;
    config.enable_noise_filtering = false;
    config.minimize_overhead = false;
    config.prefer_accuracy_over_speed = false;
    config.timeout = std::chrono::milliseconds(2000);
    config.allow_fallback_providers = true;
    config.enable_debug_logging = false;
    return config;
}

NEMBConfig NEMBConfig::from_config_file(const std::string& config_path) {
    // Load NEMB config and convert to NEMBConfig
    auto nemb_config = nemb::ConfigLoader::load_config(config_path);
    
    NEMBConfig config;
    config.target_uncertainty_percent = nemb_config.accuracy.target_uncertainty_percent;
    config.enable_cross_validation = nemb_config.coordinator.cross_validation;
    config.enable_outlier_detection = nemb_config.accuracy.outlier_detection;
    config.enable_noise_filtering = nemb_config.accuracy.noise_filtering != "none";
    config.prefer_accuracy_over_speed = (nemb_config.accuracy_mode == "production");
    config.minimize_overhead = nemb_config.accuracy.minimize_system_noise;
    
    return config;
}

// Result implementations

std::string EnergyResult::summary() const {
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(6);
    ss << "Energy: " << energy_utils::format_energy(energy_joules);
    ss << ", Power: " << energy_utils::format_power(power_watts);
    ss << ", Uncertainty: " << std::setprecision(1) << uncertainty_percent << "%";
    ss << ", Confidence: " << std::setprecision(2) << confidence;
    if (!is_valid) ss << " [INVALID]";
    return ss.str();
}

std::string EnergyDifference::summary() const {
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(6);
    ss << "Energy: " << energy_utils::format_energy(energy_joules);
    ss << ", Avg Power: " << energy_utils::format_power(average_power_watts);
    ss << ", Duration: " << std::setprecision(3) << duration_seconds << "s";
    ss << ", Uncertainty: " << std::setprecision(1) << uncertainty_percent << "%";
    if (!is_valid) ss << " [INVALID]";
    return ss.str();
}

// ScopedEnergyMeter implementation

ScopedEnergyMeter::ScopedEnergyMeter(const std::string& name, bool print_results)
    : name_(name), print_results_(print_results) {
    baseline_ = meter_.read();
}

ScopedEnergyMeter::~ScopedEnergyMeter() {
    if (!stopped_ && print_results_) {
        auto result = stop();
        std::cout << "[" << name_ << "] " << result.summary() << std::endl;
    }
}

EnergyDifference ScopedEnergyMeter::current() const {
    if (stopped_) {
        EnergyDifference invalid;
        invalid.is_valid = false;
        return invalid;
    }
    
    auto current_reading = meter_.read();
    return energy_utils::calculate_difference(current_reading, baseline_);
}

EnergyDifference ScopedEnergyMeter::stop() {
    if (stopped_) {
        EnergyDifference invalid;
        invalid.is_valid = false;
        return invalid;
    }
    
    stopped_ = true;
    auto final_reading = meter_.read();
    return energy_utils::calculate_difference(final_reading, baseline_);
}

// Utility functions

namespace energy_utils {

EnergyDifference calculate_difference(const EnergyResult& end_reading, const EnergyResult& start_reading) {
    EnergyDifference diff;
    
    if (!end_reading.is_valid || !start_reading.is_valid) {
        diff.is_valid = false;
        return diff;
    }
    
    diff.energy_joules = end_reading.energy_joules - start_reading.energy_joules;
    diff.duration_seconds = (end_reading.timestamp_ns - start_reading.timestamp_ns) / 1e9;
    
    if (diff.duration_seconds > 0) {
        diff.average_power_watts = diff.energy_joules / diff.duration_seconds;
    }
    
    // Combine uncertainties (conservative approach)
    diff.uncertainty_percent = std::sqrt(end_reading.uncertainty_percent * end_reading.uncertainty_percent + 
                                        start_reading.uncertainty_percent * start_reading.uncertainty_percent);
    
    // Calculate component differences
    for (const auto& [component, end_energy] : end_reading.components) {
        auto start_it = start_reading.components.find(component);
        if (start_it != start_reading.components.end()) {
            double component_energy = end_energy - start_it->second;
            diff.component_energy[component] = component_energy;
            if (diff.duration_seconds > 0) {
                diff.component_power[component] = component_energy / diff.duration_seconds;
            }
        }
    }
    
    diff.is_valid = diff.energy_joules >= 0 && diff.duration_seconds > 0;
    return diff;
}

double convert_energy(double energy_joules, const std::string& target_unit) {
    if (target_unit == "J" || target_unit == "joules") return energy_joules;
    if (target_unit == "mJ") return energy_joules * 1000.0;
    if (target_unit == "μJ" || target_unit == "uJ") return energy_joules * 1e6;
    if (target_unit == "kJ") return energy_joules / 1000.0;
    if (target_unit == "Wh") return energy_joules / 3600.0;
    if (target_unit == "kWh") return energy_joules / 3600000.0;
    if (target_unit == "mWh") return energy_joules * 1000.0 / 3600.0;
    return energy_joules; // Default to joules
}

std::string format_energy(double energy_joules) {
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(3);
    
    if (energy_joules >= 1000.0) {
        ss << (energy_joules / 1000.0) << " kJ";
    } else if (energy_joules >= 1.0) {
        ss << energy_joules << " J";
    } else if (energy_joules >= 0.001) {
        ss << (energy_joules * 1000.0) << " mJ";
    } else {
        ss << (energy_joules * 1e6) << " μJ";
    }
    
    return ss.str();
}

std::string format_power(double power_watts) {
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(2);
    
    if (power_watts >= 1000.0) {
        ss << (power_watts / 1000.0) << " kW";
    } else if (power_watts >= 1.0) {
        ss << power_watts << " W";
    } else {
        ss << (power_watts * 1000.0) << " mW";
    }
    
    return ss.str();
}

bool is_energy_measurement_supported() {
    try {
        EnergyMeter meter;
        return meter.is_available();
    } catch (...) {
        return false;
    }
}

std::vector<std::string> get_available_providers() {
    try {
        EnergyMeter meter;
        return meter.get_provider_info();
    } catch (...) {
        return {};
    }
}

double validate_measurement_accuracy(double duration_seconds) {
    try {
        EnergyMeter meter;
        if (!meter.is_available()) {
            return -1.0; // Unable to validate
        }
        
        // Run calibration workload for specified duration
        auto energy_consumed = meter.measure([duration_seconds]() {
            auto start = std::chrono::steady_clock::now();
            volatile double result = 0.0;
            
            while (true) {
                auto elapsed = std::chrono::steady_clock::now() - start;
                if (std::chrono::duration<double>(elapsed).count() >= duration_seconds) {
                    break;
                }
                
                // CPU-intensive work
                for (int i = 0; i < 10000; ++i) {
                    result += std::sqrt(i) + std::sin(i);
                }
            }
        }, "accuracy_validation");
        
        return energy_consumed.is_valid ? energy_consumed.uncertainty_percent : -1.0;
        
    } catch (...) {
        return -1.0;
    }
}

} // namespace energy_utils

} // namespace codegreen