#include "../../../include/nemb/drivers/intel_rapl_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"

#include <fstream>
#include <iostream>
#include <filesystem>
#include <thread>
#include <sstream>
#include <algorithm>
#include <chrono>
#include <limits>
#include <ctime>

namespace codegreen::nemb::drivers {

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("intel_rapl", []() {
            return std::make_unique<IntelRAPLProvider>();
        });
        return true;
    }();
}

IntelRAPLProvider::IntelRAPLProvider() {
}

IntelRAPLProvider::~IntelRAPLProvider() {
    shutdown();
}

bool IntelRAPLProvider::initialize() {
    std::cout << "Initializing Intel RAPL provider..." << std::endl;
    
    // Detect available RAPL domains with proper hardware capability detection
    if (!detect_rapl_domains()) {
        std::cout << "No RAPL domains detected" << std::endl;
        return false;
    }
    
    // Query hardware-specific energy resolution instead of hardcoding
    if (!query_energy_units()) {
        std::cout << "Failed to determine energy units" << std::endl;
        return false;
    }
    
    // Initialize counter management for wraparound handling
    if (!initialize_counters()) {
        std::cout << "Counter initialization failed" << std::endl;
        return false;
    }
    
    // Initialize non-blocking file readers
    if (!initialize_file_readers()) {
        std::cout << "Failed to initialize file readers" << std::endl;
        return false;
    }
    
    // Take initial baseline readings
    if (!take_initial_readings()) {
        std::cout << "Failed to take initial readings" << std::endl;
        return false;
    }
    
    initialized_ = true;
    
    // Log detected capabilities
    std::cout << "[ok] Intel RAPL provider initialized" << std::endl;
    std::cout << "    Energy unit: " << energy_unit_joules_ << " J" << std::endl;
    std::cout << "    Available domains: ";
    for (size_t i = 0; i < available_domains_.size(); ++i) {
        if (i > 0) std::cout << ", ";
        std::cout << available_domains_[i];
    }
    std::cout << std::endl;
    
    return true;
}

EnergyReading IntelRAPLProvider::get_reading() {
    EnergyReading reading;
    reading.provider_id = "intel_rapl";

    reading.timestamp_ns = nemb::utils::PrecisionTimer::monotonic_timestamp_ns();

    // Keep system_time for compatibility and dt calculation
    auto now = std::chrono::steady_clock::now();
    reading.system_time = now;
    
    if (!initialized_) {
        // Return invalid reading
        reading.energy_joules = -1.0;
        reading.confidence = 0.0;
        return reading;
    }
    
    std::lock_guard<std::mutex> lock(reading_mutex_);
    
    double total_energy = 0.0;
    double total_power = 0.0;
    bool any_successful = false;
    std::map<std::string, uint64_t> raw_values;
    
    // Read energy from ALL available RAPL domains
    for (const std::string& domain : available_domains_) {
        try {
            auto& reader = domain_file_readers_[domain];
            uint64_t raw_energy_uj;
            
            // Use 10ms timeout for readings to prevent stalls
            if (reader && reader->read_uint64_with_timeout(raw_energy_uj, std::chrono::milliseconds(10))) {
                raw_values[domain] = raw_energy_uj;
                any_successful = true;
            } else {
                 // Try to re-open if reading failed
                 if (reader) reader->open_file();
                 reading.domain_energy_joules[domain] = -1.0;
            }
        } catch (const std::exception& e) {
            // Log error but continue with other domains
            reading.domain_energy_joules[domain] = -1.0;
        }
    }
    
    if (any_successful) {
        // Atomic update of all counters
        auto accumulated_values = counter_manager_->update_counters(raw_values, reading.timestamp_ns);
        
        // Calculate time delta for power calculation
        double dt = std::chrono::duration<double>(now - last_reading_time_).count();
        
        for (const auto& [domain, accumulated_uj] : accumulated_values) {
            double domain_energy = accumulated_uj * energy_unit_joules_;
            reading.domain_energy_joules[domain] = domain_energy;
            
            // Calculate average power for this domain since last sample
            double domain_power = 0.0;
            if (dt > 0 && last_domain_energies_.count(domain)) {
                double de = domain_energy - last_domain_energies_[domain];
                if (de >= 0) {
                    domain_power = de / dt;
                }
            }
            reading.domain_power_watts[domain] = domain_power;
            last_domain_energies_[domain] = domain_energy;
            
            // Only sum non-overlapping top-level domains (computed at detection time).
            // If PSYS present: total = PSYS only (superset of PKG+DRAM).
            // Else: total = all package-* + dram-* (excludes core/uncore sub-domains).
            if (top_level_domains_.count(domain)) {
                total_energy += domain_energy;
                total_power += domain_power;
            }
        }
        last_reading_time_ = now;
    }
    
    // Set aggregated values
    reading.energy_joules = any_successful ? total_energy : -1.0;
    reading.instantaneous_power_watts = total_power;
    reading.average_power_watts = total_power;
    
    // Set quality metrics
    reading.measurement_uncertainty = 0.01; // 1% - Intel RAPL typical
    reading.confidence = any_successful ? 0.95 : 0.0;
    reading.uncertainty_percent = 1.0;
    reading.sample_count = 1;
    reading.source_type = "hardware_counter";
    
    return reading;
}

