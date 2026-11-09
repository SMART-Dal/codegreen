# C / C++ deep dive

Single-file `codegreen measure c|cpp`. For multi-file projects with Make or
CMake, use [`codegreen project`](../user-guide/project-profiling.md) with
your own `--build-cmd` and `--run-cmd`.

## How it works

1. Tree-sitter finds the function definitions and checkpoint calls are
   injected at each function's entry and exit (coarse: `main` only).
2. The instrumented copy is compiled with `-O2`, linked against
   `libcodegreen-nemb` and `-lpthread` (C also links `-lm`). The compiler is
   `measurement.toolchain.c` / `.cpp` (`gcc` / `g++`), overridden by the
   `CC` / `CXX` environment variables.
3. The binary runs with the CodeGreen library on `LD_LIBRARY_PATH`;
   arguments after `--` are passed to it.

## C

```c
// algorithm.c
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

```bash
codegreen measure c algorithm.c -g fine --sensors rapl
```

```text
Energy: 14.9292 J
Time:   0.1906 s
Power:  78.32 W

  Function                         Excl J     Incl J    Calls  Quality
  compute                         14.9270    14.9270        1  measured
  main                             0.0022    14.9292        1  measured
Validity: valid
```

## C++ with arguments

```cpp
// primes.cpp
#include <cstdlib>
#include <iostream>
#include <vector>

std::vector<int> sieve(int n) {
    std::vector<bool> composite(n + 1, false);
    std::vector<int> primes;
    for (int i = 2; i <= n; ++i) {
        if (composite[i]) continue;
        primes.push_back(i);
        for (long long j = (long long)i * i; j <= n; j += i) composite[j] = true;
    }
    return primes;
}

long long checksum(const std::vector<int>& v) {
    long long s = 0;
    for (int x : v) s = (s * 31 + x) % 1000000007;
    return s;
}

int main(int argc, char** argv) {
    int n = argc > 1 ? std::atoi(argv[1]) : 50000000;
    auto primes = sieve(n);
    std::cout << primes.size() << " " << checksum(primes) << "\n";
    return 0;
}
```

```bash
codegreen measure cpp primes.cpp -g fine --sensors rapl -- 50000000
```

```text
Energy: 15.6379 J
Time:   0.2015 s
Power:  77.62 W

  Function                         Excl J     Incl J    Calls  Quality
  sieve                           14.4312    14.4312        1  measured
  checksum                         1.1157     1.1157        1  below_resolution
  main                             0.0910    15.6379        1  measured
Validity: valid
```

`checksum` (1.12 J at about 78 W, roughly 14 ms) is too short to resolve
against the 10 ms sampler, so its energy is marked `below_resolution`. Exclusive energies
partition the run (they sum to the total); see
[Python deep dive](python.md#codegreen-measure-per-function-energy) for the
inclusive / exclusive and quality columns.

## Notes

- Only free functions get checkpoints. Member functions, whether defined in
  the class body or out of line as `Acc::add`, are not instrumented in 0.5.0;
  their energy is charged to the calling function. `codegreen analyze cpp
  file.cpp --verbose` lists the instrumentation points before you measure.
- A compile failure prints the compiler's diagnostics, is reported as the
  validity reason `COMPILE_FAILED` and exits with code 3.
- `--export-plot energy.html` (or `.png`, `.pdf`) writes the energy timeline;
  see [Reports](../user-guide/reports.md).
