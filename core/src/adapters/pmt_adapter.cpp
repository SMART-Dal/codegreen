#include "pmt_adapter.hpp"
#include "measurement.hpp"
#include "sensor_validator.hpp"
#include <pmt.h>
#include <iostream>
#include <unistd.h>
#include <cstdlib>
#include <sys/wait.h>
#include <filesystem>

namespace codegreen {

PMTAdapter::PMTAdapter(const std::vector<std::string>& sensor_types) 
    : sensor_names_(sensor_types), initialized_(false) {
}

PMTAdapter::~PMTAdapter() {
    cleanup();
}

std::string PMTAdapter::name() const {
    if (sensor_names_.empty()) {
        return "PMT";
    }
    
    std::string name = "PMT(";
    for (size_t i = 0; i < sensor_names_.size(); ++i) {
        if (i > 0) name += ",";
        name += sensor_names_[i];
    }
    name += ")";
    return name;
}

bool PMTAdapter::init() {
    if (initialized_) {
        return true;
    }

    try {
        // Initialize PMT sensors with validation
        sensors_.reserve(sensor_names_.size());
        std::vector<std::string> working_sensors;
        
        for (const auto& sensor_type : sensor_names_) {
            auto sensor = pmt::Create(sensor_type);
            if (sensor) {
                // Validate the sensor before adding it
                auto validator = CreateSensorValidator(sensor_type, std::move(sensor));
                auto health = validator->validate_sensor();
                
                if (health.is_available && !validator->is_fundamentally_broken()) {
                    // Recreate the sensor since validator consumed it
                    sensor = pmt::Create(sensor_type);
                    sensors_.push_back(std::move(sensor));
                    working_sensors.push_back(sensor_type);
                    
                    std::cout << "✅ " << sensor_type << " - " << health.status_message << std::endl;
                } else {
                    std::cerr << "❌ " << sensor_type << " - " << health.status_message << std::endl;
                    if (validator->is_fundamentally_broken()) {
                        std::cerr << "   💡 This sensor is fundamentally broken and will be disabled" << std::endl;
                    }
                }
            } else {
                std::cerr << "❌ " << sensor_type << " - Failed to create sensor" << std::endl;
            }
        }
        
        initialized_ = !sensors_.empty();
        if (initialized_) {
            std::cout << "🎯 PMT initialized with " << working_sensors.size() << " working sensors: ";
            for (const auto& sensor : working_sensors) {
                std::cout << sensor << " ";
            }
            std::cout << std::endl;
        } else {
            std::cerr << "⚠️  No PMT sensors available - falling back to dummy sensor" << std::endl;
        }
        
        return initialized_;
    } catch (const std::exception& e) {
        std::cerr << "PMT initialization error: " << e.what() << std::endl;
        return false;
    }
}

void PMTAdapter::cleanup() {
    sensors_.clear();
    initialized_ = false;
}

bool PMTAdapter::is_available() const {
    return initialized_ && !sensors_.empty();
}

std::unique_ptr<Measurement> PMTAdapter::get_measurement() const {
    if (!is_available()) {
        return nullptr;
    }

    // Try all sensors until one works
    for (size_t i = 0; i < sensors_.size(); ++i) {
        try {
            auto state = sensors_[i]->Read();
            auto measurement = convert_pmt_state(state, sensor_names_[i]);
            
            // Validate the measurement
            if (measurement && measurement->joules >= 0.0) {
                return measurement;
            }
        } catch (const std::exception& e) {
            // Log the error but continue trying other sensors
            std::cerr << "⚠️  Sensor '" << sensor_names_[i] << "' failed: " << e.what() << std::endl;
            
            // Provide helpful error messages for common failures
            if (sensor_names_[i] == "nvml") {
                std::cerr << "   💡 NVML sensor failed. To fix:" << std::endl;
                std::cerr << "      - Ensure NVIDIA GPU is present" << std::endl;
                std::cerr << "      - Install CUDA toolkit: sudo apt install nvidia-cuda-toolkit" << std::endl;
            } else if (sensor_names_[i] == "amdsmi") {
                std::cerr << "   💡 AMD SMI sensor failed. To fix:" << std::endl;
                std::cerr << "      - Install AMD SMI: sudo apt install rocm-smi" << std::endl;
            } else if (sensor_names_[i] == "powersensor3" || sensor_names_[i] == "powersensor2") {
                std::cerr << "   💡 PowerSensor failed. To fix:" << std::endl;
                std::cerr << "      - Connect PowerSensor USB device" << std::endl;
                std::cerr << "      - Ensure device permissions: sudo chmod 666 /dev/ttyACM0" << std::endl;
            } else if (sensor_names_[i] == "likwid") {
                std::cerr << "   💡 LIKWID sensor failed. To fix:" << std::endl;
                std::cerr << "      - Install LIKWID: sudo apt install likwid" << std::endl;
            } else if (sensor_names_[i] == "rocm") {
                std::cerr << "   💡 ROCm sensor failed. To fix:" << std::endl;
                std::cerr << "      - Install AMD ROCm from https://rocmdocs.amd.com/" << std::endl;
            }
            continue;
        }
    }
    
    // If all sensors failed, provide a helpful message
    std::cerr << "❌ All PMT sensors failed to provide measurements." << std::endl;
    std::cerr << "💡 This usually means:" << std::endl;
    std::cerr << "   - Hardware sensors are not properly configured" << std::endl;
    std::cerr << "   - Required libraries are missing" << std::endl;
    std::cerr << "   - Device permissions are insufficient" << std::endl;
    std::cerr << "💡 Check the error messages above for specific fixes." << std::endl;
    
    return nullptr;
}

std::unique_ptr<Measurement> PMTAdapter::convert_pmt_state(const pmt::State& state, const std::string& sensor_name) const {
    auto measurement = std::make_unique<Measurement>();
    measurement->source = sensor_name;
    
    // PMT State contains multiple measurements, use the first one
    if (state.NrMeasurements() > 0) {
        measurement->joules = static_cast<double>(state.joules(0));
        measurement->watts = static_cast<double>(state.watts(0));
    } else {
        measurement->joules = 0.0;
        measurement->watts = 0.0;
    }
    
    measurement->temperature = 0.0; // PMT doesn't provide temperature
    measurement->timestamp = std::chrono::system_clock::now();
    
    return measurement;
}

std::unique_ptr<PMTAdapter> CreatePMTAdapter() {
    // Smart sensor detection with graceful fallback
    std::vector<std::string> all_sensors = {
        "rapl",      // Intel/AMD power monitoring (usually available)
        "nvml",      // NVIDIA GPU power monitoring (if CUDA available)
        "amdsmi",    // AMD GPU power monitoring (if AMD SMI available)
        "powersensor3", // External USB power sensor (if device connected)
        "powersensor2", // External USB power sensor (if device connected)
        "likwid",    // Performance monitoring (if LIKWID available)
        "rocm",      // AMD ROCm (if ROCm available)
        "dummy"      // Fallback dummy sensor (always available)
    };
    
    std::vector<std::string> available_sensors;
    std::vector<std::string> failed_sensors;
    std::vector<std::string> runtime_disabled_sensors;
    
    std::cout << "🔍 Smart PMT sensor detection..." << std::endl;
    std::cout << "💡 All sensors are built - availability will be checked at runtime" << std::endl;
    
    for (const auto& sensor_type : all_sensors) {
        try {
            auto test_sensor = pmt::Create(sensor_type);
            if (test_sensor) {
                // Try to get a basic measurement to validate the sensor
                try {
                    auto state = test_sensor->Read();
                    auto joules = test_sensor->joules(state, state);
                    if (joules >= 0.0) {
                        available_sensors.push_back(sensor_type);
                        std::cout << "  ✅ " << sensor_type << " - Available and working" << std::endl;
                    } else {
                        runtime_disabled_sensors.push_back(sensor_type);
                        std::cout << "  ⚠️  " << sensor_type << " - Built but not working (will be disabled at runtime)" << std::endl;
                    }
                } catch (...) {
                    runtime_disabled_sensors.push_back(sensor_type);
                    std::cout << "  ⚠️  " << sensor_type << " - Built but failed validation (will be disabled at runtime)" << std::endl;
                }
            } else {
                failed_sensors.push_back(sensor_type);
                std::cout << "  ❌ " << sensor_type << " - Failed to create" << std::endl;
            }
        } catch (const std::exception& e) {
            failed_sensors.push_back(sensor_type);
            std::cout << "  ❌ " << sensor_type << " - Error: " << e.what() << std::endl;
        }
    }
    
    // Ensure we have at least one sensor
    if (available_sensors.empty()) {
        std::cout << "⚠️  No working sensors available, using dummy sensor" << std::endl;
        available_sensors.push_back("dummy");
    }
    
    // Print summary
    std::cout << "\n📊 PMT Sensor Status:" << std::endl;
    std::cout << "  ✅ Working sensors: " << available_sensors.size() << std::endl;
    std::cout << "  ⚠️  Runtime disabled: " << runtime_disabled_sensors.size() << std::endl;
    std::cout << "  ❌ Failed sensors: " << failed_sensors.size() << std::endl;
    
    if (!available_sensors.empty()) {
        std::cout << "  🎯 Primary sensors: ";
        for (size_t i = 0; i < available_sensors.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << available_sensors[i];
        }
        std::cout << std::endl;
    }
    
    if (!runtime_disabled_sensors.empty()) {
        std::cout << "  💡 Runtime disabled sensors (built but not working): ";
        for (size_t i = 0; i < runtime_disabled_sensors.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << runtime_disabled_sensors[i];
        }
        std::cout << std::endl;
        std::cout << "     These sensors will be automatically disabled when you use CodeGreen." << std::endl;
    }
    
    if (!failed_sensors.empty()) {
        std::cout << "  🔧 To fix failed sensors:" << std::endl;
        for (const auto& sensor : failed_sensors) {
            print_sensor_installation_help(sensor);
        }
    }
    
    std::cout << "\n💡 Smart behavior:" << std::endl;
    std::cout << "   - Working sensors will be used for measurements" << std::endl;
    std::cout << "   - Runtime disabled sensors will be automatically skipped" << std::endl;
    std::cout << "   - Failed sensors will show clear error messages" << std::endl;
    std::cout << std::endl;
    
    return std::make_unique<PMTAdapter>(available_sensors);
}

// Helper function to validate sensors at runtime with hardware-specific checks
bool validate_sensor_runtime(const std::string& sensor_type, std::unique_ptr<pmt::PMT>& sensor) {
    try {
        // Hardware-specific validation
        if (sensor_type == "rapl") {
            return validate_rapl_sensor(sensor);
        } else if (sensor_type == "nvml") {
            return validate_nvml_sensor(sensor);
        } else if (sensor_type == "amdsmi") {
            return validate_amdsmi_sensor(sensor);
        } else if (sensor_type == "powersensor3" || sensor_type == "powersensor2") {
            return validate_powersensor(sensor_type, sensor);
        } else if (sensor_type == "likwid") {
            return validate_likwid_sensor(sensor);
        } else if (sensor_type == "rocm") {
            return validate_rocm_sensor(sensor);
        } else if (sensor_type == "dummy") {
            return true; // Dummy sensor always works
        }
        
        // Default validation for unknown sensors
        auto state = sensor->Read();
        return sensor->joules(state, state) >= 0.0;
        
    } catch (const std::exception& e) {
        return false;
    }
}

// Hardware-specific validation functions
bool validate_rapl_sensor(std::unique_ptr<pmt::PMT>& sensor) {
    // Check if RAPL interface is actually accessible
    if (access("/sys/class/powercap/intel-rapl", R_OK) != 0) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        // RAPL should return reasonable values (not 0 or negative)
        return joules >= 0.0 && joules < 1000000.0; // Max 1MJ
    } catch (...) {
        return false;
    }
}

