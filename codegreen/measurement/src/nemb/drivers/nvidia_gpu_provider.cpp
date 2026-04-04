#include "../../../include/nemb/drivers/nvidia_gpu_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <sstream>
#include <algorithm>
#include <cmath>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

// NVML types -- always defined locally, never #include <nvml.h>.
// The real library is loaded at runtime via dlopen/LoadLibrary.
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
    NVML_ERROR_LIBRARY_NOT_FOUND = 12,
    NVML_ERROR_FUNCTION_NOT_FOUND = 13,
    NVML_ERROR_UNKNOWN = 999
} nvmlReturn_t;

#define NVML_DEVICE_NAME_BUFFER_SIZE 64
#define NVML_DEVICE_UUID_BUFFER_SIZE 80
#define NVML_SYSTEM_DRIVER_VERSION_BUFFER_SIZE 80
#define NVML_SYSTEM_NVML_VERSION_BUFFER_SIZE 80

typedef enum {
    NVML_TEMPERATURE_GPU = 0
} nvmlTemperatureSensors_t;

typedef enum {
    NVML_CLOCK_GRAPHICS = 0,
    NVML_CLOCK_SM = 1,
    NVML_CLOCK_MEM = 2,
    NVML_CLOCK_VIDEO = 3
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

// Runtime-loaded NVML function pointers
struct NvmlAPI {
    using Init_t = nvmlReturn_t(*)();
    using Shutdown_t = nvmlReturn_t(*)();
    using DeviceGetCount_t = nvmlReturn_t(*)(unsigned int*);
    using DeviceGetHandleByIndex_t = nvmlReturn_t(*)(unsigned int, nvmlDevice_t*);
    using DeviceGetName_t = nvmlReturn_t(*)(nvmlDevice_t, char*, unsigned int);
    using DeviceGetUUID_t = nvmlReturn_t(*)(nvmlDevice_t, char*, unsigned int);
    using DeviceGetMemoryInfo_t = nvmlReturn_t(*)(nvmlDevice_t, nvmlMemory_t*);
    using DeviceGetPowerUsage_t = nvmlReturn_t(*)(nvmlDevice_t, unsigned int*);
    using DeviceGetTemperature_t = nvmlReturn_t(*)(nvmlDevice_t, nvmlTemperatureSensors_t, unsigned int*);
    using DeviceGetClockInfo_t = nvmlReturn_t(*)(nvmlDevice_t, nvmlClockType_t, unsigned int*);
    using DeviceGetUtilizationRates_t = nvmlReturn_t(*)(nvmlDevice_t, nvmlUtilization_t*);
    using DeviceGetPowerManagementLimitConstraints_t = nvmlReturn_t(*)(nvmlDevice_t, unsigned int*, unsigned int*);
    using SystemGetDriverVersion_t = nvmlReturn_t(*)(char*, unsigned int);
    using SystemGetNVMLVersion_t = nvmlReturn_t(*)(char*, unsigned int);
    using ErrorString_t = const char*(*)(nvmlReturn_t);

    Init_t Init = nullptr;
    Shutdown_t Shutdown = nullptr;
    DeviceGetCount_t DeviceGetCount = nullptr;
    DeviceGetHandleByIndex_t DeviceGetHandleByIndex = nullptr;
    DeviceGetName_t DeviceGetName = nullptr;
    DeviceGetUUID_t DeviceGetUUID = nullptr;
    DeviceGetMemoryInfo_t DeviceGetMemoryInfo = nullptr;
    DeviceGetPowerUsage_t DeviceGetPowerUsage = nullptr;
    DeviceGetTemperature_t DeviceGetTemperature = nullptr;
    DeviceGetClockInfo_t DeviceGetClockInfo = nullptr;
    DeviceGetUtilizationRates_t DeviceGetUtilizationRates = nullptr;
    DeviceGetPowerManagementLimitConstraints_t DeviceGetPowerManagementLimitConstraints = nullptr;
    SystemGetDriverVersion_t SystemGetDriverVersion = nullptr;
    SystemGetNVMLVersion_t SystemGetNVMLVersion = nullptr;
    ErrorString_t ErrorString = nullptr;

    void* lib_handle = nullptr;
    bool loaded = false;
    std::string loaded_path;

    // Intentionally no dlclose in destructor. During static destruction order is
    // undefined -- calling dlclose on NVML after CUDA runtime has torn down causes
    // segfaults. The OS reclaims everything on process exit anyway.

    bool load() {
        if (loaded) return true;

        // Check for user-specified path via environment variable
        const char* user_path = std::getenv("CODEGREEN_NVML_PATH");

#ifdef _WIN32
        const char* paths[] = {
            "nvml.dll",
            "C:\\Windows\\System32\\nvml.dll",
            nullptr
        };
        if (user_path) {
            lib_handle = LoadLibraryA(user_path);
            if (lib_handle) { loaded_path = user_path; }
        }
        if (!lib_handle) {
            for (int i = 0; paths[i]; ++i) {
                lib_handle = LoadLibraryA(paths[i]);
                if (lib_handle) { loaded_path = paths[i]; break; }
            }
        }
#else
        const char* paths[] = {
            "libnvidia-ml.so.1",
            "libnvidia-ml.so",
            "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1",
            "/usr/lib64/libnvidia-ml.so.1",
            "/usr/local/cuda/lib64/libnvidia-ml.so.1",
            "/usr/local/cuda/lib64/stubs/libnvidia-ml.so",
            "/usr/lib/aarch64-linux-gnu/libnvidia-ml.so.1",
            nullptr
        };
        if (user_path) {
            lib_handle = dlopen(user_path, RTLD_LAZY | RTLD_LOCAL);
            if (lib_handle) { loaded_path = user_path; }
        }
        if (!lib_handle) {
            for (int i = 0; paths[i]; ++i) {
                lib_handle = dlopen(paths[i], RTLD_LAZY | RTLD_LOCAL);
                if (lib_handle) { loaded_path = paths[i]; break; }
            }
        }
#endif
        if (!lib_handle) {
            std::cerr << "NVML: could not load NVIDIA Management Library." << std::endl;
            std::cerr << "  Searched:" << std::endl;
            if (user_path) std::cerr << "    " << user_path << " (CODEGREEN_NVML_PATH)" << std::endl;
            for (int i = 0; paths[i]; ++i)
                std::cerr << "    " << paths[i] << std::endl;
            std::cerr << "  Fix: set CODEGREEN_NVML_PATH=/path/to/libnvidia-ml.so.1" << std::endl;
            std::cerr << "  Or ensure NVIDIA driver is installed (nvidia-smi should work)" << std::endl;
            return false;
        }
        std::cerr << "NVML: loaded from " << loaded_path << std::endl;

        // Resolve all function pointers
        Init = resolve<Init_t>("nvmlInit_v2");
        if (!Init) Init = resolve<Init_t>("nvmlInit");
        Shutdown = resolve<Shutdown_t>("nvmlShutdown");
        DeviceGetCount = resolve<DeviceGetCount_t>("nvmlDeviceGetCount_v2");
        if (!DeviceGetCount) DeviceGetCount = resolve<DeviceGetCount_t>("nvmlDeviceGetCount");
        DeviceGetHandleByIndex = resolve<DeviceGetHandleByIndex_t>("nvmlDeviceGetHandleByIndex_v2");
        if (!DeviceGetHandleByIndex) DeviceGetHandleByIndex = resolve<DeviceGetHandleByIndex_t>("nvmlDeviceGetHandleByIndex");
        DeviceGetName = resolve<DeviceGetName_t>("nvmlDeviceGetName");
        DeviceGetUUID = resolve<DeviceGetUUID_t>("nvmlDeviceGetUUID");
        DeviceGetMemoryInfo = resolve<DeviceGetMemoryInfo_t>("nvmlDeviceGetMemoryInfo");
        DeviceGetPowerUsage = resolve<DeviceGetPowerUsage_t>("nvmlDeviceGetPowerUsage");
        DeviceGetTemperature = resolve<DeviceGetTemperature_t>("nvmlDeviceGetTemperature");
        DeviceGetClockInfo = resolve<DeviceGetClockInfo_t>("nvmlDeviceGetClockInfo");
        DeviceGetUtilizationRates = resolve<DeviceGetUtilizationRates_t>("nvmlDeviceGetUtilizationRates");
        DeviceGetPowerManagementLimitConstraints = resolve<DeviceGetPowerManagementLimitConstraints_t>("nvmlDeviceGetPowerManagementLimitConstraints");
        SystemGetDriverVersion = resolve<SystemGetDriverVersion_t>("nvmlSystemGetDriverVersion");
        SystemGetNVMLVersion = resolve<SystemGetNVMLVersion_t>("nvmlSystemGetNVMLVersion");
        ErrorString = resolve<ErrorString_t>("nvmlErrorString");

        // Minimum required: Init + Shutdown + DeviceGetCount + GetHandle + GetPowerUsage
        loaded = Init && Shutdown && DeviceGetCount && DeviceGetHandleByIndex && DeviceGetPowerUsage;
        if (!loaded) {
            std::cerr << "NVML library found but missing required functions" << std::endl;
            unload();
        }
        return loaded;
    }

    void unload() {
        if (lib_handle) {
#ifdef _WIN32
            FreeLibrary(static_cast<HMODULE>(lib_handle));
#else
            dlclose(lib_handle);
#endif
            lib_handle = nullptr;
        }
        loaded = false;
    }

    const char* error_string(nvmlReturn_t r) const {
        if (ErrorString) return ErrorString(r);
        switch (r) {
            case NVML_SUCCESS: return "Success";
            case NVML_ERROR_DRIVER_NOT_LOADED: return "Driver not loaded";
            case NVML_ERROR_LIBRARY_NOT_FOUND: return "NVML library not found";
            case NVML_ERROR_NO_PERMISSION: return "Insufficient permissions";
            case NVML_ERROR_NOT_SUPPORTED: return "Not supported";
            default: return "Unknown NVML error";
        }
    }

private:
    template<typename T>
    T resolve(const char* name) {
#ifdef _WIN32
        return reinterpret_cast<T>(GetProcAddress(static_cast<HMODULE>(lib_handle), name));
#else
        return reinterpret_cast<T>(dlsym(lib_handle, name));
#endif
    }
};

// Global NVML API instance -- shared across all NVIDIAGPUProvider instances
static NvmlAPI& nvml() {
    static NvmlAPI api;
    return api;
}

namespace codegreen::nemb::drivers {

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("nvidia_gpu", []() {
            return std::make_unique<NVIDIAGPUProvider>();
        });
        return true;
    }();
}

