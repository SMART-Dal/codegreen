cmake_minimum_required(VERSION 3.16)
project(CodeGreen VERSION 0.1.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Find required packages
find_package(PkgConfig REQUIRED)
find_package(Threads REQUIRED)

# Find system libraries
pkg_check_modules(JSONCPP REQUIRED jsoncpp)
pkg_check_modules(CURL REQUIRED libcurl)
pkg_check_modules(SQLITE3 REQUIRED sqlite3)

# Global include directories
include_directories(${CMAKE_SOURCE_DIR}/core/include)
include_directories(${CMAKE_SOURCE_DIR}/packages/language-adapters/include)
include_directories(${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include)
include_directories(${CMAKE_SOURCE_DIR}/third_party/pmt)
include_directories(${CMAKE_SOURCE_DIR}/third_party/pmt/common)

# Add tree-sitter submodules
message(STATUS "Building tree-sitter language parsers...")
add_subdirectory(third_party/tree-sitter)

# Use EXCLUDE_FROM_ALL to avoid test target conflicts but still build libraries
add_subdirectory(third_party/tree-sitter-python EXCLUDE_FROM_ALL)

# Check if additional language parsers exist
if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/tree-sitter-c")
    message(STATUS "Found tree-sitter-c, but parser.c missing - C support disabled")
    set(HAS_TREE_SITTER_C OFF)
else()
    message(STATUS "tree-sitter-c not found, C support will be limited")
    set(HAS_TREE_SITTER_C OFF)
endif()

if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/tree-sitter-cpp")
    message(STATUS "Found tree-sitter-cpp, but parser.c missing - C++ support disabled")
    set(HAS_TREE_SITTER_CPP OFF)
else()
    message(STATUS "tree-sitter-cpp not found, C++ support will be limited")
    set(HAS_TREE_SITTER_CPP OFF)
endif()

if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/tree-sitter-java")
    message(STATUS "Found tree-sitter-java, but parser.c missing - Java support disabled")
    set(HAS_TREE_SITTER_JAVA OFF)
else()
    message(STATUS "tree-sitter-java not found, Java support will be limited")
    set(HAS_TREE_SITTER_JAVA OFF)
endif()

# PMT Configuration with robust sensor detection
message(STATUS "=== CodeGreen PMT Sensor Detection ===")

# Always enable dummy sensor as fallback
set(PMT_BUILD_DUMMY ON)
message(STATUS "✓ Dummy sensor enabled (always available)")

# Smart hardware detection with graceful fallbacks
set(PMT_BUILD_RAPL OFF)
set(PMT_BUILD_NVML OFF)
set(PMT_BUILD_TEGRA OFF)
set(PMT_BUILD_NVIDIA OFF)
set(PMT_BUILD_AMDSMI OFF)
set(PMT_BUILD_ROCM OFF)
set(PMT_BUILD_POWERSENSOR2 OFF)
set(PMT_BUILD_POWERSENSOR3 OFF)
set(PMT_BUILD_LIKWID OFF)
set(PMT_BUILD_CRAY OFF)
set(PMT_BUILD_XILINX OFF)

# Check for Intel/AMD RAPL support
if(EXISTS "/sys/class/powercap/intel-rapl" OR EXISTS "/sys/devices/virtual/powercap")
    message(STATUS "✓ RAPL interface detected - enabling RAPL sensor")
    set(PMT_BUILD_RAPL ON)
else()
    message(STATUS "⚠ RAPL interface not found - RAPL sensor disabled")
endif()

# Check for NVIDIA GPU support using safer file-based detection
if(EXISTS "/dev/nvidia0" OR EXISTS "/dev/nvidiactl" OR EXISTS "/proc/driver/nvidia")
    message(STATUS "✓ NVIDIA GPU detected via device files")
    
    # Check for CUDA development libraries (optional)
    find_package(CUDAToolkit QUIET)
    if(CUDAToolkit_FOUND)
        message(STATUS "  ✓ CUDA toolkit found - full NVML support enabled")
        set(PMT_BUILD_NVML ON)
        set(PMT_BUILD_NVIDIA ON)
        set(PMT_BUILD_TEGRA ON)
    else()
        message(STATUS "  ⚠ CUDA toolkit not found - disabling NVIDIA sensors for stability")
        # Disable NVIDIA sensors to avoid build issues
        set(PMT_BUILD_NVML OFF)
        set(PMT_BUILD_NVIDIA OFF)
        set(PMT_BUILD_TEGRA OFF)
    endif()
else()
    message(STATUS "⚠ No NVIDIA GPU detected - NVIDIA sensors disabled")
endif()

# Check for AMD processor and GPU support using safer file reading
if(EXISTS "/proc/cpuinfo")
    file(READ "/proc/cpuinfo" CPU_INFO)
    if(CPU_INFO MATCHES ".*AuthenticAMD.*")
        message(STATUS "✓ AMD processor detected")
    
    # Check for AMD SMI library
    find_library(AMD_SMI_LIB amdsmi QUIET)
    find_path(AMD_SMI_INCLUDE amdsmi/amdsmi.h QUIET)
    
    if(AMD_SMI_LIB AND AMD_SMI_INCLUDE)
        message(STATUS "  ✓ AMD SMI library found - enabling AMD SMI sensor")
        set(PMT_BUILD_AMDSMI ON)
    else()
        message(STATUS "  ⚠ AMD SMI library not found - AMD SMI sensor disabled")
    endif()
    
    # Check for ROCm
    if(EXISTS "/opt/rocm" AND EXISTS "/opt/rocm/include")
        message(STATUS "  ✓ ROCm installation found - enabling ROCm sensor")
        set(PMT_BUILD_ROCM ON)
    else()
        message(STATUS "  ⚠ ROCm not found - ROCm sensor disabled")
    endif()
    else()
        message(STATUS "⚠ AMD processor not detected - AMD sensors disabled")
    endif()
else()
    message(STATUS "⚠ /proc/cpuinfo not available - CPU detection disabled")
endif()

# Check for PowerSensor USB devices using safer file-based detection
set(POWERSENSOR_FOUND OFF)
file(GLOB USB_DEVICES "/sys/bus/usb/devices/*/product")
foreach(DEVICE_FILE ${USB_DEVICES})
    if(EXISTS ${DEVICE_FILE})
        file(READ ${DEVICE_FILE} DEVICE_NAME)
        if(DEVICE_NAME MATCHES ".*[Pp]ower[Ss]ensor.*")
            set(POWERSENSOR_FOUND ON)
            break()
        endif()
    endif()
endforeach()

if(POWERSENSOR_FOUND)
    message(STATUS "✓ PowerSensor USB device detected - enabling PowerSensor sensors")
    set(PMT_BUILD_POWERSENSOR3 ON)
    set(PMT_BUILD_POWERSENSOR2 ON)
else()
    message(STATUS "⚠ No PowerSensor USB devices detected - PowerSensor sensors disabled")
endif()

# Check for LIKWID (optional performance monitoring)
find_program(LIKWID_CMD likwid-topology QUIET)
if(LIKWID_CMD)
    message(STATUS "✓ LIKWID found - enabling LIKWID sensor")
    set(PMT_BUILD_LIKWID ON)
else()
    message(STATUS "⚠ LIKWID not found - LIKWID sensor disabled")
endif()

# Always disable these for production builds
set(PMT_BUILD_TESTING OFF)
set(PMT_BUILD_BINARY OFF)
set(PMT_BUILD_PYTHON OFF)

message(STATUS "=== PMT Build Summary ===")
message(STATUS "Dummy: ${PMT_BUILD_DUMMY}")
message(STATUS "RAPL: ${PMT_BUILD_RAPL}")
message(STATUS "NVML: ${PMT_BUILD_NVML}")
message(STATUS "NVIDIA: ${PMT_BUILD_NVIDIA}")
message(STATUS "TEGRA: ${PMT_BUILD_TEGRA}")
message(STATUS "AMD SMI: ${PMT_BUILD_AMDSMI}")
message(STATUS "ROCm: ${PMT_BUILD_ROCM}")
message(STATUS "PowerSensor2/3: ${PMT_BUILD_POWERSENSOR2}/${PMT_BUILD_POWERSENSOR3}")
message(STATUS "LIKWID: ${PMT_BUILD_LIKWID}")
message(STATUS "========================")

# Add PMT with error handling
message(STATUS "Building PMT (Power Measurement Toolkit)...")
add_subdirectory(third_party/pmt)

# Core library sources
set(CORE_SOURCES
    core/src/measurement_engine.cpp
    core/src/energy_monitor.cpp
    core/src/measurement_session.cpp
    core/src/energy_storage.cpp
            core/src/energy_code_mapper.cpp
        core/src/plugin/plugin_registry.cpp
        core/src/adapters/pmt_adapter.cpp
        core/src/config.cpp
        core/src/sensor_validator.cpp
        core/src/pmt_manager.cpp
)

# Verify core source files exist
foreach(SOURCE_FILE ${CORE_SOURCES})
    if(NOT EXISTS "${CMAKE_SOURCE_DIR}/${SOURCE_FILE}")
        message(WARNING "Core source file missing: ${SOURCE_FILE}")
    endif()
endforeach()

# Language adapter sources - build based on available parsers
set(LANGUAGE_ADAPTER_SOURCES
    packages/language-adapters/src/tree_sitter_adapter.cpp
    packages/language-adapters/src/python.cpp
)

# Add language-specific adapters based on availability
if(HAS_TREE_SITTER_C AND EXISTS "${CMAKE_SOURCE_DIR}/packages/language-adapters/src/c.cpp")
    list(APPEND LANGUAGE_ADAPTER_SOURCES packages/language-adapters/src/c.cpp)
    message(STATUS "✓ C language adapter added")
endif()

if(HAS_TREE_SITTER_CPP AND EXISTS "${CMAKE_SOURCE_DIR}/packages/language-adapters/src/cpp.cpp")
    list(APPEND LANGUAGE_ADAPTER_SOURCES packages/language-adapters/src/cpp.cpp)
    message(STATUS "✓ C++ language adapter added")
endif()

if(HAS_TREE_SITTER_JAVA AND EXISTS "${CMAKE_SOURCE_DIR}/packages/language-adapters/src/java.cpp")
    list(APPEND LANGUAGE_ADAPTER_SOURCES packages/language-adapters/src/java.cpp)
    message(STATUS "✓ Java language adapter added")
endif()

# Create core library
add_library(codegreen-core ${CORE_SOURCES})

target_include_directories(codegreen-core PUBLIC
    ${CMAKE_SOURCE_DIR}/core/include
    ${CMAKE_SOURCE_DIR}/third_party/pmt
    ${CMAKE_SOURCE_DIR}/third_party/pmt/common
    ${JSONCPP_INCLUDE_DIRS}
    ${CURL_INCLUDE_DIRS}
    ${SQLITE3_INCLUDE_DIRS}
)

target_link_libraries(codegreen-core PUBLIC
    pmt
    ${JSONCPP_LIBRARIES}
    ${CURL_LIBRARIES}
    ${SQLITE3_LIBRARIES}
    Threads::Threads
)

# Create language adapters library
add_library(codegreen-language-adapters ${LANGUAGE_ADAPTER_SOURCES})

target_include_directories(codegreen-language-adapters PUBLIC
    ${CMAKE_SOURCE_DIR}/core/include
    ${CMAKE_SOURCE_DIR}/packages/language-adapters/include
    ${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include
)

# Link language-specific parsers
set(LANGUAGE_PARSER_LIBS tree-sitter tree-sitter-python)

if(HAS_TREE_SITTER_C)
    list(APPEND LANGUAGE_PARSER_LIBS tree-sitter-c)
endif()

if(HAS_TREE_SITTER_CPP)
    list(APPEND LANGUAGE_PARSER_LIBS tree-sitter-cpp)
endif()

if(HAS_TREE_SITTER_JAVA)
    list(APPEND LANGUAGE_PARSER_LIBS tree-sitter-java)
endif()

target_link_libraries(codegreen-language-adapters PUBLIC
    ${LANGUAGE_PARSER_LIBS}
    codegreen-core
)

# Add package subdirectories or create placeholders
set(PACKAGE_COMPONENTS ide optimizer visualization instrumentation hardware-plugins)

foreach(component ${PACKAGE_COMPONENTS})
    if(EXISTS "${CMAKE_SOURCE_DIR}/packages/${component}/CMakeLists.txt")
        message(STATUS "✓ Adding ${component} package")
        add_subdirectory("packages/${component}")
    else()
        message(STATUS "⚠ Creating placeholder for ${component} component")
        add_library(codegreen-${component} STATIC ${CMAKE_SOURCE_DIR}/core/src/measurement_engine.cpp)
        target_link_libraries(codegreen-${component} PUBLIC codegreen-core)
    endif()
endforeach()

# Main executable
add_executable(codegreen 
    src/main.cpp
)

# Link all libraries
target_link_libraries(codegreen PRIVATE
    codegreen-core
    codegreen-language-adapters
    codegreen-ide
    codegreen-optimizer
    codegreen-visualization
    codegreen-instrumentation
    codegreen-hardware-plugins
    ${JSONCPP_LIBRARIES}
    ${CURL_LIBRARIES}
    Threads::Threads
)

target_include_directories(codegreen PRIVATE
    ${CMAKE_SOURCE_DIR}/core/include
    ${CMAKE_SOURCE_DIR}/packages/language-adapters/include
    ${JSONCPP_INCLUDE_DIRS}
    ${CURL_INCLUDE_DIRS}
)

# Compiler-specific options
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(codegreen PRIVATE 
        -Wall -Wextra -Wno-unused-parameter
        $<$<CONFIG:Debug>:-g -O0>
        $<$<CONFIG:Release>:-O3 -DNDEBUG>
    )
endif()

# Copy runtime modules to build directory
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime)
configure_file(
    ${CMAKE_SOURCE_DIR}/runtime/codegreen_runtime.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime/codegreen_runtime.py
    COPYONLY
)

# Copy additional language-specific runtime modules if they exist
if(EXISTS "${CMAKE_SOURCE_DIR}/packages/language-adapters/python/codegreen_runtime.py")
    configure_file(
        ${CMAKE_SOURCE_DIR}/packages/language-adapters/python/codegreen_runtime.py
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime/codegreen_runtime_alt.py
        COPYONLY
    )
endif()

# Copy configuration file to build directory
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/config)
if(EXISTS "${CMAKE_SOURCE_DIR}/config/codegreen.json")
    configure_file(
        ${CMAKE_SOURCE_DIR}/config/codegreen.json
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/config/codegreen.json
        COPYONLY
    )
endif()

# Installation
install(TARGETS codegreen
    RUNTIME DESTINATION bin
    COMPONENT runtime
)

# Install runtime modules
install(FILES ${CMAKE_SOURCE_DIR}/runtime/codegreen_runtime.py
    DESTINATION bin/runtime
    COMPONENT runtime
)

# Install configuration file
if(EXISTS "${CMAKE_SOURCE_DIR}/config/codegreen.json")
    install(FILES ${CMAKE_SOURCE_DIR}/config/codegreen.json
        DESTINATION bin/config
        COMPONENT runtime
    )
endif()

# Create installation package
set(CPACK_PACKAGE_NAME "CodeGreen")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "CodeGreen - Energy-Aware Code Analysis Tool")
set(CPACK_PACKAGE_VENDOR "CodeGreen Project")

