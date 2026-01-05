#include <stdio.h>
#include <stdlib.h>

// Complex recursion: Ackermann function
// Tests function entry/exit overhead and deep stack
long ackermann(long m, long n) {
    if (m == 0) return n + 1;
    if (n == 0) return ackermann(m - 1, 1);
    return ackermann(m - 1, ackermann(m, n - 1));
}

int main() {
    long m = 3, n = 8;
    printf("Computing Ackermann(%ld, %ld)...\n", m, n);
    long result = ackermann(m, n);
    printf("Result: %ld\n", result);
    return 0;
}