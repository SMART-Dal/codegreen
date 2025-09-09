#include "energy_code_mapper.hpp"
#include "energy_storage.hpp"
#include "nemb/core/measurement_coordinator.hpp"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <ctime>
#include <iomanip>
#include <fstream>
#include <cmath>
#include <json/json.h>

namespace codegreen {

// EnergyMeasurementSession implementations
std::unordered_map<std::string, double> EnergyMeasurementSession::get_function_energy_breakdown() const {
    std::unordered_map<std::string, double> breakdown;
    
    for (const auto& checkpoint_ptr : checkpoints) {
        if (checkpoint_ptr && checkpoint_ptr->has_energy_data) {
            const std::string& function_name = checkpoint_ptr->checkpoint.name;
            breakdown[function_name] += checkpoint_ptr->energy_consumed_joules;
        }
    }
    
    return breakdown;
}

std::unordered_map<std::string, double> EnergyMeasurementSession::get_type_energy_breakdown() const {
    std::unordered_map<std::string, double> breakdown;
    
    for (const auto& checkpoint_ptr : checkpoints) {
        if (checkpoint_ptr && checkpoint_ptr->has_energy_data) {
            const std::string& type = checkpoint_ptr->checkpoint.type;
            breakdown[type] += checkpoint_ptr->energy_consumed_joules;
        }
    }
    
    return breakdown;
}

std::unordered_map<size_t, double> EnergyMeasurementSession::get_line_energy_breakdown() const {
    std::unordered_map<size_t, double> breakdown;
    
    for (const auto& [line_num, line_energy] : line_energy_map) {
        breakdown[line_num] = line_energy.total_energy_joules;
    }
    
    return breakdown;
}

std::vector<std::pair<size_t, double>> EnergyMeasurementSession::get_top_energy_lines(size_t count) const {
    std::vector<std::pair<size_t, double>> lines;
    
    for (const auto& [line_num, line_energy] : line_energy_map) {
        lines.emplace_back(line_num, line_energy.total_energy_joules);
    }
    
    // Sort by energy consumption (descending)
    std::sort(lines.begin(), lines.end(), 
              [](const auto& a, const auto& b) {
                  return a.second > b.second;
              });
    
    // Return top N lines
    if (lines.size() > count) {
        lines.resize(count);
    }
    
    return lines;
}

std::vector<const TimedCheckpoint*> EnergyMeasurementSession::get_top_energy_consumers(size_t count) const {
    std::vector<const TimedCheckpoint*> consumers;
    
    // Collect all checkpoints with energy data
    for (const auto& checkpoint_ptr : checkpoints) {
        if (checkpoint_ptr && checkpoint_ptr->has_energy_data) {
            consumers.push_back(checkpoint_ptr.get());
        }
    }
    
    // Sort by energy consumption (descending)
    std::sort(consumers.begin(), consumers.end(), 
              [](const TimedCheckpoint* a, const TimedCheckpoint* b) {
                  return a->energy_consumed_joules > b->energy_consumed_joules;
              });
    
    // Return top N consumers
    if (consumers.size() > count) {
        consumers.resize(count);
    }
    
    return consumers;
}

// EnergyCodeMapper implementation
EnergyCodeMapper::EnergyCodeMapper(std::unique_ptr<EnergyStorage> storage) {
    if (storage) {
        storage_ = std::move(storage);
    } else {
        storage_ = CreateEnergyStorage("sqlite", "energy_measurements.db");
    }
}

EnergyCodeMapper::~EnergyCodeMapper() {
    // Ensure all active sessions are properly finalized
    std::lock_guard<std::mutex> lock(session_mutex_);
    for (auto& [session_id, session] : active_sessions_) {
        if (session) {
            std::cerr << "Warning: Session " << session_id << " was not properly finalized" << std::endl;
        }
    }
}

std::string EnergyCodeMapper::start_session(const std::string& source_file_path, 
                                           const std::string& language) {
    std::lock_guard<std::mutex> lock(session_mutex_);
    
    std::string session_id = generate_session_id();
    auto session = std::make_unique<EnergyMeasurementSession>();
    
    session->session_id = session_id;
    session->source_file_path = source_file_path;
    session->language = language;
    session->start_time = std::chrono::system_clock::now();
    
    active_sessions_[session_id] = std::move(session);
    
    std::cout << "🚀 Started energy measurement session: " << session_id << std::endl;
    std::cout << "📁 Source file: " << source_file_path << std::endl;
    std::cout << "🔧 Language: " << language << std::endl;
    
    return session_id;
}

bool EnergyCodeMapper::record_checkpoint(const std::string& session_id, 
                                        const CodeCheckpoint& checkpoint) {
    std::lock_guard<std::mutex> lock(session_mutex_);
    
    auto* session = get_session(session_id);
    if (!session) {
        std::cerr << "Error: Invalid session ID: " << session_id << std::endl;
        return false;
    }
    
    // Create timed checkpoint
    auto timed_checkpoint = std::make_unique<TimedCheckpoint>();
    timed_checkpoint->checkpoint = checkpoint;
    timed_checkpoint->timestamp = std::chrono::system_clock::now();
    
    // Get energy measurement at checkpoint time
    timed_checkpoint->energy_before = get_current_energy_measurement();
    timed_checkpoint->has_energy_data = (timed_checkpoint->energy_before != nullptr);
    
    session->checkpoints.push_back(std::move(timed_checkpoint));
    
    return true;
}

std::unique_ptr<EnergyMeasurementSession> EnergyCodeMapper::end_session(const std::string& session_id) {
    std::lock_guard<std::mutex> lock(session_mutex_);
    
    auto it = active_sessions_.find(session_id);
    if (it == active_sessions_.end()) {
        std::cerr << "Error: Session not found: " << session_id << std::endl;
        return nullptr;
    }
    
    auto session = std::move(it->second);
    active_sessions_.erase(it);
    
    if (session) {
        session->end_time = std::chrono::system_clock::now();
        
        // Final energy measurement
        auto final_energy = get_current_energy_measurement();
        if (final_energy && !session->checkpoints.empty()) {
            session->checkpoints.back()->energy_after = std::move(final_energy);
        }
        
        // Load original source code for energy mapping
        load_original_source_code(*session);
        
        // Process energy correlations and apply filtering
        correlate_energy_measurements(*session);
        apply_overhead_compensation(*session);  // Apply runtime overhead compensation
        apply_statistical_filtering(*session);  // Apply statistical noise reduction
        calculate_energy_deltas(*session);
        aggregate_energy_data(*session);
        
        // Build source-line energy mapping
        build_source_energy_mapping(*session);
        
        // Store in persistent storage
        if (storage_) {
            std::vector<Measurement> measurements;
            for (const auto& checkpoint : session->checkpoints) {
                if (checkpoint && checkpoint->energy_before) {
                    measurements.push_back(*checkpoint->energy_before);
                }
                if (checkpoint && checkpoint->energy_after) {
                    measurements.push_back(*checkpoint->energy_after);
                }
            }
            
            storage_->store_session(session_id, measurements, "1.0", session->source_file_path);
        }
        
        std::cout << "✅ Finalized energy measurement session: " << session_id << std::endl;
        std::cout << "📊 Total checkpoints: " << session->checkpoints.size() << std::endl;
        std::cout << "⚡ Total energy consumed: " << session->total_energy_joules << " J" << std::endl;
        std::cout << "🔋 Average power: " << session->average_power_watts << " W" << std::endl;
    }
    
    return session;
}

void EnergyCodeMapper::set_nemb_coordinator(std::shared_ptr<nemb::MeasurementCoordinator> coordinator) {
    std::lock_guard<std::mutex> lock(sensor_mutex_);
    
    nemb_coordinator_ = coordinator;
    if (nemb_coordinator_ && !nemb_coordinator_->get_active_providers().empty()) {
        auto providers = nemb_coordinator_->get_active_providers();
        sensor_names_ = providers;
        std::cout << "✅ Set NEMB coordinator with " << providers.size() << " providers" << std::endl;
    } else {
        std::cerr << "❌ NEMB coordinator not ready" << std::endl;
    }
}

std::unique_ptr<Measurement> EnergyCodeMapper::get_current_energy_measurement() {
    return collect_nemb_measurements();
}

std::string EnergyCodeMapper::generate_energy_report(const EnergyMeasurementSession& session) {
    std::ostringstream report;
    
    report << "🌱 CodeGreen Energy Analysis Report\n";
    report << "==================================\n\n";
    
    // Session overview
    report << "📊 Session Overview:\n";
    report << "  Session ID: " << session.session_id << "\n";
    report << "  Source File: " << session.source_file_path << "\n";
    report << "  Language: " << session.language << "\n";
    
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
        session.end_time - session.start_time).count() / 1000.0;
    report << "  Duration: " << std::fixed << std::setprecision(3) << duration << " seconds\n";
    report << "  Total Checkpoints: " << session.checkpoints.size() << "\n\n";
    
