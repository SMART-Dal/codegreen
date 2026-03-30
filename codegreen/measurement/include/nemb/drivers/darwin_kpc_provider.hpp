#pragma once
#ifdef __APPLE__

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace codegreen::nemb::drivers {

struct KPCCounterSnapshot {
    uint64_t cycles{0};
    uint64_t instructions{0};
    uint64_t branches{0};
    uint64_t branch_misses{0};
    uint64_t l1d_cache_misses{0};
    uint64_t l2_cache_misses{0};
    static constexpr int MAX_COUNTERS = 10; // 2 fixed + 8 configurable
    std::array<uint64_t, MAX_COUNTERS> raw{};
    uint8_t num_counters{0};
    double ipc() const { return cycles > 0 ? double(instructions) / cycles : 0; }
};

class DarwinKPCProvider {
public:
    static bool initialize();
    static void shutdown();
    static bool is_available();
    static KPCCounterSnapshot read_thread_counters();
    static std::string get_pmu_name();

private:
    static bool load_symbols();
    static bool configure_default_events();
    static void* kperf_handle_;
    static void* kperfdata_handle_;
    static bool initialized_;
    static uint32_t counter_count_;

    // Event-to-counter mapping (from kpep_config_kpc_map)
    static int cycles_slot_;
    static int instructions_slot_;
    static int branches_slot_;
    static int branch_misses_slot_;
    static int l1d_misses_slot_;
    static int l2_misses_slot_;
};

} // namespace codegreen::nemb::drivers
#endif // __APPLE__
