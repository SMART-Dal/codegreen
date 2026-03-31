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

set(NEMB_DRIVERS_SOURCES
    src/nemb/drivers/intel_rapl_provider.cpp
    src/nemb/drivers/nvidia_gpu_provider.cpp
    src/nemb/drivers/amd_gpu_provider.cpp
    src/nemb/drivers/arm_energy_provider.cpp
    src/nemb/drivers/amd_rapl_provider.cpp
)

if(APPLE)
    list(APPEND NEMB_DRIVERS_SOURCES
        src/nemb/drivers/darwin_ioreport_provider.cpp
        src/nemb/drivers/darwin_kpc_provider.cpp
    )
elseif(WIN32)
    list(APPEND NEMB_DRIVERS_SOURCES
        src/nemb/drivers/windows_emi_provider.cpp
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

target_include_directories(codegreen-nemb PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(JNI_FOUND)
    target_include_directories(codegreen-nemb PRIVATE ${JNI_INCLUDE_DIRS})
    target_compile_definitions(codegreen-nemb PRIVATE HAVE_JNI)
endif()

target_compile_definitions(codegreen-nemb PRIVATE NEMB_EXPORTS)

target_link_libraries(codegreen-nemb
    Threads::Threads
    m
)

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
    target_compile_definitions(codegreen-nemb PRIVATE CODEGREEN_WINDOWS)
endif()

install(TARGETS codegreen-nemb
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

install(DIRECTORY include/ DESTINATION include/core)
