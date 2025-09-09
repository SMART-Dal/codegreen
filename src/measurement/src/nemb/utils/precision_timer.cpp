#include "../../../include/nemb/utils/precision_timer.hpp"

#include <iostream>
#include <thread>
#include <fstream>
#include <cstring>
#include <vector>
#include <chrono>

#ifdef __x86_64__
#include <cpuid.h>
#include <x86intrin.h>
#endif

namespace codegreen::nemb::utils {

PrecisionTimer::PrecisionTimer() = default;

bool PrecisionTimer::initialize() {
    std::cout << "🕒 Initializing precision timing subsystem..." << std::endl;
    
    // Try TSC first (x86/x64 only)
    if (is_tsc_available() && initialize_tsc()) {
        clock_source_ = ClockSource::TSC_INVARIANT;
        std::cout << "  ✅ Using TSC (Time Stamp Counter) - highest precision" << std::endl;
        std::cout << "    TSC frequency: " << (tsc_frequency_hz_ / 1000000) << " MHz" << std::endl;
        std::cout << "    Resolution: ~" << (1000.0 / (tsc_frequency_hz_ / 1e9)) << " ns" << std::endl;
        return true;
    }
    
    // Fallback to POSIX clocks
    if (initialize_posix_clock()) {
        std::cout << "  ✅ Using " << get_clock_source_name() << std::endl;
        std::cout << "    Resolution: " << resolution_ns_ << " ns" << std::endl;
        return true;
    }
    
    std::cerr << "  ❌ Failed to initialize any timing source" << std::endl;
    return false;
}

uint64_t PrecisionTimer::get_timestamp_ns() const {
    switch (clock_source_) {
        case ClockSource::TSC_INVARIANT:
            return tsc_to_nanoseconds(read_tsc());
            
        case ClockSource::MONOTONIC_RAW:
            return read_posix_clock_ns(CLOCK_MONOTONIC_RAW);
            
        case ClockSource::MONOTONIC:
            return read_posix_clock_ns(CLOCK_MONOTONIC);
            
        case ClockSource::REALTIME:
            return read_posix_clock_ns(CLOCK_REALTIME);
            
        default:
            return 0;
    }
}

std::string PrecisionTimer::get_clock_source_name() const {
    switch (clock_source_) {
        case ClockSource::TSC_INVARIANT:
            return "TSC (Invariant Time Stamp Counter)";
        case ClockSource::MONOTONIC_RAW:
            return "CLOCK_MONOTONIC_RAW";
        case ClockSource::MONOTONIC:
            return "CLOCK_MONOTONIC";
        case ClockSource::REALTIME:
            return "CLOCK_REALTIME";
        default:
            return "Unknown";
    }
}

bool PrecisionTimer::is_tsc_available() {
#ifdef __x86_64__
    uint32_t eax, ebx, ecx, edx;
    
    // Check for invariant TSC (CPUID leaf 0x80000007, EDX bit 8)
    if (__get_cpuid(0x80000000, &eax, &ebx, &ecx, &edx)) {
        if (eax >= 0x80000007) {
            __get_cpuid(0x80000007, &eax, &ebx, &ecx, &edx);
            return (edx & (1 << 8)) != 0; // Invariant TSC bit
        }
    }
#endif
    return false;
}

bool PrecisionTimer::initialize_tsc() {
#ifdef __x86_64__
    if (!detect_tsc_invariant()) {
        return false;
    }
    
    // Measure TSC frequency
    tsc_frequency_hz_ = measure_tsc_frequency();
    if (tsc_frequency_hz_ == 0) {
        std::cerr << "  ⚠️  Failed to measure TSC frequency" << std::endl;
        return false;
    }
    
    // Set baseline TSC offset
    tsc_offset_ = read_tsc();
    tsc_available_ = true;
    
    // Calculate effective resolution
    resolution_ns_ = 1000000000.0 / tsc_frequency_hz_;
    
    return true;
#else
    return false;
#endif
}

bool PrecisionTimer::initialize_posix_clock() {
    // Try clocks in order of preference
    std::vector<std::pair<clockid_t, ClockSource>> clocks = {
        {CLOCK_MONOTONIC_RAW, ClockSource::MONOTONIC_RAW},
        {CLOCK_MONOTONIC, ClockSource::MONOTONIC},
        {CLOCK_REALTIME, ClockSource::REALTIME}
    };
    
    for (auto [clock_id, source] : clocks) {
        double resolution = measure_clock_resolution(clock_id);
        if (resolution > 0 && resolution < 1000000) { // Less than 1ms resolution
            clock_source_ = source;
            resolution_ns_ = resolution;
            return true;
        }
    }
    
    return false;
}

bool PrecisionTimer::detect_tsc_invariant() {
#ifdef __x86_64__
    // Check if TSC is invariant (doesn't change with frequency scaling)
    uint32_t eax, ebx, ecx, edx;
    
    // CPUID leaf 0x80000007, EDX bit 8
    if (__get_cpuid(0x80000007, &eax, &ebx, &ecx, &edx)) {
        return (edx & (1 << 8)) != 0;
    }
#endif
    return false;
}

uint64_t PrecisionTimer::measure_tsc_frequency() {
#ifdef __x86_64__
    // Use high-resolution clock to calibrate TSC
    auto start_steady = std::chrono::high_resolution_clock::now();
    uint64_t start_tsc = read_tsc();
    
    // Wait for a measurable period
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    auto end_steady = std::chrono::high_resolution_clock::now();
    uint64_t end_tsc = read_tsc();
    
    // Calculate frequency
    auto duration_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        end_steady - start_steady).count();
    