void GPUEnergyIntegrator::add_power_sample(double power_watts, uint64_t timestamp_ns) {
    std::lock_guard<std::mutex> lock(integration_mutex_);
    if (!power_samples_.empty() && last_integration_time_ > 0) {
        double time_diff_seconds = (timestamp_ns - last_integration_time_) / 1e9;
        double avg_power = (power_samples_.back().power_watts + power_watts) / 2.0;
        accumulated_energy_joules_ += avg_power * time_diff_seconds;
    }
    power_samples_.push_back({power_watts, timestamp_ns});
    last_integration_time_ = timestamp_ns;
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
    if (power_samples_.empty()) return 0.0;
    double total = 0.0;
    for (const auto& s : power_samples_) total += s.power_watts;
    return total / power_samples_.size();
}

NVIDIAGPUProvider::NVIDIAGPUProvider() = default;

NVIDIAGPUProvider::~NVIDIAGPUProvider() {
    shutdown();
}

bool NVIDIAGPUProvider::initialize() {
    if (initialized_) return true;
    if (!initialize_nvml()) return false;
    if (!detect_gpus()) {
        shutdown_nvml();
        return false;
    }
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        if (!initialize_gpu_monitoring(i)) {
            std::cerr << "Warning: Failed to initialize monitoring for GPU " << i << std::endl;
        }
    }
    initialized_ = true;
    return true;
}

