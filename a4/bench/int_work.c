/* Integer ALU workload: multiply/add LCG chain plus independent adds. */
#include <stdio.h>
#define N 1000000L
int main(void) {
    unsigned long a = 1, b = 7, c = 0, d = 0;
    for (unsigned long i = 0; i < N; i++) {
        c += a * 3UL + i;                 /* depends on a */
        d ^= (b << 3) + i;                /* independent chain */
        a = (a * 1103515245UL + 12345UL) & 0x7fffffffUL;
        b = b * 6364136223846793005UL + 1UL;
    }
    printf("int_work done: %lu %lu\n", c, d);
    return 0;
}
