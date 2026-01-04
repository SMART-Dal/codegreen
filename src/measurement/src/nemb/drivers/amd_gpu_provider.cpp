#include "../../../include/nemb/drivers/amd_gpu_provider.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <filesystem>

// ROCm SMI includes - will be conditionally compiled
#ifdef HAVE_ROCM_SMI
#include <rocm_smi/rocm_smi.h>
#else
// Stub definitions when ROCm SMI is not available
typedef enum {
    RSMI_STATUS_SUCCESS = 0,
    RSMI_STATUS_NOT_SUPPORTED,
    RSMI_STATUS_INVALID_ARGS,
    RSMI_STATUS_NOT_YET_IMPLEMENTED,
    RSMI_STATUS_FAIL_LOAD_MODULE,
    RSMI_STATUS_FAIL_LOAD_SYMBOL,
    RSMI_STATUS_DRM_ERROR,
    RSMI_STATUS_API_FAILED_INIT,
    RSMI_STATUS_INSUFFICIENT_SIZE,
    RSMI_STATUS_INTERRUPT,
    RSMI_STATUS_UNEXPECTED_SIZE,
    RSMI_STATUS_NO_DATA,
    RSMI_STATUS_UNEXPECTED_DATA,
    RSMI_STATUS_BUSY,
    RSMI_STATUS_REFCOUNT_OVERFLOW,
    RSMI_STATUS_UNKNOWN_ERROR = 0xFFFFFFFF
} rsmi_status_t;

#define RSMI_MAX_NUM_FREQUENCIES 32
#define RSMI_MAX_FAN_SPEED 255
#define RSMI_DEVICE_NAME_LEN 128
#define RSMI_MAX_NUM_POWER_PROFILES (sizeof(uint32_t) * 8)

// Stub function declarations
rsmi_status_t rsmi_init(uint64_t flags) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_shut_down() { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_num_monitor_devices(uint32_t* num_devices) { *num_devices = 0; return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_name_get(uint32_t dv_ind, char* name, size_t len) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_power_ave_get(uint32_t dv_ind, uint32_t sensor_ind, uint64_t* power) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_temp_metric_get(uint32_t dv_ind, uint32_t sensor_type, uint32_t metric, int64_t* temperature) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_memory_total_get(uint32_t dv_ind, uint32_t mem_type, uint64_t* total) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_memory_usage_get(uint32_t dv_ind, uint32_t mem_type, uint64_t* used) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_busy_percent_get(uint32_t dv_ind, uint32_t* busy_percent) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_gpu_clk_freq_get(uint32_t dv_ind, uint32_t clk_type, uint64_t* freq) { return RSMI_STATUS_NOT_SUPPORTED; }
rsmi_status_t rsmi_dev_fan_speed_get(uint32_t dv_ind, uint32_t sensor_ind, int64_t* speed) { return RSMI_STATUS_NOT_SUPPORTED; }
#endif

namespace codegreen::nemb::drivers {

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("amd_gpu", []() {
            return std::make_unique<AMDGPUProvider>();
        });
        return true;
    }();
}

// AMDGPUEnergyIntegrator implementation
void AMDGPUEnergyIntegrator::add_power_sample(double power_watts, uint64_t timestamp_ns) {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    
    if (!power_samples_.empty() && last_integration_time_ > 0) {
        // Calculate energy increment using trapezoidal rule
        double time_diff_seconds = (timestamp_ns - last_integration_time_) / 1e9;
        double avg_power = (power_samples_.back().power_watts + power_watts) / 2.0;
        accumulated_energy_joules_ += avg_power * time_diff_seconds;
    }
    
    power_samples_.push_back({power_watts, timestamp_ns});
    last_integration_time_ = timestamp_ns;
    
    // Keep only recent samples to prevent memory growth
    if (power_samples_.size() > 10000) {
        power_samples_.erase(power_samples_.begin(), power_samples_.begin() + 5000);
    }
}

double AMDGPUEnergyIntegrator::get_accumulated_energy() const {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    return accumulated_energy_joules_;
}

void AMDGPUEnergyIntegrator::reset_accumulation() {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    accumulated_energy_joules_ = 0.0;
    power_samples_.clear();
    last_integration_time_ = 0;
}

double AMDGPUEnergyIntegrator::get_average_power() const {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    
    if (power_samples_.empty()) {
        return 0.0;
    }
    
    double total_power = 0.0;
    for (const auto& sample : power_samples_) {
        total_power += sample.power_watts;
    }
    
    return total_power / power_samples_.size();
}

// AMDGPUProvider implementation
AMDGPUProvider::AMDGPUProvider() = default;

AMDGPUProvider::~AMDGPUProvider() {
    shutdown();
}

bool AMDGPUProvider::initialize() {
    if (initialized_) {
        return true;
    }
    
    if (!initialize_rsmi()) {
        return false;
    }
    
    if (!detect_amd_gpus()) {
        shutdown_rsmi();
        return false;
    }
    
    // Initialize monitoring for all GPUs
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        if (!initialize_gpu_monitoring(i)) {
            std::cerr << "Warning: Failed to initialize monitoring for AMD GPU " << i << std::endl;
        }
    }
    
    initialized_ = true;
    return true;
}

