#ifdef _WIN32
#include "../../../include/nemb/drivers/windows_emi_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <iostream>
#include <algorithm>

#pragma comment(lib, "pdh.lib")

namespace codegreen::nemb::drivers {

// Map EMI instance names to user-friendly domain names.
// Preserves all instances dynamically -- no hardcoded domain count.
// Pattern: RAPL_Package{N}_{SUFFIX} -> lowercase suffix with socket index.
// Unknown suffixes are passed through (future-proof).
std::string WindowsEMIProvider::emi_instance_to_domain(const std::string& instance) {
    auto last_sep = instance.rfind('_');
    if (last_sep == std::string::npos || last_sep == 0) return instance;
    std::string suffix = instance.substr(last_sep + 1);

    // Extract socket index if present (Package0, Package1, etc.)
    std::string socket_id;
    auto pkg_pos = instance.find("Package");
    if (pkg_pos != std::string::npos) {
        size_t num_start = pkg_pos + 7;
        size_t num_end = instance.find('_', num_start);
        if (num_end != std::string::npos && num_end > num_start)
            socket_id = instance.substr(num_start, num_end - num_start);
    }

    // Lowercase the suffix for consistency
    std::string domain;
    for (char c : suffix) domain += std::tolower(c);

    // Append socket index for multi-socket.
    // Only add suffix if the instance had a Package identifier (system-wide
    // domains like PSYS have no Package in their name, so socket_id is empty).
    if (!socket_id.empty())
        domain += "-" + socket_id;

    return domain;
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

    // Determine non-overlapping top-level domains for correct total.
    // Uses the same RAPL containment rules as Linux:
    // - PSYS (if present) is the most inclusive -- use it alone
    // - Otherwise: all pkg-* and dram-* domains are top-level
    // - pp0/pp1/core/gpu sub-domains are never top-level
    compute_top_level_domains();

    PdhCollectQueryData(query_);

    initialized_ = true;
    std::cerr << " Windows EMI energy provider initialized (" << domains_.size() << " domains:";
    for (auto& d : domains_) std::cerr << " " << d.domain;
    std::cerr << ")" << std::endl;
    return true;
}

void WindowsEMIProvider::compute_top_level_domains() {
    top_level_domains_.clear();
    bool has_psys = false;
    for (auto& dc : domains_) {
        if (dc.domain == "psys") { has_psys = true; break; }
    }
    for (auto& dc : domains_) {
        if (has_psys) {
            // PSYS is the most inclusive single counter (entire SoC)
            if (dc.domain == "psys") top_level_domains_.insert(dc.domain);
        } else {
            // pkg-* and dram-* are top-level; pp0/pp1/core/gpu are sub-domains of pkg
            if (dc.domain.rfind("pkg", 0) == 0 || dc.domain.rfind("dram", 0) == 0)
                top_level_domains_.insert(dc.domain);
        }
    }
    // If no known top-level detected (unknown hardware), treat ALL as top-level
    // This overcounts but never silently drops energy -- honest default.
    if (top_level_domains_.empty()) {
        for (auto& dc : domains_) top_level_domains_.insert(dc.domain);
    }
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
        if (top_level_domains_.count(dc.domain)) {
            total_j += dc.cumulative_joules;
        }
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
