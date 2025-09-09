#pragma once

#include "../core/energy_provider.hpp"
#include "../utils/non_blocking_file_reader.hpp"
#include <map>
#include <mutex>
#include <fstream>
#include <vector>
#include <chrono>
#include <memory>

namespace codegreen::nemb::drivers {

/**
 * @brief Intel RAPL domain information
 */
struct RAPLDomain {
    std::string name;                    ///< Domain name (package, core, uncore, dram)
    std::string sysfs_path;             ///< Path to energy_uj file
    uint32_t msr_address;               ///< MSR address for direct access
    uint64_t energy_unit_microjoules;   ///< Energy unit in microjoules
    uint64_t last_raw_value;            ///< Last raw counter value
    uint64_t accumulated_energy;        ///< Accumulated energy (handles wraparound)
    bool available;                     ///< Domain is available on this system
};

/**
 * @brief Intel CPU identification and capabilities
 */
struct IntelCPUInfo {
    uint32_t family;                    ///< CPU family
    uint32_t model;                     ///< CPU model
    uint32_t stepping;                  ///< CPU stepping
    std::string microarchitecture;      ///< Microarchitecture name
    bool supports_package_rapl;         ///< Package domain available
    bool supports_core_rapl;            ///< Core domain available
    bool supports_uncore_rapl;          ///< Uncore domain available
    bool supports_dram_rapl;            ///< DRAM domain available
    bool supports_psys_rapl;            ///< Platform domain available (Skylake+)
    uint32_t package_count;             ///< Number of physical packages
    std::vector<uint32_t> active_packages; ///< List of active package IDs
};

/**
 * @brief High-precision counter manager with wraparound handling
 */
class RAPLCounterManager {
public:
    /**
     * @brief Update counter with wraparound detection
     * @param domain_name Domain identifier
     * @param raw_value Current raw counter value
     * @param counter_bits Counter width in bits
     * @return Accumulated energy value
     */
    uint64_t update_counter(const std::string& domain_name, 
                           uint64_t raw_value, 
                           uint32_t counter_bits = 32);
    
    /**
     * @brief Reset counter accumulation
     * @param domain_name Domain to reset
     */
    void reset_counter(const std::string& domain_name);
    
    /**
     * @brief Get all accumulated counter values
     * @return Map of domain names to accumulated energy values
     */
    std::map<std::string, uint64_t> get_all_counters() const;
    
    /**
     * @brief Get wraparound statistics
     * @param domain_name Domain name
     * @return Number of wraparounds detected
     */
    uint32_t get_wraparound_count(const std::string& domain_name) const;

private:
    struct CounterState {
        uint64_t last_raw_value{0};
        uint64_t accumulated_value{0};
        uint32_t wraparound_count{0};
        uint64_t counter_mask{0};
        std::chrono::steady_clock::time_point last_update;
    };
    
    std::map<std::string, CounterState> counter_states_;
    mutable std::mutex counter_mutex_;
};

/**
 * @brief Intel RAPL energy provider implementation
 * 
 * Provides energy measurements using Intel RAPL (Running Average Power Limit)
 * interface through either MSR access or sysfs powercap interface.
 * 
 * Features:
 * - Automatic CPU detection and capability discovery
 * - Multiple RAPL domain support (package, core, uncore, DRAM)
 * - Robust counter wraparound handling
 * - Temperature and frequency compensation
 * - Multi-package system support
 */
class IntelRAPLProvider : public EnergyProvider {
public:
    IntelRAPLProvider();
    ~IntelRAPLProvider() override;
    
    // EnergyProvider interface implementation
    bool initialize() override;
    EnergyReading get_reading() override;
    EnergyProviderSpec get_specification() const override;
    bool self_test() override;
    bool is_available() const override;
    void shutdown() override;
    std::string get_name() const override { return "Intel RAPL"; }
    
    // Intel RAPL specific methods
    
    /**
     * @brief Get available RAPL domains
     * @return Map of domain name to domain information
     */
    std::map<std::string, RAPLDomain> get_available_domains() const;
    
    /**
     * @brief Get Intel CPU information
     * @return CPU capabilities and identification
     */
    IntelCPUInfo get_cpu_info() const { return cpu_info_; }
    
    /**
     * @brief Enable/disable specific RAPL domain
     * @param domain_name Domain to control
     * @param enabled Whether to enable the domain
     * @return true if successful
     */
    bool set_domain_enabled(const std::string& domain_name, bool enabled);
    
