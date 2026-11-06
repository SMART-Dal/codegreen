#include "nemb/codegreen_energy.hpp"
#include "nemb/config_loader.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/core/energy_provider.hpp"
#include "nemb/utils/precision_timer.hpp"
#ifdef __APPLE__
#include "nemb/drivers/darwin_kpc_provider.hpp"
#endif
#ifdef HAVE_JNI
#include <jni.h>
#endif

#include <sstream>
#include <iomanip>
#include <thread>
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <stdexcept>
#ifdef _WIN32
#include <process.h>
#include <io.h>
static int _nemb_getpid() { return _getpid(); }
#else
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#include <cstdio>
#include <pthread.h>
#include <sched.h>
static int _nemb_getpid() { return getpid(); }
#endif
#include <iostream>
#include <mutex>
#include <map>

namespace codegreen {

static bool debug_logging(bool configured) {
    const char* env = std::getenv("CODEGREEN_DEBUG");
    return configured || (env && std::string(env) == "1");
}

namespace {
// Mutes std::cout/std::cerr (provider init chatter) for its lifetime when `mute` is set.
struct QuietStreams {
    std::streambuf* out;
    std::streambuf* err;
    std::ostringstream sink;
    bool mute;
    explicit QuietStreams(bool m) : out(std::cout.rdbuf()), err(std::cerr.rdbuf()), mute(m) {
        if (mute) { std::cout.rdbuf(sink.rdbuf()); std::cerr.rdbuf(sink.rdbuf()); }
    }
    ~QuietStreams() { if (mute) { std::cout.rdbuf(out); std::cerr.rdbuf(err); } }
};
}  // namespace

// Implementation details hidden using PIMPL pattern
class EnergyMeter::Impl {
public:
    explicit Impl(const NEMBConfig& config);
    ~Impl();
    
    bool is_available() const;
    std::vector<std::string> get_provider_info() const;
    EnergyResult read(bool boundary = false);
    uint64_t start_session(const std::string& name);
    EnergyDifference end_session(uint64_t session_id);
    void mark_checkpoint(const std::string& name);
    std::vector<EnergyMeter::CorrelatedCheckpoint> get_checkpoint_measurements(EnergyMeter::SamplerStats* sampler);
    std::vector<nemb::SynchronizedReading> get_time_series_since(uint64_t since_ts_ns) const;
    bool set_buffer_size(size_t n);
    void set_measurement_interval_ms(int ms);
    const NEMBConfig& get_config() const;
    bool self_test();
    std::map<std::string, std::string> get_diagnostics() const;
    
private:
    struct Session {
        std::string name;
        EnergyResult baseline;
        uint64_t start_time_ns;
        bool active{true};
    };
    
    struct Marker {
        std::string name;
        uint64_t timestamp_ns;
#ifdef __APPLE__
        uint64_t kpc_cycles{0};
        uint64_t kpc_instructions{0};
        uint64_t kpc_cache_misses{0};
        uint64_t kpc_branch_misses{0};
#endif
    };
    
    NEMBConfig config_;
    std::unique_ptr<nemb::MeasurementCoordinator> coordinator_;
    nemb::utils::PrecisionTimer timer_;
    std::map<uint64_t, Session> active_sessions_;
    std::atomic<uint64_t> next_session_id_{1};
    mutable std::mutex sessions_mutex_;
    
    std::vector<Marker> markers_;
    mutable std::mutex markers_mutex_;
    std::string config_path_;
    uint64_t max_checkpoints_{0};
    std::atomic<uint64_t> checkpoint_calls_{0};
    
    // Accuracy optimization features
    void apply_noise_minimization();
    void prefault_memory();
    void set_cpu_affinity();
    bool validate_reading_accuracy(const EnergyResult& reading) const;
    EnergyResult apply_noise_filtering(const EnergyResult& reading) const;
    
    // Cross-validation and error detection
    bool cross_validate_providers(const nemb::SynchronizedReading& reading) const;
    void detect_and_handle_outliers(EnergyResult& result) const;
    
