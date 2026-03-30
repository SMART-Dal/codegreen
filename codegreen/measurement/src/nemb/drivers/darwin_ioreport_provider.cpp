#ifdef __APPLE__
#include "../../../include/nemb/drivers/darwin_ioreport_provider.hpp"
#include "../../../include/nemb/utils/precision_timer.hpp"
#include <dlfcn.h>
#include <iostream>
#include <unistd.h>
#include <CoreFoundation/CoreFoundation.h>

namespace codegreen::nemb::drivers {

static CFStringRef to_cfstr(const char* s) { return CFStringCreateWithCString(nullptr, s, kCFStringEncodingUTF8); }
static std::string from_cfstr(CFStringRef s) {
    if (!s) return "";
    char buf[256];
    if (CFStringGetCString(s, buf, sizeof(buf), kCFStringEncodingUTF8)) return buf;
    return "";
}

DarwinIOReportProvider::DarwinIOReportProvider() = default;

DarwinIOReportProvider::~DarwinIOReportProvider() { shutdown(); }

bool DarwinIOReportProvider::load_symbols() {
    lib_handle_ = dlopen("libIOReport.dylib", RTLD_LAZY);
    if (!lib_handle_) {
        std::cerr << " [darwin_ioreport] dlopen failed: " << dlerror() << std::endl;
        return false;
    }

    copy_channels_in_group_ = (CopyChannelsInGroupFn)dlsym(lib_handle_, "IOReportCopyChannelsInGroup");
    copy_all_channels_ = (CopyAllChannelsFn)dlsym(lib_handle_, "IOReportCopyAllChannels");
    create_samples_ = (CreateSamplesFn)dlsym(lib_handle_, "IOReportCreateSamples");
    create_samples_delta_ = (CreateSamplesDeltaFn)dlsym(lib_handle_, "IOReportCreateSamplesDelta");
    iterate_ = (IterateFn)dlsym(lib_handle_, "IOReportIterate");
    channel_get_group_ = (ChannelGetGroupFn)dlsym(lib_handle_, "IOReportChannelGetGroup");
    channel_get_subgroup_ = (ChannelGetSubGroupFn)dlsym(lib_handle_, "IOReportChannelGetSubGroup");
    channel_get_name_ = (ChannelGetChannelNameFn)dlsym(lib_handle_, "IOReportChannelGetChannelName");
    simple_get_int_ = (SimpleGetIntegerValueFn)dlsym(lib_handle_, "IOReportSimpleGetIntegerValue");

    if (!create_samples_ || !create_samples_delta_ || !iterate_ ||
        !channel_get_group_ || !simple_get_int_) {
        std::cerr << " [darwin_ioreport] missing symbols: "
                  << (!create_samples_ ? "CreateSamples " : "")
                  << (!create_samples_delta_ ? "CreateSamplesDelta " : "")
                  << (!iterate_ ? "Iterate " : "")
                  << (!channel_get_group_ ? "ChannelGetGroup " : "")
                  << (!simple_get_int_ ? "SimpleGetIntegerValue " : "")
                  << std::endl;
        return false;
    }
    return true;
}

bool DarwinIOReportProvider::setup_subscription() {
    CFStringRef group = to_cfstr("Energy Model");
    subscription_ = copy_channels_in_group_(group, nullptr, 0, 0, 0);
    CFRelease(group);

    if (!subscription_) {
        std::cerr << " [darwin_ioreport] 'Energy Model' channel group not found, "
                  "trying all channels (requires root)" << std::endl;
        if (copy_all_channels_)
            subscription_ = copy_all_channels_(0, 0);
    }
    if (!subscription_) {
        std::cerr << " [darwin_ioreport] no IOReport channels available "
                  "(are you running as root?)" << std::endl;
        return false;
    }

    prev_sample_ = create_samples_(subscription_, nullptr);
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
    std::cout << " Darwin IOReport energy provider initialized" << std::endl;
    return true;
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

    void* current = create_samples_(subscription_, nullptr);
    if (!current) {
        record_measurement_attempt(false);
        return reading;
    }

    void* delta = create_samples_delta_(prev_sample_, current, nullptr);
    if (!delta) {
        CFRelease(current);
        record_measurement_attempt(false);
        return reading;
    }

    double dt_s = (reading.timestamp_ns - last_ts_ns_) / 1e9;
    if (dt_s <= 0) dt_s = 0.001; // Guard against zero

    double total_power_mw = 0;

    iterate_(delta, ^(void* ch) {
        CFStringRef group_cf = (CFStringRef)channel_get_group_(ch);
        std::string group = from_cfstr(group_cf);
        if (group != "Energy Model") return 0; // skip non-energy channels

        CFStringRef name_cf = (CFStringRef)channel_get_name_(ch);
        std::string name = from_cfstr(name_cf);

        int64_t value = simple_get_int_(ch, 0);
        double power_mw = static_cast<double>(value);
        total_power_mw += power_mw;

        // Map channel names to domains
        std::string domain;
        if (name.find("CPU") != std::string::npos) domain = "cpu";
        else if (name.find("GPU") != std::string::npos) domain = "gpu";
        else if (name.find("ANE") != std::string::npos) domain = "ane";
        else if (name.find("DRAM") != std::string::npos) domain = "dram";
        else domain = "other";

        double energy_j = (power_mw / 1000.0) * dt_s;
        domains_[domain].cumulative_joules += energy_j;
        reading.domain_energy_joules[domain] = domains_[domain].cumulative_joules;
        reading.domain_power_watts[domain] = power_mw / 1000.0;
        return 0;
    });

    double total_cumulative = 0;
    for (auto& [d, acc] : domains_) total_cumulative += acc.cumulative_joules;

    reading.energy_joules = total_cumulative;
    reading.average_power_watts = total_power_mw / 1000.0;
    reading.instantaneous_power_watts = total_power_mw / 1000.0;
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
    spec.measurement_domains = {"cpu", "gpu", "ane", "dram"};
    spec.energy_resolution_joules = 1e-6;
    spec.min_measurement_interval = std::chrono::microseconds(2000);
    spec.typical_accuracy_percent = 2.0;
    spec.supports_temperature = false;
    spec.supports_frequency = false;
    return spec;
}

bool DarwinIOReportProvider::self_test() {
    if (!initialized_) return false;
    auto r1 = get_reading();
    usleep(200000); // 200ms
    auto r2 = get_reading();
    return r2.energy_joules > r1.energy_joules;
}

bool DarwinIOReportProvider::is_available() const { return initialized_; }

void DarwinIOReportProvider::shutdown() {
    if (prev_sample_) { CFRelease(prev_sample_); prev_sample_ = nullptr; }
    if (subscription_) { CFRelease(subscription_); subscription_ = nullptr; }
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
#endif // __APPLE__
