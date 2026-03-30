# Language adapters package CMakeLists.txt

set(LANGUAGE_ADAPTERS_SOURCES
    src/tree_sitter_adapter.cpp
)

# Create language adapters library
add_library(codegreen-language-adapters STATIC ${LANGUAGE_ADAPTERS_SOURCES})

# Set include directories
target_include_directories(codegreen-language-adapters PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/third_party/tree-sitter/lib/include
    ${CMAKE_SOURCE_DIR}/third_party/tree-sitter-python/src
)

# Link libraries
target_link_libraries(codegreen-language-adapters
    codegreen-core
    tree-sitter
    tree-sitter-python
)

# Install target
install(TARGETS codegreen-language-adapters
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/language-adapters)