bool validate_nvml_sensor(std::unique_ptr<pmt::PMT>& sensor) {
    // Check if NVIDIA SMI executable exists and is accessible
    if (access("/usr/bin/nvidia-smi", X_OK) != 0 && access("/usr/local/bin/nvidia-smi", X_OK) != 0) {
        return false;
    }
    
    // Check if CUDA toolkit is available by checking for nvcc
    if (access("/usr/bin/nvcc", X_OK) != 0 && access("/usr/local/cuda/bin/nvcc", X_OK) != 0) {
        return false;
    }
    
    // Check for NVIDIA device files
    if (access("/dev/nvidia0", R_OK) != 0) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        return joules >= 0.0;
    } catch (...) {
        return false;
    }
}

bool validate_amdsmi_sensor(std::unique_ptr<pmt::PMT>& sensor) {
    // Check if ROCm SMI executable exists and is accessible
    if (access("/usr/bin/rocm-smi", X_OK) != 0 && access("/opt/rocm/bin/rocm-smi", X_OK) != 0) {
        return false;
    }
    
    // Check for AMD GPU device files
    if (!std::filesystem::exists("/sys/class/drm")) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        return joules >= 0.0;
    } catch (...) {
        return false;
    }
}

bool validate_powersensor(const std::string& sensor_type, std::unique_ptr<pmt::PMT>& sensor) {
    // Check if PowerSensor USB device files are accessible
    bool device_found = false;
    
    // Check common PowerSensor device paths
    for (int i = 0; i < 10; ++i) {
        std::string acm_path = "/dev/ttyACM" + std::to_string(i);
        std::string usb_path = "/dev/ttyUSB" + std::to_string(i);
        
        if (access(acm_path.c_str(), R_OK) == 0 || access(usb_path.c_str(), R_OK) == 0) {
            device_found = true;
            break;
        }
    }
    
    if (!device_found) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        return joules >= 0.0;
    } catch (...) {
        return false;
    }
}