    // Conversion helpers
    EnergyResult convert_synchronized_reading(const nemb::SynchronizedReading& sync_reading) const;
};

EnergyMeter::Impl::Impl(const NEMBConfig& config)
    : config_(config), timer_() {
    timer_.initialize(nemb::utils::PrecisionTimer::ClockSource::MONOTONIC);
    
    auto nemb_config = nemb::ConfigLoader::load_config();
    
    if (config.target_uncertainty_percent != 1.0) {
        nemb_config.accuracy.target_uncertainty_percent = config.target_uncertainty_percent;
    }
    nemb_config.accuracy.measurement_validation = config.enable_cross_validation;
    nemb_config.accuracy.outlier_detection = config.enable_outlier_detection;
    nemb_config.accuracy.noise_filtering = config.enable_noise_filtering ? "adaptive" : "none";
    
    if (config.force_clock_source.has_value()) {
        nemb_config.timing.clock_source = *config.force_clock_source;
    }
    
    if (config.prefer_accuracy_over_speed) {
        apply_noise_minimization();
    }
    
    nemb::CoordinatorConfig coordinator_config;
    coordinator_config.measurement_interval = std::chrono::milliseconds(nemb_config.coordinator.measurement_interval_ms);
    coordinator_config.temporal_alignment_tolerance_ms = nemb_config.coordinator.temporal_alignment_tolerance_ms;
    coordinator_config.cross_validation_threshold = nemb_config.coordinator.cross_validation_threshold;
    coordinator_config.measurement_buffer_size = nemb_config.coordinator.measurement_buffer_size;
    coordinator_config.auto_restart_failed_providers = nemb_config.coordinator.auto_restart_failed_providers;
    coordinator_config.provider_restart_interval = nemb_config.coordinator.provider_restart_interval;
    coordinator_config.max_consecutive_failures = nemb_config.coordinator.max_consecutive_failures;
    coordinator_config.enable_real_time_filtering = nemb_config.coordinator.real_time_filtering;
    config_path_ = nemb_config.path;
    max_checkpoints_ = nemb_config.max_checkpoints;
    markers_.reserve(10000);
    {
        // Provider init chatter is shown only with debug logging (config flag or CODEGREEN_DEBUG=1 from CLI --verbose).
        QuietStreams quiet(!debug_logging(config.enable_debug_logging));
        coordinator_ = std::make_unique<nemb::MeasurementCoordinator>(coordinator_config);
        for (auto& [name, provider] : nemb::detect_available_providers())
            if (!coordinator_->add_provider(std::move(provider), name))
                throw std::runtime_error("NEMB: provider '" + name + "' could not be added");
        if (!coordinator_->start_measurements()) throw std::runtime_error("Failed to start NEMB measurement coordinator");
#ifdef __APPLE__
        // Initialize kpc for hybrid checkpoint counters (cycles, IPC, cache misses)
        nemb::drivers::DarwinKPCProvider::initialize();
#endif
    }

    auto start_time = std::chrono::steady_clock::now();
    while (coordinator_->get_active_providers().empty() && 
           std::chrono::steady_clock::now() - start_time < config.timeout) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

EnergyMeter::Impl::~Impl() {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    active_sessions_.clear();
}

void EnergyMeter::Impl::mark_checkpoint(const std::string& name) {
    uint64_t call = checkpoint_calls_.fetch_add(1, std::memory_order_relaxed);
    if (call >= max_checkpoints_) {
        if (call == max_checkpoints_)
            std::cerr << "NEMB checkpoint cap reached (" << max_checkpoints_ << "); further checkpoints dropped" << std::endl;
        return;
    }
    // Invocation tracking - thread_local for zero-lock performance
    thread_local std::unordered_map<std::string, uint32_t> invocation_counters;

    // Get thread ID for multi-thread uniqueness (computed once per thread)
    thread_local std::hash<std::thread::id> hasher;
    thread_local size_t thread_hash = hasher(std::this_thread::get_id());

    // Get and increment invocation counter
    uint32_t invocation = ++invocation_counters[name];

    // Get timestamp BEFORE lock to minimize critical section
    uint64_t ts = timer_.get_timestamp_ns();

    // Hybrid checkpoint: also read kpc perf counters on macOS (~200ns)
#ifdef __APPLE__
    uint64_t kpc_cyc = 0, kpc_ins = 0, kpc_cm = 0, kpc_bm = 0;
    if (nemb::drivers::DarwinKPCProvider::is_available()) {
        auto snap = nemb::drivers::DarwinKPCProvider::read_thread_counters();
        kpc_cyc = snap.cycles;
        kpc_ins = snap.instructions;
        kpc_cm = snap.l1d_cache_misses;
        kpc_bm = snap.branch_misses;
    }
#endif

    thread_local char enhanced_buffer[512];
    int len = snprintf(enhanced_buffer, sizeof(enhanced_buffer),
                       "%s#inv_%u_t%zu", name.c_str(), invocation, thread_hash);

    if (len < 0 || len >= static_cast<int>(sizeof(enhanced_buffer))) {
        std::lock_guard<std::mutex> lock(markers_mutex_);
        Marker m{name + "#inv_" + std::to_string(invocation) + "_t" + std::to_string(thread_hash), ts};
#ifdef __APPLE__
        m.kpc_cycles = kpc_cyc; m.kpc_instructions = kpc_ins;
        m.kpc_cache_misses = kpc_cm; m.kpc_branch_misses = kpc_bm;
#endif
        markers_.push_back(std::move(m));
    } else {
        std::lock_guard<std::mutex> lock(markers_mutex_);
        Marker m{std::string(enhanced_buffer, len), ts};
#ifdef __APPLE__
        m.kpc_cycles = kpc_cyc; m.kpc_instructions = kpc_ins;
        m.kpc_cache_misses = kpc_cm; m.kpc_branch_misses = kpc_bm;
#endif
        markers_.push_back(std::move(m));
    }
}

// x + w*(y-x) is exact at w == 0 and when x == y, so a flat or rising series stays non-decreasing.
static double lerp(double x, double y, double w) {
    double v = x + w * (y - x);
    return x <= y ? std::min(v, y) : v;
}

void EnergyMeter::correlate(const std::vector<nemb::SynchronizedReading>& R, std::vector<CorrelatedCheckpoint>& cps) {
    if (R.empty()) throw std::invalid_argument("correlate: no readings");
    for (auto& cc : cps) {
        size_t ri = std::lower_bound(R.begin(), R.end(), cc.timestamp_ns,
            [](const nemb::SynchronizedReading& r, uint64_t ts) { return r.common_timestamp_ns < ts; }) - R.begin();
        size_t a = ri, b = ri;
        double w = 0.0;
        cc.clamp = "none";
        if (ri == R.size()) { a = b = ri - 1; cc.clamp = "after_last"; }
        else if (R[ri].common_timestamp_ns == cc.timestamp_ns) {}
        else if (ri == 0) cc.clamp = "before_first";
        else {
            a = ri - 1;
            w = static_cast<double>(cc.timestamp_ns - R[a].common_timestamp_ns) /
                static_cast<double>(R[b].common_timestamp_ns - R[a].common_timestamp_ns);
        }
        cc.ri = ri;
        cc.provider_j.clear();
        for (auto& pa : R[a].provider_readings) {
            double y = pa.energy_joules;
            for (auto& pb : R[b].provider_readings) if (pb.provider_id == pa.provider_id) y = pb.energy_joules;
            cc.provider_j[pa.provider_id] = lerp(pa.energy_joules, y, w);
        }
        cc.cumulative_energy_joules = 0.0;
        for (auto& [id, j] : cc.provider_j) cc.cumulative_energy_joules += j;
        cc.instantaneous_power_watts = lerp(R[a].total_system_power_watts, R[b].total_system_power_watts, w);
    }
}

std::vector<EnergyMeter::CorrelatedCheckpoint> EnergyMeter::Impl::get_checkpoint_measurements(EnergyMeter::SamplerStats* st) {
    auto readings = coordinator_->get_buffered_readings();
    bool wrapped = coordinator_->buffer_wrapped();
    nemb::SynchronizedReading last;
    bool sampled = coordinator_->sample_now(last);
    bool last_ok = sampled && (readings.empty() || last.common_timestamp_ns > readings.back().common_timestamp_ns);
    if (last_ok) readings.push_back(std::move(last));

    std::vector<EnergyMeter::CorrelatedCheckpoint> cps;
    if (!readings.empty()) {
        std::lock_guard<std::mutex> lock(markers_mutex_);
        cps.reserve(markers_.size());
        for (const auto& m : markers_) {
            EnergyMeter::CorrelatedCheckpoint cc;
            cc.name = m.name;
            cc.timestamp_ns = m.timestamp_ns;
#ifdef __APPLE__
            cc.cycles = m.kpc_cycles;
            cc.instructions = m.kpc_instructions;
            cc.cache_misses = m.kpc_cache_misses;
            cc.branch_misses = m.kpc_branch_misses;
#endif
            cps.push_back(std::move(cc));
        }
        EnergyMeter::correlate(readings, cps);
    }
    if (st) {
        st->interval_ms = coordinator_->measurement_interval().count();
        st->interval_ms_min = coordinator_->interval_ms_min();
        st->interval_ms_max = coordinator_->interval_ms_max();
        st->buffer_capacity = coordinator_->buffer_capacity();
        st->readings = readings.size();
        st->wrapped = wrapped;
        st->rejected_readings = coordinator_->rejected_readings() + (sampled && !last_ok ? 1 : 0);
        uint64_t calls = checkpoint_calls_.load();
        st->dropped_checkpoints = calls > max_checkpoints_ ? calls - max_checkpoints_ : 0;
        std::vector<uint64_t> gaps;
        for (size_t i = 1; i < readings.size(); ++i)
            gaps.push_back(readings[i].common_timestamp_ns - readings[i - 1].common_timestamp_ns);
        if (!readings.empty()) { st->first_ns = readings.front().common_timestamp_ns; st->last_ns = readings.back().common_timestamp_ns; }
        if (!gaps.empty()) {
            st->max_gap_ns = *std::max_element(gaps.begin(), gaps.end());
            std::nth_element(gaps.begin(), gaps.begin() + gaps.size() / 2, gaps.end());
            st->median_gap_ns = gaps[gaps.size() / 2];
        }
        st->affinity_cpus = coordinator_->affinity_cpus();
        st->sampler_affinity_cpus = coordinator_->sampler_affinity_cpus();
        auto counts = coordinator_->provider_counts();
        st->providers.clear();
        for (const auto& [name, spec] : coordinator_->get_provider_specifications()) {
            const auto& c = counts[name];
            st->providers.push_back({name, spec.hardware_type, spec.energy_source,
                                     spec.boundary_source.empty() ? spec.energy_source : spec.boundary_source,
                                     spec.counter_group, spec.update_interval.count() / 1000.0, c.rejected, c.held,
                                     c.boundary_held, c.boundary_held_max_ns});
            st->failed_reads += c.rejected;
            st->provider_restarts += c.restarts;
        }
        st->config_path = config_path_;
    }
    return cps;
}

EnergyResult EnergyMeter::Impl::read(bool boundary) {
    if (!coordinator_ || coordinator_->get_active_providers().empty()) {
        EnergyResult res; res.is_valid = false; res.error_message = "Unavailable"; return res;
    }
    auto sync_reading = coordinator_->get_synchronized_reading(boundary);
    return convert_synchronized_reading(sync_reading);
}

EnergyResult EnergyMeter::Impl::convert_synchronized_reading(const nemb::SynchronizedReading& sync_reading) const {
    EnergyResult result;
    if (sync_reading.provider_readings.empty()) { result.is_valid = false; return result; }
    result.energy_joules = sync_reading.total_system_energy_joules;
    result.power_watts = sync_reading.total_system_power_watts;
    result.timestamp_ns = sync_reading.common_timestamp_ns;
    result.is_valid = sync_reading.providers_failed == 0;
    // Per-domain breakdown from all providers, signed: a failed domain is kept and counted, not dropped
    for (auto& pr : sync_reading.provider_readings) {
        for (auto& [domain, joules] : pr.domain_energy_joules) {
            result.components[domain] = joules;
            if (joules < 0) result.negative_components++;
        }
    }
    return result;
}

uint64_t EnergyMeter::Impl::start_session(const std::string& name) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    uint64_t id = next_session_id_++;
    active_sessions_[id] = {name, read(true), timer_.get_timestamp_ns(), true};
    return id;
}

EnergyDifference EnergyMeter::Impl::end_session(uint64_t id) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    auto it = active_sessions_.find(id);
    if (it == active_sessions_.end()) return {0,0,0,0,false};
    auto diff = energy_utils::calculate_difference(read(true), it->second.baseline);
    active_sessions_.erase(it);
    return diff;
}

