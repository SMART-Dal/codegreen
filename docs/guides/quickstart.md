# Quick Start Guide

This guide will help you get started with the CodeGreen project quickly.

## Prerequisites

1. **Install C++ Compiler**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install build-essential g++ cmake pkg-config

   # macOS
   brew install cmake pkg-config

   # CentOS/RHEL
   sudo yum groupinstall "Development Tools"
   sudo yum install cmake3 pkgconfig
   ```

2. **Install Required Libraries**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libjsoncpp-dev libcurl4-openssl-dev

   # macOS
   brew install jsoncpp curl

   # CentOS/RHEL
   sudo yum install jsoncpp-devel libcurl-devel
   ```

3. **Install Development Tools**
   ```bash
   # Install clang-format for code formatting
   sudo apt-get install clang-format

   # Install clang-tidy for static analysis
   sudo apt-get install clang-tidy

   # Install gtest for testing (optional)
   sudo apt-get install libgtest-dev
   ```

## Getting Started

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/codegreen.git
   cd codegreen
   ```

2. **Build the Project**
   ```bash
   # Create build directory
   mkdir build && cd build

   # Configure with CMake
   cmake .. -DCMAKE_BUILD_TYPE=Release

   # Build
   make -j$(nproc)
   ```

3. **Run Tests**
   ```bash
   # Run all tests
   make test

   # Run specific tests
   ctest --output-on-failure
   ```

## Development Workflow

1. **Start Development Server**
   ```bash
   # Run the application
   ./bin/codegreen

   # Or run from build directory
   ./codegreen
   ```

2. **Code Formatting**
   ```bash
   # Format code
   clang-format -i src/*.cpp include/*.hpp

   # Check formatting
   clang-format --dry-run src/*.cpp include/*.hpp
   ```

3. **Static Analysis**
   ```bash
   # Run clang-tidy
   clang-tidy src/*.cpp -checks=*

   # Run with specific checks
   clang-tidy src/*.cpp -checks=performance-*,modernize-*
   ```

## Project Structure

```
codegreen/
├── CMakeLists.txt                  # Main CMake configuration
├── src/                            # Main application source
│   └── main.cpp                   # Entry point
├── core/                           # Core library
│   ├── CMakeLists.txt             # Core library build config
│   ├── include/                    # Public headers
│   └── src/                        # Implementation files
├── packages/                        # Feature packages
│   ├── ide/                        # IDE integration
│   ├── optimizer/                  # Code optimization
│   ├── visualization/              # Data visualization
│   ├── instrumentation/            # Code instrumentation
│   ├── hardware-plugins/           # Hardware monitoring plugins
│   └── language-adapters/          # Language-specific adapters
├── docs/                           # Documentation
└── scripts/                        # Build and utility scripts
```

## Common Tasks

1. **Adding a New Package**
   ```bash
   # Create new package directory
   mkdir -p packages/my-package/{include,src}

   # Create CMakeLists.txt
   # Add to main CMakeLists.txt
   ```

2. **Adding Dependencies**
   ```bash
   # Add to CMakeLists.txt
   find_package(MyLibrary REQUIRED)
   target_link_libraries(my-target MyLibrary::MyLibrary)
   ```

3. **Running Examples**
   ```bash
   # Build examples
   make examples

   # Run specific example
   ./examples/my-example
   ```

## IDE Setup

1. **VS Code**
   - Install "C/C++" extension
   - Install "CMake Tools" extension
   - Install "CMake" extension

2. **CLion**
   - Open project as CMake project
   - Configure toolchains in settings

3. **Vim/Neovim**
   - Install "coc-clangd" for language server
   - Install "vim-cmake" for CMake support

## Debugging

1. **Using std::cout**
   ```cpp
   std::cout << "Debug: " << value << std::endl;
   ```

2. **Using GDB**
   ```bash
   # Start debugger
   gdb ./codegreen

   # Or use gdb with core dumps
   gdb ./codegreen core.dump
   ```

3. **Using Valgrind**
   ```bash
   # Check for memory leaks
   valgrind --leak-check=full ./codegreen

   # Check for memory errors
   valgrind --tool=memcheck ./codegreen
   ```

## Common Issues

1. **Build Errors**
   - Run `make clean` and try again
   - Check for missing dependencies
   - Verify CMake version compatibility

2. **Test Failures**
   - Run specific test with `ctest -R test_name`
   - Check test output with `ctest --output-on-failure`

3. **Dependency Issues**
   - Check pkg-config output
   - Verify library versions
   - Check CMake module paths

## Next Steps

1. Read the [C++ Development Guide](cpp_guide.md)
2. Explore the [Architecture Documentation](../design/architecture.md)
3. Check out the [API Documentation](../api/README.md)
4. Join the [Community Discord](https://discord.gg/cpp) 