EnergyReading AMDGPUProvider::get_reading() {
    if (!initialized_) {
        return EnergyReading{};
    }
    
    std::lock_guard<std::mutex> lock(reading_mutex_);
    
    auto now = std::chrono::steady_clock::now();
    double total_energy = 0.0;
    double total_power = 0.0;
    uint32_t active_gpus = 0;
    
    std::map<std::string, double> domain_energy;
    std::map<std::string, double> domain_power;
    
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gpu_state = gpu_states_[i];
        
        if (!gpu_state.available || !gpu_state.monitoring_enabled) {
            continue;
        }
        
        // Get current power reading
        double gpu_power = get_gpu_power(i);
        if (gpu_power > 0) {
            // Add power sample to integrator
            uint64_t timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                now.time_since_epoch()).count();
            gpu_state.energy_integrator->add_power_sample(gpu_power, timestamp_ns);
            
            // Get accumulated energy
            double gpu_energy = gpu_state.energy_integrator->get_accumulated_energy();
            
            total_energy += gpu_energy;
            total_power += gpu_power;
            active_gpus++;
            
            // Add to domain breakdown
            std::string gpu_domain = "amd_gpu" + std::to_string(i);
            domain_energy[gpu_domain] = gpu_energy;
            domain_power[gpu_domain] = gpu_power;
            
            gpu_state.consecutive_failures = 0;
        } else {
            gpu_state.consecutive_failures++;
            if (gpu_state.consecutive_failures > max_consecutive_failures_) {
                gpu_state.available = false;
                std::cerr << "AMD GPU " << i << " marked as unavailable due to consecutive failures" << std::endl;
            }
        }
        
        gpu_state.last_reading_time = now;
    }
    
    EnergyReading reading;
    reading.energy_joules = total_energy;
    reading.average_power_watts = total_power;
    reading.domain_energy_joules = std::move(domain_energy);
    reading.domain_power_watts = std::move(domain_power);
    reading.timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        now.time_since_epoch()).count();
    reading.provider_id = "amd_gpu";
    reading.confidence = (active_gpus > 0) ? 0.97 : 0.0; // 97% confidence for ROCm SMI
    reading.uncertainty_percent = (active_gpus > 0) ? 3.0 : 100.0; // 3% uncertainty for ROCm SMI
    
    return reading;
}

EnergyProviderSpec AMDGPUProvider::get_specification() const {
    EnergyProviderSpec spec;
    spec.provider_name = "AMD GPU";
    spec.hardware_type = "gpu";
    spec.vendor = "amd";
    spec.measurement_domains.push_back("amd_gpu_total");
    
    // Add individual GPU domains
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        spec.measurement_domains.push_back("amd_gpu" + std::to_string(i));
    }
    
    spec.energy_resolution_joules = 1e-3; // Millijoule precision
    spec.power_resolution_watts = 1e-3; // Milliwatt precision
    spec.update_interval = std::chrono::microseconds(100000); // 100ms update interval
    spec.counter_bits = 32; // ROCm SMI power counters are 32-bit
    
    return spec;
}