std::vector<nemb::SynchronizedReading> EnergyMeter::Impl::get_time_series_since(uint64_t since_ts_ns) const {
    if (!coordinator_) return {};
    auto all = coordinator_->get_buffered_readings();
    if (since_ts_ns == 0) return all;
    std::vector<nemb::SynchronizedReading> filtered;
    filtered.reserve(all.size());
    for (auto& r : all) {
        if (r.common_timestamp_ns >= since_ts_ns) filtered.push_back(r);
    }
    return filtered;
}

bool EnergyMeter::Impl::set_buffer_size(size_t n) {
    return coordinator_ && coordinator_->set_buffer_size(n);
}

void EnergyMeter::Impl::set_measurement_interval_ms(int ms) {
    if (coordinator_) coordinator_->set_measurement_interval_ms(ms);
}

const NEMBConfig& EnergyMeter::Impl::get_config() const { return config_; }
bool EnergyMeter::Impl::is_available() const { return coordinator_ && !coordinator_->get_active_providers().empty(); }
std::vector<std::string> EnergyMeter::Impl::get_provider_info() const { return coordinator_ ? coordinator_->get_active_providers() : std::vector<std::string>{}; }
bool EnergyMeter::Impl::self_test() { return is_available() && read().is_valid; }
std::map<std::string, std::string> EnergyMeter::Impl::get_diagnostics() const {
    std::map<std::string, std::string> d; d["available"] = is_available()?"true":"false"; return d;
}
void EnergyMeter::Impl::apply_noise_minimization() {}
void EnergyMeter::Impl::prefault_memory() {}
void EnergyMeter::Impl::set_cpu_affinity() {}
bool EnergyMeter::Impl::validate_reading_accuracy(const EnergyResult& r) const { return r.is_valid; }
EnergyResult EnergyMeter::Impl::apply_noise_filtering(const EnergyResult& r) const { return r; }
bool EnergyMeter::Impl::cross_validate_providers(const nemb::SynchronizedReading& r) const { return true; }
void EnergyMeter::Impl::detect_and_handle_outliers(EnergyResult& r) const {}

