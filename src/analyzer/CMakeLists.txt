# Visualization package CMakeLists.txt
set(VISUALIZATION_SOURCES
    src/visualization.cpp
    src/charts.cpp
    src/reports.cpp
)

# Create visualization library
add_library(codegreen-visualization STATIC ${VISUALIZATION_SOURCES})

# Set include directories
target_include_directories(codegreen-visualization PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-visualization
    codegreen-core
)

# Install target
install(TARGETS codegreen-visualization
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/visualization)