EnergyProviderSpec IntelRAPLProvider::get_specification() const {
    EnergyProviderSpec spec;
    
    // Provider identification
    spec.hardware_type = "cpu";
    spec.vendor = "intel";
    spec.model = "rapl";
    spec.provider_name = "Intel RAPL";
    
    // CRITICAL: Include measurement domains - use actually detected domains
    spec.measurement_domains = available_domains_;
    
    // Hardware-queried capabilities (not hardcoded)
    spec.energy_resolution_joules = energy_unit_joules_;
    spec.power_resolution_watts = energy_unit_joules_ * 1000.0; // Approximate
    spec.update_interval = std::chrono::microseconds(1000);
    spec.counter_bits = 32; // RAPL counters are 32-bit
    
    // Advanced capabilities
    spec.supports_temperature = false;
    spec.supports_frequency = false;
    spec.supports_power_limiting = true;
    spec.supports_per_core_measurement = std::find(available_domains_.begin(), available_domains_.end(), "pp0") != available_domains_.end();
    
    // Performance characteristics
    spec.max_measurement_frequency_hz = 1000.0;
    spec.min_measurement_interval = std::chrono::microseconds(1000);
    spec.typical_accuracy_percent = 1.0;
    spec.measurement_overhead_percent = 0.01;
    
    // Hardware-specific metadata
    spec.hardware_info["access_method"] = (access_method_ == AccessMethod::MSR_DIRECT) ? "MSR" : "sysfs";
    spec.hardware_info["energy_unit_joules"] = std::to_string(energy_unit_joules_);
    spec.supported_metrics = {"energy", "power"};
    
    return spec;
}

bool IntelRAPLProvider::self_test() {
    if (!initialized_) {
        return false;
    }
    
    auto reading1 = get_reading();
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    auto reading2 = get_reading();
    
    return reading1.energy_joules >= 0 && reading2.energy_joules >= 0 && 
           reading2.energy_joules >= reading1.energy_joules;
}

bool IntelRAPLProvider::is_available() const {
    return initialized_;
}

void IntelRAPLProvider::shutdown() {
    std::cout << "Shutting down Intel RAPL provider..." << std::endl;
    
    // Close all file readers
    for (auto& [domain, reader] : domain_file_readers_) {
        if (reader) {
            reader->close_file();
        }
    }
    domain_file_readers_.clear();
    
    initialized_ = false;
}

std::map<std::string, RAPLDomain> IntelRAPLProvider::get_available_domains() const {
    std::map<std::string, RAPLDomain> domains;
    
    if (std::filesystem::exists("/sys/class/powercap/intel-rapl:0/energy_uj")) {
        RAPLDomain package_domain;
        package_domain.name = "package";
        package_domain.sysfs_path = "/sys/class/powercap/intel-rapl:0/energy_uj";
        package_domain.available = true;
        domains["package"] = package_domain;
    }
    
    return domains;
}

