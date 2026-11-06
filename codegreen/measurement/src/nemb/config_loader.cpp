#include "nemb/config_loader.hpp"

#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <cstdlib>
#include <cmath>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

// Simple JSON parser (minimal dependency approach)
#include <sstream>
#include <unordered_map>

namespace codegreen::nemb {

namespace {
    // Simplified config parsing without recursive JSON structures
    std::map<std::string, std::string> parse_simple_config(const std::string& content) {
        std::map<std::string, std::string> config;
        std::istringstream stream(content);
        std::string line;
        
        while (std::getline(stream, line)) {
            // Skip comments and empty lines
            line.erase(0, line.find_first_not_of(" \t"));
            if (line.empty() || line[0] == '/' || line[0] == '#' || line[0] == '{' || line[0] == '}') continue;
            
            // Simple key-value parsing
            size_t colon = line.find(':');
            if (colon == std::string::npos) continue;
            
            std::string key = line.substr(0, colon);
            std::string value = line.substr(colon + 1);
            
            // Clean up key and value
            key.erase(0, key.find_first_not_of(" \t\""));
            key.erase(key.find_last_not_of(" \t\",") + 1);
            value.erase(0, value.find_first_not_of(" \t\""));
            value.erase(value.find_last_not_of(" \t\",") + 1);
            
            config[key] = value;
        }
        
        return config;
    }
    
    std::string expand_path(const std::string& path) {
        std::string expanded = path;
        
        // Expand environment variables
        size_t pos = 0;
        while ((pos = expanded.find("${", pos)) != std::string::npos) {
            size_t end = expanded.find("}", pos);
            if (end == std::string::npos) break;
            
            std::string var_name = expanded.substr(pos + 2, end - pos - 2);
            const char* env_value = std::getenv(var_name.c_str());
            
            std::string replacement;
            if (env_value) {
                replacement = env_value;
            } else if (var_name == "EXECUTABLE_DIR") {
                // Fallback for executable directory
                replacement = std::filesystem::current_path().string();
            } else if (var_name == "USER_HOME") {
                const char* home = std::getenv("HOME");
                replacement = home ? home : "/tmp";
            } else if (var_name == "SYSTEM_TEMP") {
                replacement = "/tmp";
            }
            
            expanded.replace(pos, end - pos + 1, replacement);
            pos += replacement.length();
        }
        
        return expanded;
    }
}

static const int library_anchor = 0;  // any address inside this library, for locating it on disk

static std::filesystem::path library_dir() {
#ifdef _WIN32
    HMODULE module = nullptr;
    char buf[MAX_PATH];
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCSTR>(&library_anchor), &module) &&
        GetModuleFileNameA(module, buf, MAX_PATH) > 0)
        return std::filesystem::path(buf).parent_path();
#else
    Dl_info info;
    if (dladdr(&library_anchor, &info) && info.dli_fname)
        return std::filesystem::absolute(info.dli_fname).parent_path();
#endif
    return {};
}

std::string ConfigLoader::find_config_file() {
    if (const char* env = std::getenv("CODEGREEN_CONFIG"); env && *env) {
        if (!std::filesystem::is_regular_file(env)) throw std::runtime_error(std::string("CODEGREEN_CONFIG: no such file ") + env);
        return env;
    }
    auto dir = library_dir();
    if (dir.empty()) return "";
    for (const char* rel : {"../config.json", "../codegreen/config.json", "../share/codegreen/config.json"}) {
        auto p = dir / rel;
        if (std::filesystem::is_regular_file(p)) return std::filesystem::canonical(p).string();
    }
    return "";
}

// The flat parser cannot see structure; unbalanced braces, brackets or quotes mean a truncated or malformed file.
static void check_balanced(const std::string& s) {
    int depth = 0;
    bool in_str = false;
    for (size_t i = 0; i < s.size() && depth >= 0; ++i) {
        char c = s[i];
        if (in_str) { if (c == '\\') ++i; else if (c == '"') in_str = false; }
        else if (c == '"') in_str = true;
        else if (c == '{' || c == '[') ++depth;
        else if (c == '}' || c == ']') --depth;
    }
    if (depth != 0 || in_str) throw std::invalid_argument("unbalanced braces, brackets or quotes");
}