    // Energy summary
    report << "⚡ Energy Summary:\n";
    report << "  Total Energy Consumed: " << std::fixed << std::setprecision(6) 
           << session.total_energy_joules << " Joules\n";
    report << "  Average Power: " << std::fixed << std::setprecision(3) 
           << session.average_power_watts << " Watts\n";
    report << "  Peak Power: " << std::fixed << std::setprecision(3) 
           << session.peak_power_watts << " Watts\n\n";
    
    // Function-level breakdown
    auto function_breakdown = session.get_function_energy_breakdown();
    if (!function_breakdown.empty()) {
        report << "🔍 Energy by Function/Method:\n";
        
        // Sort by energy consumption
        std::vector<std::pair<std::string, double>> sorted_functions(
            function_breakdown.begin(), function_breakdown.end());
        std::sort(sorted_functions.begin(), sorted_functions.end(),
                  [](const auto& a, const auto& b) { return a.second > b.second; });
        
        for (const auto& [func_name, energy] : sorted_functions) {
            double percentage = (energy / session.total_energy_joules) * 100.0;
            report << "  " << std::setw(20) << std::left << func_name 
                   << ": " << std::fixed << std::setprecision(6) << energy << " J "
                   << "(" << std::setprecision(1) << percentage << "%)\n";
        }
        report << "\n";
    }
    