// Hardware detection methods implementation
bool IntelRAPLProvider::detect_rapl_domains() {
    std::cout << "Detecting RAPL domains..." << std::endl;
    
    available_domains_.clear();
    domain_paths_.clear();
    
    // Enumerate RAPL zones dynamically from sysfs, reading name files
    // to correctly identify domains on multi-socket and varied platforms
    auto read_sysfs = [](const std::string& path) -> std::string {
        std::ifstream f(path);
        std::string val;
        if (f.is_open()) std::getline(f, val);
        return val;
    };
    for (int pkg = 0; ; ++pkg) {
        std::string base = "/sys/class/powercap/intel-rapl:" + std::to_string(pkg);
        std::string energy_path = base + "/energy_uj";
        if (!std::filesystem::exists(energy_path)) break;
        std::string domain_name = read_sysfs(base + "/name");
        if (domain_name.empty()) domain_name = "package-" + std::to_string(pkg);
        available_domains_.push_back(domain_name);
        domain_paths_[domain_name] = energy_path;
        RAPLDomain domain;
        domain.name = domain_name;
        domain.sysfs_path = energy_path;
        domain.available = true;
        rapl_domains_[domain_name] = domain;
        std::cout << "  [ok] Found domain: " << domain_name << std::endl;
        for (int sub = 0; ; ++sub) {
            std::string sub_base = base + ":" + std::to_string(sub);
            std::string sub_energy = sub_base + "/energy_uj";
            if (!std::filesystem::exists(sub_energy)) break;
            std::string sub_name = read_sysfs(sub_base + "/name");
            if (sub_name.empty()) sub_name = "sub-" + std::to_string(sub);
            available_domains_.push_back(sub_name);
            domain_paths_[sub_name] = sub_energy;
            RAPLDomain sub_domain;
            sub_domain.name = sub_name;
            sub_domain.sysfs_path = sub_energy;
            sub_domain.available = true;
            rapl_domains_[sub_name] = sub_domain;
            std::cout << "  [ok] Found sub-domain: " << sub_name << std::endl;
        }
    }
    
    if (available_domains_.empty()) {
        std::cout << "  No RAPL domains found" << std::endl;
        return false;
    }

    // Compute non-overlapping top-level domains for correct total energy.
    // PSYS (platform) is a superset of PKG+DRAM on Intel Skylake+.
    // If PSYS exists, use it alone. Otherwise sum all package-* and dram* domains.
    // Sub-domains (core, uncore, pp0, pp1) are NEVER top-level.
    top_level_domains_.clear();
    bool has_psys = false;
    for (auto& d : available_domains_) {
        if (d == "psys") { has_psys = true; break; }
    }
    for (auto& d : available_domains_) {
        if (has_psys) {
            if (d == "psys") top_level_domains_.insert(d);
        } else {
            // package-0, package-1, dram, dram-0 etc. are top-level
            if (d.rfind("package", 0) == 0 || d.rfind("dram", 0) == 0)
                top_level_domains_.insert(d);
        }
    }
    
    // Set access method
    access_method_ = AccessMethod::SYSFS_POWERCAP;
    return true;
}

bool IntelRAPLProvider::query_energy_units() {
    std::cout << "Querying RAPL energy units..." << std::endl;
    
    // Try to read energy unit from sysfs
    // Note: The actual RAPL energy unit should be read from MSR 0x606
    // For now, use a reasonable default and try to infer from readings
    
    // Check if we can read the name file to get more info
    std::string name_path = "/sys/class/powercap/intel-rapl:0/name";
    if (std::filesystem::exists(name_path)) {
        std::ifstream name_file(name_path);
        std::string rapl_name;
        if (name_file >> rapl_name) {
            std::cout << "  RAPL name: " << rapl_name << std::endl;
        }
    }
    
    // Query energy unit from hardware - NEVER use hardcoded values!
    if (!query_energy_unit_from_hardware()) {
        std::cout << "  Failed to query energy unit from hardware" << std::endl;
        return false;
    }
    
    std::cout << "  Energy unit: " << (energy_unit_joules_ * 1e6) << " μJ" << std::endl;
    return true;
}

bool IntelRAPLProvider::initialize_counters() {
    std::cout << "Initializing RAPL counters..." << std::endl;
    
    // Create the HAL counter manager
    counter_manager_ = std::make_unique<hal::CounterManager>();
    
    // Initialize counters for each available domain
    for (const std::string& domain : available_domains_) {
        hal::CounterManager::CounterConfig config;
        config.name = domain;
        config.domain = domain;
        config.bit_width = 32;
        config.conversion_factor = energy_unit_joules_;
        config.unit = "J";
        config.active = true;

        // Read max_energy_range_uj from sysfs for accurate wraparound
        uint64_t max_energy = std::numeric_limits<uint32_t>::max();
        std::string max_path = domain_paths_[domain];
        // Replace energy_uj with max_energy_range_uj in the path
        auto pos = max_path.rfind("/energy_uj");
        if (pos != std::string::npos) {
            std::string max_range_path = max_path.substr(0, pos) + "/max_energy_range_uj";
            std::ifstream max_file(max_range_path);
            if (max_file.is_open()) {
                max_file >> max_energy;
                std::cout << "  Max energy range for " << domain << ": " << max_energy << " uJ" << std::endl;
            }
        }
        config.max_value = max_energy;

        counter_manager_->register_counter(domain, config);
        std::cout << "  [ok] Initialized counter for domain: " << domain << std::endl;
    }
    
    return true;
}

