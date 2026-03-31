cmake_minimum_required(VERSION 3.16)
project(CodeGreen VERSION 0.3.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

find_package(PkgConfig)
find_package(Threads REQUIRED)

# Optional GPU library detection
find_library(NVML_LIBRARY nvidia-ml PATHS /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu)
find_path(NVML_INCLUDE_DIR nvml.h PATHS /usr/local/cuda/include /usr/include/nvidia/gdk)
find_library(ROCM_SMI_LIBRARY rocm_smi64 PATHS /opt/rocm/lib)
find_path(ROCM_SMI_INCLUDE_DIR rocm_smi.h PATHS /opt/rocm/include/rocm_smi)

if(NVML_LIBRARY AND NVML_INCLUDE_DIR)
    message(STATUS "NVML found: ${NVML_LIBRARY}")
    set(HAVE_NVML ON)
else()
    set(HAVE_NVML OFF)
endif()

if(ROCM_SMI_LIBRARY AND ROCM_SMI_INCLUDE_DIR)
    message(STATUS "ROCm SMI found: ${ROCM_SMI_LIBRARY}")
    set(HAVE_ROCM_SMI ON)
else()
    set(HAVE_ROCM_SMI OFF)
endif()

# Global include directories
include_directories(${CMAKE_SOURCE_DIR}/codegreen/measurement/include)

# Tree-sitter (for C++ instrumentation runtime, if submodules present)
if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/CMakeLists.txt")
    include_directories(${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include)
    add_subdirectory(third_party/tree-sitter/lib)
    if(EXISTS "${CMAKE_SOURCE_DIR}/third_party/tree-sitter-python/CMakeLists.txt")
        add_subdirectory(third_party/tree-sitter-python EXCLUDE_FROM_ALL)
    endif()
endif()

# NEMB -- the only native component
add_subdirectory(codegreen/measurement)

# Sync instrumentation files to build dir (for C/C++/Java runtime headers)
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime)
file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/python/instrumentation)

add_custom_target(sync_instrumentation
    COMMAND ${CMAKE_COMMAND} -E copy
        ${CMAKE_SOURCE_DIR}/codegreen/instrumentation/language_runtimes/python/codegreen_runtime.py
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/runtime/codegreen_runtime.py
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_SOURCE_DIR}/codegreen/instrumentation/language_runtimes
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/python/instrumentation/language_runtimes
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_SOURCE_DIR}/codegreen/instrumentation/configs
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/python/instrumentation/configs
    COMMENT "Syncing instrumentation files to build directory"
)

add_dependencies(codegreen-nemb sync_instrumentation)

# Copy config to build dir
if(EXISTS "${CMAKE_SOURCE_DIR}/config/codegreen.json")
    file(MAKE_DIRECTORY ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/config)
    configure_file(
        ${CMAKE_SOURCE_DIR}/config/codegreen.json
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/config/codegreen.json
        COPYONLY
    )
endif()

# Dev-install: copy NEMB library to project root for pip editable installs
add_custom_target(dev-install ALL
    DEPENDS codegreen-nemb
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_SOURCE_DIR}/lib
    COMMAND ${CMAKE_COMMAND} -E copy
        $<TARGET_FILE:codegreen-nemb>
        ${CMAKE_SOURCE_DIR}/lib/
    COMMENT "Dev-install: copying NEMB to ${CMAKE_SOURCE_DIR}/lib/"
)

# Install
install(TARGETS codegreen-nemb
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES
    ${CMAKE_SOURCE_DIR}/codegreen/instrumentation/language_runtimes/python/codegreen_runtime.py
    DESTINATION bin/runtime
)

if(EXISTS "${CMAKE_SOURCE_DIR}/config/codegreen.json")
    install(FILES ${CMAKE_SOURCE_DIR}/config/codegreen.json
        DESTINATION bin/config
    )
endif()

set(CPACK_PACKAGE_NAME "CodeGreen")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Energy-aware software development tool")
include(CPack)
