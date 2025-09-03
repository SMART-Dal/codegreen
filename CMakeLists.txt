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

# Optional GPU library support
find_library(NVML_LIBRARY nvidia-ml PATHS /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu)
find_path(NVML_INCLUDE_DIR nvml.h PATHS /usr/local/cuda/include /usr/include/nvidia/gdk)
find_library(ROCM_SMI_LIBRARY rocm_smi64 PATHS /opt/rocm/lib)
find_path(ROCM_SMI_INCLUDE_DIR rocm_smi.h PATHS /opt/rocm/include/rocm_smi)

if(NVML_LIBRARY AND NVML_INCLUDE_DIR)
    message(STATUS "✓ NVML library and headers found: ${NVML_LIBRARY}")
    set(HAVE_NVML ON)
elseif(NVML_LIBRARY)
    message(STATUS "⚠ NVML library found but headers missing - NVIDIA GPU energy monitoring will use fallback")
    set(HAVE_NVML OFF)
else()
    message(STATUS "⚠ NVML library not found - NVIDIA GPU energy monitoring will use fallback")
    set(HAVE_NVML OFF)
endif()

if(ROCM_SMI_LIBRARY AND ROCM_SMI_INCLUDE_DIR)
    message(STATUS "✓ ROCm SMI library and headers found: ${ROCM_SMI_LIBRARY}")
    set(HAVE_ROCM_SMI ON)
elseif(ROCM_SMI_LIBRARY)
    message(STATUS "⚠ ROCm SMI library found but headers missing - AMD GPU energy monitoring will use fallback")
    set(HAVE_ROCM_SMI OFF)  
else()
    message(STATUS "⚠ ROCm SMI library not found - AMD GPU energy monitoring will use fallback")
    set(HAVE_ROCM_SMI OFF)
endif()

# Find system libraries
pkg_check_modules(JSONCPP REQUIRED jsoncpp)
pkg_check_modules(CURL REQUIRED libcurl)
pkg_check_modules(SQLITE3 REQUIRED sqlite3)

# Global include directories
include_directories(${CMAKE_SOURCE_DIR}/core/include)
include_directories(${CMAKE_SOURCE_DIR}/packages/language-adapters/include)
include_directories(${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include)


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

# NEMB (Native Energy Measurement Backend) handles all energy measurement
# PMT has been completely replaced by NEMB native implementations

# Core library sources
set(CORE_SOURCES
    core/src/measurement_engine.cpp
    core/src/energy_monitor.cpp
    core/src/measurement_session.cpp
    core/src/energy_storage.cpp
    core/src/energy_code_mapper.cpp
    core/src/plugin/plugin_registry.cpp
    core/src/config.cpp
)

# NEMB (Native Energy Measurement Backend) sources
set(NEMB_SOURCES
    core/src/nemb/core/energy_provider.cpp
    core/src/nemb/core/measurement_coordinator.cpp
    core/src/nemb/hal/counter_manager.cpp
    core/src/nemb/utils/precision_timer.cpp
    core/src/nemb/drivers/intel_rapl_provider.cpp
    core/src/nemb/drivers/nvidia_gpu_provider.cpp
    core/src/nemb/drivers/amd_gpu_provider.cpp
    core/src/nemb/config_loader.cpp
    core/src/nemb/codegreen_energy.cpp
    core/src/nemb/accuracy_validator.cpp
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
    ${JSONCPP_INCLUDE_DIRS}
    ${CURL_INCLUDE_DIRS}
    ${SQLITE3_INCLUDE_DIRS}
)

target_link_libraries(codegreen-core PUBLIC
    codegreen-nemb
    ${JSONCPP_LIBRARIES}
    ${CURL_LIBRARIES}
    ${SQLITE3_LIBRARIES}
    Threads::Threads
)

# Create NEMB library (separate from legacy core)
add_library(codegreen-nemb STATIC ${NEMB_SOURCES})

target_include_directories(codegreen-nemb PUBLIC
    ${CMAKE_SOURCE_DIR}/core/include
)

target_link_libraries(codegreen-nemb PUBLIC
    Threads::Threads
    m  # Math library for sqrt, etc.
)

# Add optional GPU libraries
if(HAVE_NVML)
    target_link_libraries(codegreen-nemb PRIVATE ${NVML_LIBRARY})
    target_include_directories(codegreen-nemb PRIVATE ${NVML_INCLUDE_DIR})
    target_compile_definitions(codegreen-nemb PRIVATE HAVE_NVML=1)
endif()

if(HAVE_ROCM_SMI)
    target_link_libraries(codegreen-nemb PRIVATE ${ROCM_SMI_LIBRARY})
    target_include_directories(codegreen-nemb PRIVATE ${ROCM_SMI_INCLUDE_DIR})
    target_compile_definitions(codegreen-nemb PRIVATE HAVE_ROCM_SMI=1)
endif()

target_compile_options(codegreen-nemb PRIVATE -fPIC)

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
message(STATUS "  ✓ Intel/AMD RAPL (NEMB)")
message(STATUS "  ✓ NVIDIA NVML (NEMB)")
message(STATUS "  ✓ Dummy sensor (fallback)")
message(STATUS "")
message(STATUS "Build Target: ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/codegreen")
message(STATUS "=====================================")
message(STATUS "")