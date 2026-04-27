cmake_minimum_required(VERSION 3.16)

# Single source of truth: pyproject.toml [project].version
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/pyproject.toml" _PYPROJECT_TOML)
string(REGEX MATCH "version *= *\"([0-9]+\\.[0-9]+\\.[0-9]+)\"" _VERSION_MATCH "${_PYPROJECT_TOML}")
if(NOT CMAKE_MATCH_1)
    message(FATAL_ERROR "Could not parse [project].version from pyproject.toml")
endif()
set(_CODEGREEN_VERSION "${CMAKE_MATCH_1}")

project(CodeGreen VERSION ${_CODEGREEN_VERSION} LANGUAGES CXX)

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

# GPU libraries are loaded at runtime (dlopen/LoadLibrary), not linked.
# These checks are informational only.
find_library(NVML_LIBRARY nvidia-ml PATHS
    /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu
    "C:/Windows/System32" "$ENV{ProgramFiles}/NVIDIA Corporation/NVSMI")
if(NVML_LIBRARY)
    message(STATUS "NVML found (runtime-loaded): ${NVML_LIBRARY}")
endif()

find_library(ROCM_SMI_LIBRARY rocm_smi64 PATHS /opt/rocm/lib)
if(ROCM_SMI_LIBRARY)
    message(STATUS "ROCm SMI found: ${ROCM_SMI_LIBRARY}")
endif()

# Global include directories
include_directories(${CMAKE_SOURCE_DIR}/codegreen/measurement/include)

# NEMB -- the only native component (no tree-sitter dependency;
# instrumentation uses the tree-sitter-language-pack pip package)
add_subdirectory(codegreen/measurement)


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

# Install -- DLLs go to lib/ (not bin/) so setup.py finds them consistently
install(TARGETS codegreen-nemb
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION lib
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
