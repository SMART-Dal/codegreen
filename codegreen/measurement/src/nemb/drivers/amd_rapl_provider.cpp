#include "../../../include/nemb/core/energy_provider.hpp"
#include "../../../include/nemb/hal/counter_manager.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <iostream>
#include <fstream>
#include <fcntl.h>
#include <unistd.h>
#include <cmath>
#include <string>
#include <vector>
#include <chrono>

namespace codegreen::nemb::drivers {

/**
 * @brief AMD Native RAPL provider for Zen architectures (Family 17h+)
 */
class AMDRAPLProvider : public EnergyProvider {
public:
    AMDRAPLProvider() = default;
    ~AMDRAPLProvider() override { shutdown(); }

    bool initialize() override {
        // Check if Family 17h or newer
        std::ifstream cpuinfo("/proc/cpuinfo");
        std::string line;
        int family = 0;
        while (std::getline(cpuinfo, line)) {
            if (line.find("cpu family") != std::string::npos) {
                try {
                    family = std::stoi(line.substr(line.find(":") + 1));
                } catch (...) { continue; }
                break;
            }
        }
        if (family < 23) return false; // 23 = 17h (Zen)

        // Try to open MSR device for CPU 0
        msr_fd_ = open("/dev/cpu/0/msr", O_RDONLY);
        if (msr_fd_ < 0) return false;

        // Query energy unit (MSR_AMD_RAPL_POWER_UNIT 0xC0010299)
        uint64_t units;
        if (pread(msr_fd_, &units, sizeof(units), 0xC0010299) != sizeof(units)) {
            close(msr_fd_);
            msr_fd_ = -1;
            return false;
        }
        // Energy unit is in bits 12:8
        uint32_t energy_unit_raw = (units >> 8) & 0x1F;
        energy_unit_ = 1.0 / (1ULL << energy_unit_raw);

        initialized_ = true;
        return true;
    }

    EnergyReading get_reading() override {
        if (!initialized_) return {};

        uint64_t raw_energy;
        if (pread(msr_fd_, &raw_energy, sizeof(raw_energy), 0xC001029B) != sizeof(raw_energy)) {
            record_measurement_attempt(false);
            return {};
        }

        uint64_t ts = nemb::utils::PrecisionTimer::monotonic_timestamp_ns();
        uint32_t raw32 = static_cast<uint32_t>(raw_energy & 0xFFFFFFFF);
        uint64_t accumulated = counter_.update(raw32, ts);
        double energy_j = accumulated * energy_unit_;

        EnergyReading reading;
        reading.timestamp_ns = ts;
        reading.energy_joules = energy_j;
        reading.provider_id = "amd_rapl";
        reading.domain_energy_joules["package"] = energy_j;

        // Compute average power
        if (last_ts_ns_ > 0 && last_energy_ >= 0) {
            double dt = static_cast<double>(ts - last_ts_ns_) / 1e9;
            if (dt > 0) reading.average_power_watts = (energy_j - last_energy_) / dt;
        }
        last_energy_ = energy_j;
        last_ts_ns_ = ts;

        record_measurement_attempt(true);
        return reading;
    }

    EnergyProviderSpec get_specification() const override {
        EnergyProviderSpec spec;
        spec.provider_name = "AMD Native RAPL";
        spec.hardware_type = "cpu";
        spec.vendor = "amd";
        spec.measurement_domains = {"package"};
        spec.energy_resolution_joules = energy_unit_;
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
    
    void shutdown() override {
        if (msr_fd_ >= 0) {
            close(msr_fd_);
            msr_fd_ = -1;
        }
        initialized_ = false;
    }
    
    std::string get_name() const override { return "AMD Native RAPL"; }

private:
    int msr_fd_{-1};
    double energy_unit_{0.0};
    bool initialized_{false};
    hal::Counter32 counter_{std::numeric_limits<uint32_t>::max(), "amd_pkg"};
    double last_energy_{-1.0};
    uint64_t last_ts_ns_{0};
};

std::unique_ptr<EnergyProvider> create_amd_rapl_provider() {
    return std::make_unique<AMDRAPLProvider>();
}

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("amd_rapl", []() {
            return std::make_unique<AMDRAPLProvider>();
        });
        return true;
    }();
}

} // namespace codegreen::nemb::drivers