# Language Runtimes

This directory contains language-specific runtime libraries that are injected into or linked with user code during instrumentation.

## Structure

- **python/**: Contains the Python runtime (`codegreen_runtime.py`) which acts as a wrapper around the C++ NEMB backend via ctypes.
- **java/**: (Placeholder) Will contain the Java runtime library (e.g., `CodeGreenRuntime.java` or JAR) wrapping the native backend via JNI.
- **cpp/**: (Placeholder) Will contain C++ headers and source files (e.g., `codegreen_runtime.hpp`) that link against the NEMB shared library.
- **c/**: (Placeholder) Will contain C headers and wrappers for the NEMB backend.

## Usage

These runtimes are designed to be lightweight shims that delegate actual energy measurement to the shared `libcodegreen-nemb.so` library, ensuring consistent high-precision measurement across all supported languages.