bool AMDGPUProvider::self_test() {
    if (!initialized_) {
        return false;
    }
    
    // Test basic ROCm SMI functionality
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        double power = get_gpu_power(i);
        if (power < 0) {
            std::cerr << "Self-test failed for AMD GPU " << i << ": Cannot read power" << std::endl;
            return false;
        }
        
        // Verify power reading is reasonable (0.1W to 1000W)
        if (power < 0.1 || power > 1000.0) {
            std::cerr << "Self-test warning for AMD GPU " << i << ": Unusual power reading: " << power << "W" << std::endl;
        }
    }
    
    return true;
}

bool AMDGPUProvider::is_available() const {
    return initialized_ && gpu_count_ > 0;
}

void AMDGPUProvider::shutdown() {
    if (initialized_) {
        // Reset all energy integrators
        for (auto& gpu_state : gpu_states_) {
            if (gpu_state.energy_integrator) {
                gpu_state.energy_integrator->reset_accumulation();
            }
        }
        
        shutdown_rsmi();
        initialized_ = false;
    }
}

bool AMDGPUProvider::initialize_rsmi() {
#ifdef HAVE_ROCM_SMI
    rsmi_status_t result = rsmi_init(0);
    if (result != RSMI_STATUS_SUCCESS) {
        std::cerr << "Failed to initialize ROCm SMI: " << result << std::endl;
        return false;
    }
    
    rsmi_initialized_ = true;
    return true;
#else
    // Check if we can detect AMD GPUs through sysfs as fallback
    return detect_amd_gpus_fallback();
#endif
}

void AMDGPUProvider::shutdown_rsmi() {
#ifdef HAVE_ROCM_SMI
    if (rsmi_initialized_) {
        rsmi_shut_down();
        rsmi_initialized_ = false;
    }
#endif
}

bool AMDGPUProvider::detect_amd_gpus() {
#ifdef HAVE_ROCM_SMI
    rsmi_status_t result = rsmi_num_monitor_devices(&gpu_count_);
    if (result != RSMI_STATUS_SUCCESS) {
        std::cerr << "Failed to get AMD GPU count: " << result << std::endl;
        return false;
    }
    
    if (gpu_count_ == 0) {
        std::cerr << "No AMD GPUs detected by ROCm SMI" << std::endl;
        return false;
    }
    
    // Initialize GPU states
    gpu_states_.resize(gpu_count_);
    gpu_info_.resize(gpu_count_);
    
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gpu_state = gpu_states_[i];
        auto& gpu_info = gpu_info_[i];
        
        // Get basic GPU information
        char name[RSMI_DEVICE_NAME_LEN];
        result = rsmi_dev_name_get(i, name, sizeof(name));
        if (result == RSMI_STATUS_SUCCESS) {
            gpu_info.name = name;
        } else {
            gpu_info.name = "AMD GPU " + std::to_string(i);
        }
        
        // Get memory information
        uint64_t memory_total;
        result = rsmi_dev_memory_total_get(i, 0, &memory_total); // Type 0 = VRAM
        if (result == RSMI_STATUS_SUCCESS) {
            gpu_info.memory_total_bytes = memory_total;
        }
        
        // Test power monitoring capability
        uint64_t power;
        result = rsmi_dev_power_ave_get(i, 0, &power);
        gpu_info.supports_power_monitoring = (result == RSMI_STATUS_SUCCESS);
        
        gpu_info.device_index = i;
        gpu_info.supports_energy_monitoring = false; // ROCm SMI doesn't directly support energy
        gpu_state.info = gpu_info;
        gpu_state.available = true;
        
        // Create energy integrator
        gpu_state.energy_integrator = std::make_unique<AMDGPUEnergyIntegrator>();
    }
    
    return true;
#else
    // Fallback detection through sysfs
    return detect_amd_gpus_fallback();
#endif
}

