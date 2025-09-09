#pragma once

#include "../core/energy_provider.hpp"
#include <vector>
#include <memory>
#include <mutex>

// Forward declarations for ROCm SMI
typedef void* rsmi_device_t;

namespace codegreen::nemb::drivers {

/**
 * @brief AMD GPU information and capabilities
 */
struct AMDGPUInfo {
    uint32_t device_index;              ///< GPU device index
    std::string name;                   ///< GPU model name
    std::string device_id;              ///< Device ID
    std::string vendor_id;              ///< Vendor ID
    std::string subsystem_id;           ///< Subsystem ID
    uint64_t memory_total_bytes;        ///< Total VRAM in bytes
    std::string vbios_version;          ///< VBIOS version
    
    // Architecture information
    std::string architecture;           ///< Architecture (RDNA, RDNA2, CDNA, etc.)
    uint32_t compute_units;             ///< Number of compute units
    uint32_t max_shader_engines;        ///< Maximum shader engines
    uint32_t simd_count;                ///< SIMD count per compute unit
    
    // Power management capabilities
    bool supports_power_monitoring;     ///< Power monitoring available
    bool supports_energy_monitoring;    ///< Energy monitoring available
    bool supports_overdrive;            ///< Overdrive/overclocking support
    uint32_t power_cap_watts;           ///< Power cap in watts
    uint32_t power_cap_min_watts;       ///< Minimum power cap
    uint32_t power_cap_max_watts;       ///< Maximum power cap
    
    // Performance monitoring capabilities
    bool supports_utilization_monitoring; ///< GPU utilization monitoring
    bool supports_memory_monitoring;    ///< Memory utilization monitoring
    bool supports_temperature_monitoring; ///< Temperature monitoring
    bool supports_clock_monitoring;     ///< Clock frequency monitoring
    bool supports_fan_monitoring;       ///< Fan speed monitoring
};

/**
 * @brief AMD GPU power state information
 */
struct AMDGPUPowerState {
    uint32_t performance_level;         ///< Performance level (0-7 typically)
    uint32_t sclk_frequency_mhz;        ///< System/shader clock frequency
    uint32_t mclk_frequency_mhz;        ///< Memory clock frequency
    uint32_t pcie_frequency_mhz;        ///< PCIe clock frequency
    double temperature_celsius;         ///< GPU temperature
    double temperature_hotspot_celsius; ///< Hotspot temperature
    double temperature_mem_celsius;     ///< Memory temperature
    uint32_t fan_speed_rpm;             ///< Fan speed in RPM
    uint32_t fan_speed_percent;         ///< Fan speed percentage
    uint32_t power_cap_watts;           ///< Current power cap
    bool power_cap_enabled;             ///< Is power capping active
    bool thermal_throttling;            ///< Is thermal throttling active
};

/**
 * @brief GPU utilization information
 */
struct AMDGPUUtilization {
    uint32_t gpu_busy_percent;          ///< GPU busy percentage
    uint32_t memory_busy_percent;       ///< Memory controller busy percentage
    uint64_t memory_used_bytes;         ///< Used VRAM in bytes
    uint64_t memory_total_bytes;        ///< Total VRAM in bytes
    uint32_t pcie_bandwidth_counter;    ///< PCIe bandwidth counter
    uint64_t gfx_activity_counter;      ///< Graphics activity counter
    uint64_t mem_activity_counter;      ///< Memory activity counter
};

/**
 * @brief Energy integration for AMD GPUs using power sampling
 */
class AMDGPUEnergyIntegrator {
public:
    /**
     * @brief Add power sample for energy integration
     * @param power_watts Current power consumption
     * @param timestamp_ns Timestamp in nanoseconds
     */
    void add_power_sample(double power_watts, uint64_t timestamp_ns);
    
    /**
     * @brief Get accumulated energy since last reset
     * @return Energy in joules
     */
    double get_accumulated_energy() const;
    
    /**
     * @brief Reset energy accumulation
     */
    void reset_accumulation();
    
    /**
     * @brief Get average power over integration period
     * @return Average power in watts
     */
    double get_average_power() const;

private:
    struct PowerSample {
        double power_watts;
        uint64_t timestamp_ns;
    };
    
    std::vector<PowerSample> power_samples_;
    double accumulated_energy_joules_{0.0};
    uint64_t last_integration_time_{0};
    mutable std::mutex integration_mutex_;
};

/**
 * @brief AMD GPU energy provider implementation using ROCm SMI
 * 
 * Provides energy monitoring for AMD GPUs using the ROCm System Management Interface.
 * Supports RDNA, RDNA2, and CDNA architectures.
 * 
 * Features:
 * - Real-time power monitoring
 * - Energy calculation through power integration
 * - Multi-GPU support with individual GPU breakdown
 * - Advanced power state monitoring
 * - Temperature and throttling detection
 * - Memory and clock monitoring
 * - Fan speed control and monitoring
 */
class AMDGPUProvider : public EnergyProvider {
public:
    AMDGPUProvider();
    ~AMDGPUProvider() override;
    