    /**
     * @brief Get per-domain energy breakdown
     * @return Map of domain name to energy consumption in joules
     */
    std::map<std::string, double> get_domain_energy_breakdown();
    
private:
    // Hardware detection and initialization
    bool detect_intel_cpu();
    bool detect_rapl_domains();
    bool initialize_msr_access();
    bool initialize_sysfs_access();
    bool validate_rapl_functionality();
    
    // Energy reading methods
    uint64_t read_domain_energy_msr(const std::string& domain_name);
    uint64_t read_domain_energy_sysfs(const std::string& domain_name);
    double raw_energy_to_joules(uint64_t raw_energy, const std::string& domain_name);
    
    // MSR access
    uint64_t read_msr(uint32_t msr_address);
    bool open_msr_device();
    void close_msr_device();
    
    // Temperature and frequency compensation
    double get_package_temperature();
    uint32_t get_package_frequency();
    double apply_thermal_compensation(double raw_power, double temperature);
    double apply_frequency_compensation(double raw_power, uint32_t frequency);
    
    // Validation and diagnostics
    bool validate_energy_monotonicity(const std::map<std::string, double>& current_readings,
                                     const std::map<std::string, double>& previous_readings);
    void log_domain_status() const;
    
    // Member variables
    IntelCPUInfo cpu_info_;
    std::map<std::string, RAPLDomain> rapl_domains_;
    std::unique_ptr<RAPLCounterManager> counter_manager_;
    bool initialized_{false};
    
    // Hardware capability detection results
    std::vector<std::string> available_domains_;
    double energy_unit_joules_{0.0};
    std::map<std::string, std::string> domain_paths_;
    
    // Hardware detection methods
    bool query_energy_units();
    bool query_energy_unit_from_hardware();
    bool initialize_counters();
    bool initialize_file_readers();
    bool take_initial_readings();
    
    // Access method (MSR vs sysfs)
    enum class AccessMethod {
        NONE,
        MSR_DIRECT,    ///< Direct MSR access (/dev/cpu/*/msr)
        SYSFS_POWERCAP ///< sysfs powercap interface
    };
    AccessMethod access_method_{AccessMethod::NONE};
    
    // MSR access
    int msr_fd_{-1};
    std::map<std::string, uint32_t> domain_msr_map_;
    
    // Non-blocking file readers for sysfs access
    std::map<std::string, std::unique_ptr<utils::NonBlockingFileReader>> domain_file_readers_;
    
    // sysfs access
    std::map<std::string, std::string> domain_sysfs_map_;
    
    // State management  
    mutable std::mutex reading_mutex_;
    std::map<std::string, double> last_domain_energies_;
    std::chrono::steady_clock::time_point last_reading_time_;
    EnergyReading last_reading_;
    
    // Thermal and frequency tracking
    double last_temperature_{0.0};
    uint32_t last_frequency_{0};
    
    // MSR addresses (Intel SDM Volume 4)
    static constexpr uint32_t MSR_RAPL_POWER_UNIT = 0x606;
    static constexpr uint32_t MSR_PKG_ENERGY_STATUS = 0x611;
    static constexpr uint32_t MSR_PP0_ENERGY_STATUS = 0x639;  // Core
    static constexpr uint32_t MSR_PP1_ENERGY_STATUS = 0x641;  // Uncore/GPU
    static constexpr uint32_t MSR_DRAM_ENERGY_STATUS = 0x619; // DRAM
    static constexpr uint32_t MSR_PSYS_ENERGY_STATUS = 0x64D; // Platform (Skylake+)
    
    // Thermal MSRs
    static constexpr uint32_t MSR_IA32_PACKAGE_THERM_STATUS = 0x1B1;
    static constexpr uint32_t MSR_IA32_THERM_STATUS = 0x19C;
    
    // Performance MSRs
    static constexpr uint32_t MSR_IA32_PERF_STATUS = 0x198;
    static constexpr uint32_t MSR_TURBO_RATIO_LIMIT = 0x1AD;
};

/**
 * @brief Factory function for creating Intel RAPL provider
 * @return Unique pointer to Intel RAPL provider, or nullptr if not supported
 */
std::unique_ptr<IntelRAPLProvider> create_intel_rapl_provider();

/**
 * @brief Check if Intel RAPL is available on current system
 * @return true if Intel CPU with RAPL support is detected
 */
bool is_intel_rapl_available();

} // namespace codegreen::nemb::drivers