#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <unistd.h>

#include "nemb/codegreen_energy.hpp"
#include "nemb/config_loader.hpp"
#include "nemb/core/energy_provider.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/drivers/intel_rapl_provider.hpp"
#include "nemb/drivers/nvidia_gpu_provider.hpp"
#include "nemb/utils/precision_timer.hpp"

using namespace codegreen;
using namespace codegreen::nemb;
using CP = EnergyMeter::CorrelatedCheckpoint;
namespace fs = std::filesystem;

static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::cerr << "FAIL " << __LINE__ << ": " #c "\n"; ++failures; } } while (0)

static SynchronizedReading sr(uint64_t t, double cpu, double gpu, double watts) {
    SynchronizedReading r;
    r.common_timestamp_ns = t;
    for (auto [id, j] : {std::pair<const char*, double>{"intel_rapl", cpu}, {"nvidia_gpu", gpu}}) {
        EnergyReading e; e.provider_id = id; e.energy_joules = j; e.timestamp_ns = t;
        r.provider_readings.push_back(e);
    }
    r.total_system_energy_joules = cpu + gpu;
    r.total_system_power_watts = watts;
    r.providers_active = 2;
    return r;
}

static std::vector<CP> correlate(const std::vector<SynchronizedReading>& R, std::vector<uint64_t> ts) {
    std::vector<CP> cps;
    for (auto t : ts) { CP c; c.name = "m"; c.timestamp_ns = t; cps.push_back(c); }
    EnergyMeter::correlate(R, cps);
    for (auto& c : cps) {
        double s = 0; for (auto& [id, j] : c.provider_j) s += j;
        CHECK(s == c.cumulative_energy_joules);
    }
    return cps;
}

static void test_correlate() {
    std::vector<SynchronizedReading> R{sr(100, 10, 1, 5), sr(200, 20, 2, 6), sr(400, 40, 4, 8)};
    auto c = correlate(R, {50, 150, 200, 250, 350, 500});
    CHECK(c[0].clamp == "before_first" && c[0].ri == 0 && c[0].cumulative_energy_joules == 11);
    CHECK(c[1].clamp == "none" && c[1].ri == 1 && c[1].provider_j["intel_rapl"] == 15 && c[1].provider_j["nvidia_gpu"] == 1.5);
    CHECK(std::fabs(c[1].instantaneous_power_watts - 5.5) < 1e-12);
    CHECK(c[2].clamp == "none" && c[2].ri == 1 && c[2].cumulative_energy_joules == 22);
    CHECK(c[3].ri == 2 && c[4].ri == 2 && c[4].ri - c[3].ri == 0);  // window inside one sampler gap: zero samples
    CHECK(std::fabs(c[4].cumulative_energy_joules - c[3].cumulative_energy_joules - 11) < 1e-12);
    CHECK(c[5].clamp == "after_last" && c[5].ri == 3 && c[5].cumulative_energy_joules == 44);
    std::vector<SynchronizedReading> flat{sr(100, 1.681159797089, 0.3, 1), sr(200, 1.681159797089, 0.3, 1), sr(300, 1.7, 0.3, 1)};
    double prev = 0;
    for (auto& f : correlate(flat, {110, 137, 151, 199, 200, 201, 260, 299})) { CHECK(f.provider_j["intel_rapl"] >= prev); prev = f.provider_j["intel_rapl"]; }
    std::vector<SynchronizedReading> wrapped{sr(1000, 100, 0, 1), sr(1010, 101, 0, 1)};
    auto w = correlate(wrapped, {500, 1005});
    CHECK(w[0].clamp == "before_first" && w[1].clamp == "none" && w[1].ri == 1);
    bool threw = false;
    try { correlate({}, {1}); } catch (const std::invalid_argument&) { threw = true; }
    CHECK(threw);
}