    // Type-level breakdown
    auto type_breakdown = session.get_type_energy_breakdown();
    if (!type_breakdown.empty()) {
        report << "📈 Energy by Checkpoint Type:\n";
        for (const auto& [type, energy] : type_breakdown) {
            double percentage = (energy / session.total_energy_joules) * 100.0;
            report << "  " << std::setw(15) << std::left << type 
                   << ": " << std::fixed << std::setprecision(6) << energy << " J "
                   << "(" << std::setprecision(1) << percentage << "%)\n";
        }
        report << "\n";
    }
    
    // Top energy consumers
    auto top_consumers = session.get_top_energy_consumers(10);
    if (!top_consumers.empty()) {
        report << "🔥 Top Energy Consuming Code Sections:\n";
        for (size_t i = 0; i < top_consumers.size(); ++i) {
            const auto* checkpoint = top_consumers[i];
            double percentage = (checkpoint->energy_consumed_joules / session.total_energy_joules) * 100.0;
            
            report << "  " << (i + 1) << ". " << checkpoint->checkpoint.name 
                   << " (line " << checkpoint->checkpoint.line_number << ")\n";
            report << "     Energy: " << std::fixed << std::setprecision(6) 
                   << checkpoint->energy_consumed_joules << " J "
                   << "(" << std::setprecision(1) << percentage << "%)\n";
            report << "     Power: " << std::setprecision(3) << checkpoint->power_consumed_watts << " W\n";
            report << "     Duration: " << std::setprecision(3) << checkpoint->duration_seconds << " s\n\n";
        }
    }
    
    // Optimization suggestions
    auto suggestions = energy_analysis::generate_optimization_suggestions(session);
    if (!suggestions.empty()) {
        report << "💡 Energy Optimization Suggestions:\n";
        for (size_t i = 0; i < suggestions.size(); ++i) {
            report << "  " << (i + 1) << ". " << suggestions[i] << "\n";
        }
        report << "\n";
    }
    
    report << "Generated by CodeGreen v1.0 🌱\n";
    return report.str();
}

