#pragma once

#include "../core/energy_provider.hpp"
#include <vector>
#include <memory>
#include <mutex>

// Forward declarations to avoid including NVML headers in header
struct nvmlDevice_st;
typedef struct nvmlDevice_st* nvmlDevice_t;

namespace codegreen::nemb::drivers {

/**
 * @brief NVIDIA GPU information and capabilities
 */
struct NVIDIAGPUInfo {
    uint32_t device_index;              ///< GPU device index
    std::string name;                   ///< GPU model name
    std::string uuid;                   ///< GPU UUID
    std::string serial;                 ///< Serial number
    uint32_t memory_total_mb;           ///< Total VRAM in MB
    uint32_t power_limit_watts;         ///< Default power limit
    uint32_t max_power_limit_watts;     ///< Maximum power limit
    uint32_t min_power_limit_watts;     ///< Minimum power limit
    
    // Architecture information
    uint32_t cuda_compute_capability_major; ///< CUDA compute capability major
    uint32_t cuda_compute_capability_minor; ///< CUDA compute capability minor
    std::string architecture;           ///< Architecture name (Pascal, Turing, Ampere, etc.)
    uint32_t sm_count;                  ///< Streaming multiprocessor count
    uint32_t memory_bus_width;          ///< Memory bus width in bits
    
    // Power management capabilities
    bool supports_power_monitoring;     ///< Power monitoring available
    bool supports_energy_monitoring;    ///< Energy monitoring available (newer cards)
    bool supports_per_gpu_accounting;   ///< Per-process accounting available
    bool supports_nvlink;               ///< NVLink support
    uint32_t nvlink_link_count;         ///< Number of NVLink connections
    
    // Performance monitoring capabilities
    bool supports_utilization_monitoring; ///< GPU utilization monitoring
    bool supports_memory_monitoring;    ///< Memory utilization monitoring
    bool supports_temperature_monitoring; ///< Temperature monitoring
    bool supports_clock_monitoring;     ///< Clock frequency monitoring
};

/**
 * @brief GPU workload classification for power modeling
 */
enum class GPUWorkloadType {
    UNKNOWN,        ///< Workload type not determined
    COMPUTE,        ///< CUDA compute workload
    GRAPHICS,       ///< 3D graphics rendering
    RAY_TRACING,    ///< Ray tracing workload (RTX cards)
    TENSOR,         ///< AI/ML tensor operations
    MEMORY_BOUND,   ///< Memory bandwidth limited
    MIXED,          ///< Mixed workload types
    IDLE            ///< GPU idle
};

/**
 * @brief Advanced GPU power management state
 */
struct GPUPowerState {
    uint32_t performance_state;         ///< P-state (P0-P12)
    uint32_t graphics_clock_mhz;        ///< Current graphics clock
    uint32_t memory_clock_mhz;          ///< Current memory clock  
    uint32_t shader_clock_mhz;          ///< Shader clock (older architectures)
    double temperature_celsius;         ///< GPU temperature
    uint32_t fan_speed_percent;         ///< Fan speed percentage
    uint32_t power_limit_watts;         ///< Current power limit
    bool thermal_throttling;            ///< Is thermal throttling active
    bool power_throttling;              ///< Is power throttling active
    GPUWorkloadType workload_type;      ///< Detected workload type
};

/**
 * @brief Cumulative joules of an NVML total-energy counter (mJ). The counter advances once per update period and a
 * read discards what it accumulated since its last update, so session boundaries read it at most once per period:
 * due() is false within one period of the previous read and the caller answers with joules() (a held value).
 * Deltas accumulate, so a driver counter reset counts from zero. period_ns 0 = no counter; the first read is due.
 * Each read also records the provider's power integral at that time: check() compares both from the first read on.
 */
class GPUEnergyCounter {
public:
    GPUEnergyCounter(uint64_t period_ns = 0, unsigned long long total_mj = 0) : period_ns_(period_ns), last_mj_(total_mj) {}
    bool due(uint64_t t_ns) const { return !t_ns_ || t_ns - t_ns_ >= period_ns_; }
    void add(unsigned long long total_mj, uint64_t t_ns, double integral_j) {
        j_ += (total_mj >= last_mj_ ? total_mj - last_mj_ : total_mj) / 1000.0;
        if (!t_ns_) { j0_ = j_; i0_ = integral_j; t0_ = t_ns; }
        ++reads_;
        last_mj_ = total_mj;
        t_ns_ = t_ns;
        i_ = integral_j;
    }
    CounterCheck check() const { return {j_ - j0_, i_ - i0_, t_ns_ - t0_, reads_}; }
    double joules() const { return j_; }
    uint64_t period_ns() const { return period_ns_; }
    uint64_t t_ns() const { return t_ns_; }  // time of the last counter read; 0 = none yet
private:
    uint64_t period_ns_, t_ns_{0}, t0_{0}, reads_{0};
    unsigned long long last_mj_;
    double j_{0}, j0_{0}, i_{0}, i0_{0};
};

/**
 * @brief NVIDIA GPU energy provider implementation
 * 
 * Provides comprehensive energy monitoring for NVIDIA GPUs using NVML
 * (NVIDIA Management Library). Supports single and multi-GPU systems.
 * 
 * Features:
 * - Real-time power monitoring with high precision
 * - Energy calculation through power integration (sampler); session boundaries read the
 *   cumulative energy counter (nvmlDeviceGetTotalEnergyConsumption) when every GPU has one
 * - Multi-GPU synchronization and aggregation
 * - Advanced power state monitoring
 * - Workload-aware power modeling
 * - Temperature and throttling detection
 * - NVLink power accounting (when available)
 */
class NVIDIAGPUProvider : public EnergyProvider {
public:
    NVIDIAGPUProvider();
    ~NVIDIAGPUProvider() override;
    
