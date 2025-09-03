#include "../../../include/nemb/core/energy_provider.hpp"
#include "../../../include/nemb/drivers/intel_rapl_provider.hpp"

#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>

namespace codegreen::nemb {

// Factory function implementation
std::unique_ptr<EnergyProvider> create_energy_provider(const std::string& provider_type) {
    if (provider_type == "intel_rapl") {
        return drivers::create_intel_rapl_provider();
    }
    // Add more providers as they are implemented
    // else if (provider_type == "nvidia_nvml") {
    //     return drivers::create_nvidia_gpu_provider();
    // }
    
    std::cerr << "Unknown energy provider type: " << provider_type << std::endl;
    return nullptr;
}

// CPU vendor detection helper
namespace {
    enum class CPUVendor {
        UNKNOWN,
        INTEL,
        AMD,
        ARM
    };
    
    CPUVendor detect_cpu_vendor() {
        std::ifstream cpuinfo("/proc/cpuinfo");
        std::string line;
        
        while (std::getline(cpuinfo, line)) {
            if (line.find("vendor_id") != std::string::npos) {
                if (line.find("GenuineIntel") != std::string::npos) {
                    return CPUVendor::INTEL;
                } else if (line.find("AuthenticAMD") != std::string::npos) {
                    return CPUVendor::AMD;
                }
            } else if (line.find("CPU implementer") != std::string::npos) {
                if (line.find("0x41") != std::string::npos) { // ARM Ltd
                    return CPUVendor::ARM;
                }
            }
        }
        
        return CPUVendor::UNKNOWN;
    }
    
    bool check_intel_rapl_availability() {
        // Check for RAPL interface in sysfs
        std::ifstream rapl_check("/sys/class/powercap/intel-rapl:0/energy_uj");
        return rapl_check.good();
    }
    
    bool check_nvidia_gpu_availability() {
        // Check for NVIDIA device files
        std::ifstream nvidia_check("/dev/nvidia0");
        return nvidia_check.good();
    }
    
    bool check_amd_gpu_availability() {
        // Check for AMD GPU in /sys/class/drm
        std::ifstream amd_check("/sys/class/drm/card0/device/vendor");
        if (!amd_check.good()) return false;
        
        std::string vendor_id;
        amd_check >> vendor_id;
        return vendor_id == "0x1002"; // AMD vendor ID
    }
}

std::vector<std::unique_ptr<EnergyProvider>> detect_available_providers() {
    std::vector<std::unique_ptr<EnergyProvider>> providers;
    
    std::cout << "🔍 Detecting available energy providers..." << std::endl;
    
    // CPU energy providers
    CPUVendor cpu_vendor = detect_cpu_vendor();
    switch (cpu_vendor) {
        case CPUVendor::INTEL:
            if (check_intel_rapl_availability()) {
                auto intel_provider = drivers::create_intel_rapl_provider();
                if (intel_provider && intel_provider->initialize()) {
                    std::cout << "  ✅ Intel RAPL CPU provider" << std::endl;
                    providers.push_back(std::move(intel_provider));
                } else {
                    std::cout << "  ❌ Intel RAPL CPU provider failed initialization" << std::endl;
                }
            } else {
                std::cout << "  ⚠️  Intel RAPL interface not available" << std::endl;
            }
            break;
            
        case CPUVendor::AMD:
            std::cout << "  🚧 AMD RAPL provider not yet implemented" << std::endl;
            break;
            
        case CPUVendor::ARM:
            std::cout << "  🚧 ARM EAS provider not yet implemented" << std::endl;
            break;
            
        default:
            std::cout << "  ❌ Unknown CPU vendor" << std::endl;
            break;
    }
    
    // GPU energy providers
    if (check_nvidia_gpu_availability()) {
        std::cout << "  🚧 NVIDIA GPU provider not yet implemented" << std::endl;
        // TODO: Implement NVIDIA provider
        // auto nvidia_provider = drivers::create_nvidia_gpu_provider();
        // if (nvidia_provider && nvidia_provider->initialize()) {
        //     providers.push_back(std::move(nvidia_provider));
        // }
    }
    
    if (check_amd_gpu_availability()) {
        std::cout << "  🚧 AMD GPU provider not yet implemented" << std::endl;
        // TODO: Implement AMD GPU provider
    }
    
    if (providers.empty()) {
        std::cout << "  ⚠️  No energy providers available - measurements will be limited" << std::endl;
    } else {
        std::cout << "  ✅ Successfully initialized " << providers.size() << " energy provider(s)" << std::endl;
    }
    
    return providers;
}

} // namespace codegreen::nemb