include(CPack)

# Display build summary
message(STATUS "")
message(STATUS "=== CodeGreen Build Configuration ===")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "Language Support:")
message(STATUS "  ✓ Python (tree-sitter)")
if(HAS_TREE_SITTER_C)
    message(STATUS "  ✓ C (tree-sitter)")
endif()
if(HAS_TREE_SITTER_CPP)
    message(STATUS "  ✓ C++ (tree-sitter)")
endif()
if(HAS_TREE_SITTER_JAVA)
    message(STATUS "  ✓ Java (tree-sitter)")
endif()
message(STATUS "Hardware Sensors:")
if(PMT_BUILD_RAPL)
    message(STATUS "  ✓ Intel/AMD RAPL")
endif()
if(PMT_BUILD_NVML)
    message(STATUS "  ✓ NVIDIA NVML")
endif()
if(PMT_BUILD_AMDSMI)
    message(STATUS "  ✓ AMD SMI")
endif()
if(PMT_BUILD_ROCM)
    message(STATUS "  ✓ AMD ROCm")
endif()
if(PMT_BUILD_POWERSENSOR3)
    message(STATUS "  ✓ PowerSensor USB")
endif()
if(PMT_BUILD_LIKWID)
    message(STATUS "  ✓ LIKWID")
endif()
message(STATUS "  ✓ Dummy sensor (fallback)")
message(STATUS "")
message(STATUS "Build Target: ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/codegreen")
message(STATUS "=====================================")
message(STATUS "")