bool validate_likwid_sensor(std::unique_ptr<pmt::PMT>& sensor) {
    // Check if LIKWID executables exist and are accessible
    if (access("/usr/bin/likwid-topology", X_OK) != 0 && access("/usr/local/bin/likwid-topology", X_OK) != 0) {
        return false;
    }
    
    if (access("/usr/bin/likwid-perfctr", X_OK) != 0 && access("/usr/local/bin/likwid-perfctr", X_OK) != 0) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        return joules >= 0.0;
    } catch (...) {
        return false;
    }
}

bool validate_rocm_sensor(std::unique_ptr<pmt::PMT>& sensor) {
    // Check if ROCm is actually installed and accessible
    if (access("/opt/rocm", R_OK) != 0) {
        return false;
    }
    
    // Check if ROCm SMI executable exists
    if (access("/opt/rocm/bin/rocm-smi", X_OK) != 0 && access("/usr/bin/rocm-smi", X_OK) != 0) {
        return false;
    }
    
    try {
        auto state = sensor->Read();
        auto joules = sensor->joules(state, state);
        return joules >= 0.0;
    } catch (...) {
        return false;
    }
}

// Helper function to print installation help
void print_sensor_installation_help(const std::string& sensor) {
    if (sensor == "nvml") {
        std::cout << "    - Install CUDA toolkit for " << sensor << std::endl;
    } else if (sensor == "amdsmi") {
        std::cout << "    - Install AMD SMI library for " << sensor << std::endl;
    } else if (sensor == "powersensor3" || sensor == "powersensor2") {
        std::cout << "    - Connect PowerSensor USB device for " << sensor << std::endl;
    } else if (sensor == "likwid") {
        std::cout << "    - Install LIKWID: sudo apt install likwid" << std::endl;
    } else if (sensor == "rocm") {
        std::cout << "    - Install AMD ROCm for " << sensor << std::endl;
    }
}

} // namespace codegreen