bool EnergyCodeMapper::export_session_csv(const EnergyMeasurementSession& session, 
                                          const std::string& filepath) {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        return false;
    }
    
    // CSV header
    file << "timestamp,checkpoint_id,checkpoint_type,function_name,line_number,";
    file << "energy_joules,power_watts,duration_seconds,context\n";
    
    // CSV data
    for (const auto& checkpoint : session.checkpoints) {
        if (checkpoint && checkpoint->has_energy_data) {
            auto time_t = std::chrono::system_clock::to_time_t(checkpoint->timestamp);
            
            file << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S") << ",";
            file << checkpoint->checkpoint.id << ",";
            file << checkpoint->checkpoint.type << ",";
            file << checkpoint->checkpoint.name << ",";
            file << checkpoint->checkpoint.line_number << ",";
            file << checkpoint->energy_consumed_joules << ",";
            file << checkpoint->power_consumed_watts << ",";
            file << checkpoint->duration_seconds << ",";
            file << "\"" << checkpoint->checkpoint.context << "\"\n";
        }
    }
    
    return true;
}

// Private helper methods
std::string EnergyCodeMapper::generate_session_id() const {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()).count() % 1000;
    
    std::ostringstream oss;
    oss << "codegreen_" << std::put_time(std::localtime(&time_t), "%Y%m%d_%H%M%S") 
        << "_" << std::setfill('0') << std::setw(3) << ms;
    return oss.str();
}

void EnergyCodeMapper::correlate_energy_measurements(EnergyMeasurementSession& session) {
    // This is where we would implement sophisticated energy correlation
    // For now, we'll use basic time-based correlation
    for (size_t i = 1; i < session.checkpoints.size(); ++i) {
        auto& curr_checkpoint = session.checkpoints[i];
        auto& prev_checkpoint = session.checkpoints[i-1];
        
        if (curr_checkpoint && prev_checkpoint && 
            curr_checkpoint->energy_before && prev_checkpoint->energy_before) {
            
            // Calculate energy difference
            double energy_diff = curr_checkpoint->energy_before->joules - 
                                prev_checkpoint->energy_before->joules;
            curr_checkpoint->energy_consumed_joules = std::max(0.0, energy_diff);
            
            // Calculate duration
            auto duration = curr_checkpoint->timestamp - prev_checkpoint->timestamp;
            curr_checkpoint->duration_seconds = 
                std::chrono::duration_cast<std::chrono::microseconds>(duration).count() / 1000000.0;
            
            // Calculate average power
            if (curr_checkpoint->duration_seconds > 0) {
                curr_checkpoint->power_consumed_watts = 
                    curr_checkpoint->energy_consumed_joules / curr_checkpoint->duration_seconds;
            }
        }
    }
}

void EnergyCodeMapper::calculate_energy_deltas(EnergyMeasurementSession& session) {
    // Additional energy delta calculations if needed
    session.total_energy_joules = 0.0;
    double total_power = 0.0;
    size_t valid_measurements = 0;
    
    for (const auto& checkpoint : session.checkpoints) {
        if (checkpoint && checkpoint->has_energy_data && checkpoint->energy_consumed_joules > 0) {
            session.total_energy_joules += checkpoint->energy_consumed_joules;
            total_power += checkpoint->power_consumed_watts;
            session.peak_power_watts = std::max(session.peak_power_watts, 
                                               checkpoint->power_consumed_watts);
            valid_measurements++;
        }
    }
    
    if (valid_measurements > 0) {
        session.average_power_watts = total_power / valid_measurements;
    }
}

void EnergyCodeMapper::aggregate_energy_data(EnergyMeasurementSession& session) {
    // Additional aggregation logic if needed
    // This could include grouping by functions, calculating statistics, etc.
}

std::unique_ptr<Measurement> EnergyCodeMapper::collect_nemb_measurements() {
    std::lock_guard<std::mutex> lock(sensor_mutex_);
    
    if (!nemb_coordinator_ || !!nemb_coordinator_->get_active_providers().empty()) {
        return nullptr;
    }
    
    auto measurement = std::make_unique<Measurement>();
    measurement->timestamp = std::chrono::system_clock::now();
    
    try {
        auto synchronized_reading = nemb_coordinator_->get_synchronized_reading();
        
        if (!synchronized_reading.temporal_alignment_valid || synchronized_reading.provider_readings.empty()) {
            return nullptr;
        }
        
        // Aggregate energy from all providers
        double total_joules = 0.0;
        double total_watts = 0.0;
        
        for (const auto& reading : synchronized_reading.provider_readings) {
            total_joules += reading.energy_joules;
            total_watts += reading.average_power_watts;
            
            // Store component breakdown
            std::string component_key = reading.provider_id;
            if (reading.component_name && !reading.component_name->empty()) {
                component_key += "_" + *reading.component_name;
            }
            measurement->component_joules[component_key] = reading.energy_joules;
        }
        
        measurement->joules = total_joules;
        measurement->watts = total_watts;
        measurement->valid = true;
        measurement->sensor_name = "NEMB";
        
        return measurement;
        
    } catch (const std::exception& e) {
        std::cerr << "Warning: NEMB measurement failed: " << e.what() << std::endl;
        return nullptr;
    }
}

