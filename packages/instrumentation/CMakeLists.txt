# Instrumentation package CMakeLists.txt
set(INSTRUMENTATION_SOURCES
    src/instrumenter.cpp
    src/parser.cpp
    src/metrics/mod.cpp
    src/hardware/mod.cpp
    src/error.cpp
)

# Create instrumentation library
add_library(codegreen-instrumentation STATIC ${INSTRUMENTATION_SOURCES})

# Set include directories
target_include_directories(codegreen-instrumentation PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-instrumentation
    codegreen-core
)

# Install target
install(TARGETS codegreen-instrumentation
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/instrumentation)
