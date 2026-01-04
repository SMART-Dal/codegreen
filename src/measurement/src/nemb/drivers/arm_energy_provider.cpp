#include "../../../include/nemb/core/energy_provider.hpp"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <chrono>
#include <unistd.h>
#include <string>
#include <vector>

namespace codegreen::nemb::drivers {

/**
 * @brief ARM Energy Aware Scheduling (EAS) provider using SCMI/HWMON energy counters
 */
class ARMEnergyProvider : public EnergyProvider {
public:
    ARMEnergyProvider() = default;
    ~ARMEnergyProvider() override = default;

    bool initialize() override {
        // Search for SCMI energy counters in hwmon
        if (!std::filesystem::exists("/sys/class/hwmon")) return false;
        
        for (const auto& entry : std::filesystem::directory_iterator("/sys/class/hwmon")) {
            std::ifstream name_file(entry.path() / "name");
            std::string name;
            if (name_file >> name && (name == "scmi_energy" || name == "arm_energy")) {
                std::string energy_path = (entry.path() / "energy1_input").string();
                if (std::filesystem::exists(energy_path)) {
                    energy_path_ = energy_path;
                    initialized_ = true;
                    return true;
                }
            }
        }
        return false;
    }

    EnergyReading get_reading() override {
        if (!initialized_) return {};
        
        std::ifstream f(energy_path_);
        uint64_t microjoules;
        if (!(f >> microjoules)) {
            record_measurement_attempt(false);
            return {};
        }

        EnergyReading reading;
        reading.timestamp_ns = std::chrono::steady_clock::now().time_since_epoch().count();
        reading.energy_joules = microjoules / 1e6;
        reading.provider_id = "arm_eas";
        reading.domain_energy_joules["soc"] = reading.energy_joules;
        
        record_measurement_attempt(true);
        return reading;
    }

    EnergyProviderSpec get_specification() const override {
        EnergyProviderSpec spec;
        spec.provider_name = "ARM EAS";
        spec.hardware_type = "soc";
        spec.vendor = "arm";
        spec.measurement_domains = {"soc"};
        spec.energy_resolution_joules = 1e-6;
        return spec;
    }

    bool self_test() override { 
        if (!initialized_) return false;
        auto r1 = get_reading();
        usleep(100000);
        auto r2 = get_reading();
        return r2.energy_joules >= r1.energy_joules;
    }
    
    bool is_available() const override { return initialized_; }
    void shutdown() override { initialized_ = false; }
    std::string get_name() const override { return "ARM EAS"; }

private:
    std::string energy_path_;
    bool initialized_{false};
};

std::unique_ptr<EnergyProvider> create_arm_energy_provider() {
    return std::make_unique<ARMEnergyProvider>();
}

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("arm_eas", []() {
            return std::make_unique<ARMEnergyProvider>();
        });
        return true;
    }();
}

} // namespace codegreen::nemb::drivers