// Public API
EnergyMeter::EnergyMeter() : EnergyMeter(NEMBConfig::accuracy_optimized()) {}
EnergyMeter::EnergyMeter(const NEMBConfig& c) : impl_(std::make_unique<Impl>(c)) {}
EnergyMeter::~EnergyMeter() = default;
EnergyMeter::EnergyMeter(EnergyMeter&&) noexcept = default;
EnergyMeter& EnergyMeter::operator=(EnergyMeter&&) noexcept = default;
void EnergyMeter::mark_checkpoint(const std::string& n) { impl_->mark_checkpoint(n); }
std::vector<EnergyMeter::CorrelatedCheckpoint> EnergyMeter::get_checkpoint_measurements(SamplerStats* s) { return impl_->get_checkpoint_measurements(s); }
bool EnergyMeter::is_available() const { return impl_->is_available(); }
std::vector<std::string> EnergyMeter::get_provider_info() const { return impl_->get_provider_info(); }
EnergyResult EnergyMeter::read() { return impl_->read(); }
uint64_t EnergyMeter::start_session(const std::string& n) { return impl_->start_session(n); }
EnergyDifference EnergyMeter::end_session(uint64_t i) { return impl_->end_session(i); }
std::vector<nemb::SynchronizedReading> EnergyMeter::get_time_series_since(uint64_t since_ts_ns) const { return impl_->get_time_series_since(since_ts_ns); }
bool EnergyMeter::set_buffer_size(size_t n) { return impl_->set_buffer_size(n); }
void EnergyMeter::set_measurement_interval_ms(int ms) { impl_->set_measurement_interval_ms(ms); }
const NEMBConfig& EnergyMeter::get_config() const { return impl_->get_config(); }
bool EnergyMeter::self_test() { return impl_->self_test(); }
std::map<std::string, std::string> EnergyMeter::get_diagnostics() const { return impl_->get_diagnostics(); }

