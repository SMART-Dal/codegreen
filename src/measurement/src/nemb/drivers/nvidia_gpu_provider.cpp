#include "../../../include/nemb/drivers/nvidia_gpu_provider.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <sstream>
#include <algorithm>
#include <cmath>

// NVML headers - conditionally compiled
#ifdef HAVE_NVML
#include <nvml.h>
#else
// Stub definitions when NVML is not available
typedef enum {
    NVML_SUCCESS = 0,
    NVML_ERROR_UNINITIALIZED = 1,
    NVML_ERROR_INVALID_ARGUMENT = 2,
    NVML_ERROR_NOT_SUPPORTED = 3,
    NVML_ERROR_NO_PERMISSION = 4,
    NVML_ERROR_ALREADY_INITIALIZED = 5,
    NVML_ERROR_NOT_FOUND = 6,
    NVML_ERROR_INSUFFICIENT_SIZE = 7,
    NVML_ERROR_INSUFFICIENT_POWER = 8,
    NVML_ERROR_DRIVER_NOT_LOADED = 9,
    NVML_ERROR_TIMEOUT = 10,
    NVML_ERROR_IRQ_ISSUE = 11,
    NVML_ERROR_LIBRARY_NOT_FOUND = 12,
    NVML_ERROR_FUNCTION_NOT_FOUND = 13,
    NVML_ERROR_CORRUPTED_INFOROM = 14,
    NVML_ERROR_GPU_IS_LOST = 15,
    NVML_ERROR_RESET_REQUIRED = 16,
    NVML_ERROR_OPERATING_SYSTEM = 17,
    NVML_ERROR_LIB_RM_VERSION_MISMATCH = 18,
    NVML_ERROR_IN_USE = 19,
    NVML_ERROR_MEMORY = 20,
    NVML_ERROR_NO_DATA = 21,
    NVML_ERROR_VGPU_ECC_NOT_SUPPORTED = 22,
    NVML_ERROR_INSUFFICIENT_RESOURCES = 23,
    NVML_ERROR_UNKNOWN = 999
} nvmlReturn_t;

#define NVML_DEVICE_NAME_BUFFER_SIZE 64
#define NVML_DEVICE_UUID_BUFFER_SIZE 80
#define NVML_SYSTEM_DRIVER_VERSION_BUFFER_SIZE 80
#define NVML_SYSTEM_NVML_VERSION_BUFFER_SIZE 80

typedef enum {
    NVML_TEMPERATURE_GPU = 0,
    NVML_TEMPERATURE_COUNT
} nvmlTemperatureSensors_t;

typedef enum {
    NVML_CLOCK_GRAPHICS = 0,
    NVML_CLOCK_SM = 1,
    NVML_CLOCK_MEM = 2,
    NVML_CLOCK_VIDEO = 3,
    NVML_CLOCK_COUNT
} nvmlClockType_t;

typedef struct {
    unsigned long long total;
    unsigned long long free;
    unsigned long long used;
} nvmlMemory_t;

typedef struct {
    unsigned int gpu;
    unsigned int memory;
} nvmlUtilization_t;

