#pragma once
#ifdef __APPLE__

#include "../core/energy_provider.hpp"
#include <map>
#include <mutex>
#include <string>
#include <vector>

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

    // IOReport function pointers (resolved via dlsym from libIOReport.dylib)
    using CopyChannelsInGroupFn = void*(*)(void*, void*, uint64_t, uint64_t, uint64_t);
    using CopyAllChannelsFn = void*(*)(uint64_t, uint64_t);
    using CreateSamplesFn = void*(*)(void*, void*);
    using CreateSamplesDeltaFn = void*(*)(void*, void*, void*);
    using IterateFn = void(*)(void*, int(^)(void*));
    using ChannelGetGroupFn = void*(*)(void*);
    using ChannelGetSubGroupFn = void*(*)(void*);
    using ChannelGetChannelNameFn = void*(*)(void*);
    using SimpleGetIntegerValueFn = int64_t(*)(void*, int32_t);

    CopyChannelsInGroupFn copy_channels_in_group_{nullptr};
    CopyAllChannelsFn copy_all_channels_{nullptr};
    CreateSamplesFn create_samples_{nullptr};
    CreateSamplesDeltaFn create_samples_delta_{nullptr};
    IterateFn iterate_{nullptr};
    ChannelGetGroupFn channel_get_group_{nullptr};
    ChannelGetSubGroupFn channel_get_subgroup_{nullptr};
    ChannelGetChannelNameFn channel_get_name_{nullptr};
    SimpleGetIntegerValueFn simple_get_int_{nullptr};

    // Subscription and sample state
    void* subscription_{nullptr};
    void* prev_sample_{nullptr};

    // Accumulated energy per domain
    struct DomainAccumulator {
        double cumulative_joules{0.0};
    };
    std::map<std::string, DomainAccumulator> domains_;
    uint64_t last_ts_ns_{0};
    std::mutex reading_mutex_;
};

} // namespace codegreen::nemb::drivers
#endif // __APPLE__
