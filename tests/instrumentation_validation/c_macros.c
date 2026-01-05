#include <stdio.h>

#define PROCESS_DATA(x) {     int val = (x) * 2;     printf("Processed: %d\\n", val); \
}

#define WRAPPER_FUNC(name) \
    void name() { \
        printf("Inside " #name "\\n"); \
    }

WRAPPER_FUNC(generated_func)

int main() {
    int i = 10;
    PROCESS_DATA(i);
    generated_func();
    return 0;
}