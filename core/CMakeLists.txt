# Core library CMakeLists.txt
set(CORE_SOURCES
    src/measurement_engine.cpp
    src/energy_monitor.cpp
    src/measurement_session.cpp
    src/plugin/plugin_registry.cpp
    src/adapters/arm_pmu.cpp
    src/adapters/intel_rapl.cpp
    src/adapters/nvidia_gpu.cpp
)

# Create core library
add_library(codegreen-core STATIC ${CORE_SOURCES})

# Set include directories
target_include_directories(codegreen-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Set compile definitions
target_compile_definitions(codegreen-core PRIVATE
    CODECREEN_CORE_EXPORTS
)

# Link libraries
target_link_libraries(codegreen-core
    ${JSONCPP_LIBRARIES}
    Threads::Threads
)

# Install target
install(TARGETS codegreen-core
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/core)
