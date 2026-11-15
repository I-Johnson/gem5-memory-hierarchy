#include <stdio.h>
#define N 2000000L
int main(void) {
    unsigned long a = 1, c = 0;
    for (unsigned long i = 0; i < N; i++) { c += a * 3UL + i; a = (a * 1103515245UL + 12345UL) & 0x7fffffffUL; }
    printf("int pilot done: %lu\n", c);
    return 0;
}
