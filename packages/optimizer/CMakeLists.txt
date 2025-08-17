# Optimizer package CMakeLists.txt
set(OPTIMIZER_SOURCES
    src/optimizer.cpp
    src/analysis.cpp
    src/metrics.cpp
    src/suggestions.cpp
)

# Create optimizer library
add_library(codegreen-optimizer STATIC ${OPTIMIZER_SOURCES})

# Set include directories
target_include_directories(codegreen-optimizer PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-optimizer
    codegreen-core
)

# Install target
install(TARGETS codegreen-optimizer
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/optimizer)
