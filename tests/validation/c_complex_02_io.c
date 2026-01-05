#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Complex IO: File processing simulation
// Tests loop instrumentation and IO waits
void process_file() {
    FILE *fp = fopen("temp_test.dat", "w+");
    if (!fp) return;
    
    // Write data
    for (int i = 0; i < 10000; i++) {
        fprintf(fp, "Line %d: data data data\n", i);
    }
    
    rewind(fp);
    
    // Read and process
    char buffer[100];
    long sum = 0;
    while (fgets(buffer, sizeof(buffer), fp)) {
        sum += strlen(buffer);
    }
    
    printf("Total length: %ld\n", sum);
    fclose(fp);
    remove("temp_test.dat");
}

int main() {
    process_file();
    return 0;
}