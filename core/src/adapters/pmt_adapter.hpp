#pragma once

#include "plugin/hardware_plugin.hpp"
#include <memory>
#include <vector>
#include <string>

// Forward declarations to avoid tight coupling
namespace pmt {
    class PMT;
    class State;
}

namespace codegreen {

/// Lightweight adapter for PMT that implements HardwarePlugin interface
/// Designed for minimal overhead and easy replacement
class PMTAdapter : public HardwarePlugin {
public:
    /// Create PMT adapter with specified sensor types
    /// sensor_types: e.g., {"dummy", "rapl", "nvml"}
    explicit PMTAdapter(const std::vector<std::string>& sensor_types = {"dummy"});
    
    ~PMTAdapter() override;

    // HardwarePlugin interface
    std::string name() const override;
    std::unique_ptr<Measurement> get_measurement() const override;
    bool init() override;
    void cleanup() override;
    bool is_available() const override;

private:
    std::vector<std::unique_ptr<pmt::PMT>> sensors_;
    std::vector<std::string> sensor_names_;
    bool initialized_;
    
    // Helper to convert PMT State to CodeGreen Measurement
    std::unique_ptr<Measurement> convert_pmt_state(const pmt::State& state, const std::string& sensor_name) const;
};

/// Factory function to create PMT adapter with auto-detection
std::unique_ptr<PMTAdapter> CreatePMTAdapter();

// Helper functions for sensor validation
bool validate_sensor_runtime(const std::string& sensor_type, std::unique_ptr<pmt::PMT>& sensor);
void print_sensor_installation_help(const std::string& sensor);

// Hardware-specific validation functions
bool validate_rapl_sensor(std::unique_ptr<pmt::PMT>& sensor);
bool validate_nvml_sensor(std::unique_ptr<pmt::PMT>& sensor);
bool validate_amdsmi_sensor(std::unique_ptr<pmt::PMT>& sensor);
bool validate_powersensor(const std::string& sensor_type, std::unique_ptr<pmt::PMT>& sensor);
bool validate_likwid_sensor(std::unique_ptr<pmt::PMT>& sensor);
bool validate_rocm_sensor(std::unique_ptr<pmt::PMT>& sensor);

} // namespace codegreen
