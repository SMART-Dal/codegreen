#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// Complex Math: Monte Carlo Pi estimation
// Tests loop density and FPU usage
void compute_pi() {
    long iterations = 1000000;
    long inside = 0;
    
    for (long i = 0; i < iterations; i++) {
        double x = (double)rand() / RAND_MAX;
        double y = (double)rand() / RAND_MAX;
        if (x*x + y*y <= 1.0) inside++;
    }
    
    double pi = 4.0 * inside / iterations;
    printf("Pi approx: %f\n", pi);
}

int main() {
    compute_pi();
    return 0;
}