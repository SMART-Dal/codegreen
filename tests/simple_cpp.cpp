#include <iostream>

int add(int a, int b) {
    return a + b;
}

int main() {
    int x = add(1, 2);
    std::cout << "Result: " << x << std::endl;
    return 0;
}
