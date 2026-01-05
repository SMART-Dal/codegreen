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