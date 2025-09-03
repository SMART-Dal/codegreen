#include "../../../include/nemb/hal/counter_manager.hpp"

#include <iostream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cmath>

namespace codegreen::nemb::hal {

// CounterManager implementation

bool CounterManager::register_counter(const std::string& counter_id, const CounterConfig& config) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (!is_valid_counter_id(counter_id)) {
        std::cerr << "Invalid counter ID: " << counter_id << std::endl;
        return false;
    }
    
    if (counters_.find(counter_id) != counters_.end()) {
        std::cerr << "Counter already registered: " << counter_id << std::endl;
        return false;
    }
    
    ManagedCounter managed_counter;
    managed_counter.config = config;
    managed_counter.counter = std::make_unique<Counter64>(config.max_value, config.name);
    managed_counter.initialized = false;
    
    counters_[counter_id] = std::move(managed_counter);
    counter_configs_[counter_id] = config;
    
    log_counter_event("REGISTER", counter_id);
    return true;
}

bool CounterManager::initialize_counters(const std::map<std::string, uint64_t>& initial_values,
                                       uint64_t timestamp_ns) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    bool all_initialized = true;
    
    for (auto& [counter_id, managed_counter] : counters_) {
        auto it = initial_values.find(counter_id);
        if (it != initial_values.end()) {
            managed_counter.counter->initialize(it->second, timestamp_ns);
            managed_counter.initialized = true;
            log_counter_event("INITIALIZE", counter_id);
        } else {
            std::cerr << "Missing initial value for counter: " << counter_id << std::endl;
            all_initialized = false;
        }
    }
    
    return all_initialized;
}

std::map<std::string, uint64_t> CounterManager::update_counters(
    const std::map<std::string, uint64_t>& raw_values,
    uint64_t timestamp_ns) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    std::map<std::string, uint64_t> accumulated_values;
    
    for (auto& [counter_id, managed_counter] : counters_) {
        if (!managed_counter.config.active) {
            continue;
        }
        
        auto it = raw_values.find(counter_id);
        if (it != raw_values.end()) {
            uint64_t accumulated = managed_counter.counter->update(it->second, timestamp_ns);
            accumulated_values[counter_id] = accumulated;
        } else {
            std::cerr << "Missing raw value for active counter: " << counter_id << std::endl;
        }
    }
    
    return accumulated_values;
}

std::map<std::string, uint64_t> CounterManager::get_accumulated_values() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    std::map<std::string, uint64_t> values;
    for (const auto& [counter_id, managed_counter] : counters_) {
        if (managed_counter.config.active && managed_counter.initialized) {
            values[counter_id] = managed_counter.counter->get_accumulated();
        }
    }
    
    return values;
}

double CounterManager::get_energy_joules(const std::string& counter_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = counters_.find(counter_id);
    if (it == counters_.end() || !it->second.initialized || !it->second.config.active) {
        return 0.0;
    }
    
    uint64_t accumulated = it->second.counter->get_accumulated();
    return convert_to_joules(accumulated, it->second.config);
}

double CounterManager::get_total_energy_joules() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    double total_energy = 0.0;
    for (const auto& [counter_id, managed_counter] : counters_) {
        if (managed_counter.config.active && managed_counter.initialized) {
            uint64_t accumulated = managed_counter.counter->get_accumulated();
            total_energy += convert_to_joules(accumulated, managed_counter.config);
        }
    }
    
    return total_energy;
}

std::optional<Counter64::Statistics> CounterManager::get_counter_statistics(
    const std::string& counter_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = counters_.find(counter_id);
    if (it == counters_.end()) {
        return std::nullopt;
    }
    
    return it->second.counter->get_statistics();
}

void CounterManager::reset_all_counters() {
    std::lock_guard<std::mutex> lock(mutex_);
    
    for (auto& [counter_id, managed_counter] : counters_) {
        managed_counter.counter->reset();
        managed_counter.initialized = false;
        log_counter_event("RESET", counter_id);
    }
}

void CounterManager::set_counter_active(const std::string& counter_id, bool active) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = counters_.find(counter_id);
    if (it != counters_.end()) {
        it->second.config.active = active;
        counter_configs_[counter_id].active = active;
        log_counter_event(active ? "ACTIVATE" : "DEACTIVATE", counter_id);
    }
}

