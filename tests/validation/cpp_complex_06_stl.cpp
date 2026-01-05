#include <iostream>
#include <map>
#include <string>
#include <algorithm>

// Complex STL: Map and string operations
void process_data() {
    std::map<int, std::string> data;
    
    // Insert
    for (int i = 0; i < 10000; i++) {
        data[i] = "Value_" + std::to_string(i);
    }
    
    // Find and modify
    long total_chars = 0;
    for (int i = 0; i < 10000; i++) {
        if (data.find(i) != data.end()) {
            total_chars += data[i].length();
        }
    }
    
    std::cout << "Total chars: " << total_chars << std::endl;
}

int main() {
    process_data();
    return 0;
}