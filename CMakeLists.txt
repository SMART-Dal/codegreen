cmake_minimum_required(VERSION 3.16)
project(CodeGreen VERSION 0.1.0 LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Find required packages
find_package(PkgConfig REQUIRED)
find_package(Threads REQUIRED)

# Find system libraries
pkg_check_modules(JSONCPP REQUIRED jsoncpp)
pkg_check_modules(CURL REQUIRED libcurl)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)
include_directories(${CMAKE_SOURCE_DIR}/core/include)
include_directories(${CMAKE_SOURCE_DIR}/packages/*/include)

# Add subdirectories
add_subdirectory(core)
add_subdirectory(packages/ide)
add_subdirectory(packages/optimizer)
add_subdirectory(packages/visualization)
add_subdirectory(packages/instrumentation)
add_subdirectory(packages/hardware-plugins)
add_subdirectory(packages/language-adapters)

# Main executable
add_executable(codegreen 
    src/main.cpp
)

target_link_libraries(codegreen
    codegreen-core
    codegreen-ide
    codegreen-optimizer
    codegreen-visualization
    codegreen-instrumentation
    codegreen-hardware-plugins
    codegreen-language-adapters
    ${JSONCPP_LIBRARIES}
    ${CURL_LIBRARIES}
    Threads::Threads
)

target_include_directories(codegreen PRIVATE
    ${JSONCPP_INCLUDE_DIRS}
    ${CURL_INCLUDE_DIRS}
)

# Install target
install(TARGETS codegreen
    RUNTIME DESTINATION bin
)

# Install headers
install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY core/include/ DESTINATION include/core)
install(DIRECTORY packages/*/include/ DESTINATION include/packages)