bool CounterManager::validate_counter_consistency() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Check for reasonable energy values
    for (const auto& [counter_id, managed_counter] : counters_) {
        if (!managed_counter.config.active || !managed_counter.initialized) {
            continue;
        }
        
        auto stats = managed_counter.counter->get_statistics();
        
        // Check for excessive wraparounds (might indicate problems)
        if (stats.wraparound_count > 1000) {
            std::cerr << "Warning: Counter " << counter_id 
                      << " has excessive wraparounds: " << stats.wraparound_count << std::endl;
        }
        
        // Check for unreasonable energy values (>1000J suggests a problem)
        double energy_j = convert_to_joules(stats.accumulated_value, managed_counter.config);
        if (energy_j > 1000.0) {
            std::cerr << "Warning: Counter " << counter_id 
                      << " reports excessive energy: " << energy_j << " J" << std::endl;
        }
    }
    
    return true;
}

std::string CounterManager::get_summary() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    std::stringstream ss;
    ss << std::fixed << std::setprecision(6);
    ss << "Counter Manager Summary:\n";
    ss << "========================\n";
    
    double total_energy = 0.0;
    uint32_t active_counters = 0;
    
    for (const auto& [counter_id, managed_counter] : counters_) {
        const auto& config = managed_counter.config;
        ss << "Counter: " << counter_id << "\n";
        ss << "  Name: " << config.name << "\n";
        ss << "  Domain: " << config.domain << "\n";
        ss << "  Active: " << (config.active ? "Yes" : "No") << "\n";
        ss << "  Initialized: " << (managed_counter.initialized ? "Yes" : "No") << "\n";
        
        if (config.active && managed_counter.initialized) {
            auto stats = managed_counter.counter->get_statistics();
            double energy_j = convert_to_joules(stats.accumulated_value, config);
            
            ss << "  Accumulated: " << stats.accumulated_value << " raw units\n";
            ss << "  Energy: " << energy_j << " J\n";
            ss << "  Wraparounds: " << stats.wraparound_count << "\n";
            ss << "  Last Raw: " << stats.last_raw_value << "\n";
            
            total_energy += energy_j;
            active_counters++;
        }
        ss << "\n";
    }
    
    ss << "Total Energy: " << total_energy << " J\n";
    ss << "Active Counters: " << active_counters << "\n";
    
    return ss.str();
}

// Private helper methods

bool CounterManager::is_valid_counter_id(const std::string& counter_id) const {
    // Counter ID should be non-empty and contain only alphanumeric chars and underscores
    if (counter_id.empty()) {
        return false;
    }
    
    return std::all_of(counter_id.begin(), counter_id.end(), [](char c) {
        return std::isalnum(c) || c == '_' || c == '-';
    });
}

double CounterManager::convert_to_joules(uint64_t raw_value, const CounterConfig& config) const {
    return static_cast<double>(raw_value) * config.conversion_factor;
}

void CounterManager::log_counter_event(const std::string& event, const std::string& counter_id) const {
    std::cout << "🔢 Counter " << event << ": " << counter_id << std::endl;
}

// RAPLCounterManager implementation

bool RAPLCounterManager::initialize_rapl_counters(double energy_unit, uint32_t available_domains) {
    energy_unit_ = energy_unit;
    available_domains_ = available_domains;
    
    std::cout << "🔋 Initializing RAPL counters..." << std::endl;
    std::cout << "  Energy unit: " << (energy_unit * 1e6) << " μJ" << std::endl;
    std::cout << "  Available domains: 0x" << std::hex << available_domains << std::dec << std::endl;
    
    // Register each available domain
    std::vector<Domain> domains_to_register;
    if (available_domains & (1 << static_cast<int>(Domain::PACKAGE))) {
        domains_to_register.push_back(Domain::PACKAGE);
    }
    if (available_domains & (1 << static_cast<int>(Domain::PP0))) {
        domains_to_register.push_back(Domain::PP0);
    }
    if (available_domains & (1 << static_cast<int>(Domain::PP1))) {
        domains_to_register.push_back(Domain::PP1);
    }
    if (available_domains & (1 << static_cast<int>(Domain::DRAM))) {
        domains_to_register.push_back(Domain::DRAM);
    }
    if (available_domains & (1 << static_cast<int>(Domain::PSYS))) {
        domains_to_register.push_back(Domain::PSYS);
    }
    
    bool all_registered = true;
    for (Domain domain : domains_to_register) {
        CounterConfig config;
        config.name = get_domain_name(domain);
        config.domain = config.name;
        config.bit_width = 32;  // RAPL counters are 32-bit
        config.max_value = UINT32_MAX;
        config.conversion_factor = energy_unit;
        config.unit = "J";
        config.active = true;
        
        std::string counter_id = domain_to_counter_id(domain);
        if (!register_counter(counter_id, config)) {
            all_registered = false;
            std::cerr << "Failed to register RAPL domain: " << get_domain_name(domain) << std::endl;
        } else {
            std::cout << "  ✅ Registered " << get_domain_name(domain) << std::endl;
        }
    }
    
    return all_registered;
}