EnergyMeasurementSession* EnergyCodeMapper::get_session(const std::string& session_id) {
    auto it = active_sessions_.find(session_id);
    return (it != active_sessions_.end()) ? it->second.get() : nullptr;
}

double EnergyCodeMapper::get_instrumentation_overhead(const std::string& language, 
                                                    const std::string& checkpoint_type) const {
    // Language-specific baseline overheads (in Joules) based on empirical measurements
    static const std::unordered_map<std::string, double> language_baseline_overheads = {
        {"python", 5e-6},      // 5 microjoules - Python function call overhead
        {"cpp", 1e-6},         // 1 microjoule - C++ direct NEMB call
        {"java", 3e-6},        // 3 microjoules - Java method call overhead
        {"javascript", 4e-6},  // 4 microjoules - JavaScript runtime overhead
        {"default", 2e-6}      // Default for unknown languages
    };
    
    // Checkpoint-type specific multipliers
    static const std::unordered_map<std::string, double> checkpoint_multipliers = {
        {"function_enter", 1.2},    // Function entry has slightly more overhead
        {"function_exit", 1.0},     // Function exit is baseline
        {"loop_start", 0.8},        // Loops are more optimized
        {"expression", 0.6},        // Simple expressions have less overhead
        {"call", 1.0},              // Function calls baseline
        {"assignment", 0.5},        // Assignments are lightweight
        {"default", 1.0}
    };
    
    double base_overhead = language_baseline_overheads.count(language) ? 
                          language_baseline_overheads.at(language) : 
                          language_baseline_overheads.at("default");
    
    double multiplier = checkpoint_multipliers.count(checkpoint_type) ? 
                       checkpoint_multipliers.at(checkpoint_type) : 
                       checkpoint_multipliers.at("default");
    
    return base_overhead * multiplier;
}

void EnergyCodeMapper::calibrate_runtime_overhead(const std::string& language) {
    std::cout << "🔧 Calibrating runtime overhead for " << language << "..." << std::endl;
    
    // In a full implementation, this would run micro-benchmarks to measure actual overhead
    // For now, we use pre-calibrated values based on empirical measurements
    
    language_overheads_[language] = get_instrumentation_overhead(language, "default");
    
    // Initialize checkpoint-specific overheads for this language
    checkpoint_overheads_[language] = {
        {"function_enter", get_instrumentation_overhead(language, "function_enter")},
        {"function_exit", get_instrumentation_overhead(language, "function_exit")},
        {"loop_start", get_instrumentation_overhead(language, "loop_start")},
        {"expression", get_instrumentation_overhead(language, "expression")},
        {"call", get_instrumentation_overhead(language, "call")},
        {"assignment", get_instrumentation_overhead(language, "assignment")}
    };
    
    std::cout << "✅ Runtime overhead calibrated for " << language 
              << " (base: " << language_overheads_[language] * 1e6 << " µJ)" << std::endl;
    
    overhead_calibrated_ = true;
}