EnergyReading NVIDIAGPUProvider::get_reading() {
    if (!initialized_) return EnergyReading{};
    std::lock_guard<std::mutex> lock(reading_mutex_);

    auto now = std::chrono::steady_clock::now();
    double total_energy = 0.0, total_power = 0.0;
    uint32_t active_gpus = 0;
    std::map<std::string, double> domain_energy, domain_power;

    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gs = gpu_states_[i];
        if (!gs.available || !gs.monitoring_enabled) continue;

        double gpu_power = get_gpu_power(i);
        if (gpu_power > 0) {
            uint64_t ts = std::chrono::duration_cast<std::chrono::nanoseconds>(
                now.time_since_epoch()).count();
            gs.energy_integrator->add_power_sample(gpu_power, ts);
            double gpu_energy = gs.energy_integrator->get_accumulated_energy();
            total_energy += gpu_energy;
            total_power += gpu_power;
            active_gpus++;
            std::string dom = "gpu" + std::to_string(i);
            domain_energy[dom] = gpu_energy;
            domain_power[dom] = gpu_power;
            gs.consecutive_failures = 0;
        } else {
            gs.consecutive_failures++;
            if (gs.consecutive_failures > max_consecutive_failures_) {
                gs.available = false;
                std::cerr << "GPU " << i << " marked unavailable after " << max_consecutive_failures_ << " failures" << std::endl;
            }
        }
        gs.last_reading_time = now;
    }

    EnergyReading reading;
    reading.energy_joules = total_energy;
    reading.average_power_watts = total_power;
    reading.domain_energy_joules = std::move(domain_energy);
    reading.domain_power_watts = std::move(domain_power);
    reading.timestamp_ns = nemb::utils::PrecisionTimer::monotonic_timestamp_ns();
    reading.provider_id = "nvidia_gpu";
    reading.confidence = (active_gpus > 0) ? 0.98 : 0.0;
    reading.uncertainty_percent = (active_gpus > 0) ? 2.0 : 100.0;
    return reading;
}

