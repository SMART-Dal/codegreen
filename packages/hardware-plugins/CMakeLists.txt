# Hardware plugins package CMakeLists.txt
set(HARDWARE_PLUGINS_SOURCES
    src/lib.cpp
    src/common.cpp
    src/intel.cpp
    src/amd.cpp
    src/arm.cpp
    src/nvidia.cpp
)

# Create hardware plugins library
add_library(codegreen-hardware-plugins STATIC ${HARDWARE_PLUGINS_SOURCES})

# Set include directories
target_include_directories(codegreen-hardware-plugins PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-hardware-plugins
    codegreen-core
)

# Install target
install(TARGETS codegreen-hardware-plugins
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/hardware-plugins)