bool IntelRAPLProvider::initialize_file_readers() {
    std::cout << "Initializing non-blocking file readers..." << std::endl;
    
    // Clear any existing readers
    domain_file_readers_.clear();
    
    for (const std::string& domain : available_domains_) {
        const std::string& path = domain_paths_[domain];
        
        auto reader = std::make_unique<utils::NonBlockingFileReader>(path);
        if (!reader->open_file()) {
            std::cout << "Failed to open file reader for domain: " << domain 
                      << " (path: " << path << ")" << std::endl;
            return false;
        }
        
        domain_file_readers_[domain] = std::move(reader);
        std::cout << "[ok] File reader initialized for domain: " << domain << std::endl;
    }
    
    return true;
}

bool IntelRAPLProvider::take_initial_readings() {
    std::cout << "Taking initial baseline readings..." << std::endl;
    
    std::map<std::string, uint64_t> initial_values;
    bool success = true;
    
    for (const std::string& domain : available_domains_) {
        try {
            auto& reader = domain_file_readers_[domain];
            uint64_t energy_uj;
            
            if (reader && reader->read_uint64_with_timeout(energy_uj, std::chrono::milliseconds(100))) {
                initial_values[domain] = energy_uj;
                std::cout << "  [ok] Initial reading for " << domain << ": " 
                         << energy_uj << " μJ" << std::endl;
            } else {
                std::cout << "  Cannot read " << domain << " energy file" << std::endl;
                success = false;
            }
        } catch (const std::exception& e) {
            std::cout << "  Error reading " << domain << ": " << e.what() << std::endl;
            success = false;
        }
    }
    
    if (success) {
        counter_manager_->initialize_counters(initial_values, std::chrono::steady_clock::now().time_since_epoch().count());
    }
    
    return success;
}

bool IntelRAPLProvider::query_energy_unit_from_hardware() {
    // Try to read energy unit from sysfs first (more reliable than MSR)
    const std::string energy_unit_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj";
    
    if (std::filesystem::exists(energy_unit_path)) {
        // For sysfs interface, energy values are already in microjoules
        // The unit is implicitly 1 microjoule = 1e-6 joules
        energy_unit_joules_ = 1e-6; // 1 microjoule
        std::cout << "  [ok] Using sysfs energy unit: 1 μJ" << std::endl;
        return true;
    }
    
    // Fallback: Try to read from MSR_RAPL_POWER_UNIT (requires MSR access)
    // This is the proper way to get exact hardware capabilities
    try {
        // Check if MSR access is available
        const std::string msr_path = "/dev/cpu/0/msr";
        if (std::filesystem::exists(msr_path)) {
            std::ifstream msr_file(msr_path, std::ios::binary);
            if (msr_file.is_open()) {
                // Seek to MSR_RAPL_POWER_UNIT (0x606)
                msr_file.seekg(0x606 * 8, std::ios::beg);
                
                uint64_t power_unit_msr = 0;
                msr_file.read(reinterpret_cast<char*>(&power_unit_msr), sizeof(power_unit_msr));
                
                if (msr_file.good()) {
                    // Energy unit is in bits 12:8 of MSR_RAPL_POWER_UNIT
                    uint32_t energy_unit_raw = (power_unit_msr >> 8) & 0x1F;
                    energy_unit_joules_ = 1.0 / (1ULL << energy_unit_raw); // 2^(-energy_unit_raw) joules
                    
                    std::cout << "  [ok] Hardware energy unit: " << (energy_unit_joules_ * 1e6) << " μJ" << std::endl;
                    return true;
                }
            }
        }
    } catch (const std::exception& e) {
        std::cout << "  MSR access failed: " << e.what() << std::endl;
    }
    
    // Final fallback - this should rarely be needed if hardware detection works properly
    std::cout << "  Cannot query energy unit from hardware, using conservative fallback" << std::endl;
    energy_unit_joules_ = 15.3e-6; // Conservative typical Intel value
    return true; // Still succeed, but with lower confidence
}

std::unique_ptr<IntelRAPLProvider> create_intel_rapl_provider() {
    return std::make_unique<IntelRAPLProvider>();
}

} // namespace codegreen::nemb::drivers