EnergyProviderSpec NVIDIAGPUProvider::get_specification() const {
    EnergyProviderSpec spec;
    spec.provider_name = "NVIDIA GPU";
    spec.hardware_type = "gpu";
    spec.vendor = "nvidia";
    spec.measurement_domains.push_back("gpu_total");
    for (uint32_t i = 0; i < gpu_count_; ++i)
        spec.measurement_domains.push_back("gpu" + std::to_string(i));
    spec.energy_resolution_joules = 1e-3;
    spec.power_resolution_watts = 1e-3;
    spec.update_interval = std::chrono::microseconds(100000);
    spec.counter_bits = 32;
    return spec;
}

bool NVIDIAGPUProvider::self_test() {
    if (!initialized_) return false;
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        double power = get_gpu_power(i);
        if (power < 0) {
            std::cerr << "Self-test failed for GPU " << i << ": Cannot read power" << std::endl;
            return false;
        }
        if (power < 0.1 || power > 1000.0)
            std::cerr << "Self-test warning GPU " << i << ": unusual power " << power << "W" << std::endl;
    }
    return true;
}

bool NVIDIAGPUProvider::is_available() const {
    return initialized_ && gpu_count_ > 0;
}

void NVIDIAGPUProvider::shutdown() {
    if (initialized_) {
        for (auto& gs : gpu_states_)
            if (gs.energy_integrator) gs.energy_integrator->reset_accumulation();
        shutdown_nvml();
        initialized_ = false;
    }
}

bool NVIDIAGPUProvider::initialize_nvml() {
    auto& api = nvml();
    if (!api.load()) {
        std::cerr << "NVML: library not found (no NVIDIA GPU driver installed?)" << std::endl;
        return false;
    }
    nvmlReturn_t result = api.Init();
    if (result != NVML_SUCCESS) {
        std::cerr << "NVML init failed: " << api.error_string(result) << std::endl;
        return false;
    }
    nvml_initialized_ = true;
    return true;
}

void NVIDIAGPUProvider::shutdown_nvml() {
    if (nvml_initialized_) {
        auto& api = nvml();
        if (api.Shutdown) api.Shutdown();
        nvml_initialized_ = false;
    }
}

