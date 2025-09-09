#include "config.hpp"
#include <fstream>
#include <iostream>
#include <regex>
#include <cstdlib>
#include <chrono>

#ifdef _WIN32
#include <windows.h>
#include <shlobj.h>
#else
#include <unistd.h>
#include <pwd.h>
#endif

namespace codegreen {

Config& Config::instance() {
    static Config instance;
    return instance;
}

bool Config::load_from_file(const std::filesystem::path& config_file) {
    std::filesystem::path actual_config_file = config_file.empty() ? find_config_file() : config_file;
    
    if (!std::filesystem::exists(actual_config_file)) {
        std::cerr << "Config file not found: " << actual_config_file << std::endl;
        std::cerr << "Loading default configuration..." << std::endl;
        load_defaults();
        return false;
    }
    
    std::ifstream file(actual_config_file);
    if (!file.is_open()) {
        std::cerr << "Failed to open config file: " << actual_config_file << std::endl;
        load_defaults();
        return false;
    }
    
    Json::CharReaderBuilder builder;
    std::string errs;
    if (!Json::parseFromStream(builder, file, &config_data_, &errs)) {
        std::cerr << "Failed to parse config file: " << errs << std::endl;
        load_defaults();
        return false;
    }
    
    if (!validate_configuration()) {
        std::cerr << "Configuration validation failed:" << std::endl;
        for (const auto& error : validation_errors_) {
            std::cerr << "  - " << error << std::endl;
        }
        return false;
    }
    
    std::cout << "Configuration loaded from: " << actual_config_file << std::endl;
    return true;
}

bool Config::save_to_file(const std::filesystem::path& config_file) {
    std::filesystem::path actual_config_file = config_file.empty() ? find_config_file() : config_file;
    
    // Ensure directory exists
    std::filesystem::create_directories(actual_config_file.parent_path());
    
    std::ofstream file(actual_config_file);
    if (!file.is_open()) {
        std::cerr << "Failed to open config file for writing: " << actual_config_file << std::endl;
        return false;
    }
    
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "  ";
    std::unique_ptr<Json::StreamWriter> writer(builder.newStreamWriter());
    writer->write(config_data_, &file);
    
    return true;
}

void Config::load_defaults() {
    // Create default configuration
    config_data_ = Json::Value(Json::objectValue);
    
    // Paths
    config_data_["paths"]["runtime_modules"]["python"] = "runtime/codegreen_runtime.py";
    config_data_["paths"]["runtime_modules"]["base_directory"] = "${EXECUTABLE_DIR}/runtime";
    config_data_["paths"]["temp_directory"]["base"] = "${SYSTEM_TEMP}";
    config_data_["paths"]["temp_directory"]["prefix"] = "codegreen_";
    config_data_["paths"]["temp_directory"]["cleanup_on_exit"] = true;
    config_data_["paths"]["database"]["default_path"] = "${USER_HOME}/.codegreen/energy_data.db";
    config_data_["paths"]["logs"]["directory"] = "${USER_HOME}/.codegreen/logs";
    config_data_["paths"]["logs"]["level"] = "INFO";
    
    // Measurement settings
    config_data_["measurement"]["timing"]["precision"] = "high";
    config_data_["measurement"]["timing"]["sync_method"] = "perf_counter";
    // NEMB handles all energy measurement - no PMT configuration needed
    config_data_["measurement"]["accuracy"]["separate_instrumentation_phase"] = true;
    
    // Performance settings
    config_data_["performance"]["string_optimization"]["cache_checkpoint_calls"] = true;
    config_data_["performance"]["database"]["batch_operations"] = true;
    
    // Security settings
    config_data_["security"]["sql_injection_protection"] = true;
    config_data_["security"]["path_validation"] = true;
    
    // Languages
    config_data_["languages"]["python"]["executable"] = "python3";
    config_data_["languages"]["python"]["runtime_module"] = "codegreen_runtime.py";
    config_data_["languages"]["python"]["extensions"].append(".py");
    config_data_["languages"]["python"]["extensions"].append(".pyw");
    config_data_["languages"]["python"]["extensions"].append(".pyi");
    
    // Developer settings
    config_data_["developer"]["debug_mode"] = false;
    config_data_["developer"]["verbose_logging"] = false;
    config_data_["developer"]["preserve_temp_files"] = false;
    
    std::cout << "Default configuration loaded" << std::endl;
}

std::filesystem::path Config::get_runtime_module_path(const std::string& language) const {
    std::string base_dir = get_string("paths.runtime_modules.base_directory", "${EXECUTABLE_DIR}/runtime");
    std::string module_file = get_string("languages." + language + ".runtime_module", "runtime.py");
    
    std::filesystem::path resolved_base = resolve_path(base_dir);
    return resolved_base / module_file;
}

std::filesystem::path Config::get_temp_directory() const {
    std::string base = get_string("paths.temp_directory.base", "${SYSTEM_TEMP}");
    std::string prefix = get_string("paths.temp_directory.prefix", "codegreen_");
    
    std::filesystem::path temp_base = resolve_path(base);
    
    // Create secure temporary directory with unpredictable name
    std::filesystem::path temp_dir;
    for (int attempts = 0; attempts < 100; ++attempts) {
        // Generate more secure random directory name
        auto now = std::chrono::high_resolution_clock::now();
        auto nanos = now.time_since_epoch().count();
        std::string unique_name = prefix + std::to_string(nanos) + "_" + 
                                std::to_string(getpid()) + "_" + std::to_string(attempts);
        
        temp_dir = temp_base / unique_name;
        
        try {
            // Try to create directory with secure permissions (owner only)
            std::filesystem::create_directories(temp_dir);
            std::filesystem::permissions(temp_dir, 
                                       std::filesystem::perms::owner_read |
                                       std::filesystem::perms::owner_write |
                                       std::filesystem::perms::owner_exec,
                                       std::filesystem::perm_options::replace);
            break; // Success
        } catch (const std::filesystem::filesystem_error& e) {
            if (attempts == 99) {
                throw std::runtime_error("Failed to create secure temp directory after 100 attempts");
            }
            // Continue to next attempt
        }
    }
    
    return temp_dir;
}

std::filesystem::path Config::get_database_path() const {
    std::string db_path = get_string("paths.database.default_path", "${USER_HOME}/.codegreen/energy_data.db");
    return resolve_path(db_path);
}

std::filesystem::path Config::get_log_directory() const {
    std::string log_dir = get_string("paths.logs.directory", "${USER_HOME}/.codegreen/logs");
    return resolve_path(log_dir);
}

std::string Config::get_string(const std::string& key, const std::string& default_value) const {
    Json::Value value = get_nested_value(key);
    return value.isString() ? value.asString() : default_value;
}

int Config::get_int(const std::string& key, int default_value) const {
    Json::Value value = get_nested_value(key);
    return value.isInt() ? value.asInt() : default_value;
}

double Config::get_double(const std::string& key, double default_value) const {
    Json::Value value = get_nested_value(key);
    return value.isDouble() ? value.asDouble() : default_value;
}

bool Config::get_bool(const std::string& key, bool default_value) const {
    Json::Value value = get_nested_value(key);
    return value.isBool() ? value.asBool() : default_value;
}

std::vector<std::string> Config::get_string_array(const std::string& key) const {
    std::vector<std::string> result;
    Json::Value value = get_nested_value(key);
    
    if (value.isArray()) {
        for (const auto& item : value) {
            if (item.isString()) {
                result.push_back(item.asString());
            }
        }
    }
    
    return result;
}

void Config::set_string(const std::string& key, const std::string& value) {
    // Navigate to nested key and set value
    std::vector<std::string> keys;
    std::stringstream ss(key);
    std::string item;
    
    while (std::getline(ss, item, '.')) {
        keys.push_back(item);
    }
    
    Json::Value* current = &config_data_;
    for (size_t i = 0; i < keys.size() - 1; ++i) {
        current = &(*current)[keys[i]];
    }
    (*current)[keys.back()] = value;
}

void Config::set_int(const std::string& key, int value) {
    // Similar implementation to set_string but for int
    std::vector<std::string> keys;
    std::stringstream ss(key);
    std::string item;
    
    while (std::getline(ss, item, '.')) {
        keys.push_back(item);
    }
    
    Json::Value* current = &config_data_;
    for (size_t i = 0; i < keys.size() - 1; ++i) {
        current = &(*current)[keys[i]];
    }
    (*current)[keys.back()] = value;
}

void Config::set_bool(const std::string& key, bool value) {
    std::vector<std::string> keys;
    std::stringstream ss(key);
    std::string item;
    
    while (std::getline(ss, item, '.')) {
        keys.push_back(item);
    }
    
    Json::Value* current = &config_data_;
    for (size_t i = 0; i < keys.size() - 1; ++i) {
        current = &(*current)[keys[i]];
    }
    (*current)[keys.back()] = value;
}

// PMT methods removed - NEMB handles all energy measurement

std::string Config::get_language_executable(const std::string& language) const {
    return get_string("languages." + language + ".executable", language);
}

std::vector<std::string> Config::get_language_extensions(const std::string& language) const {
    return get_string_array("languages." + language + ".extensions");
}

bool Config::is_debug_mode() const {
    return get_bool("developer.debug_mode", false);
}

bool Config::is_verbose_logging() const {
    return get_bool("developer.verbose_logging", false);
}

std::filesystem::path Config::resolve_path(const std::string& path_template) const {
    std::string resolved = substitute_variables(path_template);
    return std::filesystem::path(resolved);
}

std::filesystem::path Config::get_executable_directory() const {
    if (executable_dir_cached_) {
        return executable_dir_;
    }
    
#ifdef _WIN32
    char buffer[MAX_PATH];
    GetModuleFileNameA(nullptr, buffer, MAX_PATH);
    executable_dir_ = std::filesystem::path(buffer).parent_path();
#else
    char buffer[1024];
    ssize_t len = readlink("/proc/self/exe", buffer, sizeof(buffer) - 1);
    if (len != -1) {
        buffer[len] = '\0';
        executable_dir_ = std::filesystem::path(buffer).parent_path();
    } else {
        executable_dir_ = std::filesystem::current_path();
    }
#endif
    
    executable_dir_cached_ = true;
    return executable_dir_;
}

std::filesystem::path Config::get_user_home_directory() const {
#ifdef _WIN32
    char* home = getenv("USERPROFILE");
    if (home) {
        return std::filesystem::path(home);
    }
    return std::filesystem::path("C:\\Users\\Default");
#else
    char* home = getenv("HOME");
    if (home) {
        return std::filesystem::path(home);
    }
    
    struct passwd* pw = getpwuid(getuid());
    if (pw) {
        return std::filesystem::path(pw->pw_dir);
    }
    return std::filesystem::path("/tmp");
#endif
}

std::filesystem::path Config::get_system_temp_directory() const {
    return std::filesystem::temp_directory_path();
}

bool Config::validate_configuration() const {
    validation_errors_.clear();
    
    // Validate required paths exist or can be created
    try {
        auto temp_dir = get_temp_directory().parent_path();
        // Atomic directory creation - no TOCTOU race condition
        std::filesystem::create_directories(temp_dir);
    } catch (const std::exception& e) {
        validation_errors_.push_back("Cannot create temp directory: " + std::string(e.what()));
    }
    
    // Validate language configurations
    auto languages = {"python", "cpp", "java"};
    for (const auto& lang : languages) {
        std::string exec = get_language_executable(lang);
        auto extensions = get_language_extensions(lang);
        if (extensions.empty()) {
            validation_errors_.push_back("Language " + std::string(lang) + " has no file extensions defined");
        }
    }
    
    // NEMB handles sensor validation - no PMT validation needed
    
    return validation_errors_.empty();
}

std::vector<std::string> Config::get_validation_errors() const {
    return validation_errors_;
}

std::string Config::substitute_variables(const std::string& template_str) const {
    std::string result = template_str;
    
    // Replace common variables
    std::regex executable_dir_regex(R"(\$\{EXECUTABLE_DIR\})");
    result = std::regex_replace(result, executable_dir_regex, get_executable_directory().string());
    
    std::regex user_home_regex(R"(\$\{USER_HOME\})");
    result = std::regex_replace(result, user_home_regex, get_user_home_directory().string());
    
    std::regex system_temp_regex(R"(\$\{SYSTEM_TEMP\})");
    result = std::regex_replace(result, system_temp_regex, get_system_temp_directory().string());
    
    // Replace environment variables
    std::regex env_regex(R"(\$\{([^}]+)\})");
    std::smatch match;
    
    while (std::regex_search(result, match, env_regex)) {
        std::string var_name = match[1].str();
        const char* env_value = std::getenv(var_name.c_str());
        std::string replacement = env_value ? env_value : "";
        result = std::regex_replace(result, std::regex("\\$\\{" + var_name + "\\}"), replacement);
    }
    
    return result;
}

Json::Value Config::get_nested_value(const std::string& key) const {
    std::vector<std::string> keys;
    std::stringstream ss(key);
    std::string item;
    
    while (std::getline(ss, item, '.')) {
        keys.push_back(item);
    }
    
    Json::Value current = config_data_;
    for (const auto& k : keys) {
        if (current.isMember(k)) {
            current = current[k];
        } else {
            return Json::Value::null;
        }
    }
    
    return current;
}

std::filesystem::path Config::find_config_file() const {
    // Search order: current dir, executable dir, user config dir, system config dir
    std::vector<std::filesystem::path> search_paths = {
        std::filesystem::current_path() / "config" / "codegreen.json",
        get_executable_directory() / "config" / "codegreen.json",
        get_user_home_directory() / ".codegreen" / "config.json",
        get_executable_directory().parent_path() / "config" / "codegreen.json"
    };
    
    for (const auto& path : search_paths) {
        if (std::filesystem::exists(path)) {
            return path;
        }
    }
    
    // Return default path if none found
    return get_executable_directory() / "config" / "codegreen.json";
}

void Config::ensure_directory_exists(const std::filesystem::path& dir) const {
    // Atomic directory creation - no TOCTOU race condition  
    std::filesystem::create_directories(dir);
}

// ConfigLoader implementation
ConfigLoader::ConfigLoader(const std::filesystem::path& config_file) 
    : config_(Config::instance()), loaded_(false) {
    
    loaded_ = config_.load_from_file(config_file);
    if (!loaded_) {
        error_message_ = "Failed to load configuration from: " + config_file.string();
    }
}

} // namespace codegreen