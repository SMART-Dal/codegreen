# Core API Reference

NEMB (Native Energy Measurement Backend) C++ API for advanced users and language runtime developers.

## Overview

The NEMB core API provides low-level access to energy measurement functionality. Most users should use the CLI (`codegreen measure`) instead. This API is for:

- Creating custom language runtimes
- Embedding energy measurement in applications
- Building profiling tools
- Direct hardware sensor access

## Public API

### Header File

```cpp
#include <codegreen_energy.hpp>
```

### Initialization

**Initialize NEMB measurement system:**

```cpp
bool nemb_initialize();
```

**Returns:** `true` on success, `false` if sensors unavailable

**Example:**
```cpp
#include <codegreen_energy.hpp>

int main() {
    if (!nemb_initialize()) {
        std::cerr << "Failed to initialize NEMB" << std::endl;
        return 1;
    }

    // Ready to measure
    return 0;
}
```

### Checkpoint Marking

**Mark execution checkpoint:**

```cpp
void nemb_mark_checkpoint(const char* name);
```

**Parameters:**
- `name`: Checkpoint identifier (function name, label)

**Performance:** ~100-200ns overhead

**Thread-safe:** Yes (thread-local storage)

**Example:**
```cpp
void process_data(const std::vector<int>& data) {
    nemb_mark_checkpoint("process_data_entry");

    // Function logic here
    int sum = 0;
    for (int x : data) {
        sum += x;
    }

    nemb_mark_checkpoint("process_data_exit");
}
```

### Energy Reading

**Read current cumulative energy:**

```cpp
double nemb_read_current();
```

**Returns:** Cumulative energy in joules since initialization

**Note:** Prefer checkpoint-based measurement for accuracy

**Example:**
```cpp
double energy_before = nemb_read_current();

// Run workload
compute_intensive_function();

double energy_after = nemb_read_current();
double energy_consumed = energy_after - energy_before;

std::cout << "Energy consumed: " << energy_consumed << " J" << std::endl;
```

### Reporting

**Generate energy report at program exit:**

```cpp
void nemb_report_at_exit(const char* output_file);
```

**Parameters:**
- `output_file`: Path to JSON output file, or `nullptr` for stdout

**Automatically called at program exit if registered**

**Example:**
```cpp
int main() {
    nemb_initialize();
    nemb_report_at_exit("energy_report.json");

    // Program logic with checkpoints
    nemb_mark_checkpoint("main_start");
    run_application();
    nemb_mark_checkpoint("main_end");

    return 0;
}
// Report generated automatically at exit
```

## Language Runtime API

For implementing language-specific wrappers:

### Python Runtime

```cpp
// codegreen_runtime.py (Cython wrapper)
cdef extern from "codegreen_energy.hpp":
    bint nemb_initialize()
    void nemb_mark_checkpoint(const char* name)
    double nemb_read_current()
    void nemb_report_at_exit(const char* output_file)

def checkpoint(name: str):
    nemb_mark_checkpoint(name.encode('utf-8'))

def initialize():
    return nemb_initialize()

def get_current_energy():
    return nemb_read_current()
```

### C Runtime

```c
// codegreen_runtime.h
#ifdef __cplusplus
extern "C" {
#endif

int nemb_initialize(void);
void nemb_mark_checkpoint(const char* name);
double nemb_read_current(void);
void nemb_report_at_exit(const char* output_file);

#ifdef __cplusplus
}
#endif
```

### Java JNI

```java
// CodeGreenRuntime.java
public class CodeGreenRuntime {
    static {
        System.loadLibrary("codegreen-nemb");
    }

    public static native boolean initialize();
    public static native void markCheckpoint(String name);
    public static native double readCurrent();
    public static native void reportAtExit(String outputFile);

    public static void checkpoint(String name) {
        markCheckpoint(name);
    }
}
```

## Macro API (C/C++)

Convenience macros for instrumentation:

```cpp
#define CODEGREEN_CHECKPOINT(name) nemb_mark_checkpoint(name)
#define CODEGREEN_FUNCTION_ENTRY() CODEGREEN_CHECKPOINT(__FUNCTION__ "_entry")
#define CODEGREEN_FUNCTION_EXIT() CODEGREEN_CHECKPOINT(__FUNCTION__ "_exit")
```

**Usage:**
```cpp
void my_function() {
    CODEGREEN_FUNCTION_ENTRY();

    // Function body

    CODEGREEN_FUNCTION_EXIT();
}
```

## Compilation

### Linking

Link against the NEMB library:

```bash
g++ -o program program.cpp -lcodegreen-nemb -pthread
```

### CMake Integration

```cmake
find_library(CODEGREEN_NEMB codegreen-nemb REQUIRED)

add_executable(myapp main.cpp)
target_link_libraries(myapp ${CODEGREEN_NEMB} pthread)
```

## Examples

### Minimal Example

```cpp
// minimal.cpp
#include <iostream>
#include <codegreen_energy.hpp>

void compute() {
    nemb_mark_checkpoint("compute_entry");

    int sum = 0;
    for (int i = 0; i < 1000000; i++) {
        sum += i;
    }

    nemb_mark_checkpoint("compute_exit");
    std::cout << "Sum: " << sum << std::endl;
}

int main() {
    if (!nemb_initialize()) {
        std::cerr << "Failed to initialize NEMB" << std::endl;
        return 1;
    }

    nemb_report_at_exit("energy.json");

    nemb_mark_checkpoint("main_start");
    compute();
    nemb_mark_checkpoint("main_end");

    return 0;
}
```

**Compile and run:**
```bash
g++ -o minimal minimal.cpp -lcodegreen-nemb -pthread
./minimal
cat energy.json
```

### Multi-threaded Example

```cpp
// threaded.cpp
#include <thread>
#include <vector>
#include <codegreen_energy.hpp>

void worker(int thread_id) {
    char checkpoint_name[64];
    snprintf(checkpoint_name, sizeof(checkpoint_name),
             "worker_%d_entry", thread_id);
    nemb_mark_checkpoint(checkpoint_name);

    // Worker logic
    volatile int sum = 0;
    for (int i = 0; i < 10000000; i++) {
        sum += i;
    }

    snprintf(checkpoint_name, sizeof(checkpoint_name),
             "worker_%d_exit", thread_id);
    nemb_mark_checkpoint(checkpoint_name);
}

int main() {
    nemb_initialize();
    nemb_report_at_exit(nullptr);  // Print to stdout

    std::vector<std::thread> threads;
    for (int i = 0; i < 4; i++) {
        threads.emplace_back(worker, i);
    }

    for (auto& t : threads) {
        t.join();
    }

    return 0;
}
```

## Advanced Configuration

### Runtime Configuration

Load custom configuration:

```cpp
#include <codegreen/config_loader.hpp>

int main() {
    codegreen::ConfigLoader config("custom_config.json");

    // Configuration applied automatically
    nemb_initialize();

    // ...
}
```

### Provider Selection

Enable specific sensors:

```json
{
  "measurement": {
    "nemb": {
      "providers": {
        "intel_rapl": { "enabled": true },
        "nvidia_nvml": { "enabled": false }
      }
    }
  }
}
```

## Error Handling

NEMB uses return codes and error logging:

```cpp
if (!nemb_initialize()) {
    // Check system logs
    // Possible causes:
    // - No supported hardware sensors
    // - Permission denied (RAPL)
    // - Missing driver (NVML)
    std::cerr << "Initialization failed" << std::endl;
    return 1;
}
```

**Enable debug logging:**
```bash
export CODEGREEN_LOG_LEVEL=DEBUG
./program
```

## See Also

- [Architecture](../development/architecture.md) - NEMB design details
- [Configuration Reference](../user-guide/configuration-reference.md) - Config options
- [Building from Source](../development/building.md) - Build instructions
- [Examples](../examples/cpp.md) - C++ usage examples