bool NVIDIAGPUProvider::detect_gpus() {
    auto& api = nvml();
    nvmlReturn_t result = api.DeviceGetCount(&gpu_count_);
    if (result != NVML_SUCCESS) {
        std::cerr << "Failed to get GPU count: " << api.error_string(result) << std::endl;
        return false;
    }
    if (gpu_count_ == 0) {
        std::cerr << "No NVIDIA GPUs detected" << std::endl;
        return false;
    }

    gpu_states_.resize(gpu_count_);
    gpu_info_.resize(gpu_count_);

    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gs = gpu_states_[i];
        auto& gi = gpu_info_[i];

        result = api.DeviceGetHandleByIndex(i, &gs.device_handle);
        if (result != NVML_SUCCESS) {
            std::cerr << "Failed to get handle for GPU " << i << ": " << api.error_string(result) << std::endl;
            continue;
        }

        if (api.DeviceGetName) {
            char name[NVML_DEVICE_NAME_BUFFER_SIZE];
            if (api.DeviceGetName(gs.device_handle, name, sizeof(name)) == NVML_SUCCESS)
                gi.name = name;
        }
        if (api.DeviceGetUUID) {
            char uuid[NVML_DEVICE_UUID_BUFFER_SIZE];
            if (api.DeviceGetUUID(gs.device_handle, uuid, sizeof(uuid)) == NVML_SUCCESS)
                gi.uuid = uuid;
        }
        if (api.DeviceGetMemoryInfo) {
            nvmlMemory_t mem;
            if (api.DeviceGetMemoryInfo(gs.device_handle, &mem) == NVML_SUCCESS)
                gi.memory_total_mb = static_cast<uint32_t>(mem.total / (1024 * 1024));
        }
        if (api.DeviceGetPowerManagementLimitConstraints) {
            api.DeviceGetPowerManagementLimitConstraints(gs.device_handle,
                &gi.min_power_limit_watts, &gi.max_power_limit_watts);
        }

        unsigned int power_mw;
        result = api.DeviceGetPowerUsage(gs.device_handle, &power_mw);
        gi.supports_power_monitoring = (result == NVML_SUCCESS);
        if (gi.supports_power_monitoring)
            gi.power_limit_watts = power_mw / 1000;

        gi.device_index = i;
        gi.supports_energy_monitoring = false;
        gs.info = gi;
        gs.available = true;
        gs.energy_integrator = std::make_unique<GPUEnergyIntegrator>();
    }
    return true;
}

bool NVIDIAGPUProvider::initialize_gpu_monitoring(uint32_t gpu_index) {
    if (gpu_index >= gpu_count_) return false;
    auto& gs = gpu_states_[gpu_index];
    double power = get_gpu_power(gpu_index);
    if (power < 0) {
        std::cerr << "Cannot init monitoring for GPU " << gpu_index << ": power read failed" << std::endl;
        gs.available = false;
        return false;
    }
    gs.monitoring_enabled = true;
    return true;
}

double NVIDIAGPUProvider::get_gpu_power(uint32_t gpu_index) {
    if (gpu_index >= gpu_count_) return -1.0;
    auto& gs = gpu_states_[gpu_index];
    if (!gs.available) return -1.0;
    unsigned int power_mw;
    nvmlReturn_t result = nvml().DeviceGetPowerUsage(gs.device_handle, &power_mw);
    if (result != NVML_SUCCESS) {
        handle_nvml_error("get_gpu_power", result);
        return -1.0;
    }
    return static_cast<double>(power_mw) / 1000.0;
}

void NVIDIAGPUProvider::handle_nvml_error(const std::string& operation, int nvml_result) {
    std::cerr << "NVML error in " << operation << ": "
              << nvml().error_string(static_cast<nvmlReturn_t>(nvml_result)) << std::endl;
}

std::unique_ptr<NVIDIAGPUProvider> create_nvidia_gpu_provider() {
    return std::make_unique<NVIDIAGPUProvider>();
}

bool is_nvidia_gpu_available() {
    auto& api = nvml();
    if (!api.load()) return false;
    nvmlReturn_t result = api.Init();
    if (result != NVML_SUCCESS) return false;
    uint32_t count;
    result = api.DeviceGetCount(&count);
    api.Shutdown();
    return (result == NVML_SUCCESS && count > 0);
}

