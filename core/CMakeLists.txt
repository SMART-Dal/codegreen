# Core library CMakeLists.txt

# Legacy CodeGreen sources
set(CORE_SOURCES
    src/measurement_engine.cpp
    src/energy_monitor.cpp
    src/measurement_session.cpp
    src/plugin/plugin_registry.cpp
    src/adapters/arm_pmu.cpp
    src/adapters/intel_rapl.cpp
    src/adapters/nvidia_gpu.cpp
    src/adapters/pmt_adapter.cpp
    src/energy_storage.cpp
)

# NEMB (Native Energy Measurement Backend) sources
set(NEMB_CORE_SOURCES
    src/nemb/core/energy_provider.cpp
    src/nemb/core/measurement_coordinator.cpp
)

set(NEMB_HAL_SOURCES
    src/nemb/hal/counter_manager.cpp
)

set(NEMB_UTILS_SOURCES
    src/nemb/utils/precision_timer.cpp
    src/nemb/utils/non_blocking_file_reader.cpp
)

set(NEMB_DRIVERS_SOURCES
    src/nemb/drivers/intel_rapl_provider.cpp
)

# All NEMB sources
set(NEMB_SOURCES
    ${NEMB_CORE_SOURCES}
    ${NEMB_HAL_SOURCES}
    ${NEMB_UTILS_SOURCES}
    ${NEMB_DRIVERS_SOURCES}
)

# Create core library (legacy CodeGreen)
add_library(codegreen-core STATIC ${CORE_SOURCES})

# Create NEMB library
add_library(codegreen-nemb STATIC ${NEMB_SOURCES})

# Set include directories for legacy core
target_include_directories(codegreen-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/third_party/pmt
    ${SQLITE3_INCLUDE_DIRS}
)

# Set include directories for NEMB
target_include_directories(codegreen-nemb PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Set compile definitions for legacy core
target_compile_definitions(codegreen-core PRIVATE
    CODECREEN_CORE_EXPORTS
)

# Set compile definitions for NEMB
target_compile_definitions(codegreen-nemb PRIVATE
    NEMB_EXPORTS
)

# Link libraries for legacy core
target_link_libraries(codegreen-core
    ${JSONCPP_LIBRARIES}
    Threads::Threads
    pmt
    ${SQLITE3_LIBRARIES}
)

# Link libraries for NEMB
target_link_libraries(codegreen-nemb
    Threads::Threads
    m  # Math library for sqrt, etc.
)

# Install targets
install(TARGETS codegreen-core codegreen-nemb
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/core)

# Optional: Test executables for NEMB
if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR BUILD_TESTS)
    # NEMB validation test
    add_executable(nemb_test
        tests/nemb_validation_test.cpp
    )
    
    target_link_libraries(nemb_test
        PRIVATE
            codegreen-nemb
            Threads::Threads
    )
    
    target_include_directories(nemb_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
    
    # RAPL provider test
    add_executable(rapl_test
        tests/rapl_provider_test.cpp
    )
    
    target_link_libraries(rapl_test
        PRIVATE
            codegreen-nemb
            Threads::Threads
    )
    
    target_include_directories(rapl_test PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
endif()
