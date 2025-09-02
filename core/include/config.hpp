#pragma once

#include <string>
#include <filesystem>
#include <unordered_map>
#include <vector>
#include <memory>
#include <json/json.h>

namespace codegreen {

/**
 * Comprehensive configuration management system for CodeGreen
 * Supports flexible path resolution, environment variable substitution,
 * and runtime configuration updates
 */
class Config {
public:
    static Config& instance();
    
    // Core initialization
    bool load_from_file(const std::filesystem::path& config_file = "");
    bool save_to_file(const std::filesystem::path& config_file = "");
    void load_defaults();
    
    // Path resolution with environment variable substitution
    std::filesystem::path get_runtime_module_path(const std::string& language) const;
    std::filesystem::path get_temp_directory() const;
    std::filesystem::path get_database_path() const;
    std::filesystem::path get_log_directory() const;
    
    // Configuration getters with defaults
    std::string get_string(const std::string& key, const std::string& default_value = "") const;
    int get_int(const std::string& key, int default_value = 0) const;
    double get_double(const std::string& key, double default_value = 0.0) const;
    bool get_bool(const std::string& key, bool default_value = false) const;
    std::vector<std::string> get_string_array(const std::string& key) const;
    
    // Configuration setters
    void set_string(const std::string& key, const std::string& value);
    void set_int(const std::string& key, int value);
    void set_double(const std::string& key, double value);
    void set_bool(const std::string& key, bool value);
    
    // Specialized getters for common configurations
    std::vector<std::string> get_preferred_pmt_sensors() const;
    std::string get_language_executable(const std::string& language) const;
    std::vector<std::string> get_language_extensions(const std::string& language) const;
    bool is_debug_mode() const;
    bool is_verbose_logging() const;
    
    // Path utilities
    std::filesystem::path resolve_path(const std::string& path_template) const;
    std::filesystem::path get_executable_directory() const;
    std::filesystem::path get_user_home_directory() const;
    std::filesystem::path get_system_temp_directory() const;
    
    // Validation
    bool validate_configuration() const;
    std::vector<std::string> get_validation_errors() const;
    
private:
    Config() = default;
    ~Config() = default;
    Config(const Config&) = delete;
    Config& operator=(const Config&) = delete;
    
    Json::Value config_data_;
    mutable std::vector<std::string> validation_errors_;
    mutable std::filesystem::path executable_dir_;
    mutable bool executable_dir_cached_ = false;
    
    // Helper methods
    std::string substitute_variables(const std::string& template_str) const;
    Json::Value get_nested_value(const std::string& key) const;
    std::filesystem::path find_config_file() const;
    void ensure_directory_exists(const std::filesystem::path& dir) const;
};

/**
 * RAII Configuration loader that ensures proper cleanup
 */
class ConfigLoader {
public:
    explicit ConfigLoader(const std::filesystem::path& config_file = "");
    ~ConfigLoader() = default;
    
    Config& get_config() { return config_; }
    const Config& get_config() const { return config_; }
    
    bool is_loaded() const { return loaded_; }
    const std::string& get_error() const { return error_message_; }
    
private:
    Config& config_;
    bool loaded_;
    std::string error_message_;
};

// Convenience macros for common config access
#define CODEGREEN_CONFIG() codegreen::Config::instance()
#define CODEGREEN_GET_STRING(key, default_val) CODEGREEN_CONFIG().get_string(key, default_val)
#define CODEGREEN_GET_BOOL(key, default_val) CODEGREEN_CONFIG().get_bool(key, default_val)
#define CODEGREEN_GET_PATH(path_template) CODEGREEN_CONFIG().resolve_path(path_template)

} // namespace codegreen