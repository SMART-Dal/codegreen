# Java deep dive

Single-file `codegreen measure java`. For a build system and per-method
attribution across a project, see
[04 - Project hotspots (Java)](04_project_hotspots_java.md) and
[Project Profiling](../user-guide/project-profiling.md).

## How it works

1. Tree-sitter finds the method declarations and checkpoint calls are
   injected at each method's entry and exit (coarse: `main` only).
2. The instrumented copy is compiled with `javac` against the CodeGreen Java
   runtime.
3. The class runs with the runtime on the classpath; it loads
   `libcodegreen-nemb` through JNI. Arguments after `--` are passed to
   `main`.

## Example

```java
// Main.java
public class Main {
    static double compute(int n) {
        double sum = 0;
        for (int i = 0; i < n; i++)
            sum += Math.sin(i) * Math.cos(i);
        return sum;
    }

    public static void main(String[] args) {
        int n = args.length > 0 ? Integer.parseInt(args[0]) : 1000000;
        System.out.println(compute(n));
    }
}
```

```bash
codegreen measure java Main.java -g fine --sensors rapl -- 20000000
```

```text
Energy: 74.1257 J
Time:   0.9593 s
Power:  77.27 W

  Function                         Excl J     Incl J    Calls  Quality
  Main.compute                    74.0776    74.0776        1  measured
  Main.main                        0.0481    74.1257        1  measured
Validity: valid
```

The window starts when `main` is entered, so JVM start-up is not included.
With the default `n` of 1,000,000 the program runs for about 50 ms on this
host and both methods are `below_resolution`; pass a larger `n` as shown.

## Notes

- The file name must match the public class name (`javac` rule).
- Methods are reported as `Class.method`.
- `codegreen measure java` handles one source file. For several files, a
  build tool or JMH benchmarks, use `codegreen project java`.