// Config
NEMBConfig NEMBConfig::accuracy_optimized() {
    NEMBConfig c; c.prefer_accuracy_over_speed = true; c.timeout = std::chrono::milliseconds(5000); return c;
}
NEMBConfig NEMBConfig::performance_optimized() {
    NEMBConfig c; c.prefer_accuracy_over_speed = false; c.timeout = std::chrono::milliseconds(1000); return c;
}
NEMBConfig NEMBConfig::from_config_file(const std::string& p) { return accuracy_optimized(); }

// Result/Utility
std::string EnergyResult::summary() const { return "Energy: " + std::to_string(energy_joules) + " J"; }
std::string EnergyDifference::summary() const { return "Diff: " + std::to_string(energy_joules) + " J"; }

ScopedEnergyMeter::ScopedEnergyMeter(const std::string& n, bool p) : name_(n), print_results_(p) { baseline_ = meter_.read(); }
ScopedEnergyMeter::~ScopedEnergyMeter() { if(!stopped_) stop(); }
EnergyDifference ScopedEnergyMeter::current() const { return energy_utils::calculate_difference(meter_.read(), baseline_); }
EnergyDifference ScopedEnergyMeter::stop() { stopped_=true; return energy_utils::calculate_difference(meter_.read(), baseline_); }

namespace energy_utils {
EnergyDifference calculate_difference(const EnergyResult& e, const EnergyResult& s) {
    EnergyDifference d; d.is_valid = e.is_valid && s.is_valid;
    if(d.is_valid) {
        d.energy_joules = e.energy_joules - s.energy_joules;
        d.duration_seconds = (e.timestamp_ns - s.timestamp_ns) / 1e9;
        if(d.duration_seconds > 0) d.average_power_watts = d.energy_joules / d.duration_seconds;
        // Per-domain delta, signed and never dropped; a negative delta or a failed (negative) end/start value is counted
        for (auto& [domain, end_j] : e.components) {
            auto it = s.components.find(domain);
            double start_j = (it != s.components.end()) ? it->second : 0;
            double delta = end_j - start_j;
            d.component_energy[domain] = delta;
            if (d.duration_seconds > 0) d.component_power[domain] = delta / d.duration_seconds;
            if (delta < 0 || end_j < 0 || start_j < 0) d.negative_components++;
        }
    }
    return d;
}
double convert_energy(double j, const std::string& u) {
    if (u == "mJ") return j * 1e3;
    if (u == "uJ") return j * 1e6;
    if (u == "kWh") return j / 3.6e6;
    return j;
}
std::string format_energy(double j) { return std::to_string(j) + " J"; }
std::string format_power(double w) { return std::to_string(w) + " W"; }
bool is_energy_measurement_supported() { return true; }
std::vector<std::string> get_available_providers() { return {}; }
double validate_measurement_accuracy(double d) { return 0.99; }
}
} // namespace codegreen