    // EnergyProvider interface implementation
    bool initialize() override;
    EnergyReading get_reading() override;
    EnergyReading get_boundary_reading() override;
    std::map<std::string, CounterCheck> counter_checks() const override;
    EnergyProviderSpec get_specification() const override;
    bool self_test() override;
    bool is_available() const override;
    void shutdown() override;
    std::string get_name() const override { return "NVIDIA GPU"; }
    
    // NVIDIA GPU specific methods
    
    /**
     * @brief Get information for all available GPUs
     * @return Vector of GPU information structures
     */
    std::vector<NVIDIAGPUInfo> get_gpu_info() const { return gpu_info_; }
    
    /**
     * @brief Get number of detected GPUs
     * @return GPU count
     */
    uint32_t get_gpu_count() const { return gpu_count_; }
    
    /**
     * @brief Get per-GPU energy breakdown
     * @return Map of GPU index to energy consumption in joules
     */
    std::map<uint32_t, double> get_per_gpu_energy_breakdown();
    
    /**
     * @brief Get current power state for specific GPU
     * @param gpu_index GPU device index
     * @return Power state information
     */
    GPUPowerState get_gpu_power_state(uint32_t gpu_index);
    
    /**
     * @brief Enable/disable specific GPU for monitoring
     * @param gpu_index GPU to control
     * @param enabled Whether to monitor this GPU
     * @return true if successful
     */
    bool set_gpu_monitoring_enabled(uint32_t gpu_index, bool enabled);
    
    /**
     * @brief Get GPU utilization information
     * @param gpu_index GPU device index
     * @return Map of utilization type to percentage
     */
    std::map<std::string, uint32_t> get_gpu_utilization(uint32_t gpu_index);
    
    /**
     * @brief Set power limit for GPU (if supported)
     * @param gpu_index GPU device index
     * @param power_limit_watts New power limit in watts
     * @return true if successful
     */
    bool set_power_limit(uint32_t gpu_index, uint32_t power_limit_watts);
    
    /**
     * @brief Detect workload type based on utilization patterns
     * @param gpu_index GPU device index
     * @return Detected workload type
     */
    GPUWorkloadType detect_workload_type(uint32_t gpu_index);

private:
    // GPU management
    struct GPUState {
        nvmlDevice_t device_handle;
        NVIDIAGPUInfo info;
        bool monitoring_enabled{true};
        bool available{false};
        GPUPowerState last_power_state;
        std::chrono::steady_clock::time_point last_reading_time;
        GPUEnergyCounter counter;
    };
    
    std::vector<GPUState> gpu_states_;
    uint32_t gpu_count_{0};
    std::vector<NVIDIAGPUInfo> gpu_info_;
    
    // NVML management
    bool nvml_initialized_{false};
    bool initialize_nvml();
    void shutdown_nvml();
    bool detect_gpus();
    bool initialize_gpu_monitoring(uint32_t gpu_index);
    
    // Power monitoring
    double get_gpu_power(uint32_t gpu_index);
    bool get_gpu_power_advanced(uint32_t gpu_index, double& total_power, 
                               double& gpu_power, double& memory_power);
    
    // Utilization monitoring
    bool get_gpu_utilization_advanced(uint32_t gpu_index,
                                     uint32_t& gpu_util,
                                     uint32_t& memory_util,
                                     uint32_t& encoder_util,
                                     uint32_t& decoder_util);
    
    // Temperature and throttling
    double get_gpu_temperature(uint32_t gpu_index);
    bool is_gpu_throttling(uint32_t gpu_index);
    
    // Memory monitoring
    void get_gpu_memory_info(uint32_t gpu_index, uint64_t& used_bytes, uint64_t& total_bytes);
    
    // Clock monitoring
    void get_gpu_clock_info(uint32_t gpu_index, uint32_t& graphics_clock, uint32_t& memory_clock);
    
    // Multi-GPU aggregation
    EnergyReading aggregate_multi_gpu_readings();
    
    // Workload detection
    GPUWorkloadType analyze_workload_pattern(uint32_t gpu_index,
                                            uint32_t gpu_util,
                                            uint32_t memory_util,
                                            uint32_t encoder_util,
                                            uint32_t decoder_util);
    
    // Error handling
    void handle_nvml_error(const std::string& operation, int nvml_result);
    bool is_recoverable_error(int nvml_result);
    void log_gpu_status() const;
    
    // Validation
    bool validate_power_readings(const std::vector<double>& power_readings);
    bool validate_gpu_consistency();
    
    // State management
    bool initialized_{false};
    mutable std::mutex reading_mutex_;
    EnergyReading last_aggregated_reading_;
    std::chrono::steady_clock::time_point last_reading_time_;
    
    // Configuration
    double power_measurement_timeout_ms_{100.0};
    PowerIntegrator integrator_;  // per-GPU energy; a lost GPU makes every later reading invalid
    bool counters_{false};        // every GPU has a total-energy counter: boundary reads use it
    bool enable_advanced_metrics_{true};
    bool enable_workload_detection_{true};
};

/**
 * @brief Factory function for creating NVIDIA GPU provider
 * @return Unique pointer to NVIDIA GPU provider, or nullptr if not supported
 */
std::unique_ptr<NVIDIAGPUProvider> create_nvidia_gpu_provider();

/**
 * @brief Check if NVIDIA GPUs are available on current system
 * @return true if NVIDIA GPU with NVML support is detected
 */
bool is_nvidia_gpu_available();

/**
 * @brief Get NVIDIA driver and NVML version information
 * @return Map with version information
 */
std::map<std::string, std::string> get_nvidia_version_info();

} // namespace codegreen::nemb::drivers