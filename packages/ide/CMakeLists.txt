# IDE package CMakeLists.txt
set(IDE_SOURCES
    src/ide_integration.cpp
    src/common.cpp
    src/intellij.cpp
    src/vscode.cpp
    src/jetbrains/jetbrains_plugin.cpp
    src/vscode/vscode_extension.cpp
)

# Create IDE library
add_library(codegreen-ide STATIC ${IDE_SOURCES})

# Set include directories
target_include_directories(codegreen-ide PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link libraries
target_link_libraries(codegreen-ide
    codegreen-core
)

# Install target
install(TARGETS codegreen-ide
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install headers
install(DIRECTORY include/ DESTINATION include/ide)
