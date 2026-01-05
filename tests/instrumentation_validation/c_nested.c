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
                        printf("Even\\n");
                    }
                }
            }
        }
    }
    return 0;
}