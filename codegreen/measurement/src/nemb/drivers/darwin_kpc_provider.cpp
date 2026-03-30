#ifdef __APPLE__
#include "../../../include/nemb/drivers/darwin_kpc_provider.hpp"
#include <dlfcn.h>
#include <iostream>
#include <cstring>

#define KPC_CLASS_FIXED          0
#define KPC_CLASS_CONFIGURABLE   1
#define KPC_CLASS_FIXED_MASK     (1u << KPC_CLASS_FIXED)
#define KPC_CLASS_CONFIGURABLE_MASK (1u << KPC_CLASS_CONFIGURABLE)

namespace codegreen::nemb::drivers {

// Static member definitions
void* DarwinKPCProvider::kperf_handle_ = nullptr;
void* DarwinKPCProvider::kperfdata_handle_ = nullptr;
bool DarwinKPCProvider::initialized_ = false;
uint32_t DarwinKPCProvider::counter_count_ = 0;
int DarwinKPCProvider::cycles_slot_ = 0;
int DarwinKPCProvider::instructions_slot_ = 1;
int DarwinKPCProvider::branches_slot_ = -1;
int DarwinKPCProvider::branch_misses_slot_ = -1;
int DarwinKPCProvider::l1d_misses_slot_ = -1;
int DarwinKPCProvider::l2_misses_slot_ = -1;

// kpc function pointer types
using kpc_pmu_version_fn = uint32_t(*)();
using kpc_force_all_ctrs_set_fn = int(*)(int);
using kpc_set_counting_fn = int(*)(uint32_t);
using kpc_set_thread_counting_fn = int(*)(uint32_t);
using kpc_set_config_fn = int(*)(uint32_t, uint64_t*);
using kpc_get_thread_counters_fn = int(*)(int, uint32_t, uint64_t*);
using kpc_get_counter_count_fn = uint32_t(*)(uint32_t);
using kpc_get_config_count_fn = uint32_t(*)(uint32_t);

// kpep function pointer types
struct kpep_db;
struct kpep_event;
struct kpep_config;
using kpep_db_create_fn = int(*)(const char*, kpep_db**);
using kpep_db_free_fn = void(*)(kpep_db*);
using kpep_db_event_fn = int(*)(kpep_db*, const char*, kpep_event**);
using kpep_config_create_fn = int(*)(kpep_db*, kpep_config**);
using kpep_config_free_fn = void(*)(kpep_config*);
using kpep_config_add_event_fn = int(*)(kpep_config*, kpep_event**, uint32_t, uint32_t*);
using kpep_config_kpc_fn = int(*)(kpep_config*, uint64_t*, size_t);
using kpep_config_kpc_classes_fn = int(*)(kpep_config*, uint32_t*);
using kpep_config_kpc_map_fn = int(*)(kpep_config*, size_t*, size_t);
using kpep_config_force_counters_fn = int(*)(kpep_config*);

// Resolved function pointers
static kpc_pmu_version_fn s_pmu_version;
static kpc_force_all_ctrs_set_fn s_force_all_ctrs;
static kpc_set_counting_fn s_set_counting;
static kpc_set_thread_counting_fn s_set_thread_counting;
static kpc_set_config_fn s_set_config;
static kpc_get_thread_counters_fn s_get_thread_counters;
static kpc_get_counter_count_fn s_get_counter_count;
static kpc_get_config_count_fn s_get_config_count;
static kpep_db_create_fn s_db_create;
static kpep_db_free_fn s_db_free;
static kpep_db_event_fn s_db_event;
static kpep_config_create_fn s_config_create;
static kpep_config_free_fn s_config_free;
static kpep_config_add_event_fn s_config_add_event;
static kpep_config_kpc_fn s_config_kpc;
static kpep_config_kpc_classes_fn s_config_kpc_classes;
static kpep_config_kpc_map_fn s_config_kpc_map;
static kpep_config_force_counters_fn s_config_force_counters;

template<typename T>
static bool load_sym(void* h, const char* name, T& out) {
    out = (T)dlsym(h, name);
    return out != nullptr;
}

bool DarwinKPCProvider::load_symbols() {
    kperf_handle_ = dlopen("/System/Library/PrivateFrameworks/kperf.framework/kperf", RTLD_LAZY);
    kperfdata_handle_ = dlopen("/System/Library/PrivateFrameworks/kperfdata.framework/kperfdata", RTLD_LAZY);
    if (!kperf_handle_) {
        std::cerr << " [darwin_kpc] kperf.framework: " << dlerror() << std::endl;
        return false;
    }
    if (!kperfdata_handle_) {
        std::cerr << " [darwin_kpc] kperfdata.framework: " << dlerror() << std::endl;
        return false;
    }

    bool ok = true;
    ok &= load_sym(kperf_handle_, "kpc_pmu_version", s_pmu_version);
    ok &= load_sym(kperf_handle_, "kpc_force_all_ctrs_set", s_force_all_ctrs);
    ok &= load_sym(kperf_handle_, "kpc_set_counting", s_set_counting);
    ok &= load_sym(kperf_handle_, "kpc_set_thread_counting", s_set_thread_counting);
    ok &= load_sym(kperf_handle_, "kpc_set_config", s_set_config);
    ok &= load_sym(kperf_handle_, "kpc_get_thread_counters", s_get_thread_counters);
    ok &= load_sym(kperf_handle_, "kpc_get_counter_count", s_get_counter_count);
    ok &= load_sym(kperf_handle_, "kpc_get_config_count", s_get_config_count);
    ok &= load_sym(kperfdata_handle_, "kpep_db_create", s_db_create);
    ok &= load_sym(kperfdata_handle_, "kpep_db_free", s_db_free);
    ok &= load_sym(kperfdata_handle_, "kpep_db_event", s_db_event);
    ok &= load_sym(kperfdata_handle_, "kpep_config_create", s_config_create);
    ok &= load_sym(kperfdata_handle_, "kpep_config_free", s_config_free);
    ok &= load_sym(kperfdata_handle_, "kpep_config_add_event", s_config_add_event);
    ok &= load_sym(kperfdata_handle_, "kpep_config_kpc", s_config_kpc);
    ok &= load_sym(kperfdata_handle_, "kpep_config_kpc_classes", s_config_kpc_classes);
    ok &= load_sym(kperfdata_handle_, "kpep_config_kpc_map", s_config_kpc_map);
    ok &= load_sym(kperfdata_handle_, "kpep_config_force_counters", s_config_force_counters);
    return ok;
}

bool DarwinKPCProvider::configure_default_events() {
    kpep_db* db = nullptr;
    if (s_db_create(nullptr, &db) != 0 || !db) return false;

    kpep_config* cfg = nullptr;
    if (s_config_create(db, &cfg) != 0 || !cfg) { s_db_free(db); return false; }

    // Events to configure (Apple Silicon names, with fallbacks)
    struct EventDef { const char* primary; const char* fallback; int* slot; };
    EventDef events[] = {
        {"FIXED_CYCLES", nullptr, &cycles_slot_},
        {"FIXED_INSTRUCTIONS", nullptr, &instructions_slot_},
        {"INST_BRANCH", nullptr, &branches_slot_},
        {"BRANCH_MISPRED_NONSPEC", "BRANCH_MISPREDICT", &branch_misses_slot_},
        {"L1D_CACHE_MISS_LD_NONSPEC", "L1D_CACHE_MISS_LD", &l1d_misses_slot_},
        {"L2_CACHE_MISS_DATA", nullptr, &l2_misses_slot_},
    };

    int n_added = 0;
    for (auto& e : events) {
        kpep_event* ev = nullptr;
        if (s_db_event(db, e.primary, &ev) != 0 || !ev) {
            if (e.fallback && s_db_event(db, e.fallback, &ev) == 0 && ev) {
                // fallback found
            } else {
                *e.slot = -1;
                continue;
            }
        }
        uint32_t idx = 0;
        if (s_config_add_event(cfg, &ev, 0, &idx) == 0) {
            n_added++;
        } else {
            *e.slot = -1;
        }
    }

    if (n_added < 2) { // Need at least cycles + instructions
        s_config_free(cfg);
        s_db_free(db);
        return false;
    }

    s_config_force_counters(cfg);

    // Get KPC register configuration
    uint32_t classes = 0;
    s_config_kpc_classes(cfg, &classes);

    uint32_t config_count = s_get_config_count(classes);
    std::vector<uint64_t> kpc_config(config_count, 0);
    s_config_kpc(cfg, kpc_config.data(), config_count * sizeof(uint64_t));

    // Get counter mapping
    counter_count_ = s_get_counter_count(classes);
    std::vector<size_t> map(counter_count_, 0);
    s_config_kpc_map(cfg, map.data(), counter_count_ * sizeof(size_t));

    // Map event index -> counter slot
    int event_idx = 0;
    for (auto& e : events) {
        if (*e.slot != -1 && event_idx < (int)map.size()) {
            *e.slot = (int)map[event_idx];
        }
        if (*e.slot != -1) event_idx++;
    }

    // Apply configuration
    s_force_all_ctrs(1);
    s_set_config(classes, kpc_config.data());
    s_set_counting(classes);
    s_set_thread_counting(classes);

    // 1ms delay for counters to initialize (from mperf)
    usleep(1000);

    s_config_free(cfg);
    s_db_free(db);
    return true;
}

bool DarwinKPCProvider::initialize() {
    if (initialized_) return true;
    if (!load_symbols()) return false;

    uint32_t pmu_ver = s_pmu_version();
    if (pmu_ver == 0) {
        std::cerr << " [darwin_kpc] PMU version 0 (insufficient privileges, need root)" << std::endl;
        return false;
    }

    if (!configure_default_events()) return false;

    initialized_ = true;
    std::cout << " Darwin KPC perf counter provider initialized (PMU v" << pmu_ver << ")" << std::endl;
    std::cout << " Counters: " << counter_count_ << " (2 fixed + "
              << (counter_count_ - 2) << " configurable)" << std::endl;
    return true;
}

void DarwinKPCProvider::shutdown() {
    if (!initialized_) return;
    uint32_t classes = KPC_CLASS_FIXED_MASK | KPC_CLASS_CONFIGURABLE_MASK;
    s_set_counting(0);
    s_set_thread_counting(0);
    s_force_all_ctrs(0);
    if (kperf_handle_) { dlclose(kperf_handle_); kperf_handle_ = nullptr; }
    if (kperfdata_handle_) { dlclose(kperfdata_handle_); kperfdata_handle_ = nullptr; }
    initialized_ = false;
}

bool DarwinKPCProvider::is_available() { return initialized_; }

KPCCounterSnapshot DarwinKPCProvider::read_thread_counters() {
    KPCCounterSnapshot snap;
    if (!initialized_) return snap;

    snap.num_counters = counter_count_;
    s_get_thread_counters(0, counter_count_, snap.raw.data());

    if (cycles_slot_ >= 0) snap.cycles = snap.raw[cycles_slot_];
    if (instructions_slot_ >= 0) snap.instructions = snap.raw[instructions_slot_];
    if (branches_slot_ >= 0) snap.branches = snap.raw[branches_slot_];
    if (branch_misses_slot_ >= 0) snap.branch_misses = snap.raw[branch_misses_slot_];
    if (l1d_misses_slot_ >= 0) snap.l1d_cache_misses = snap.raw[l1d_misses_slot_];
    if (l2_misses_slot_ >= 0) snap.l2_cache_misses = snap.raw[l2_misses_slot_];
    return snap;
}

std::string DarwinKPCProvider::get_pmu_name() {
    if (!s_pmu_version) return "unknown";
    uint32_t v = s_pmu_version();
    if (v == 2) return "ARM_APPLE";
    if (v == 4) return "ARM_V2";
    return "PMUv" + std::to_string(v);
}

} // namespace codegreen::nemb::drivers
#endif // __APPLE__