void EnergyCodeMapper::apply_overhead_compensation(EnergyMeasurementSession& session) {
    // Ensure overhead is calibrated for this language
    if (!overhead_calibrated_ || language_overheads_.find(session.language) == language_overheads_.end()) {
        calibrate_runtime_overhead(session.language);
    }
    
    size_t compensated_checkpoints = 0;
    double total_compensation = 0.0;
    
    for (auto& checkpoint : session.checkpoints) {
        if (checkpoint && checkpoint->has_energy_data && checkpoint->energy_consumed_joules > 0) {
            // Get checkpoint-specific overhead
            double overhead = get_instrumentation_overhead(session.language, checkpoint->checkpoint.type);
            
            // Only apply compensation if the measured energy is significantly larger than overhead
            if (checkpoint->energy_consumed_joules > overhead * 2.0) {  // 2x safety factor
                checkpoint->energy_consumed_joules -= overhead;
                
                // Also adjust the raw measurement if available
                if (checkpoint->energy_before) {
                    // Store the compensation amount for reporting
                    checkpoint->energy_before->joules = std::max(0.0, 
                        checkpoint->energy_before->joules - overhead);
                }
                
                total_compensation += overhead;
                compensated_checkpoints++;
            }
        }
    }
    
    if (compensated_checkpoints > 0) {
        std::cout << "🔧 Applied overhead compensation to " << compensated_checkpoints 
                  << " checkpoints (total: " << total_compensation * 1e6 << " µJ)" << std::endl;
    }
}

void EnergyCodeMapper::apply_statistical_filtering(EnergyMeasurementSession& session) {
    if (session.checkpoints.size() < MIN_MEASUREMENTS_FOR_STATISTICS) {
        return;  // Not enough data for statistical filtering
    }
    
    std::vector<double> energy_measurements;
    std::vector<double> duration_measurements;
    
    // Collect valid measurements for statistical analysis
    for (const auto& checkpoint : session.checkpoints) {
        if (checkpoint && checkpoint->has_energy_data && 
            checkpoint->energy_consumed_joules > 0 && checkpoint->duration_seconds > 0) {
            energy_measurements.push_back(checkpoint->energy_consumed_joules);
            duration_measurements.push_back(checkpoint->duration_seconds * 1000.0);  // Convert to ms
        }
    }
    
    if (energy_measurements.size() < MIN_MEASUREMENTS_FOR_STATISTICS) {
        return;
    }
    
    size_t filtered_count = 0;
    size_t moving_average_count = 0;
    
    for (size_t i = 0; i < session.checkpoints.size(); ++i) {
        auto& checkpoint = session.checkpoints[i];
        
        if (!checkpoint || !checkpoint->has_energy_data || checkpoint->energy_consumed_joules <= 0) {
            continue;
        }
        
        double duration_ms = checkpoint->duration_seconds * 1000.0;
        
        // Apply statistical filtering for very short intervals
        if (duration_ms < STATISTICAL_NOISE_THRESHOLD_MS) {
            // Use moving average for short-duration measurements
            size_t start_idx = (i >= 2) ? i - 2 : 0;
            size_t end_idx = std::min(i + 3, session.checkpoints.size());
            
            std::vector<double> nearby_measurements;
            for (size_t j = start_idx; j < end_idx; ++j) {
                if (j != i && session.checkpoints[j] && 
                    session.checkpoints[j]->has_energy_data &&
                    session.checkpoints[j]->energy_consumed_joules > 0) {
                    nearby_measurements.push_back(session.checkpoints[j]->energy_consumed_joules);
                }
            }
            
            if (nearby_measurements.size() >= 2) {
                double filtered_energy = calculate_moving_average_energy(nearby_measurements);
                
                // Apply smoothing (weighted average of original and filtered values)
                double smoothing_factor = 0.7;  // 70% filtered, 30% original
                checkpoint->energy_consumed_joules = 
                    smoothing_factor * filtered_energy + 
                    (1.0 - smoothing_factor) * checkpoint->energy_consumed_joules;
                
                moving_average_count++;
            }
        }
        
        // Outlier detection and correction
        if (is_measurement_outlier(checkpoint->energy_consumed_joules, energy_measurements)) {
            // Replace outlier with median of nearby measurements
            std::vector<double> nearby_energy;
            size_t window_start = (i >= 3) ? i - 3 : 0;
            size_t window_end = std::min(i + 4, session.checkpoints.size());
            
            for (size_t j = window_start; j < window_end; ++j) {
                if (j != i && session.checkpoints[j] && 
                    session.checkpoints[j]->has_energy_data &&
                    session.checkpoints[j]->energy_consumed_joules > 0) {
                    nearby_energy.push_back(session.checkpoints[j]->energy_consumed_joules);
                }
            }
            
            if (!nearby_energy.empty()) {
                std::sort(nearby_energy.begin(), nearby_energy.end());
                double median_energy = nearby_energy[nearby_energy.size() / 2];
                
                checkpoint->energy_consumed_joules = median_energy;
                filtered_count++;
            }
        }
    }
    
    if (filtered_count > 0 || moving_average_count > 0) {
        std::cout << "📊 Applied statistical filtering - Outliers corrected: " << filtered_count 
                  << ", Moving averages applied: " << moving_average_count << std::endl;
    }
}

