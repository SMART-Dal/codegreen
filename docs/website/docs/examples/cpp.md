# C/C++ Examples

## Basic C Measurement

Given `algorithm.c`:
```c
#include <stdio.h>
#include <math.h>

double compute(int n) {
    double sum = 0.0;
    for (int i = 0; i < n; i++)
        sum += sin(i) * cos(i);
    return sum;
}

int main() {
    double result = compute(10000000);
    printf("Result: %f\n", result);
    return 0;
}
```

Measure energy:
```bash
# Coarse: total program energy
codegreen measure c algorithm.c --

# Fine: per-function breakdown
codegreen measure c algorithm.c -g fine
```

CodeGreen automatically compiles with `-O2` and links against `libcodegreen-nemb.so`.

## C++ Measurement

Given `nbody.cpp`:
```bash
codegreen measure cpp nbody.cpp -- 5000
codegreen measure cpp nbody.cpp -g fine --export-plot energy.html -- 5000
```

## How It Works for C/C++

1. Tree-sitter parses the source and identifies function definitions
2. Checkpoint calls are injected at function enter/exit points
3. The instrumented source is compiled with `gcc`/`g++`, linking `-lcodegreen-nemb -lpthread`
4. The compiled binary runs with `LD_LIBRARY_PATH` set to find `libcodegreen-nemb.so`
5. Results are collected via the same NEMB backend as Python

## Notes

- C++ class bodies are not instrumented (executable statements cannot be placed there)
- Compilation flags: `-O2` by default for realistic energy measurement
- The `-lpthread` flag is required for the NEMB background polling thread