    if (duration_ns > 0) {
        return ((end_tsc - start_tsc) * 1000000000ULL) / duration_ns;
    }
#endif
    return 0;
}

double PrecisionTimer::measure_clock_resolution(clockid_t clock_id) {
    struct timespec resolution;
    if (clock_getres(clock_id, &resolution) != 0) {
        return -1.0; // Clock not available
    }
    
    return resolution.tv_sec * 1e9 + resolution.tv_nsec;
}

uint64_t PrecisionTimer::read_tsc() const {
#ifdef __x86_64__
    return __rdtsc();
#else
    return 0;
#endif
}

uint64_t PrecisionTimer::tsc_to_nanoseconds(uint64_t tsc_value) const {
    if (tsc_frequency_hz_ == 0) return 0;
    
    uint64_t tsc_delta = tsc_value - tsc_offset_;
    return (tsc_delta * 1000000000ULL) / tsc_frequency_hz_;
}

uint64_t PrecisionTimer::read_posix_clock_ns(clockid_t clock_id) const {
    struct timespec ts;
    if (clock_gettime(clock_id, &ts) != 0) {
        return 0;
    }
    
    return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

// ScopedTimer implementation
ScopedTimer::ScopedTimer(const std::string& name) 
    : name_(name), timer_(std::make_unique<PrecisionTimer>()) {
    timer_->initialize();
    start_time_ns_ = timer_->get_timestamp_ns();
}

ScopedTimer::~ScopedTimer() {
    uint64_t end_time_ns = timer_->get_timestamp_ns();
    uint64_t elapsed = end_time_ns - start_time_ns_;
    
    std::cout << "⏱️  " << name_ << " elapsed: " 
              << PrecisionTimer::ns_to_seconds(elapsed) << " seconds ("
              << elapsed << " ns)" << std::endl;
}

uint64_t ScopedTimer::elapsed_ns() const {
    return timer_->get_timestamp_ns() - start_time_ns_;
}

void ScopedTimer::reset() {
    start_time_ns_ = timer_->get_timestamp_ns();
}

// IntervalTimer implementation
IntervalTimer::IntervalTimer(std::chrono::nanoseconds interval)
    : interval_(interval), timer_(std::make_unique<PrecisionTimer>()) {
    timer_->initialize();
}

bool IntervalTimer::start() {
    if (running_.load()) {
        return false; // Already running
    }
    
    next_target_time_ns_ = timer_->get_timestamp_ns() + interval_.count();
    running_.store(true);
    
    // Reset statistics
    reset_stats();
    
    return true;
}

void IntervalTimer::stop() {
    running_.store(false);
}

bool IntervalTimer::wait_for_next() {
    if (!running_.load()) {
        return false;
    }
    
    uint64_t current_time = timer_->get_timestamp_ns();
    
    if (current_time < next_target_time_ns_) {
        // Sleep until target time
        uint64_t sleep_ns = next_target_time_ns_ - current_time;
        
        if (sleep_ns > 1000000) { // > 1ms, use system sleep
            auto sleep_duration = std::chrono::nanoseconds(sleep_ns - 100000); // Subtract 100μs for precision
            std::this_thread::sleep_for(sleep_duration);
            
            // Busy wait for the remaining time
            while (timer_->get_timestamp_ns() < next_target_time_ns_ && running_.load()) {
                std::this_thread::yield();
            }
        } else {
            // Busy wait for short intervals
            while (timer_->get_timestamp_ns() < next_target_time_ns_ && running_.load()) {
                std::this_thread::yield();
            }
        }
    }
    
    // Update timing statistics
    uint64_t actual_time = timer_->get_timestamp_ns();
    uint64_t drift = (actual_time > next_target_time_ns_) ? 
                     (actual_time - next_target_time_ns_) : 0;
    
    total_drift_ns_ += drift;
    max_drift_ns_ = std::max(max_drift_ns_, drift);
    intervals_completed_++;
    
    // Set next target time
    next_target_time_ns_ += interval_.count();
    
    return running_.load();
}

IntervalTimer::TimingStats IntervalTimer::get_stats() const {
    TimingStats stats;
    stats.intervals_completed = intervals_completed_;
    stats.total_drift_ns = total_drift_ns_;
    stats.max_drift_ns = max_drift_ns_;
    
    if (intervals_completed_ > 0) {
        stats.average_drift_ns = static_cast<double>(total_drift_ns_) / intervals_completed_;
    }
    
    return stats;
}

void IntervalTimer::reset_stats() {
    intervals_completed_ = 0;
    total_drift_ns_ = 0;
    max_drift_ns_ = 0;
}

} // namespace codegreen::nemb::utils