// ok: readings carry energy; init: initialize()/self_test() succeed; group: counter_group; hold: every read is a held value;
// boundary: session boundaries read a separate counter series (energy_source integrated_power, boundary_source counter);
// stall: reads succeed but the cumulative energy never changes.
class FakeProvider : public EnergyProvider {
public:
    explicit FakeProvider(bool ok, std::string group = "", bool init = true, bool hold = false, bool boundary = false,
                          bool stall = false)
        : ok_(ok), init_(init), hold_(hold), boundary_(boundary), stall_(stall), group_(std::move(group)) {}
    bool initialize() override { return init_; }
    EnergyReading get_reading() override {
        EnergyReading r; r.provider_id = "fake"; r.timestamp_ns = utils::PrecisionTimer::monotonic_timestamp_ns();
        r.energy_joules = ok_ ? (j_ += stall_ ? 0.0 : 0.5) : -1.0;
        r.average_power_watts = ok_ ? j_ : 0.0;  // rising power: an EMA lags behind it
        if (hold_) held_readings_++;
        return r;
    }
    EnergyReading get_boundary_reading(bool shared) override {  // a separate counter series, far above the sampled one
        EnergyReading r = get_reading();
        if (boundary_ && shared) r.energy_joules = b_ + 1;  // last counter value plus the integral since: no counter read
        else if (boundary_) { r.energy_joules = b_ += 10; record_boundary_hold(static_cast<uint64_t>(b_ - 1e6)); }
        return r;
    }
    std::map<std::string, CounterCheck> counter_checks() const override {
        return boundary_ ? std::map<std::string, CounterCheck>{{"dev0", {b_ - 1e6, 9.5, 1000, 3}}} : std::map<std::string, CounterCheck>{};
    }
    EnergyProviderSpec get_specification() const override {
        EnergyProviderSpec s;
        s.hardware_type = "cpu";
        s.counter_group = group_;
        s.update_interval = std::chrono::microseconds(2500);
        if (boundary_) { s.energy_source = "integrated_power"; s.boundary_source = "counter"; }
        return s;
    }
    bool self_test() override { return init_; }
    bool is_available() const override { return true; }
    void shutdown() override {}
    std::string get_name() const override { return ok_ ? "fake_ok" : "fake_bad"; }
private:
    bool ok_, init_, hold_, boundary_, stall_;
    std::string group_;
    double j_{0}, b_{1e6};
};

static void register_fakes() {
    EnergyProvider::register_provider("fake_ok", [] { return std::make_unique<FakeProvider>(true); });
    EnergyProvider::register_provider("fake_bad", [] { return std::make_unique<FakeProvider>(false); });
    EnergyProvider::register_provider("fake_hold", [] { return std::make_unique<FakeProvider>(true, "", true, true); });
    EnergyProvider::register_provider("fake_boundary", [] { return std::make_unique<FakeProvider>(true, "", true, false, true); });
    EnergyProvider::register_provider("fake_stall", [] { return std::make_unique<FakeProvider>(true, "", true, false, false, true); });
    EnergyProvider::register_provider("fake_grp_a", [] { return std::make_unique<FakeProvider>(true, "g"); });
    EnergyProvider::register_provider("fake_grp_b", [] { return std::make_unique<FakeProvider>(true, "g"); });
    EnergyProvider::register_provider("fake_noinit", [] { return std::make_unique<FakeProvider>(true, "g", false); });
}

