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