ConfigLoader::NEMBConfig ConfigLoader::parse_json_config(const std::string& json_content) {
    NEMBConfig config;
    check_balanced(json_content);
    {
        auto parsed_config = parse_simple_config(json_content);

        auto get_str = [&](const std::string& key, const std::string& def) -> std::string {
            auto it = parsed_config.find(key);
            return (it != parsed_config.end() && !it->second.empty()) ? it->second : def;
        };
        auto get_double = [&](const std::string& key, double def) -> double {
            auto it = parsed_config.find(key);
            if (it == parsed_config.end()) return def;
            size_t n = 0;
            double v = 0;
            try { v = std::stod(it->second, &n); } catch (const std::exception&) { n = 0; }
            if (n == 0 || n != it->second.size()) throw std::invalid_argument("'" + key + "' is not a number: " + it->second);
            return v;
        };
        auto get_uint = [&](const std::string& key, uint32_t def) -> uint32_t {
            double v = get_double(key, def);
            if (v < 0 || v > 4294967295.0 || v != std::floor(v)) throw std::invalid_argument("'" + key + "' is not an unsigned integer");
            return static_cast<uint32_t>(v);
        };
        auto get_bool = [&](const std::string& key, bool def) -> bool {
            auto it = parsed_config.find(key);
            if (it == parsed_config.end()) return def;
            return (it->second == "true" || it->second == "1");
        };

        // A key missing from the file keeps the NEMBConfig member default; those defaults equal the bundled config.json.
        auto& a = config.accuracy;
        auto& t = config.timing;
        auto& c = config.coordinator;
        a.target_uncertainty_percent = get_double("target_uncertainty_percent", a.target_uncertainty_percent);
        a.measurement_validation = get_bool("measurement_validation", a.measurement_validation);
        a.outlier_detection = get_bool("outlier_detection", a.outlier_detection);
        a.noise_filtering = get_str("noise_filtering", a.noise_filtering);
        a.statistical_validation = get_bool("statistical_validation", a.statistical_validation);
        a.confidence_threshold = get_double("confidence_threshold", a.confidence_threshold);
        t.precision = get_str("precision", t.precision);
        t.clock_source = get_str("clock_source", t.clock_source);
        c.measurement_interval_ms = get_uint("measurement_interval_ms", c.measurement_interval_ms);
        c.cross_validation = get_bool("cross_validation", c.cross_validation);
        c.cross_validation_threshold = get_double("cross_validation_threshold", c.cross_validation_threshold);
        c.measurement_buffer_size = get_uint("measurement_buffer_size", c.measurement_buffer_size);
        config.max_checkpoints = get_uint("max_checkpoints", config.max_checkpoints);
        c.auto_restart_failed_providers = get_bool("auto_restart_failed_providers", c.auto_restart_failed_providers);
        uint32_t restart_ms = get_uint("provider_restart_interval", static_cast<uint32_t>(c.provider_restart_interval.count() * 1000));
        c.provider_restart_interval = std::chrono::seconds(restart_ms / 1000);
        c.max_consecutive_failures = get_uint("max_consecutive_failures", c.max_consecutive_failures);
        c.real_time_filtering = get_bool("real_time_filtering", c.real_time_filtering);
    }
    return config;
}

ConfigLoader::NEMBConfig ConfigLoader::load_config(const std::string& config_path) {
    std::string path = config_path.empty() ? find_config_file() : config_path;
    if (path.empty())
        throw std::runtime_error("NEMB config: no config file found; set CODEGREEN_CONFIG or install config.json at "
                                 "<library dir>/../config.json, ../codegreen/config.json or ../share/codegreen/config.json (library dir: " +
                                 library_dir().string() + ")");
    std::ifstream file(path);
    if (!file.is_open()) throw std::runtime_error("NEMB config: cannot read " + path);
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    try {
        NEMBConfig config = parse_json_config(content);
        config.path = path;
        return config;
    } catch (const std::exception& e) {
        throw std::runtime_error("NEMB config: cannot parse " + path + ": " + e.what());
    }
}

} // namespace codegreen::nemb