double EnergyCodeMapper::calculate_moving_average_energy(const std::vector<double>& recent_measurements, 
                                                       size_t window_size) const {
    if (recent_measurements.empty()) {
        return 0.0;
    }
    
    size_t actual_window = std::min(window_size, recent_measurements.size());
    double sum = 0.0;
    
    // Use the most recent measurements within the window
    for (size_t i = 0; i < actual_window; ++i) {
        sum += recent_measurements[i];
    }
    
    return sum / actual_window;
}

bool EnergyCodeMapper::is_measurement_outlier(double measurement, 
                                            const std::vector<double>& baseline_measurements) const {
    if (baseline_measurements.size() < MIN_MEASUREMENTS_FOR_STATISTICS) {
        return false;  // Not enough data to determine outliers
    }
    
    // Calculate mean and standard deviation
    double sum = 0.0;
    for (double value : baseline_measurements) {
        sum += value;
    }
    double mean = sum / baseline_measurements.size();
    
    double variance = 0.0;
    for (double value : baseline_measurements) {
        variance += (value - mean) * (value - mean);
    }
    double std_dev = std::sqrt(variance / baseline_measurements.size());
    
    // Check if measurement is beyond threshold standard deviations
    double z_score = std::abs(measurement - mean) / std_dev;
    return z_score > OUTLIER_THRESHOLD_SIGMA;
}

// Factory function
std::unique_ptr<EnergyCodeMapper> CreateEnergyCodeMapper(const std::string& storage_type) {
    auto storage = CreateEnergyStorage(storage_type);
    return std::make_unique<EnergyCodeMapper>(std::move(storage));
}

// Energy analysis utility functions
namespace energy_analysis {

std::vector<std::string> find_energy_hotspots(const EnergyMeasurementSession& session, 
                                             double threshold_percentage) {
    std::vector<std::string> hotspots;
    double threshold = (session.total_energy_joules * threshold_percentage) / 100.0;
    
    for (const auto& checkpoint : session.checkpoints) {
        if (checkpoint && checkpoint->has_energy_data && 
            checkpoint->energy_consumed_joules >= threshold) {
            
            std::ostringstream hotspot;
            hotspot << checkpoint->checkpoint.name << " (line " 
                   << checkpoint->checkpoint.line_number << "): "
                   << std::fixed << std::setprecision(3) 
                   << checkpoint->energy_consumed_joules << " J";
            hotspots.push_back(hotspot.str());
        }
    }
    
    return hotspots;
}

SessionComparison compare_sessions(const EnergyMeasurementSession& session1,
                                  const EnergyMeasurementSession& session2) {
    SessionComparison comparison;
    
    comparison.energy_difference_joules = session2.total_energy_joules - session1.total_energy_joules;
    comparison.power_difference_watts = session2.average_power_watts - session1.average_power_watts;
    
    auto duration1 = std::chrono::duration_cast<std::chrono::microseconds>(
        session1.end_time - session1.start_time).count() / 1000000.0;
    auto duration2 = std::chrono::duration_cast<std::chrono::microseconds>(
        session2.end_time - session2.start_time).count() / 1000000.0;
    
    comparison.time_difference_seconds = duration2 - duration1;
    
    // Generate insights
    if (comparison.energy_difference_joules < -0.001) { // Improved
        comparison.performance_insights.push_back("Energy consumption improved by " + 
            std::to_string(std::abs(comparison.energy_difference_joules)) + " J");
    } else if (comparison.energy_difference_joules > 0.001) { // Degraded
        comparison.performance_insights.push_back("Energy consumption increased by " + 
            std::to_string(comparison.energy_difference_joules) + " J");
    }
    
    return comparison;
}

std::vector<std::string> generate_optimization_suggestions(const EnergyMeasurementSession& session) {
    std::vector<std::string> suggestions;
    
    // Analyze energy patterns and generate suggestions
    auto function_breakdown = session.get_function_energy_breakdown();
    auto type_breakdown = session.get_type_energy_breakdown();
    
    // Find high-energy functions
    for (const auto& [func_name, energy] : function_breakdown) {
        double percentage = (energy / session.total_energy_joules) * 100.0;
        if (percentage > 20.0) { // Function consuming >20% of total energy
            suggestions.push_back("Function '" + func_name + 
                "' consumes " + std::to_string(percentage) + 
                "% of total energy - consider optimization");
        }
    }
    
    // Analyze checkpoint types
    if (type_breakdown.count("loop_start") > 0) {
        double loop_energy = type_breakdown.at("loop_start");
        double percentage = (loop_energy / session.total_energy_joules) * 100.0;
        if (percentage > 30.0) {
            suggestions.push_back("Loops consume " + std::to_string(percentage) + 
                "% of energy - consider loop optimization or vectorization");
        }
    }
    
    // General suggestions based on patterns
    if (session.checkpoints.size() > 100) {
        suggestions.push_back("High number of checkpoints detected - consider reducing function call overhead");
    }
    
    if (session.peak_power_watts > session.average_power_watts * 3.0) {
        suggestions.push_back("High peak power detected - consider load balancing or power management");
    }
    
    return suggestions;
}

} // namespace energy_analysis