std::map<std::string, std::string> get_nvidia_version_info() {
    std::map<std::string, std::string> info;
    auto& api = nvml();
    if (!api.load()) {
        info["error"] = "NVML library not found";
        return info;
    }
    nvmlReturn_t result = api.Init();
    if (result != NVML_SUCCESS) {
        info["error"] = std::string("NVML init failed: ") + api.error_string(result);
        return info;
    }
    if (api.SystemGetDriverVersion) {
        char ver[NVML_SYSTEM_DRIVER_VERSION_BUFFER_SIZE];
        if (api.SystemGetDriverVersion(ver, sizeof(ver)) == NVML_SUCCESS)
            info["driver_version"] = ver;
    }
    if (api.SystemGetNVMLVersion) {
        char ver[NVML_SYSTEM_NVML_VERSION_BUFFER_SIZE];
        if (api.SystemGetNVMLVersion(ver, sizeof(ver)) == NVML_SUCCESS)
            info["nvml_version"] = ver;
    }
    api.Shutdown();
    return info;
}

std::map<uint32_t, double> NVIDIAGPUProvider::get_per_gpu_energy_breakdown() {
    std::map<uint32_t, double> breakdown;
    for (uint32_t i = 0; i < gpu_count_; ++i) {
        auto& gs = gpu_states_[i];
        if (gs.available && gs.monitoring_enabled && gs.energy_integrator)
            breakdown[i] = gs.energy_integrator->get_accumulated_energy();
    }
    return breakdown;
}

GPUPowerState NVIDIAGPUProvider::get_gpu_power_state(uint32_t gpu_index) {
    GPUPowerState state{};
    if (gpu_index >= gpu_count_) return state;
    auto& gs = gpu_states_[gpu_index];
    if (!gs.available) return state;
    auto& api = nvml();
    if (api.DeviceGetPowerManagementLimitConstraints) {
        unsigned int max_mw;
        if (api.DeviceGetPowerManagementLimitConstraints(gs.device_handle, nullptr, &max_mw) == NVML_SUCCESS)
            state.power_limit_watts = max_mw / 1000;
    }
    if (api.DeviceGetClockInfo) {
        unsigned int clk;
        if (api.DeviceGetClockInfo(gs.device_handle, NVML_CLOCK_GRAPHICS, &clk) == NVML_SUCCESS)
            state.graphics_clock_mhz = clk;
        if (api.DeviceGetClockInfo(gs.device_handle, NVML_CLOCK_MEM, &clk) == NVML_SUCCESS)
            state.memory_clock_mhz = clk;
    }
    if (api.DeviceGetTemperature) {
        unsigned int temp;
        if (api.DeviceGetTemperature(gs.device_handle, NVML_TEMPERATURE_GPU, &temp) == NVML_SUCCESS)
            state.temperature_celsius = static_cast<double>(temp);
    }
    return state;
}

bool NVIDIAGPUProvider::set_gpu_monitoring_enabled(uint32_t gpu_index, bool enabled) {
    if (gpu_index >= gpu_count_) return false;
    gpu_states_[gpu_index].monitoring_enabled = enabled;
    return true;
}

std::map<std::string, uint32_t> NVIDIAGPUProvider::get_gpu_utilization(uint32_t gpu_index) {
    std::map<std::string, uint32_t> util;
    if (gpu_index >= gpu_count_) return util;
    auto& gs = gpu_states_[gpu_index];
    if (!gs.available || !nvml().DeviceGetUtilizationRates) return util;
    nvmlUtilization_t u;
    if (nvml().DeviceGetUtilizationRates(gs.device_handle, &u) == NVML_SUCCESS) {
        util["gpu"] = u.gpu;
        util["memory"] = u.memory;
    }
    return util;
}

bool NVIDIAGPUProvider::set_power_limit(uint32_t, uint32_t) {
    return false;
}

GPUWorkloadType NVIDIAGPUProvider::detect_workload_type(uint32_t gpu_index) {
    auto util = get_gpu_utilization(gpu_index);
    if (util.empty()) return GPUWorkloadType::UNKNOWN;
    uint32_t gu = util.count("gpu") ? util["gpu"] : 0;
    uint32_t mu = util.count("memory") ? util["memory"] : 0;
    if (gu < 5 && mu < 5) return GPUWorkloadType::IDLE;
    if (mu > 80 && gu < 50) return GPUWorkloadType::MEMORY_BOUND;
    if (gu > 80) return GPUWorkloadType::COMPUTE;
    return GPUWorkloadType::MIXED;
}

} // namespace codegreen::nemb::drivers
