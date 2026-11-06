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
#include "nemb/core/energy_provider.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include "nemb/utils/precision_timer.hpp"

using namespace codegreen;
using namespace codegreen::nemb;
using CP = EnergyMeter::CorrelatedCheckpoint;

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

class FakeProvider : public EnergyProvider {
public:
    explicit FakeProvider(bool ok) : ok_(ok) {}
    bool initialize() override { return true; }
    EnergyReading get_reading() override {
        EnergyReading r; r.provider_id = "fake"; r.timestamp_ns = utils::PrecisionTimer::monotonic_timestamp_ns();
        r.energy_joules = ok_ ? (j_ += 0.5) : -1.0;
        return r;
    }
    EnergyProviderSpec get_specification() const override { return {}; }
    bool self_test() override { return true; }
    bool is_available() const override { return true; }
    void shutdown() override {}
    std::string get_name() const override { return ok_ ? "fake_ok" : "fake_bad"; }
private:
    bool ok_;
    double j_{0};
};

static void test_coordinator() {
    CoordinatorConfig cfg;
    cfg.measurement_interval = std::chrono::milliseconds(1000);
    cfg.measurement_buffer_size = 3;
    MeasurementCoordinator good(cfg);
    CHECK(good.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(good.start_measurements());
    CHECK(!good.get_buffered_readings().empty());  // seed reading precedes the sampler thread
    good.set_measurement_interval_ms(1);
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    CHECK(good.buffer_wrapped() && good.get_buffered_readings().size() == 3 && good.rejected_readings() == 0);
    good.stop_measurements();

    cfg.measurement_interval = std::chrono::milliseconds(1);
    MeasurementCoordinator bad(cfg);
    CHECK(bad.add_provider(std::make_unique<FakeProvider>(true)));
    CHECK(bad.add_provider(std::make_unique<FakeProvider>(false)));
    CHECK(bad.start_measurements());
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    auto r = bad.get_synchronized_reading();
    CHECK(r.providers_failed == 1 && r.total_system_energy_joules >= 0);
    CHECK(bad.get_buffered_readings().empty() && bad.rejected_readings() > 0);
    bad.stop_measurements();
}

static bool throws_with(const char* env) {
    setenv("CODEGREEN_PROVIDERS", env, 1);
    try { detect_available_providers(); } catch (const std::runtime_error&) { unsetenv("CODEGREEN_PROVIDERS"); return true; }
    unsetenv("CODEGREEN_PROVIDERS");
    return false;
}

static void test_provider_selection() {
    EnergyProvider::register_provider("fake_ok", [] { return std::make_unique<FakeProvider>(true); });
    setenv("CODEGREEN_PROVIDERS", "fake_ok", 1);
    auto p = detect_available_providers();
    CHECK(p.size() == 1 && p.count("fake_ok"));
    unsetenv("CODEGREEN_PROVIDERS");
    CHECK(throws_with("no_such_provider"));
    CHECK(throws_with(","));
    auto all = detect_available_providers();
    CHECK(!(all.count("intel_rapl") && all.count("amd_rapl")));
}

static void test_checkpoint_cap() {
    auto dir = std::filesystem::temp_directory_path() / ("nemb_cap_" + std::to_string(getpid()));
    std::filesystem::create_directories(dir / "codegreen");
    std::ofstream(dir / "codegreen" / "config.json") << "{\n  \"max_checkpoints\": 3,\n  \"measurement_interval_ms\": 1\n}\n";
    setenv("CODEGREEN_INSTALL_DIR", dir.c_str(), 1);
    setenv("CODEGREEN_PROVIDERS", "fake_ok", 1);
    {
        EnergyMeter m;
        for (int i = 0; i < 5; ++i) m.mark_checkpoint("cp");
        EnergyMeter::SamplerStats st;
        auto cps = m.get_checkpoint_measurements(&st);
        CHECK(cps.size() == 3 && st.dropped_checkpoints == 2);
        CHECK(st.config_path == (dir / "codegreen" / "config.json").string());
    }
    unsetenv("CODEGREEN_PROVIDERS");
    unsetenv("CODEGREEN_INSTALL_DIR");
    std::filesystem::remove_all(dir);
}

extern "C" void nemb_mark_checkpoint(const char* n);

// Child mode: stdout is closed after (or before) the first marker; the atexit report must
// still arrive through the fd saved at init, or fail loud on stderr.
static int child(const std::string& mode) {
    EnergyProvider::register_provider("fake_ok", [] { return std::make_unique<FakeProvider>(true); });
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
        if (std::string(mode) == "keep") CHECK(out.find("workload output") < s);
    }
    auto out = run_child("close_before");
    CHECK(out.find("NEMB result fd unavailable") != std::string::npos && out.find("CODEGREEN_RESULT_START") == std::string::npos);
}

int main(int argc, char** argv) {
    if (argc > 1) return child(argv[1]);
    test_correlate();
    test_coordinator();
    test_provider_selection();
    test_checkpoint_cap();
    test_result_fd();
    std::cout << (failures ? "FAILED " : "PASSED ") << failures << " failure(s)\n";
    return failures ? 1 : 0;
}
