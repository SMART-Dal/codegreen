# Java Examples

## Basic Measurement

Given `Main.java`:
```java
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
codegreen measure java Main.java -- 1000000
codegreen measure java Main.java -g fine --export-plot energy.html
```

## How It Works for Java

1. Tree-sitter parses the Java source and identifies method definitions
2. Checkpoint calls are injected at method enter/exit points
3. The instrumented source is compiled with `javac`
4. The compiled class runs with the CodeGreen Java runtime on the classpath
5. Energy data is collected via the NEMB C++ backend

## Known Limitations

- Java filename must match the public class name
- JNI bridge for NEMB has known issues with some JVM configurations
- Best results with simple single-file programs
