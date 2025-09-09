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
include_directories(${CMAKE_SOURCE_DIR}/src/measurement/include)
include_directories(${CMAKE_SOURCE_DIR}/src/instrumentation/include)
include_directories(${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include)


# Add tree-sitter submodules
message(STATUS "Building tree-sitter language parsers...")
add_subdirectory(third_party/tree-sitter/lib)

# Use EXCLUDE_FROM_ALL to avoid test target conflicts but still build libraries
add_subdirectory(third_party/tree-sitter-python EXCLUDE_FROM_ALL)

# Add measurement module
add_subdirectory(src/measurement)

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

# Core library sources are now defined in src/measurement/CMakeLists.txt


# Language adapters are now created in src/instrumentation/CMakeLists.txt

# Add instrumentation module
# Instrumentation is now Python-based, no C++ build needed
# add_subdirectory(src/instrumentation)

# Main executable
add_executable(codegreen 
    src/measurement/main.cpp
)

# Link all libraries
target_link_libraries(codegreen PRIVATE
    codegreen-core
    codegreen-nemb
    ${JSONCPP_LIBRARIES}
    ${CURL_LIBRARIES}
    Threads::Threads
)

target_include_directories(codegreen PRIVATE
    ${CMAKE_SOURCE_DIR}/src/measurement/include
    ${CMAKE_SOURCE_DIR}/src/instrumentation/include
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
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation)
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/codegreen_runtime.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime/codegreen_runtime.py
    COPYONLY
)

# Copy Python bridge scripts
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/bridge_analyze.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation/bridge_analyze.py
    COPYONLY
)
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/bridge_instrument.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation/bridge_instrument.py
    COPYONLY
)

# Copy Python instrumentation modules
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/language_engine.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation/language_engine.py
    COPYONLY
)
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/ast_processor.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation/ast_processor.py
    COPYONLY
)
configure_file(
    ${CMAKE_SOURCE_DIR}/src/instrumentation/language_configs.py
    ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/src/instrumentation/language_configs.py
    COPYONLY
)

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

# Create development bin directory and copy binary for CLI integration
add_custom_target(dev-install ALL
    DEPENDS codegreen
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_SOURCE_DIR}/bin
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/codegreen ${CMAKE_SOURCE_DIR}/bin/
    COMMENT "Copying binary to development bin directory for CLI integration"
)

# Install runtime modules
install(FILES ${CMAKE_SOURCE_DIR}/src/instrumentation/codegreen_runtime.py
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