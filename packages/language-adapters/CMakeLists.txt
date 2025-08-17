# Language adapters package CMakeLists.txt
set(LANGUAGE_ADAPTERS_SOURCES
    src/lib.cpp
    src/common.cpp
    src/cpp.cpp
    src/python.cpp
)

# Create language adapters library
add_library(codegreen-language-adapters STATIC ${LANGUAGE_ADAPTERS_SOURCES})

# Set include directories
target_include_directories(codegreen-language-adapters PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-language-adapters
    codegreen-core
)

# Install target
install(TARGETS codegreen-language-adapters
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/language-adapters)