// Stub functions
nvmlReturn_t nvmlInit() { return NVML_ERROR_LIBRARY_NOT_FOUND; }
nvmlReturn_t nvmlShutdown() { return NVML_SUCCESS; }
nvmlReturn_t nvmlDeviceGetCount(unsigned int* deviceCount) { *deviceCount = 0; return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetHandleByIndex(unsigned int index, nvmlDevice_t* device) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetName(nvmlDevice_t device, char* name, unsigned int length) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetUUID(nvmlDevice_t device, char* uuid, unsigned int length) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetMemoryInfo(nvmlDevice_t device, nvmlMemory_t* memory) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetPowerUsage(nvmlDevice_t device, unsigned int* power) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetTemperature(nvmlDevice_t device, nvmlTemperatureSensors_t sensorType, unsigned int* temp) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetClockInfo(nvmlDevice_t device, nvmlClockType_t type, unsigned int* clock) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetUtilizationRates(nvmlDevice_t device, nvmlUtilization_t* utilization) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetPowerManagementDefaultLimitConstraints(nvmlDevice_t device, unsigned int* minLimit, unsigned int* maxLimit) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceGetPowerManagementLimitConstraints(nvmlDevice_t device, unsigned int* minLimit, unsigned int* maxLimit) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlDeviceSetPowerManagementLimitConstraints(nvmlDevice_t device, unsigned int limit) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlSystemGetDriverVersion(char* version, unsigned int length) { return NVML_ERROR_NOT_SUPPORTED; }
nvmlReturn_t nvmlSystemGetNVMLVersion(char* version, unsigned int length) { return NVML_ERROR_NOT_SUPPORTED; }
const char* nvmlErrorString(nvmlReturn_t result) { return "NVML not available"; }
#endif

namespace codegreen::nemb::drivers {

// GPUEnergyIntegrator implementation
void GPUEnergyIntegrator::add_power_sample(double power_watts, uint64_t timestamp_ns) {
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

double GPUEnergyIntegrator::get_accumulated_energy() const {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    return accumulated_energy_joules_;
}

void GPUEnergyIntegrator::reset_accumulation() {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    accumulated_energy_joules_ = 0.0;
    power_samples_.clear();
    last_integration_time_ = 0;
}

double GPUEnergyIntegrator::get_average_power() const {
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

// NVIDIAGPUProvider implementation
NVIDIAGPUProvider::NVIDIAGPUProvider() = default;

NVIDIAGPUProvider::~NVIDIAGPUProvider() {
    shutdown();
}

bool NVIDIAGPUProvider::initialize() {
    if (initialized_) {
        return true;
    }
    
    if (!initialize_nvml()) {
        return false;
    }
    
    if (!detect_gpus()) {
        shutdown_nvml();
        return false;
    }
    
    // Initialize monitoring for all GPUs
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        if (!initialize_gpu_monitoring(i)) {
            std::cerr << "Warning: Failed to initialize monitoring for GPU " << i << std::endl;
        }
    }
    
    initialized_ = true;
    return true;
}

EnergyReading NVIDIAGPUProvider::get_reading() {
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
            std::string gpu_domain = "gpu" + std::to_string(i);
            domain_energy[gpu_domain] = gpu_energy;
            domain_power[gpu_domain] = gpu_power;
            
            gpu_state.consecutive_failures = 0;
        } else {
            gpu_state.consecutive_failures++;
            if (gpu_state.consecutive_failures > max_consecutive_failures_) {
                gpu_state.available = false;
                std::cerr << "GPU " << i << " marked as unavailable due to consecutive failures" << std::endl;
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
    reading.provider_id = "nvidia_gpu";
    reading.confidence = (active_gpus > 0) ? 0.98 : 0.0; // 98% confidence for NVML
    reading.uncertainty_percent = (active_gpus > 0) ? 2.0 : 100.0; // 2% uncertainty for NVML
    
    return reading;
}

EnergyProviderSpec NVIDIAGPUProvider::get_specification() const {
    EnergyProviderSpec spec;
    spec.provider_name = "NVIDIA GPU";
    spec.hardware_type = "gpu";
    spec.vendor = "nvidia";
    spec.measurement_domains.push_back("gpu_total");
    
    // Add individual GPU domains
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        spec.measurement_domains.push_back("gpu" + std::to_string(i));
    }
    
    spec.energy_resolution_joules = 1e-3; // Millijoule precision
    spec.power_resolution_watts = 1e-3; // Milliwatt precision
    spec.update_interval = std::chrono::microseconds(100000); // 100ms update interval
    spec.counter_bits = 32; // NVML power counters are 32-bit
    
    return spec;
}

bool NVIDIAGPUProvider::self_test() {
    if (!initialized_) {
        return false;
    }
    
    // Test basic NVML functionality
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        double power = get_gpu_power(i);
        if (power < 0) {
            std::cerr << "Self-test failed for GPU " << i << ": Cannot read power" << std::endl;
            return false;
        }
        
        // Verify power reading is reasonable (0.1W to 1000W)
        if (power < 0.1 || power > 1000.0) {
            std::cerr << "Self-test warning for GPU " << i << ": Unusual power reading: " << power << "W" << std::endl;
        }
    }
    
    return true;
}

bool NVIDIAGPUProvider::is_available() const {
    return initialized_ && gpu_count_ > 0;
}

void NVIDIAGPUProvider::shutdown() {
    if (initialized_) {
        // Reset all energy integrators
        for (auto& gpu_state : gpu_states_) {
            if (gpu_state.energy_integrator) {
                gpu_state.energy_integrator->reset_accumulation();
            }
        }
        
        shutdown_nvml();
        initialized_ = false;
    }
}

bool NVIDIAGPUProvider::initialize_nvml() {
    nvmlReturn_t result = nvmlInit();
    if (result != NVML_SUCCESS) {
        std::cerr << "Failed to initialize NVML: " << nvmlErrorString(result) << std::endl;
        return false;
    }
    
    nvml_initialized_ = true;
    return true;
}

void NVIDIAGPUProvider::shutdown_nvml() {
    if (nvml_initialized_) {
        nvmlShutdown();
        nvml_initialized_ = false;
    }
}

bool NVIDIAGPUProvider::detect_gpus() {
    nvmlReturn_t result = nvmlDeviceGetCount(&gpu_count_);
    if (result != NVML_SUCCESS) {
        std::cerr << "Failed to get GPU count: " << nvmlErrorString(result) << std::endl;
        return false;
    }
    
    if (gpu_count_ == 0) {
        std::cerr << "No NVIDIA GPUs detected" << std::endl;
        return false;
    }
    
    // Initialize GPU states
    gpu_states_.resize(gpu_count_);
    gpu_info_.resize(gpu_count_);
    
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gpu_state = gpu_states_[i];
        auto& gpu_info = gpu_info_[i];
        
        // Get device handle
        result = nvmlDeviceGetHandleByIndex(i, &gpu_state.device_handle);
        if (result != NVML_SUCCESS) {
            std::cerr << "Failed to get handle for GPU " << i << ": " << nvmlErrorString(result) << std::endl;
            continue;
        }
        
        // Get basic GPU information
        char name[NVML_DEVICE_NAME_BUFFER_SIZE];
        result = nvmlDeviceGetName(gpu_state.device_handle, name, sizeof(name));
        if (result == NVML_SUCCESS) {
            gpu_info.name = name;
        }
        
        // Get UUID
        char uuid[NVML_DEVICE_UUID_BUFFER_SIZE];
        result = nvmlDeviceGetUUID(gpu_state.device_handle, uuid, sizeof(uuid));
        if (result == NVML_SUCCESS) {
            gpu_info.uuid = uuid;
        }
        
        // Get memory information
        nvmlMemory_t memory;
        result = nvmlDeviceGetMemoryInfo(gpu_state.device_handle, &memory);
        if (result == NVML_SUCCESS) {
            gpu_info.memory_total_mb = static_cast<uint32_t>(memory.total / (1024 * 1024));
        }
        
        // Get power limits
        uint32_t power_limit;
        result = nvmlDeviceGetPowerManagementLimitConstraints(gpu_state.device_handle, 
                                                             &gpu_info.min_power_limit_watts, 
                                                             &gpu_info.max_power_limit_watts);
        if (result == NVML_SUCCESS) {
            result = nvmlDeviceGetPowerUsage(gpu_state.device_handle, &power_limit);
            if (result == NVML_SUCCESS) {
                gpu_info.power_limit_watts = power_limit / 1000; // Convert mW to W
            }
        }
        
        // Check power monitoring support
        result = nvmlDeviceGetPowerUsage(gpu_state.device_handle, &power_limit);
        gpu_info.supports_power_monitoring = (result == NVML_SUCCESS);
        
        gpu_info.device_index = i;
        gpu_info.supports_energy_monitoring = false; // NVML doesn't directly support energy
        gpu_state.info = gpu_info;
        gpu_state.available = true;
        
        // Create energy integrator
        gpu_state.energy_integrator = std::make_unique<GPUEnergyIntegrator>();
    }
    
    return true;
}

bool NVIDIAGPUProvider::initialize_gpu_monitoring(uint32_t gpu_index) {
    if (gpu_index >= gpu_count_) {
        return false;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    
    // Test power reading
    double power = get_gpu_power(gpu_index);
    if (power < 0) {
        std::cerr << "Cannot initialize monitoring for GPU " << gpu_index << ": Power reading failed" << std::endl;
        gpu_state.available = false;
        return false;
    }
    
    gpu_state.monitoring_enabled = true;
    return true;
}

double NVIDIAGPUProvider::get_gpu_power(uint32_t gpu_index) {
    if (gpu_index >= gpu_count_) {
        return -1.0;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return -1.0;
    }
    
    uint32_t power_mw;
    nvmlReturn_t result = nvmlDeviceGetPowerUsage(gpu_state.device_handle, &power_mw);
    if (result != NVML_SUCCESS) {
        handle_nvml_error("get_gpu_power", result);
        return -1.0;
    }
    
    // Convert from milliwatts to watts
    return static_cast<double>(power_mw) / 1000.0;
}

void NVIDIAGPUProvider::handle_nvml_error(const std::string& operation, int nvml_result) {
    std::cerr << "NVML error in " << operation << ": " << nvmlErrorString(static_cast<nvmlReturn_t>(nvml_result)) << std::endl;
}

// Factory functions
std::unique_ptr<NVIDIAGPUProvider> create_nvidia_gpu_provider() {
    return std::make_unique<NVIDIAGPUProvider>();
}

bool is_nvidia_gpu_available() {
    nvmlReturn_t result = nvmlInit();
    if (result != NVML_SUCCESS) {
        return false;
    }
    
    uint32_t gpu_count;
    result = nvmlDeviceGetCount(&gpu_count);
    
    nvmlShutdown();
    
    return (result == NVML_SUCCESS && gpu_count > 0);
}

std::map<std::string, std::string> get_nvidia_version_info() {
    std::map<std::string, std::string> info;
    
    nvmlReturn_t result = nvmlInit();
    if (result != NVML_SUCCESS) {
        info["error"] = "Failed to initialize NVML";
        return info;
    }
    
    char driver_version[NVML_SYSTEM_DRIVER_VERSION_BUFFER_SIZE];
    result = nvmlSystemGetDriverVersion(driver_version, sizeof(driver_version));
    if (result == NVML_SUCCESS) {
        info["driver_version"] = driver_version;
    }
    
    char nvml_version[NVML_SYSTEM_NVML_VERSION_BUFFER_SIZE];
    result = nvmlSystemGetNVMLVersion(nvml_version, sizeof(nvml_version));
    if (result == NVML_SUCCESS) {
        info["nvml_version"] = nvml_version;
    }
    
    nvmlShutdown();
    return info;
}

// Additional method implementations that were declared in header
std::map<uint32_t, double> NVIDIAGPUProvider::get_per_gpu_energy_breakdown() {
    std::map<uint32_t, double> breakdown;
    
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gpu_state = gpu_states_[i];
        if (gpu_state.available && gpu_state.monitoring_enabled && gpu_state.energy_integrator) {
            breakdown[i] = gpu_state.energy_integrator->get_accumulated_energy();
        }
    }
    
    return breakdown;
}

GPUPowerState NVIDIAGPUProvider::get_gpu_power_state(uint32_t gpu_index) {
    GPUPowerState state{};
    
    if (gpu_index >= gpu_count_) {
        return state;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return state;
    }
    
    // Get power limit
    uint32_t power_limit_mw;
    if (nvmlDeviceGetPowerManagementLimitConstraints(gpu_state.device_handle, nullptr, &power_limit_mw) == NVML_SUCCESS) {
        state.power_limit_watts = power_limit_mw / 1000;
    }
    
    // Get clocks
    uint32_t graphics_clock, memory_clock;
    if (nvmlDeviceGetClockInfo(gpu_state.device_handle, NVML_CLOCK_GRAPHICS, &graphics_clock) == NVML_SUCCESS) {
        state.graphics_clock_mhz = graphics_clock;
    }
    if (nvmlDeviceGetClockInfo(gpu_state.device_handle, NVML_CLOCK_MEM, &memory_clock) == NVML_SUCCESS) {
        state.memory_clock_mhz = memory_clock;
    }
    
    // Get temperature
    uint32_t temp;
    if (nvmlDeviceGetTemperature(gpu_state.device_handle, NVML_TEMPERATURE_GPU, &temp) == NVML_SUCCESS) {
        state.temperature_celsius = static_cast<double>(temp);
    }
    
    return state;
}

bool NVIDIAGPUProvider::set_gpu_monitoring_enabled(uint32_t gpu_index, bool enabled) {
    if (gpu_index >= gpu_count_) {
        return false;
    }
    
    gpu_states_[gpu_index].monitoring_enabled = enabled;
    return true;
}

std::map<std::string, uint32_t> NVIDIAGPUProvider::get_gpu_utilization(uint32_t gpu_index) {
    std::map<std::string, uint32_t> utilization;
    
    if (gpu_index >= gpu_count_) {
        return utilization;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return utilization;
    }
    
    nvmlUtilization_t util;
    if (nvmlDeviceGetUtilizationRates(gpu_state.device_handle, &util) == NVML_SUCCESS) {
        utilization["gpu"] = util.gpu;
        utilization["memory"] = util.memory;
    }
    
    return utilization;
}

bool NVIDIAGPUProvider::set_power_limit(uint32_t gpu_index, uint32_t power_limit_watts) {
    if (gpu_index >= gpu_count_) {
        return false;
    }
    
    auto& gpu_state = gpu_states_[gpu_index];
    if (!gpu_state.available) {
        return false;
    }
    
    // Convert watts to milliwatts
    uint32_t power_limit_mw = power_limit_watts * 1000;
    
    // Note: Power limit setting requires proper NVML function
    // This is a placeholder - actual implementation would use nvmlDeviceSetPowerManagementLimit
    std::cerr << "Power limit setting not fully implemented for GPU " << gpu_index << std::endl;
    return false;
}

GPUWorkloadType NVIDIAGPUProvider::detect_workload_type(uint32_t gpu_index) {
    auto utilization = get_gpu_utilization(gpu_index);
    
    if (utilization.empty()) {
        return GPUWorkloadType::UNKNOWN;
    }
    
    uint32_t gpu_util = utilization.count("gpu") ? utilization["gpu"] : 0;
    uint32_t mem_util = utilization.count("memory") ? utilization["memory"] : 0;
    
    if (gpu_util < 5 && mem_util < 5) {
        return GPUWorkloadType::IDLE;
    } else if (mem_util > 80 && gpu_util < 50) {
        return GPUWorkloadType::MEMORY_BOUND;
    } else if (gpu_util > 80) {
        return GPUWorkloadType::COMPUTE;
    } else {
        return GPUWorkloadType::MIXED;
    }
}

} // namespace codegreen::nemb::drivers