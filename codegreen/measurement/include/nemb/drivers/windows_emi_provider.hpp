#pragma once
#ifdef _WIN32

#include "../core/energy_provider.hpp"
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include <windows.h>
#include <pdh.h>

namespace codegreen::nemb::drivers {

class WindowsEMIProvider : public EnergyProvider {
public:
    WindowsEMIProvider();
    ~WindowsEMIProvider() override;

    bool initialize() override;
    EnergyReading get_reading() override;
    EnergyProviderSpec get_specification() const override;
    bool self_test() override;
    bool is_available() const override;
    void shutdown() override;
    std::string get_name() const override { return "Windows EMI (RAPL)"; }

private:
    bool initialized_{false};
    PDH_HQUERY query_{nullptr};

    // EMI instance -> RAPL domain mapping
    // Verified on i7-1165G7 Windows 11 (build 26100):
    //   RAPL_Package0_PKG  -> package
    //   RAPL_Package0_PP0  -> core
    //   RAPL_Package0_PP1  -> gpu (iGPU)
    //   RAPL_Package0_DRAM -> dram
    struct DomainCounter {
        std::string emi_instance;  // e.g. "RAPL_Package0_PKG"
        std::string domain;        // e.g. "package"
        PDH_HCOUNTER counter{nullptr};
        double cumulative_joules{0.0};
        double prev_pwh{0.0};
        bool has_prev{false};
    };
    std::vector<DomainCounter> domains_;
    std::mutex reading_mutex_;

    static std::string emi_instance_to_domain(const std::string& instance);
};

} // namespace codegreen::nemb::drivers
#endif // _WIN32
