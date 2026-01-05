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