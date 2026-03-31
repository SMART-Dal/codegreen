#ifdef _WIN32
#include "../../../include/nemb/drivers/windows_emi_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <iostream>
#include <algorithm>

#pragma comment(lib, "pdh.lib")

namespace codegreen::nemb::drivers {

// Map EMI instance names to CodeGreen energy domains.
// Verified on i7-1165G7 Windows 11 build 26100:
//   RAPL_Package0_PKG, RAPL_Package0_PP0, RAPL_Package0_PP1, RAPL_Package0_DRAM
// Multi-socket systems may have RAPL_Package1_* etc.
std::string WindowsEMIProvider::emi_instance_to_domain(const std::string& instance) {
    // Extract domain from pattern: RAPL_Package{N}_{DOMAIN}
    auto pos = instance.rfind('_');
    if (pos == std::string::npos) return "";
    std::string suffix = instance.substr(pos + 1);
    if (suffix == "PKG") return "package";
    if (suffix == "PP0") return "core";
    if (suffix == "PP1") return "gpu";
    if (suffix == "DRAM") return "dram";
    if (suffix == "PSYS") return "platform";
    return "";
}

WindowsEMIProvider::WindowsEMIProvider() = default;

WindowsEMIProvider::~WindowsEMIProvider() { shutdown(); }

bool WindowsEMIProvider::initialize() {
    // Open PDH query
    if (PdhOpenQuery(NULL, 0, &query_) != ERROR_SUCCESS) {
        std::cerr << " [windows_emi] PdhOpenQuery failed" << std::endl;
        return false;
    }

    // Enumerate Energy Meter instances to discover RAPL domains
    DWORD buf_size = 0, instance_size = 0;
    PdhEnumObjectItems(NULL, NULL, "Energy Meter", NULL, &buf_size,
                       NULL, &instance_size, PERF_DETAIL_WIZARD, 0);

    if (instance_size == 0) {
        std::cerr << " [windows_emi] no Energy Meter instances found "
                  "(requires Windows 11 with intelpep.sys)" << std::endl;
        PdhCloseQuery(query_);
        query_ = nullptr;
        return false;
    }

    std::vector<char> counter_buf(buf_size + 1, 0);
    std::vector<char> instance_buf(instance_size + 1, 0);
    PdhEnumObjectItems(NULL, NULL, "Energy Meter",
                       counter_buf.data(), &buf_size,
                       instance_buf.data(), &instance_size,
                       PERF_DETAIL_WIZARD, 0);

    // Parse multi-string instance list (null-separated, double-null terminated)
    const char* p = instance_buf.data();
    while (*p) {
        std::string instance(p);
        p += instance.size() + 1;

        if (instance == "_Total") continue;

        std::string domain = emi_instance_to_domain(instance);
        if (domain.empty()) continue;

        // Add PDH counter for this domain's Energy value
        std::string path = "\\Energy Meter(" + instance + ")\\Energy";
        DomainCounter dc;
        dc.emi_instance = instance;
        dc.domain = domain;

        PDH_STATUS status = PdhAddCounter(query_, path.c_str(), 0, &dc.counter);
        if (status != ERROR_SUCCESS) {
            std::cerr << " [windows_emi] PdhAddCounter failed for " << path
                      << " (status=0x" << std::hex << status << std::dec << ")" << std::endl;
            continue;
        }
        domains_.push_back(std::move(dc));
    }

    if (domains_.empty()) {
        std::cerr << " [windows_emi] no RAPL domains discovered" << std::endl;
        PdhCloseQuery(query_);
        query_ = nullptr;
        return false;
    }

    // Initial collect to prime counters
    PdhCollectQueryData(query_);

    initialized_ = true;
    std::cout << " Windows EMI energy provider initialized (" << domains_.size() << " domains:";
    for (auto& d : domains_) std::cout << " " << d.domain;
    std::cout << ")" << std::endl;
    return true;
}

EnergyReading WindowsEMIProvider::get_reading() {
    EnergyReading reading;
    reading.provider_id = "windows_emi";
    reading.timestamp_ns = utils::PrecisionTimer::monotonic_timestamp_ns();

    if (!initialized_) {
        reading.confidence = 0.0;
        record_measurement_attempt(false);
        return reading;
    }

    std::lock_guard<std::mutex> lock(reading_mutex_);

    if (PdhCollectQueryData(query_) != ERROR_SUCCESS) {
        record_measurement_attempt(false);
        return reading;
    }

    double total_j = 0;
    for (auto& dc : domains_) {
        PDH_FMT_COUNTERVALUE value;
        if (PdhGetFormattedCounterValue(dc.counter, PDH_FMT_LARGE, NULL, &value) != ERROR_SUCCESS)
            continue;

        // EMI Energy counter is cumulative picowatt-hours
        double current_pwh = static_cast<double>(value.largeValue);

        if (dc.has_prev) {
            double delta_pwh = current_pwh - dc.prev_pwh;
            // Handle counter wrap (64-bit pWh wraps after ~2.1M years, but be safe)
            if (delta_pwh < 0) delta_pwh = 0;
            double delta_j = delta_pwh * 3.6e-9;
            dc.cumulative_joules += delta_j;
        }
        dc.prev_pwh = current_pwh;
        dc.has_prev = true;

        reading.domain_energy_joules[dc.domain] = dc.cumulative_joules;
        total_j += dc.cumulative_joules;
    }

    reading.energy_joules = total_j;
    reading.source_type = "hardware_counter";
    reading.confidence = 0.95;
    reading.uncertainty_percent = 2.0;
    reading.sample_count = 1;

    record_measurement_attempt(true);
    return reading;
}

EnergyProviderSpec WindowsEMIProvider::get_specification() const {
    EnergyProviderSpec spec;
    spec.provider_name = "Windows EMI (RAPL)";
    spec.hardware_type = "cpu";
    spec.vendor = "intel";
    for (auto& dc : domains_)
        spec.measurement_domains.push_back(dc.domain);
    spec.energy_resolution_joules = 3.6e-9; // 1 pWh = 3.6 nJ
    spec.min_measurement_interval = std::chrono::microseconds(1000);
    spec.typical_accuracy_percent = 2.0;
    spec.supports_temperature = false;
    spec.supports_frequency = false;
    return spec;
}

bool WindowsEMIProvider::self_test() {
    if (!initialized_) return false;
    auto r1 = get_reading();
    Sleep(200);
    auto r2 = get_reading();
    if (r2.energy_joules <= r1.energy_joules) {
        std::cerr << " [windows_emi] self_test: no energy delta after 200ms" << std::endl;
        return false;
    }
    double delta = r2.energy_joules - r1.energy_joules;
    double power = delta / 0.2;
    if (power < 0.1 || power > 1000) {
        std::cerr << " [windows_emi] self_test: implausible power " << power << " W" << std::endl;
        return false;
    }
    return true;
}

bool WindowsEMIProvider::is_available() const { return initialized_; }

void WindowsEMIProvider::shutdown() {
    if (query_) {
        PdhCloseQuery(query_);
        query_ = nullptr;
    }
    domains_.clear();
    initialized_ = false;
}

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("windows_emi", []() {
            return std::make_unique<WindowsEMIProvider>();
        });
        return true;
    }();
}

} // namespace codegreen::nemb::drivers
#endif // _WIN32