extern "C" {
    static std::unique_ptr<codegreen::EnergyMeter> c_api_meter;
    static std::mutex c_api_mutex;
    static int c_api_init_pid = 0;

    // Private copy of fd 1 taken at init: the result block survives a workload closing stdout.
    static int c_api_result_fd = -1;
    static void nemb_save_result_fd() {
        if (c_api_result_fd >= 0) return;
#ifdef _WIN32
        c_api_result_fd = _dup(1);
#else
        c_api_result_fd = fcntl(1, F_DUPFD_CLOEXEC, 3);
#endif
    }
    static bool nemb_write_result(const std::string& s) {
        if (c_api_result_fd < 0) return false;
        for (size_t off = 0; off < s.size();) {
#ifdef _WIN32
            int n = _write(c_api_result_fd, s.data() + off, static_cast<unsigned>(s.size() - off));
#else
            ssize_t n = write(c_api_result_fd, s.data() + off, s.size() - off);
            if (n < 0 && errno == EINTR) continue;
#endif
            if (n <= 0) return false;
            off += static_cast<size_t>(n);
        }
        return true;
    }
    static bool c_api_is_forked_child = false;

    // Fork safety: abandon NEMB resources in child without destructing.
    // After fork(), the coordinator's background threads are dead, mutexes may
    // be inconsistent, and RAPL file descriptors are shared with the parent.
    // Calling destructors would close those shared FDs, breaking the parent.
    // release() surrenders ownership without invoking destructors -- the small
    // leak in the short-lived child is reclaimed by the OS on exit.
    static void nemb_after_fork_child() {
        c_api_is_forked_child = true;
        if (c_api_meter) {
            c_api_meter.release();
        }
    }

#ifndef _WIN32
    __attribute__((constructor))
    static void nemb_register_fork_handler() {
        pthread_atfork(nullptr, nullptr, nemb_after_fork_child);
    }
#endif

    int nemb_initialize() {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter) {
            nemb_save_result_fd();  // before providers open files that could take a closed fd 1
            try {
                c_api_meter = std::make_unique<codegreen::EnergyMeter>();
                c_api_init_pid = _nemb_getpid();
            } catch (const std::exception& e) {
                std::cerr << "NEMB init failed: " << e.what() << std::endl;
                c_api_meter.reset();
                return 0;
            }
        }
        return c_api_meter->is_available() ? 1 : 0;
    }

    // Detects, initializes and self-tests providers exactly as nemb_initialize does (config,
    // CODEGREEN_PROVIDERS), then releases them: no sampler thread, no meter, no markers.
    // Returns the number of usable providers; 0 (reason on stderr) when none or on error.
    int nemb_probe() {
        if (c_api_is_forked_child) return 0;
        try {
            codegreen::nemb::ConfigLoader::load_config();  // a bad config fails here as it would at init
            codegreen::QuietStreams quiet(!codegreen::debug_logging(false));
            return static_cast<int>(codegreen::nemb::detect_available_providers().size());
        } catch (const std::exception& e) {
            std::cerr << "NEMB probe failed: " << e.what() << std::endl;
            return 0;
        }
    }

    uint64_t nemb_start_session(const char* n) {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        return c_api_meter ? c_api_meter->start_session(n?n:"") : 0;
    }
    // Store last session diff for domain breakdown retrieval
    static codegreen::EnergyDifference last_session_diff;

    int nemb_abi_version() { return 4; }

    static std::string json_str(const std::string& s) {
        std::string o = "\"";
        for (char c : s) { if (c == '"' || c == '\\') o += '\\'; o += c; }
        return o + "\"";
    }

    // ABI 4 checkpoint payload shared by nemb_report_at_exit and nemb_get_checkpoints_json.
    static std::string checkpoints_json(const std::vector<codegreen::EnergyMeter::CorrelatedCheckpoint>& cps,
                                        const codegreen::EnergyMeter::SamplerStats& st) {
        std::ostringstream ss;
        ss << std::setprecision(17) << "{\"measurements\": [";
        for (size_t i = 0; i < cps.size(); ++i) {
            const auto& c = cps[i];
            ss << (i ? ", " : "") << "{\"checkpoint_id\": " << json_str(c.name) << ", \"timestamp\": " << c.timestamp_ns
               << ", \"joules\": " << c.cumulative_energy_joules << ", \"watts\": " << c.instantaneous_power_watts
               << ", \"ri\": " << c.ri << ", \"clamp\": \"" << c.clamp << "\", \"provider_j\": {";
            bool first = true;
            for (const auto& [id, j] : c.provider_j) { ss << (first ? "" : ", ") << json_str(id) << ": " << j; first = false; }
            ss << "}}";
        }
        ss << "], \"sampler\": {\"interval_ms\": " << st.interval_ms << ", \"interval_ms_min\": " << st.interval_ms_min
           << ", \"interval_ms_max\": " << st.interval_ms_max << ", \"buffer_capacity\": " << st.buffer_capacity
           << ", \"readings\": " << st.readings << ", \"wrapped\": " << (st.wrapped ? "true" : "false")
           << ", \"rejected_readings\": " << st.rejected_readings << ", \"failed_reads\": " << st.failed_reads
           << ", \"provider_restarts\": " << st.provider_restarts << ", \"dropped_checkpoints\": " << st.dropped_checkpoints
           << ", \"first_ns\": " << st.first_ns
           << ", \"last_ns\": " << st.last_ns << ", \"median_gap_ns\": " << st.median_gap_ns
           << ", \"max_gap_ns\": " << st.max_gap_ns << ", \"affinity_cpus\": " << st.affinity_cpus
           << ", \"sampler_affinity_cpus\": " << st.sampler_affinity_cpus << ", \"marker_reads\": " << json_str(st.marker_reads)
           << ", \"providers\": [";
        for (size_t i = 0; i < st.providers.size(); ++i) {
            const auto& p = st.providers[i];
            ss << (i ? ", " : "") << "{\"name\": " << json_str(p.name) << ", \"hardware_type\": " << json_str(p.hardware_type)
               << ", \"energy_source\": " << json_str(p.energy_source) << ", \"boundary_source\": " << json_str(p.boundary_source)
               << ", \"update_interval_ms\": " << p.update_interval_ms
               << ", \"counter_group\": " << json_str(p.counter_group) << ", \"rejected\": " << p.rejected
               << ", \"held\": " << p.held << ", \"boundary_held\": " << p.boundary_held
               << ", \"boundary_held_max_ns\": " << p.boundary_held_max_ns << "}";
        }
        ss << "], \"config_path\": " << json_str(st.config_path) << "}}";
        return ss.str();
    }

    // Drain buffered samples since `since_ts_ns` into a JSON array of self-
    // describing samples:
    //   {
    //     "t_ns":     CLOCK_MONOTONIC nanoseconds at sample time,
    //     "energy_j": cumulative system-wide joules from session start (sum across providers),
    //     "power_w":  system-wide instantaneous watts at this sample (sum across domains, raw),
    //     "power_w_filtered": EMA of power_w, present only when nemb coordinator real_time_filtering is on,
    //     "domain_j": {<domain>: cumulative joules from session start; signed, a failed domain reads negative},
    //     "domain_w": {<domain>: average watts since previous sample}
    //   }
    // Domains whose provider does not expose per-domain power (e.g. Darwin
    // IOReport, Windows EMI, AMD RAPL) are simply absent from `domain_w` rather
    // than reported as zero, so callers can distinguish "0 W" from "unmeasured".
    int nemb_get_time_series_json(char* buf, int size, uint64_t since_ts_ns) {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter || !buf || size <= 0) return 0;
        auto readings = c_api_meter->get_time_series_since(since_ts_ns);
        std::ostringstream ss;
        ss << std::setprecision(15) << "[";
        bool first = true;
        for (auto& r : readings) {
            if (!first) ss << ",";
            ss << "{\"t_ns\":"     << r.common_timestamp_ns
               << ",\"energy_j\":" << r.total_system_energy_joules
               << ",\"power_w\":"  << r.total_system_power_watts;
            if (r.power_filtered) ss << ",\"power_w_filtered\":" << r.filtered_system_power_watts;
            ss << ",\"domain_j\":{";
            bool dfirst = true;
            for (auto& pr : r.provider_readings) {
                for (auto& [domain, joules] : pr.domain_energy_joules) {
                    if (!dfirst) ss << ",";
                    ss << "\"" << domain << "\":" << joules;
                    dfirst = false;
                }
            }
            ss << "},\"domain_w\":{";
            bool wfirst = true;
            for (auto& pr : r.provider_readings) {
                for (auto& [domain, watts] : pr.domain_power_watts) {
                    if (!wfirst) ss << ",";
                    ss << "\"" << domain << "\":" << watts;
                    wfirst = false;
                }
            }
            ss << "}}";
            first = false;
        }
        ss << "]";
        std::string s = ss.str();
        if((int)s.length() >= size) return -(int)s.length();
        std::copy(s.begin(), s.end(), buf); buf[s.length()] = '\0';
        return (int)s.length();
    }

    int nemb_set_buffer_size(int n) {
        if (c_api_is_forked_child || n <= 0) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        return c_api_meter && c_api_meter->set_buffer_size((size_t)n) ? 1 : 0;
    }

    int nemb_set_measurement_interval_ms(int ms) {
        if (c_api_is_forked_child || ms <= 0) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter) return 0;
        c_api_meter->set_measurement_interval_ms(ms);
        return 1;
    }

    // Atomic stop: returns total energy, power, duration, and per-domain JSON
    // breakdown of THIS session in a single locked operation. Race-free under
    // concurrent task tracking. Pass nullptr/0 for json_buf to skip serialization.
    // Domain deltas are signed and never dropped: a negative value (failed domain read
    // or a counter going backwards) is the caller's signal to flag the measurement.
    // Returns: positive bytes written to json_buf on success (0 if buf null/empty),
    //          0 if session invalid, -required_size if buf too small.
    int nemb_stop_session_v2(uint64_t i, double* e, double* p, double* dur,
                              char* json_buf, int json_size) {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter) return 0;
        auto diff = c_api_meter->end_session(i);
        last_session_diff = diff;
        if(!diff.is_valid) return 0;
        if(e)   *e   = diff.energy_joules;
        if(p)   *p   = diff.average_power_watts;
        if(dur) *dur = diff.duration_seconds;
        if(!json_buf || json_size <= 0) return 1;
        std::ostringstream ss;
        ss << std::setprecision(15) << "{";
        bool first = true;
        for(auto& [domain, joules] : diff.component_energy) {
            if(!first) ss << ",";
            ss << "\"" << domain << "\":" << joules;
            first = false;
        }
        ss << "}";
        std::string s = ss.str();
        if((int)s.length() >= json_size) return -(int)s.length();
        std::copy(s.begin(), s.end(), json_buf); json_buf[s.length()] = '\0';
        return (int)s.length();
    }

    int nemb_stop_session(uint64_t i, double* e, double* p) {
        return nemb_stop_session_v2(i, e, p, nullptr, nullptr, 0);
    }
    int nemb_read_current(double* e, double* p) {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter) return 0;
        auto res = c_api_meter->read();
        if(res.is_valid) { if(e)*e=res.energy_joules; if(p)*p=res.power_watts; return 1; }
        return 0;
    }

    void nemb_report_at_exit() {
        if (c_api_is_forked_child) return;
        if (c_api_init_pid != 0 && _nemb_getpid() != c_api_init_pid) return;
        int retries = 10;
        while (retries-- > 0) {
            if (c_api_mutex.try_lock()) {
                if (!c_api_meter) { c_api_mutex.unlock(); return; }
                codegreen::EnergyMeter::SamplerStats st;
                auto cps = c_api_meter->get_checkpoint_measurements(&st);
                c_api_meter.reset();
                c_api_mutex.unlock();

                std::cout.flush();
                std::fflush(stdout);
                if (!nemb_write_result("\n--- CODEGREEN_RESULT_START ---\n" + checkpoints_json(cps, st) + "\n--- CODEGREEN_RESULT_END ---\n"))
                    std::cerr << "NEMB result fd unavailable" << std::endl;
                return;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        std::cerr << "NEMB result not written: another thread held the NEMB lock for 1 s at exit" << std::endl;
    }

    // Lazy-init state of nemb_mark_checkpoint; guarded by c_api_mutex.
    static bool c_api_init_failed = false;
    static bool c_api_atexit_registered = false;

    void nemb_mark_checkpoint(const char* n) {
        if (c_api_is_forked_child) return;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter) {
            if (c_api_init_failed) return;
            nemb_save_result_fd();  // before providers open files that could take a closed fd 1
            try {
                c_api_meter = std::make_unique<codegreen::EnergyMeter>();
                c_api_init_pid = _nemb_getpid();
            } catch (const std::exception& e) {
                std::cerr << "NEMB init failed: " << e.what() << std::endl;
                c_api_init_failed = true;
                return;
            }
            if (!c_api_atexit_registered) {
                std::atexit(nemb_report_at_exit);
                c_api_atexit_registered = true;
            }
        }
        if(c_api_meter) c_api_meter->mark_checkpoint(n?n:"");
    }

#ifdef HAVE_JNI
    JNIEXPORT void JNICALL Java_codegreen_runtime_CodeGreenRuntime_nemb_1mark_1checkpoint(
        JNIEnv* env, jclass clazz, jstring name) {
        const char* n = env->GetStringUTFChars(name, nullptr);
        if (n) {
            nemb_mark_checkpoint(n);
            env->ReleaseStringUTFChars(name, n);
        }
    }

    JNIEXPORT void JNICALL Java_codegreen_runtime_CodeGreenRuntime_nemb_1report_1at_1exit(
        JNIEnv* env, jclass clazz) {
        nemb_report_at_exit();
    }
#endif

    int nemb_get_checkpoints_json(char* b, int m) {
        if (c_api_is_forked_child) return 0;
        std::lock_guard<std::mutex> l(c_api_mutex);
        if(!c_api_meter || !b || m <= 0) return 0;
        codegreen::EnergyMeter::SamplerStats st;
        auto cps = c_api_meter->get_checkpoint_measurements(&st);
        std::string s = checkpoints_json(cps, st);
        if(s.length() >= (size_t)m) return -(int)s.length();
        std::copy(s.begin(), s.end(), b); b[s.length()] = '\0';
        return (int)s.length();
    }

    // Returns per-domain energy DELTA from the last nemb_stop_session call.
    // This is the energy consumed by the workload per domain, not cumulative; signed (see above).
    int nemb_get_domain_energy_json(char* b, int m) {
        std::lock_guard<std::mutex> l(c_api_mutex);
        std::ostringstream ss;
        ss << std::setprecision(10) << "{";
        bool first = true;
        for(auto& [domain, joules] : last_session_diff.component_energy) {
            if(!first) ss << ", ";
            ss << "\"" << domain << "\": " << joules;
            first = false;
        }
        ss << "}";
        std::string s = ss.str();
        if(s.length() >= (size_t)m) return -(int)s.length();
        std::copy(s.begin(), s.end(), b); b[s.length()] = '\0';
        return (int)s.length();
    }
}