    // EnergyProvider interface implementation
    bool initialize() override;
    EnergyReading get_reading() override;
    EnergyProviderSpec get_specification() const override;
    bool self_test() override;
    bool is_available() const override;
    void shutdown() override;
    std::string get_name() const override { return "AMD GPU"; }
    
    // AMD GPU specific methods
    
    /**
     * @brief Get information for all available AMD GPUs
     * @return Vector of AMD GPU information structures
     */
    std::vector<AMDGPUInfo> get_gpu_info() const { return gpu_info_; }
    
    /**
     * @brief Get number of detected AMD GPUs
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
    AMDGPUPowerState get_gpu_power_state(uint32_t gpu_index);
    
    /**
     * @brief Get GPU utilization information
     * @param gpu_index GPU device index
     * @return Utilization information
     */
    AMDGPUUtilization get_gpu_utilization(uint32_t gpu_index);
    
    /**
     * @brief Enable/disable specific GPU for monitoring
     * @param gpu_index GPU to control
     * @param enabled Whether to monitor this GPU
     * @return true if successful
     */
    bool set_gpu_monitoring_enabled(uint32_t gpu_index, bool enabled);
    
    /**
     * @brief Set power cap for GPU (if supported)
     * @param gpu_index GPU device index
     * @param power_cap_watts New power cap in watts
     * @return true if successful
     */
    bool set_power_cap(uint32_t gpu_index, uint32_t power_cap_watts);
    
    /**
     * @brief Set fan speed (if supported)
     * @param gpu_index GPU device index
     * @param fan_speed_percent Fan speed percentage (0-100)
     * @return true if successful
     */
    bool set_fan_speed(uint32_t gpu_index, uint32_t fan_speed_percent);

private:
    // GPU management
    struct AMDGPUState {
        rsmi_device_t device_handle;
        AMDGPUInfo info;
        std::unique_ptr<AMDGPUEnergyIntegrator> energy_integrator;
        bool monitoring_enabled{true};
        bool available{false};
        uint32_t consecutive_failures{0};
        AMDGPUPowerState last_power_state;
        std::chrono::steady_clock::time_point last_reading_time;
    };
    
    std::vector<AMDGPUState> gpu_states_;
    uint32_t gpu_count_{0};
    std::vector<AMDGPUInfo> gpu_info_;
    
    // ROCm SMI management
    bool rsmi_initialized_{false};
    bool initialize_rsmi();
    void shutdown_rsmi();
    bool detect_amd_gpus();
    bool detect_amd_gpus_fallback();
    bool initialize_gpu_monitoring(uint32_t gpu_index);
    
    // Power monitoring
    double get_gpu_power(uint32_t gpu_index);
    bool get_gpu_power_detailed(uint32_t gpu_index, double& socket_power, double& soc_power);
    
    // Temperature monitoring
    double get_gpu_temperature(uint32_t gpu_index, const std::string& sensor_type = "edge");
    
    // Clock monitoring  
    void get_gpu_clock_info(uint32_t gpu_index, uint32_t& sclk_mhz, uint32_t& mclk_mhz);
    
    // Memory monitoring
    void get_gpu_memory_info(uint32_t gpu_index, uint64_t& used_bytes, uint64_t& total_bytes);
    
    // Fan monitoring
    uint32_t get_gpu_fan_speed_rpm(uint32_t gpu_index);
    uint32_t get_gpu_fan_speed_percent(uint32_t gpu_index);
    
    // Multi-GPU aggregation
    EnergyReading aggregate_multi_gpu_readings();
    
    // Error handling
    void handle_rsmi_error(const std::string& operation, int rsmi_result);
    bool is_recoverable_error(int rsmi_result);
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
    uint32_t max_consecutive_failures_{5};
    bool enable_advanced_metrics_{true};
};

/**
 * @brief Factory function for creating AMD GPU provider
 * @return Unique pointer to AMD GPU provider, or nullptr if not supported
 */
std::unique_ptr<AMDGPUProvider> create_amd_gpu_provider();

/**
 * @brief Check if AMD GPUs are available on current system
 * @return true if AMD GPU with ROCm SMI support is detected
 */
bool is_amd_gpu_available();

/**
 * @brief Get AMD driver and ROCm SMI version information
 * @return Map with version information
 */
std::map<std::string, std::string> get_amd_version_info();

} // namespace codegreen::nemb::drivers