bool AMDGPUProvider::detect_amd_gpus_fallback() {
    // Try to detect AMD GPUs through /sys/class/drm/
    gpu_count_ = 0;
    
    try {
        std::filesystem::path drm_path("/sys/class/drm");
        if (!std::filesystem::exists(drm_path)) {
            return false;
        }
        
        for (const auto& entry : std::filesystem::directory_iterator(drm_path)) {
            if (entry.is_symlink() || !entry.is_directory()) {
                continue;
            }
            
            std::string dirname = entry.path().filename().string();
            if (dirname.find("card") != 0 || dirname.find("-") != std::string::npos) {
                continue; // Skip render nodes and non-card entries
            }
            
            // Check if this is an AMD GPU
            std::ifstream vendor_file(entry.path() / "device" / "vendor");
            std::string vendor_id;
            if (vendor_file >> vendor_id) {
                // AMD vendor ID is 0x1002
                if (vendor_id == "0x1002") {
                    gpu_count_++;
                }
            }
        }
        
        if (gpu_count_ > 0) {
            gpu_states_.resize(gpu_count_);
            gpu_info_.resize(gpu_count_);
            
            // Initialize basic info for fallback mode
            for (uint32_t i = 0; i < gpu_count_; ++i) {
                auto& gpu_state = gpu_states_[i];
                auto& gpu_info = gpu_info_[i];
                
                gpu_info.device_index = i;
                gpu_info.name = "AMD GPU " + std::to_string(i) + " (Fallback)";
                gpu_info.supports_power_monitoring = false; // No power monitoring in fallback
                gpu_info.supports_energy_monitoring = false;
                
                gpu_state.info = gpu_info;
                gpu_state.available = false; // Not available for energy monitoring
                gpu_state.energy_integrator = std::make_unique<AMDGPUEnergyIntegrator>();
            }
            
            std::cout << "AMD GPU fallback detection found " << gpu_count_ << " GPUs (no power monitoring)" << std::endl;
            return true;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "AMD GPU fallback detection failed: " << e.what() << std::endl;
    }
    
    return false;
}

bool AMDGPUProvider::initialize_gpu_monitoring(uint32_t gpu_index) {
    if (gpu_index >= gpu_count_) {
        return false;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    
    // Test power reading
    double power = get_gpu_power(gpu_index);
    if (power < 0) {
        std::cerr << "Cannot initialize monitoring for AMD GPU " << gpu_index << ": Power reading failed" << std::endl;
        gpu_state.available = false;
        return false;
    }
    
    gpu_state.monitoring_enabled = true;
    return true;
}

double AMDGPUProvider::get_gpu_power(uint32_t gpu_index) {
#ifdef HAVE_ROCM_SMI
    if (gpu_index >= gpu_count_) {
        return -1.0;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return -1.0;
    }
    
    uint64_t power_uw; // Power in microwatts
    rsmi_status_t result = rsmi_dev_power_ave_get(gpu_index, 0, &power_uw);
    if (result != RSMI_STATUS_SUCCESS) {
        handle_rsmi_error("get_gpu_power", result);
        return -1.0;
    }
    
    // Convert from microwatts to watts
    return static_cast<double>(power_uw) / 1e6;
#else
    // No power monitoring available in fallback mode
    return -1.0;
#endif
}

void AMDGPUProvider::handle_rsmi_error(const std::string& operation, int rsmi_result) {
    std::cerr << "ROCm SMI error in " << operation << ": " << rsmi_result << std::endl;
}

// Additional method implementations
std::map<uint32_t, double> AMDGPUProvider::get_per_gpu_energy_breakdown() {
    std::map<uint32_t, double> breakdown;
    
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gpu_state = gpu_states_[i];
        if (gpu_state.available && gpu_state.monitoring_enabled && gpu_state.energy_integrator) {
            breakdown[i] = gpu_state.energy_integrator->get_accumulated_energy();
        }
    }
    
    return breakdown;
}

AMDGPUPowerState AMDGPUProvider::get_gpu_power_state(uint32_t gpu_index) {
    AMDGPUPowerState state{};
    
#ifdef HAVE_ROCM_SMI
    if (gpu_index >= gpu_count_) {
        return state;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return state;
    }
    
    // Get temperature
    int64_t temp;
    if (rsmi_dev_temp_metric_get(gpu_index, 0, 0, &temp) == RSMI_STATUS_SUCCESS) {
        state.temperature_celsius = static_cast<double>(temp) / 1000.0; // Convert from millidegrees
    }
    
    // Get clock frequencies
    uint64_t sclk_freq, mclk_freq;
    if (rsmi_dev_gpu_clk_freq_get(gpu_index, 0, &sclk_freq) == RSMI_STATUS_SUCCESS) {
        state.sclk_frequency_mhz = static_cast<uint32_t>(sclk_freq / 1000000); // Convert to MHz
    }
    if (rsmi_dev_gpu_clk_freq_get(gpu_index, 1, &mclk_freq) == RSMI_STATUS_SUCCESS) {
        state.mclk_frequency_mhz = static_cast<uint32_t>(mclk_freq / 1000000); // Convert to MHz
    }
    
    // Get fan speed
    int64_t fan_speed;
    if (rsmi_dev_fan_speed_get(gpu_index, 0, &fan_speed) == RSMI_STATUS_SUCCESS) {
        state.fan_speed_rpm = static_cast<uint32_t>(fan_speed);
    }
#endif
    
    return state;
}

AMDGPUUtilization AMDGPUProvider::get_gpu_utilization(uint32_t gpu_index) {
    AMDGPUUtilization utilization{};
    
#ifdef HAVE_ROCM_SMI
    if (gpu_index >= gpu_count_) {
        return utilization;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return utilization;
    }
    
    // Get GPU busy percentage
    uint32_t busy_percent;
    if (rsmi_dev_busy_percent_get(gpu_index, &busy_percent) == RSMI_STATUS_SUCCESS) {
        utilization.gpu_busy_percent = busy_percent;
    }
    
    // Get memory usage
    uint64_t memory_used, memory_total;
    if (rsmi_dev_memory_usage_get(gpu_index, 0, &memory_used) == RSMI_STATUS_SUCCESS) {
        utilization.memory_used_bytes = memory_used;
    }
    if (rsmi_dev_memory_total_get(gpu_index, 0, &memory_total) == RSMI_STATUS_SUCCESS) {
        utilization.memory_total_bytes = memory_total;
    }
#endif
    
    return utilization;
}

bool AMDGPUProvider::set_gpu_monitoring_enabled(uint32_t gpu_index, bool enabled) {
    if (gpu_index >= gpu_count_) {
        return false;
    }
    
    gpu_states_[gpu_index].monitoring_enabled = enabled;
    return true;
}

bool AMDGPUProvider::set_power_cap(uint32_t gpu_index, uint32_t power_cap_watts) {
    // Power capping implementation would require additional ROCm SMI functions
    // This is a placeholder for now
    return false;
}

bool AMDGPUProvider::set_fan_speed(uint32_t gpu_index, uint32_t fan_speed_percent) {
    // Fan speed control implementation would require additional ROCm SMI functions
    // This is a placeholder for now
    return false;
}

// Factory functions
std::unique_ptr<AMDGPUProvider> create_amd_gpu_provider() {
    return std::make_unique<AMDGPUProvider>();
}

bool is_amd_gpu_available() {
    // Try quick detection through vendor ID in /sys
    try {
        std::filesystem::path drm_path("/sys/class/drm");
        if (!std::filesystem::exists(drm_path)) {
            return false;
        }
        
        for (const auto& entry : std::filesystem::directory_iterator(drm_path)) {
            if (entry.is_symlink() || !entry.is_directory()) {
                continue;
            }
            
            std::string dirname = entry.path().filename().string();
            if (dirname.find("card") != 0 || dirname.find("-") != std::string::npos) {
                continue;
            }
            
            std::ifstream vendor_file(entry.path() / "device" / "vendor");
            std::string vendor_id;
            if (vendor_file >> vendor_id && vendor_id == "0x1002") {
                return true; // Found AMD GPU
            }
        }
    } catch (const std::exception&) {
        // Ignore errors
    }
    
    return false;
}

std::map<std::string, std::string> get_amd_version_info() {
    std::map<std::string, std::string> info;
    
#ifdef HAVE_ROCM_SMI
    // ROCm SMI version information would be retrieved here
    info["rocm_smi"] = "available";
#else
    info["rocm_smi"] = "not_available";
    info["fallback_detection"] = "enabled";
#endif
    
    return info;
}

} // namespace codegreen::nemb::drivers