#pragma once
#ifdef __APPLE__

#include "../core/energy_provider.hpp"
#include <CoreFoundation/CoreFoundation.h>
#include <map>
#include <mutex>
#include <string>

namespace codegreen::nemb::drivers {

class DarwinIOReportProvider : public EnergyProvider {
public:
    DarwinIOReportProvider();
    ~DarwinIOReportProvider() override;

    bool initialize() override;
    EnergyReading get_reading() override;
    EnergyProviderSpec get_specification() const override;
    bool self_test() override;
    bool is_available() const override;
    void shutdown() override;
    std::string get_name() const override { return "Darwin IOReport Energy"; }

private:
    bool load_symbols();
    bool setup_subscription();

    void* lib_handle_{nullptr};
    bool initialized_{false};

    // Verified function signatures (tested on M4, macOS 25C56)
    using CopyChannelsInGroupFn = CFDictionaryRef(*)(CFStringRef, CFStringRef, CFTypeRef);
    using CreateSubscriptionFn = void*(*)(void*, CFDictionaryRef, CFMutableDictionaryRef*, uint64_t, CFTypeRef);
    using CreateSamplesFn = CFDictionaryRef(*)(void*, CFMutableDictionaryRef, CFTypeRef);
    using CreateSamplesDeltaFn = CFDictionaryRef(*)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
    using IterateFn = void(*)(CFDictionaryRef, int(^)(CFDictionaryRef));
    using ChannelGetGroupFn = CFStringRef(*)(CFDictionaryRef);
    using ChannelGetChannelNameFn = CFStringRef(*)(CFDictionaryRef);
    using SimpleGetIntegerValueFn = int64_t(*)(CFDictionaryRef, int32_t);

    CopyChannelsInGroupFn copy_channels_in_group_{nullptr};
    CreateSubscriptionFn create_subscription_{nullptr};
    CreateSamplesFn create_samples_{nullptr};
    CreateSamplesDeltaFn create_samples_delta_{nullptr};
    IterateFn iterate_{nullptr};
    ChannelGetGroupFn channel_get_group_{nullptr};
    ChannelGetChannelNameFn channel_get_name_{nullptr};
    SimpleGetIntegerValueFn simple_get_int_{nullptr};

    // Subscription state
    void* sub_handle_{nullptr};
    CFMutableDictionaryRef subbed_channels_{nullptr};
    CFDictionaryRef prev_sample_{nullptr};

    // Accumulated energy per domain
    struct DomainAccumulator { double cumulative_mj{0.0}; };
    std::map<std::string, DomainAccumulator> domains_;
    uint64_t last_ts_ns_{0};
    std::mutex reading_mutex_;
};

} // namespace codegreen::nemb::drivers
#endif