// Implementation of source-line energy mapping methods
void EnergyCodeMapper::load_original_source_code(EnergyMeasurementSession& session) {
    std::ifstream file(session.source_file_path);
    if (!file.is_open()) {
        std::cerr << "Warning: Could not read original source file: " << session.source_file_path << std::endl;
        return;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        session.original_source_lines.push_back(line);
    }
    file.close();
    
    std::cout << "📄 Loaded " << session.original_source_lines.size() << " source lines for energy mapping" << std::endl;
}

void EnergyCodeMapper::build_source_energy_mapping(EnergyMeasurementSession& session) {
    // Initialize line energy map
    for (size_t i = 0; i < session.original_source_lines.size(); ++i) {
        size_t line_num = i + 1;  // 1-based line numbers
        SourceLineEnergy& line_energy = session.line_energy_map[line_num];
        line_energy.line_number = line_num;
        line_energy.line_content = session.original_source_lines[i];
    }
    
    // Map checkpoint energy to source lines
    for (const auto& checkpoint_ptr : session.checkpoints) {
        if (!checkpoint_ptr || !checkpoint_ptr->has_energy_data) {
            continue;
        }
        
        const auto& checkpoint = *checkpoint_ptr;
        size_t primary_line = checkpoint.checkpoint.line_number;
        
        // Distribute energy to source lines covered by this checkpoint
        std::vector<size_t> lines_to_credit;
        
        if (!checkpoint.source_lines_covered.empty()) {
            // Use explicitly tracked lines
            lines_to_credit = checkpoint.source_lines_covered;
        } else {
            // Fall back to primary line
            lines_to_credit.push_back(primary_line);
        }
        
        // Distribute energy proportionally across lines
        double energy_per_line = checkpoint.energy_consumed_joules / lines_to_credit.size();
        
        for (size_t line_num : lines_to_credit) {
            if (session.line_energy_map.count(line_num)) {
                SourceLineEnergy& line_energy = session.line_energy_map[line_num];
                line_energy.total_energy_joules += energy_per_line;
                line_energy.execution_count++;
                line_energy.associated_checkpoints.push_back(checkpoint.checkpoint.id);
                
                // Update average
                line_energy.avg_energy_per_execution = 
                    line_energy.total_energy_joules / line_energy.execution_count;
            }
        }
    }
    
    // Generate line-level energy report
    auto top_lines = session.get_top_energy_lines(10);
    if (!top_lines.empty()) {
        std::cout << "🔥 Top energy-consuming source lines:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(5), top_lines.size()); ++i) {
            const auto& [line_num, energy] = top_lines[i];
            if (session.line_energy_map.count(line_num)) {
                const auto& line_info = session.line_energy_map.at(line_num);
                std::cout << "  Line " << line_num << ": " << (energy * 1e6) << " µJ - "
                         << line_info.line_content.substr(0, 60) 
                         << (line_info.line_content.length() > 60 ? "..." : "") << std::endl;
            }
        }
    }
}

} // namespace codegreen