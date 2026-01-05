# Core library CMakeLists.txt

# Legacy CodeGreen sources
set(CORE_SOURCES
    src/measurement_engine.cpp
    src/measurement_session.cpp
    src/adapters/python_bridge_adapter.cpp
    src/energy_storage.cpp
    src/config.cpp
)

# NEMB (Native Energy Measurement Backend) sources
set(NEMB_CORE_SOURCES
    src/nemb/core/energy_provider.cpp
    src/nemb/core/measurement_coordinator.cpp
)

# Find JNI for Java runtime support
find_package(JNI)
if(JNI_FOUND)
    message(STATUS "✓ JNI found: ${JNI_INCLUDE_DIRS}")
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

set(NEMB_CONFIG_SOURCES
    src/nemb/config_loader.cpp
    src/nemb/codegreen_energy.cpp
)

# All NEMB sources
set(NEMB_SOURCES
    ${NEMB_CORE_SOURCES}
    ${NEMB_HAL_SOURCES}
    ${NEMB_UTILS_SOURCES}
    ${NEMB_DRIVERS_SOURCES}
    ${NEMB_CONFIG_SOURCES}
)

# Create core library (legacy CodeGreen)
add_library(codegreen-core STATIC ${CORE_SOURCES})

# Create NEMB library
add_library(codegreen-nemb SHARED ${NEMB_SOURCES})

# Set include directories for legacy core
target_include_directories(codegreen-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${JSONCPP_INCLUDE_DIRS}
    ${SQLITE3_INCLUDE_DIRS}
)

# Set include directories for NEMB
target_include_directories(codegreen-nemb PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(JNI_FOUND)
    target_include_directories(codegreen-nemb PRIVATE ${JNI_INCLUDE_DIRS})
endif()

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

# Optional: Test executables for NEMB (disabled for now due to API mismatches)
# if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR BUILD_TESTS)
#     # NEMB validation test
#     add_executable(nemb_test
#         tests/nemb_validation_test.cpp
#     )
#     
#     target_link_libraries(nemb_test
#         PRIVATE
#             codegreen-nemb
#             Threads::Threads
#     )
#     
#     target_include_directories(nemb_test PRIVATE
#         ${CMAKE_CURRENT_SOURCE_DIR}/include
#     )
#     
#     # RAPL provider test
#     add_executable(rapl_test
#         tests/rapl_provider_test.cpp
#     )
#     
#     target_link_libraries(rapl_test
#         PRIVATE
#             codegreen-nemb
#             Threads::Threads
#     )
#     
#     target_include_directories(rapl_test PRIVATE
#         ${CMAKE_CURRENT_SOURCE_DIR}/include
#     )
# endif()
