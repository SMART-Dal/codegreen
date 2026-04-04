# NEMB (Native Energy Measurement Backend) - Cross-platform energy measurement library

set(NEMB_CORE_SOURCES
    src/nemb/core/energy_provider.cpp
    src/nemb/core/measurement_coordinator.cpp
)

find_package(JNI)
if(JNI_FOUND)
    message(STATUS "[ok] JNI found: ${JNI_INCLUDE_DIRS}")
endif()

set(NEMB_HAL_SOURCES
    src/nemb/hal/counter_manager.cpp
)

set(NEMB_UTILS_SOURCES
    src/nemb/utils/precision_timer.cpp
    src/nemb/utils/non_blocking_file_reader.cpp
)

# Platform-conditional drivers: each platform only compiles its own providers
set(NEMB_DRIVERS_SOURCES
    src/nemb/drivers/nvidia_gpu_provider.cpp
)

if(WIN32)
    list(APPEND NEMB_DRIVERS_SOURCES
        src/nemb/drivers/windows_emi_provider.cpp
    )
elseif(APPLE)
    list(APPEND NEMB_DRIVERS_SOURCES
        src/nemb/drivers/darwin_ioreport_provider.cpp
        src/nemb/drivers/darwin_kpc_provider.cpp
    )
else()
    # Linux/POSIX: all RAPL + ARM providers
    list(APPEND NEMB_DRIVERS_SOURCES
        src/nemb/drivers/intel_rapl_provider.cpp
        src/nemb/drivers/amd_rapl_provider.cpp
        src/nemb/drivers/amd_gpu_provider.cpp
        src/nemb/drivers/arm_energy_provider.cpp
    )
endif()

set(NEMB_CONFIG_SOURCES
    src/nemb/config_loader.cpp
    src/nemb/codegreen_energy.cpp
)

set(NEMB_SOURCES
    ${NEMB_CORE_SOURCES}
    ${NEMB_HAL_SOURCES}
    ${NEMB_UTILS_SOURCES}
    ${NEMB_DRIVERS_SOURCES}
    ${NEMB_CONFIG_SOURCES}
)

add_library(codegreen-nemb SHARED ${NEMB_SOURCES})

# Export all symbols on Windows so ctypes can find C API functions.
# On Linux/macOS all symbols are exported by default; on MSVC nothing
# is exported unless marked with __declspec(dllexport) or this property.
set_target_properties(codegreen-nemb PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)

target_include_directories(codegreen-nemb PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(JNI_FOUND)
    target_include_directories(codegreen-nemb PRIVATE ${JNI_INCLUDE_DIRS})
    target_compile_definitions(codegreen-nemb PRIVATE HAVE_JNI)
endif()

target_compile_definitions(codegreen-nemb PRIVATE NEMB_EXPORTS)

# NVML is loaded at runtime via dlopen/LoadLibrary (no compile-time dependency).
# The NVIDIAGPUProvider always compiles and gracefully returns false if the
# NVIDIA driver is not installed on the target machine.

target_link_libraries(codegreen-nemb Threads::Threads)
if(NOT WIN32)
    target_link_libraries(codegreen-nemb dl m)
endif()

if(APPLE)
    find_library(CORE_FOUNDATION CoreFoundation REQUIRED)
    target_link_libraries(codegreen-nemb ${CORE_FOUNDATION} "-ldl")
    target_compile_definitions(codegreen-nemb PRIVATE CODEGREEN_DARWIN)
    set_target_properties(codegreen-nemb PROPERTIES
        SUFFIX ".dylib"
        INSTALL_RPATH "@loader_path"
    )
elseif(WIN32)
    target_link_libraries(codegreen-nemb pdh)
    target_compile_definitions(codegreen-nemb PRIVATE CODEGREEN_WINDOWS NOMINMAX)
endif()

install(TARGETS codegreen-nemb
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

install(DIRECTORY include/ DESTINATION include/core)
