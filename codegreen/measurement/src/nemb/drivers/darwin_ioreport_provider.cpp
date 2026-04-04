#ifdef __APPLE__
#include "../../../include/nemb/drivers/darwin_ioreport_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <dlfcn.h>
#include <iostream>
#include <unistd.h>

namespace codegreen::nemb::drivers {

static std::string cfstr_to_std(CFStringRef s) {
    if (!s) return "";
    char buf[256];
    if (CFStringGetCString(s, buf, sizeof(buf), kCFStringEncodingUTF8)) return buf;
    return "";
}

// Convert raw IOReport value to joules using per-channel unit label.
// Verified on M4: most channels report "mJ", "GPU Energy" reports "nJ".
// Future chips may use "uJ" or other units -- handle all known cases.
static double to_joules(int64_t raw, const std::string& unit) {
    if (unit == "mJ") return raw / 1e3;
    if (unit == "uJ") return raw / 1e6;
    if (unit == "nJ") return raw / 1e9;
    if (unit == "J")  return static_cast<double>(raw);
    // Unknown unit -- return 0 rather than silently misinterpret
    return 0;
}

// Map IOReport channel names to CodeGreen energy domains.
// Verified on M4 MacBook Pro (Mac16,1, macOS 25C56, 175 channels).
// Only aggregate channels are mapped; per-core/SRAM/DTL/PCIe are skipped.
// Convert IOReport channel name to a clean domain identifier.
// All channels are normalized to lowercase_with_underscores.
// Per-core channels (ECPU0, PCPU1, etc.) and fine-grained noise channels
// (DTL, SRAM, PCIe) are skipped to avoid ~150 low-value entries.
// No channel name is hardcoded as the primary mapping -- the normalization
// handles current and future Apple chips uniformly.
static std::string channel_to_domain(const std::string& name) {
    if (name.empty()) return "";

    // Skip per-core channels: any name that is a known cluster prefix + digits
    // (e.g., ECPU0, ECPU5, PCPU0, PCPU3, ECPUDTL07, PCPUDTL312)
    // but keep cluster aggregates (ECPU, PCPU, CPU Energy, etc.)
    for (const char* prefix : {"ECPU", "PCPU"}) {
        if (name.rfind(prefix, 0) == 0 && name.size() > 4) {
            char fifth = name[4];
            if (std::isdigit(fifth) || fifth == 'D') return ""; // per-core or DTL
        }
    }
    // Skip fine-grained channels that are noise for software profiling
    if (name.find("SRAM") != std::string::npos) return "";
    if (name.find("PCIe") != std::string::npos) return "";
    if (name.find("apciec") != std::string::npos) return "";
    if (name.find("SOC_") != std::string::npos) return "";

    // Normalize: lowercase, spaces -> underscores
    std::string domain;
    domain.reserve(name.size());
    for (char c : name) {
        if (c == ' ') domain += '_';
        else domain += std::tolower(c);
    }
    return domain;
}

DarwinIOReportProvider::DarwinIOReportProvider() = default;
DarwinIOReportProvider::~DarwinIOReportProvider() { shutdown(); }

bool DarwinIOReportProvider::load_symbols() {
    lib_handle_ = dlopen("libIOReport.dylib", RTLD_LAZY);
    if (!lib_handle_) {
        std::cerr << " [darwin_ioreport] dlopen: " << dlerror() << std::endl;
        return false;
    }

    copy_channels_in_group_ = (CopyChannelsInGroupFn)dlsym(lib_handle_, "IOReportCopyChannelsInGroup");
    create_subscription_ = (CreateSubscriptionFn)dlsym(lib_handle_, "IOReportCreateSubscription");
    create_samples_ = (CreateSamplesFn)dlsym(lib_handle_, "IOReportCreateSamples");
    create_samples_delta_ = (CreateSamplesDeltaFn)dlsym(lib_handle_, "IOReportCreateSamplesDelta");
    iterate_ = (IterateFn)dlsym(lib_handle_, "IOReportIterate");
    channel_get_group_ = (ChannelGetGroupFn)dlsym(lib_handle_, "IOReportChannelGetGroup");
    channel_get_name_ = (ChannelGetChannelNameFn)dlsym(lib_handle_, "IOReportChannelGetChannelName");
    channel_get_unit_ = (ChannelGetUnitLabelFn)dlsym(lib_handle_, "IOReportChannelGetUnitLabel");
    simple_get_int_ = (SimpleGetIntegerValueFn)dlsym(lib_handle_, "IOReportSimpleGetIntegerValue");

    const char* missing = nullptr;
    if (!copy_channels_in_group_) missing = "CopyChannelsInGroup";
    else if (!create_subscription_) missing = "CreateSubscription";
    else if (!create_samples_) missing = "CreateSamples";
    else if (!create_samples_delta_) missing = "CreateSamplesDelta";
    else if (!iterate_) missing = "Iterate";
    else if (!channel_get_group_) missing = "ChannelGetGroup";
    else if (!channel_get_name_) missing = "ChannelGetChannelName";
    else if (!simple_get_int_) missing = "SimpleGetIntegerValue";

    if (missing) {
        std::cerr << " [darwin_ioreport] missing symbol: IOReport" << missing << std::endl;
        return false;
    }
    return true;
}

bool DarwinIOReportProvider::setup_subscription() {
    CFDictionaryRef channels = copy_channels_in_group_(CFSTR("Energy Model"), NULL, NULL);
    if (!channels) {
        std::cerr << " [darwin_ioreport] no 'Energy Model' channels available" << std::endl;
        return false;
    }

    sub_handle_ = create_subscription_(NULL, channels, &subbed_channels_, 0, NULL);
    CFRelease(channels);

    if (!sub_handle_ || !subbed_channels_) {
        std::cerr << " [darwin_ioreport] CreateSubscription failed" << std::endl;
        return false;
    }

    prev_sample_ = create_samples_(sub_handle_, subbed_channels_, NULL);
    if (!prev_sample_) {
        std::cerr << " [darwin_ioreport] initial sample failed" << std::endl;
        return false;
    }
    return true;
}

bool DarwinIOReportProvider::initialize() {
    if (!load_symbols()) return false;
    if (!setup_subscription()) return false;

    last_ts_ns_ = utils::PrecisionTimer::monotonic_timestamp_ns();
    initialized_ = true;
    std::cerr << " Darwin IOReport energy provider initialized" << std::endl;
    return true;
}

void DarwinIOReportProvider::compute_top_level_domains() {
    // Determine which domains are sub-components that would double-count if summed.
    // Rule: if domain X is a known sub-component of domain Y (both present),
    // then X is NOT top-level. We detect this by checking if the aggregate exists.
    top_level_domains_.clear();
    bool has_cpu_aggregate = domains_.count("cpu_energy") > 0;
    bool has_dram = domains_.count("dram") > 0;

    for (auto& [d, _] : domains_) {
        bool is_sub = false;
        // ecpu/pcpu are sub-clusters of cpu_energy
        if (has_cpu_aggregate && (d == "ecpu" || d == "pcpu")) is_sub = true;
        // ecpm/pcpm are management overheads already in cpu_energy
        if (has_cpu_aggregate && (d == "ecpm" || d == "pcpm")) is_sub = true;
        // amcc/dcs overlap with dram
        if (has_dram && (d == "amcc" || d == "dcs")) is_sub = true;
        // display is hardware noise, not software-driven
        if (d == "disp" || d == "dispext") is_sub = true;
        // msr, ave, isp are small peripheral domains -- include for completeness
        // but mark as non-sub (they don't overlap with cpu/gpu/dram)

        if (!is_sub) top_level_domains_.insert(d);
    }
    if (top_level_domains_.empty()) {
        for (auto& [d, _] : domains_) top_level_domains_.insert(d);
    }
}

EnergyReading DarwinIOReportProvider::get_reading() {
    EnergyReading reading;
    reading.provider_id = "darwin_ioreport";
    reading.timestamp_ns = utils::PrecisionTimer::monotonic_timestamp_ns();

    if (!initialized_) {
        reading.confidence = 0.0;
        record_measurement_attempt(false);
        return reading;
    }

    std::lock_guard<std::mutex> lock(reading_mutex_);

    CFDictionaryRef current = create_samples_(sub_handle_, subbed_channels_, NULL);
    if (!current) {
        record_measurement_attempt(false);
        return reading;
    }

    CFDictionaryRef delta = create_samples_delta_(prev_sample_, current, NULL);
    if (!delta) {
        CFRelease(current);
        record_measurement_attempt(false);
        return reading;
    }

    // Each channel has its own unit (mJ, uJ, nJ) read via IOReportChannelGetUnitLabel.
    // Verified on M4: most channels "mJ", "GPU Energy" is "nJ".
    auto& domains_ref = domains_;
    auto get_name = channel_get_name_;
    auto get_unit = channel_get_unit_;
    auto get_int = simple_get_int_;
    iterate_(delta, ^(CFDictionaryRef ch) {
        std::string name = cfstr_to_std(get_name(ch));
        std::string domain = channel_to_domain(name);
        if (domain.empty()) return 0;

        std::string unit = get_unit ? cfstr_to_std(get_unit(ch)) : "mJ";
        int64_t raw = get_int(ch, 0);
        double delta_j = to_joules(raw, unit);

        if (delta_j < 0) delta_j = 0; // clamp: counter reset or sleep
        domains_ref[domain].cumulative_joules += delta_j;
        domains_ref[domain].last_delta_j = delta_j;
        return 0;
    });

    // Recompute every sample -- handles domains appearing after first sample.
    // O(N) with N~10 domains, negligible overhead vs IOReport snapshot cost.
    compute_top_level_domains();

    // All domains go into breakdown (users get full visibility for analysis)
    // Only top-level domains contribute to total (no double-counting)
    double total_j = 0;
    double delta_top_level_j = 0;
    for (auto& [d, acc] : domains_) {
        reading.domain_energy_joules[d] = acc.cumulative_joules;
        if (top_level_domains_.count(d)) {
            total_j += acc.cumulative_joules;
            delta_top_level_j += acc.last_delta_j;
        }
    }
    reading.energy_joules = total_j;

    double dt_s = (reading.timestamp_ns - last_ts_ns_) / 1e9;
    reading.average_power_watts = (dt_s > 0) ? delta_top_level_j / dt_s : 0;
    reading.instantaneous_power_watts = reading.average_power_watts;
    reading.source_type = "hardware_counter";
    reading.confidence = 0.95;
    reading.uncertainty_percent = 2.0;
    reading.sample_count = 1;

    CFRelease(prev_sample_);
    prev_sample_ = current;
    CFRelease(delta);
    last_ts_ns_ = reading.timestamp_ns;

    record_measurement_attempt(true);
    return reading;
}

EnergyProviderSpec DarwinIOReportProvider::get_specification() const {
    EnergyProviderSpec spec;
    spec.provider_name = "Darwin IOReport Energy";
    spec.hardware_type = "soc";
    spec.vendor = "apple";
    for (auto& [d, _] : domains_) spec.measurement_domains.push_back(d);
    spec.energy_resolution_joules = 1e-3; // millijoule resolution
    spec.min_measurement_interval = std::chrono::microseconds(2000);
    spec.typical_accuracy_percent = 2.0;
    spec.supports_temperature = false;
    spec.supports_frequency = false;
    return spec;
}

bool DarwinIOReportProvider::self_test() {
    if (!initialized_) return false;
    auto r1 = get_reading();
    usleep(200000);
    auto r2 = get_reading();
    if (r2.energy_joules <= r1.energy_joules) {
        std::cerr << " [darwin_ioreport] self_test: no energy delta after 200ms" << std::endl;
        return false;
    }
    return true;
}

bool DarwinIOReportProvider::is_available() const { return initialized_; }

void DarwinIOReportProvider::shutdown() {
    if (prev_sample_) { CFRelease(prev_sample_); prev_sample_ = nullptr; }
    if (subbed_channels_) { CFRelease(subbed_channels_); subbed_channels_ = nullptr; }
    // sub_handle_ is opaque, not a CF type -- do not CFRelease
    sub_handle_ = nullptr;
    if (lib_handle_) { dlclose(lib_handle_); lib_handle_ = nullptr; }
    initialized_ = false;
}

namespace {
    bool registered = []() {
        EnergyProvider::register_provider("darwin_ioreport", []() {
            return std::make_unique<DarwinIOReportProvider>();
        });
        return true;
    }();
}

} // namespace codegreen::nemb::drivers
#endif