static void test_coordinator() {
    CoordinatorConfig cfg;
    cfg.measurement_interval = std::chrono::milliseconds(1000);
    cfg.measurement_buffer_size = 3;
    MeasurementCoordinator good(cfg);
    CHECK(good.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(good.start_measurements());
    CHECK(!good.get_buffered_readings().empty());  // seed reading precedes the sampler thread
    CHECK(good.interval_ms_min() == 1000 && good.interval_ms_max() == 1000);
    CHECK(good.affinity_cpus() > 0 && good.sampler_affinity_cpus() > 0);
    good.set_measurement_interval_ms(1);
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    CHECK(good.buffer_wrapped() && good.get_buffered_readings().size() == 3 && good.rejected_readings() == 0);
    CHECK(good.measurement_interval().count() == 1 && good.interval_ms_min() == 1 && good.interval_ms_max() == 1000);
    good.set_measurement_interval_ms(100000);
    CHECK(good.measurement_interval().count() == 60000 && good.interval_ms_max() == 60000);
    good.stop_measurements();

    auto before = good.get_buffered_readings();
    CHECK(good.set_buffer_size(5) && good.get_buffered_readings().size() == 3 && good.buffer_wrapped());
    CHECK(good.set_buffer_size(2));
    auto after = good.get_buffered_readings();
    CHECK(after.size() == 2 && after[0].common_timestamp_ns == before[1].common_timestamp_ns &&
          after[1].common_timestamp_ns == before[2].common_timestamp_ns);
    CHECK(!good.set_buffer_size(0));

    cfg.measurement_interval = std::chrono::milliseconds(1);
    cfg.measurement_buffer_size = 100000;
    MeasurementCoordinator grow(cfg);
    CHECK(grow.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(grow.start_measurements());
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    grow.stop_measurements();
    auto all = grow.get_buffered_readings();
    CHECK(!grow.buffer_wrapped() && all.size() >= 2);
    CHECK(grow.set_buffer_size(1) && grow.buffer_wrapped());  // a resize that drops readings reports them
    auto kept = grow.get_buffered_readings();
    CHECK(kept.size() == 1 && kept[0].common_timestamp_ns == all.back().common_timestamp_ns);
    for (const auto& x : all) CHECK(!x.power_filtered);  // filtering is off by default

    CoordinatorConfig fcfg = cfg;
    fcfg.enable_real_time_filtering = true;
    MeasurementCoordinator filt(fcfg);
    CHECK(filt.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(filt.start_measurements());
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    filt.stop_measurements();
    size_t n_filtered = 0;
    bool lagged = false;
    for (const auto& x : filt.get_buffered_readings()) {
        CHECK(x.total_system_power_watts == x.provider_readings[0].average_power_watts);  // primary power stays raw
        if (x.power_filtered) { ++n_filtered; lagged |= x.filtered_system_power_watts < x.total_system_power_watts; }
    }
    CHECK(n_filtered >= 2 && lagged);

    MeasurementCoordinator bad(cfg);
    CHECK(bad.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(bad.add_provider(std::make_unique<FakeProvider>(false)));
    CHECK(bad.start_measurements());
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    auto r = bad.get_synchronized_reading();
    CHECK(r.providers_failed == 1 && r.total_system_energy_joules >= 0);
    bad.stop_measurements();
    auto counts = bad.provider_counts();
    CHECK(bad.get_buffered_readings().empty() && bad.rejected_readings() > 0);
    CHECK(counts["fake_bad"].rejected == bad.rejected_readings() && counts["fake_ok"].rejected == 0);
}

static void test_power_integrator() {
    PowerIntegrator p(2);
    CHECK(!p.add(0, 10.0, 1000000000ULL, 2) && p.joules(0) == 0);
    CHECK(!p.add(0, 20.0, 2000000000ULL, 2) && p.joules(0) == 15);
    CHECK(p.add(0, std::nullopt, 3000000000ULL, 2) && p.joules(0) == 15);              // held across a failed read
    CHECK(!p.add(0, 0.0, 4000000000ULL, 2) && p.joules(0) == 35 && p.lost_devices() == 0);  // 0 W is valid; gap integrated
    for (uint64_t i = 0; i < 3; ++i) CHECK(p.add(1, std::nullopt, 5000000000ULL + i, 2));
    CHECK(p.lost_devices() == 1);
    CHECK(!p.add(1, 5.0, 6000000000ULL, 2) && p.lost_devices() == 1);                 // lost for good
    p.reset();
    CHECK(p.lost_devices() == 0 && p.joules(0) == 0);
}

static void test_gpu_energy_counter() {
    drivers::GPUEnergyCounter c(100, 1000);  // update period 100 ns, primed at 1000 mJ
    CHECK(c.due(1) && c.joules() == 0);      // the first read is due
    c.add(3500, 1000, 7.0);
    CHECK(c.joules() == 2.5 && !c.due(1099) && c.due(1100));  // within one period the last read answers (held)
    CHECK(c.check().counter_j == 0 && c.check().integral_j == 0 && c.check().span_ns == 0 && c.check().reads == 1);  // spans start at the first read
    c.add(200, 1100, 7.5);                                    // driver counter reset counts from zero
    CHECK(std::fabs(c.joules() - 2.7) < 1e-12);
    CHECK(std::fabs(c.check().counter_j - 0.2) < 1e-12 && c.check().integral_j == 0.5 && c.check().span_ns == 100 && c.check().reads == 2);
    CHECK(std::fabs(c.joules_at(8.0) - 3.2) < 1e-12);  // shared read: last counter value plus the integral since
    CHECK(drivers::GPUEnergyCounter().period_ns() == 0);
}

static void test_signed_domains() {
    EnergyResult s, e;
    s.is_valid = e.is_valid = true;
    e.timestamp_ns = 1000000000ULL;
    s.components = {{"package", 10}, {"dram", 5}, {"core", 3}};
    e.components = {{"package", 12}, {"dram", 4}, {"core", -1}};  // dram went backwards, core read failed
    auto d = energy_utils::calculate_difference(e, s);
    CHECK(d.is_valid && d.component_energy.size() == 3 && d.component_energy["package"] == 2);
    CHECK(d.component_energy["dram"] == -1 && d.component_energy["core"] == -4 && d.negative_components == 2);
}

static bool throws_with(const char* env) {
    setenv("CODEGREEN_PROVIDERS", env, 1);
    try { detect_available_providers(); } catch (const std::runtime_error&) { unsetenv("CODEGREEN_PROVIDERS"); return true; }
    unsetenv("CODEGREEN_PROVIDERS");
    return false;
}

static std::map<std::string, std::unique_ptr<EnergyProvider>> detect_with(const char* env) {
    setenv("CODEGREEN_PROVIDERS", env, 1);
    auto p = detect_available_providers();
    unsetenv("CODEGREEN_PROVIDERS");
    return p;
}

static void test_provider_selection() {
    auto p = detect_with("fake_ok");
    CHECK(p.size() == 1 && p.count("fake_ok"));
    p = detect_with("fake_noinit|fake_grp_b");
    CHECK(p.size() == 1 && p.count("fake_grp_b"));
    p = detect_with("fake_grp_a|fake_grp_b,fake_ok");
    CHECK(p.size() == 2 && p.count("fake_grp_a") && p.count("fake_ok"));
    p = detect_with("fake_grp_a,fake_grp_b");  // same counter_group: the second is a duplicate counter
    CHECK(p.size() == 1 && p.count("fake_grp_a"));
    CHECK(throws_with("no_such_provider"));
    CHECK(throws_with("fake_noinit"));
    CHECK(throws_with(","));
    CHECK(throws_with("fake_ok|"));
    CHECK(throws_with("fake_ok,,fake_grp_a"));
    auto all = detect_available_providers();
    CHECK(all.count("fake_grp_a") && !all.count("fake_grp_b") && !all.count("fake_noinit"));
    CHECK(!(all.count("intel_rapl") && all.count("amd_rapl")));
}

static fs::path write_config(const std::string& tag, const std::string& body) {
    auto p = fs::temp_directory_path() / ("nemb_" + tag + "_" + std::to_string(getpid()) + ".json");
    std::ofstream(p) << body;
    return p;
}

static bool load_throws_naming(const fs::path& p) {
    setenv("CODEGREEN_CONFIG", p.c_str(), 1);
    bool named = false;
    try { ConfigLoader::load_config(); } catch (const std::runtime_error& e) { named = std::string(e.what()).find(p.string()) != std::string::npos; }
    unsetenv("CODEGREEN_CONFIG");
    return named;
}

static void test_config_resolution() {
    auto good = write_config("good", "{\n  \"measurement_interval_ms\": 7,\n  \"max_consecutive_failures\": 9\n}\n");
    setenv("CODEGREEN_CONFIG", good.c_str(), 1);
    auto cfg = ConfigLoader::load_config();
    CHECK(cfg.path == good.string() && cfg.coordinator.measurement_interval_ms == 7 && cfg.coordinator.max_consecutive_failures == 9);
    unsetenv("CODEGREEN_CONFIG");
    auto bad_value = write_config("badval", "{\n  \"measurement_interval_ms\": ten\n}\n");
    auto truncated = write_config("trunc", "{\n  \"measurement_interval_ms\": 7,\n");
    auto negative = write_config("neg", "{\n  \"max_consecutive_failures\": -1\n}\n");
    CHECK(load_throws_naming(bad_value) && load_throws_naming(truncated) && load_throws_naming(negative));
    CHECK(load_throws_naming(fs::temp_directory_path() / "nemb_no_such_config.json"));
    auto found = ConfigLoader::find_config_file();  // the build tree places the bundled config at <libdir>/../config.json
    CHECK(!found.empty() && fs::is_regular_file(found));
    auto bundled = ConfigLoader::load_config(found);
    auto partial = ConfigLoader::load_config(good.string());  // keys missing here fall back to member defaults == bundled values
    CHECK(partial.coordinator.measurement_buffer_size == bundled.coordinator.measurement_buffer_size &&
          partial.coordinator.provider_restart_interval == bundled.coordinator.provider_restart_interval &&
          partial.coordinator.real_time_filtering == bundled.coordinator.real_time_filtering && !bundled.coordinator.real_time_filtering);
    for (const auto& p : {good, bad_value, truncated, negative}) fs::remove(p);
}

static void test_meter_sampler() {
    auto cfg = write_config("meter", "{\n  \"max_checkpoints\": 3,\n  \"measurement_interval_ms\": 1,\n"
                                     "  \"provider_restart_interval\": 1000,\n  \"max_consecutive_failures\": 2\n}\n");
    setenv("CODEGREEN_CONFIG", cfg.c_str(), 1);
    setenv("CODEGREEN_PROVIDERS", "fake_ok", 1);
    {
        EnergyMeter m;
        for (int i = 0; i < 5; ++i) m.mark_checkpoint("cp");
        EnergyMeter::SamplerStats st;
        auto cps = m.get_checkpoint_measurements(&st);
        CHECK(cps.size() == 3 && st.dropped_checkpoints == 2);
        CHECK(st.config_path == cfg.string() && st.marker_reads == "interpolated");
        CHECK(st.interval_ms_min <= st.interval_ms && st.interval_ms <= st.interval_ms_max && st.interval_ms == 1);
        CHECK(st.affinity_cpus > 0 && st.sampler_affinity_cpus > 0);
        CHECK(st.providers.size() == 1 && st.providers[0].name == "fake_ok" && st.providers[0].hardware_type == "cpu" &&
              st.providers[0].energy_source == "counter" && st.providers[0].boundary_source == "counter" &&
              st.providers[0].update_interval_ms == 2.5 &&
              st.providers[0].rejected == 0 && st.providers[0].held == 0 && st.providers[0].boundary_held == 0 &&
              st.failed_reads == 0);
        CHECK(st.providers[0].readings >= 2 && st.providers[0].last_ns >= st.last_ns && st.providers[0].max_stall_ns == 0);
    }
    setenv("CODEGREEN_PROVIDERS", "fake_ok,fake_stall", 1);
    {
        EnergyMeter m;
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
        EnergyMeter::SamplerStats st;
        m.get_checkpoint_measurements(&st);
        const auto& s = st.providers[1];  // successful reads of an unchanging energy: counted as a stall, still read
        CHECK(st.providers[0].max_stall_ns == 0 && s.name == "fake_stall" && s.readings >= 10 && s.readings == st.providers[0].readings);
        CHECK(s.max_stall_ns >= 20000000 && s.last_ns >= st.last_ns);
    }
    setenv("CODEGREEN_PROVIDERS", "fake_boundary", 1);
    {
        EnergyMeter m;
        auto d = m.end_session(m.start_session("s"));
        CHECK(d.is_valid && d.energy_joules == 10);  // sessions read get_boundary_reading
        uint64_t outer = m.start_session("outer"), inner = m.start_session("inner");
        CHECK(m.end_session(inner).energy_joules == 0 && m.end_session(outer).energy_joules == 10);  // nested reads are shared
        CHECK(m.read().energy_joules < 1e6);          // one-shot reads and the sampler read get_reading
        EnergyMeter::SamplerStats st;
        for (const auto& c : m.get_checkpoint_measurements(&st)) CHECK(c.cumulative_energy_joules < 1e6);
        CHECK(st.providers[0].energy_source == "integrated_power" && st.providers[0].boundary_source == "counter");
        CHECK(st.providers[0].held == 0 && st.providers[0].boundary_held == 4 && st.providers[0].boundary_held_max_ns == 40);
        const auto& k = st.providers[0].counter_check.at("dev0");
        CHECK(st.providers[0].counter_check.size() == 1 && k.counter_j == 40 && k.integral_j == 9.5 && k.span_ns == 1000 && k.reads == 3);
    }
    setenv("CODEGREEN_PROVIDERS", "fake_ok,fake_bad,fake_hold", 1);
    {
        EnergyMeter m;
        std::this_thread::sleep_for(std::chrono::milliseconds(1500));  // fake_bad fails, is marked failed, restarted
        EnergyMeter::SamplerStats st;
        m.get_checkpoint_measurements(&st);
        CHECK(st.providers.size() == 3 && st.providers[0].name == "fake_bad" && st.providers[1].name == "fake_hold");
        CHECK(st.providers[0].rejected > 0 && st.providers[1].rejected == 0 && st.providers[2].rejected == 0);
        CHECK(st.providers[1].held > 0 && st.failed_reads == st.providers[0].rejected && st.rejected_readings > 0);
        CHECK(st.provider_restarts >= 1 && st.providers[0].readings == 0 && st.providers[1].readings > 0);
    }
    setenv("CODEGREEN_CONFIG", (fs::temp_directory_path() / "nemb_no_such_config.json").c_str(), 1);
    bool threw = false;
    try { EnergyMeter m; } catch (const std::runtime_error&) { threw = true; }
    CHECK(threw);
    unsetenv("CODEGREEN_PROVIDERS");
    unsetenv("CODEGREEN_CONFIG");
    fs::remove(cfg);
}

static void write_file(const fs::path& p, const std::string& s) { std::ofstream(p) << s; }

static void test_rapl_partial_domain() {
    auto root = fs::temp_directory_path() / ("nemb_rapl_" + std::to_string(getpid()));
    for (auto [dir, name] : {std::pair<const char*, const char*>{"intel-rapl:0", "package-0"}, {"intel-rapl:0:0", "core"}, {"intel-rapl:0:1", "dram"}}) {
        fs::create_directories(root / dir);
        write_file(root / dir / "name", std::string(name) + "\n");
        write_file(root / dir / "energy_uj", "1000\n");
        write_file(root / dir / "max_energy_range_uj", "262143328850\n");
    }
    drivers::IntelRAPLProvider rapl(root.string());
    CHECK(rapl.initialize());
    CHECK(rapl.get_reading().energy_joules >= 0);
    write_file(root / "intel-rapl:0:0" / "energy_uj", "garbage\n");  // sub-domain of package: total unaffected
    CHECK(rapl.get_reading().energy_joules >= 0);
    write_file(root / "intel-rapl:0:1" / "energy_uj", "garbage\n");  // dram is summed: the reading is invalid
    CHECK(rapl.get_reading().energy_joules < 0);
    write_file(root / "intel-rapl:0:1" / "energy_uj", "2000\n");
    CHECK(rapl.get_reading().energy_joules >= 0);
    rapl.shutdown();
    fs::remove_all(root);
}

extern "C" void nemb_mark_checkpoint(const char* n);
extern "C" int nemb_probe();
extern "C" int nemb_get_checkpoints_json(char* b, int m);

static void test_probe() {
    setenv("CODEGREEN_PROVIDERS", "fake_ok,fake_hold", 1);
    CHECK(nemb_probe() == 2);
    char buf[64];
    CHECK(nemb_get_checkpoints_json(buf, sizeof(buf)) == 0);  // no meter was created
    setenv("CODEGREEN_PROVIDERS", "no_such_provider", 1);
    CHECK(nemb_probe() == 0);
    unsetenv("CODEGREEN_PROVIDERS");
}

// Child mode: stdout is closed after (or before) the first marker; the atexit report must
// still arrive through the fd saved at init, or fail loud on stderr.
static int child(const std::string& mode) {
    register_fakes();
    setenv("CODEGREEN_PROVIDERS", "fake_ok", 1);
    if (mode == "close_before") close(1);
    nemb_mark_checkpoint("enter:main:1");
    std::cout << "workload output" << std::endl;
    if (mode == "close_after") close(1);
    nemb_mark_checkpoint("exit:main:1");
    return 0;
}

static std::string run_child(const std::string& mode) {
    char exe[4096];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    CHECK(n > 0);
    exe[n > 0 ? n : 0] = '\0';
    FILE* p = popen((std::string(exe) + " " + mode + " 2>&1").c_str(), "r");
    std::string out;
    for (char b[4096]; size_t k = fread(b, 1, sizeof(b), p);) out.append(b, k);
    CHECK(pclose(p) == 0);
    return out;
}

static void test_result_fd() {
    for (const char* mode : {"keep", "close_after"}) {
        auto out = run_child(mode);
        auto s = out.find("--- CODEGREEN_RESULT_START ---"), e = out.find("--- CODEGREEN_RESULT_END ---");
        CHECK(s != std::string::npos && e > s && out.find("\"exit:main:1#inv_1", s) < e);
        CHECK(out.find("\"marker_reads\": \"interpolated\"", s) < e);
        CHECK(out.find("\"providers\": [{\"name\": \"fake_ok\", \"hardware_type\": \"cpu\", \"energy_source\": \"counter\", "
                       "\"boundary_source\": \"counter\"", s) < e);
        CHECK(out.find("\"held\": 0, \"boundary_held\": 0, \"boundary_held_max_ns\": 0, \"readings\": ", s) < e);
        CHECK(out.find("\"max_stall_ns\": 0, \"counter_check\": {}}", s) < e);
        if (std::string(mode) == "keep") CHECK(out.find("workload output") < s);
    }
    auto out = run_child("close_before");
    CHECK(out.find("NEMB result fd unavailable") != std::string::npos && out.find("CODEGREEN_RESULT_START") == std::string::npos);
}

int main(int argc, char** argv) {
    if (argc > 1) return child(argv[1]);
    register_fakes();
    test_correlate();
    test_coordinator();
    test_power_integrator();
    test_gpu_energy_counter();
    test_signed_domains();
    test_provider_selection();
    test_config_resolution();
    test_meter_sampler();
    test_rapl_partial_domain();
    test_probe();
    test_result_fd();
    std::cout << (failures ? "FAILED " : "PASSED ") << failures << " failure(s)\n";
    return failures ? 1 : 0;
}
