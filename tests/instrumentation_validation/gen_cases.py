
import os
from pathlib import Path

path = Path("tests/instrumentation_validation")
os.makedirs(path, exist_ok=True)

# ---------------------------------------------------------
# C Workloads
# ---------------------------------------------------------

def generate_c_macros():
    content = """
#include <stdio.h>

#define PROCESS_DATA(x) { \
    int val = (x) * 2; \
    printf(\"Processed: %d\\\\n\", val); \\
}

#define WRAPPER_FUNC(name) \\
    void name() { \\
        printf(\"Inside \" #name \"\\\\n\"); \\
    }

WRAPPER_FUNC(generated_func)

int main() {
    int i = 10;
    PROCESS_DATA(i);
    generated_func();
    return 0;
}
"""
    with open(path / "c_macros.c", "w") as f: f.write(content.strip())

def generate_c_structs():
    content = """
#include <stdio.h>

typedef struct Outer {
    int id;
    struct Inner {
        float val;
        union {
            int i;
            float f;
        } data;
    } inner;
} Outer;

void process_struct(Outer* o) {
    if (o->inner.val > 0) {
        o->inner.data.i = 100;
    } else {
        o->inner.data.f = 1.0;
    }
}

int main() {
    Outer o;
    o.inner.val = 5.5;
    process_struct(&o);
    return 0;
}
"""
    with open(path / "c_structs.c", "w") as f: f.write(content.strip())

def generate_c_nested():
    content = """
#include <stdio.h>

int main() {
    int x = 0;
    if (x == 0) {
        {
            int y = 1;
            if (y > 0) {
                while (y < 10) {
                    y++;
                    if (y % 2 == 0) {
                        printf(\"Even\\\\n\");
                    }
                }
            }
        }
    }
    return 0;
}
"""
    with open(path / "c_nested.c", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# C++ Workloads
# ---------------------------------------------------------

def generate_cpp_templates():
    content = """
#include <iostream>

template <typename T>
T add(T a, T b) {
    return a + b;
}

template <typename T>
class Container {
    T val;
public:
    Container(T v) : val(v) {}
    T get() { return val; }
};

int main() {
    std::cout << add(1, 2) << std::endl;
    std::cout << add(1.5, 2.5) << std::endl;
    Container<int> c(10);
    std::cout << c.get() << std::endl;
    return 0;
}
"""
    with open(path / "cpp_templates.cpp", "w") as f: f.write(content.strip())

def generate_cpp_lambdas():
    content = """
#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::vector<int> v = {1, 2, 3, 4, 5};
    int multiplier = 2;
    
    std::for_each(v.begin(), v.end(), [multiplier](int& n) {
        if (n % 2 == 0) {
            n *= multiplier;
        } else {
            n += 1;
        }
    });
    
    auto lambda_func = []() {
        std::cout << "Inside lambda" << std::endl;
        return 0;
    };
    
    lambda_func();
    
    return 0;
}
"""
    with open(path / "cpp_lambdas.cpp", "w") as f: f.write(content.strip())

def generate_cpp_classes():
    content = """
#include <iostream>

class Outer {
private:
    int x;
    
    class Inner {
    public:
        void print() {
            std::cout << "Inner class" << std::endl;
        }
    };
    
public:
    Outer() : x(0) {}
    
    void run() {
        Inner i;
        i.print();
    }
    
    friend class FriendClass;
};

class FriendClass {
public:
    void access(Outer& o) {
        o.x = 10;
    }
};

int main() {
    Outer o;
    o.run();
    FriendClass f;
    f.access(o);
    return 0;
}
"""
    with open(path / "cpp_classes.cpp", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# Java Workloads
# ---------------------------------------------------------

def generate_java_inner():
    content = """
public class java_inner {
    private int x = 10;
    
    class Inner {
        void display() {
            System.out.println("Inner: " + x);
        }
    }
    
    static class StaticNested {
        void show() {
            System.out.println(\"Static Nested\");
        }
    }
    
    public static void main(String[] args) {
        java_inner outer = new java_inner();
        java_inner.Inner inner = outer.new Inner();
        inner.display();
        
        java_inner.StaticNested staticNested = new java_inner.StaticNested();
        staticNested.show();
    }
}
"""
    with open(path / "java_inner.java", "w") as f: f.write(content.strip())

def generate_java_anon():
    content = """
interface Greeter {
    void greet();
}

public class java_anon {
    public static void main(String[] args) {
        Greeter g = new Greeter() {
            @Override
            public void greet() {
                System.out.println(\"Hello from anonymous class\");
                helper();
            }
            
            private void helper() {
                System.out.println(\"Helper method\");
            }
        };
        
        g.greet();
    }
}
"""
    with open(path / "java_anon.java", "w") as f: f.write(content.strip())

def generate_java_generics():
    content = """
public class java_generics {
    public static <T> void printArray(T[] inputArray) {
        for (T element : inputArray) {
            System.out.printf("%s ", element);
        }
        System.out.println();
    }

    public static void main(String[] args) {
        Integer[] intArray = { 1, 2, 3, 4, 5 };
        Double[] doubleArray = { 1.1, 2.2, 3.3, 4.4 };
        Character[] charArray = { 'H', 'E', 'L', 'L', 'O' };

        System.out.println(\"Array integerArray contains:\");
        printArray(intArray);

        System.out.println(\"\\\\nArray doubleArray contains:\");
        printArray(doubleArray);

        System.out.println(\"\\\\nArray characterArray contains:\");
        printArray(charArray);
    }
}
"""
    with open(path / "java_generics.java", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# Python Workloads
# ---------------------------------------------------------

def generate_python_decorators():
    content = """
import time

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end-start}s")
        return result
    return wrapper

@timer_decorator
def heavy_computation(n):
    total = 0
    for i in range(n):
        total += i
    return total

def main():
    heavy_computation(10000)

if __name__ == "__main__":
    main()
"""
    with open(path / "python_decorators.py", "w") as f: f.write(content.strip())

def generate_python_nested():
    content = """
def outer_function(text):
    text = text.upper()
    
    def inner_function():
        print(text)
        
    inner_function()
    
    def closure_maker(x):
        def closure(y):
            return x + y
        return closure
        
    add5 = closure_maker(5)
    print(add5(10))

def main():
    outer_function("hello")

if __name__ == "__main__":
    main()
"""
    with open(path / "python_nested.py", "w") as f: f.write(content.strip())

def generate_python_async():
    content = """
import asyncio

async def async_task(name, delay):
    print(f"Task {name} starting")
    await asyncio.sleep(delay)
    print(f"Task {name} finished")
    return len(name)

async def main():
    task1 = asyncio.create_task(async_task("A", 0.1))
    task2 = asyncio.create_task(async_task("B", 0.2))
    
    await task1
    await task2
    print("All tasks done")

if __name__ == "__main__":
    asyncio.run(main())
"""
    with open(path / "python_async.py", "w") as f: f.write(content.strip())

if __name__ == "__main__":
    generate_c_macros()
    generate_c_structs()
    generate_c_nested()
    generate_cpp_templates()
    generate_cpp_lambdas()
    generate_cpp_classes()
    generate_java_inner()
    generate_java_anon()
    generate_java_generics()
    generate_python_decorators()
    generate_python_nested()
    generate_python_async()
    print("Generated instrumentation validation workloads.")