std::map<RAPLCounterManager::Domain, double> RAPLCounterManager::update_rapl_readings(
    uint32_t package_energy,
    uint32_t pp0_energy,
    uint32_t pp1_energy,
    uint32_t dram_energy,
    uint32_t psys_energy,
    uint64_t timestamp_ns) {
    
    std::map<std::string, uint64_t> raw_values;
    
    // Map domain values to counter IDs
    if (is_domain_available(Domain::PACKAGE)) {
        raw_values[domain_to_counter_id(Domain::PACKAGE)] = package_energy;
    }
    if (is_domain_available(Domain::PP0)) {
        raw_values[domain_to_counter_id(Domain::PP0)] = pp0_energy;
    }
    if (is_domain_available(Domain::PP1)) {
        raw_values[domain_to_counter_id(Domain::PP1)] = pp1_energy;
    }
    if (is_domain_available(Domain::DRAM)) {
        raw_values[domain_to_counter_id(Domain::DRAM)] = dram_energy;
    }
    if (is_domain_available(Domain::PSYS)) {
        raw_values[domain_to_counter_id(Domain::PSYS)] = psys_energy;
    }
    
    // Update all counters
    update_counters(raw_values, timestamp_ns);
    
    // Return domain-mapped energy values
    std::map<Domain, double> domain_energies;
    for (const auto& [raw_counter_id, raw_value] : raw_values) {
        Domain domain = counter_id_to_domain(raw_counter_id);
        domain_energies[domain] = get_energy_joules(raw_counter_id);
    }
    
    return domain_energies;
}

double RAPLCounterManager::get_domain_energy(Domain domain) const {
    if (!is_domain_available(domain)) {
        return 0.0;
    }
    
    std::string counter_id = domain_to_counter_id(domain);
    return get_energy_joules(counter_id);
}

double RAPLCounterManager::get_total_package_energy() const {
    // For RAPL, we typically want to use the PACKAGE domain as the primary measure
    // to avoid double-counting (since PP0+PP1+DRAM should roughly equal PACKAGE)
    if (is_domain_available(Domain::PACKAGE)) {
        return get_domain_energy(Domain::PACKAGE);
    }
    
    // Fallback: sum all available domains
    double total = 0.0;
    if (is_domain_available(Domain::PP0)) {
        total += get_domain_energy(Domain::PP0);
    }
    if (is_domain_available(Domain::PP1)) {
        total += get_domain_energy(Domain::PP1);
    }
    if (is_domain_available(Domain::DRAM)) {
        total += get_domain_energy(Domain::DRAM);
    }
    
    return total;
}

bool RAPLCounterManager::is_domain_available(Domain domain) const {
    return (available_domains_ & (1 << static_cast<int>(domain))) != 0;
}

std::string RAPLCounterManager::get_domain_name(Domain domain) {
    switch (domain) {
        case Domain::PACKAGE:
            return "Package";
        case Domain::PP0:
            return "PP0 (Cores)";
        case Domain::PP1:
            return "PP1 (Uncore)";
        case Domain::DRAM:
            return "DRAM";
        case Domain::PSYS:
            return "Platform";
        default:
            return "Unknown";
    }
}

// Private helper methods

std::string RAPLCounterManager::domain_to_counter_id(Domain domain) const {
    switch (domain) {
        case Domain::PACKAGE:
            return "rapl_package";
        case Domain::PP0:
            return "rapl_pp0";
        case Domain::PP1:
            return "rapl_pp1";
        case Domain::DRAM:
            return "rapl_dram";
        case Domain::PSYS:
            return "rapl_psys";
        default:
            return "rapl_unknown";
    }
}

RAPLCounterManager::Domain RAPLCounterManager::counter_id_to_domain(const std::string& counter_id) const {
    if (counter_id == "rapl_package") return Domain::PACKAGE;
    if (counter_id == "rapl_pp0") return Domain::PP0;
    if (counter_id == "rapl_pp1") return Domain::PP1;
    if (counter_id == "rapl_dram") return Domain::DRAM;
    if (counter_id == "rapl_psys") return Domain::PSYS;
    return Domain::PACKAGE; // Default fallback
}

} // namespace codegreen::nemb::hal