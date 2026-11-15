/* Branch workload, UNPREDICTABLE: direction depends on pseudo-random bits.
 * noinline + volatile sinks keep the compiler from turning it into cmov. */
#include <stdio.h>
#define N 1000000L
static volatile unsigned long sink_a, sink_b;
int main(void) {
    unsigned long r = 88172645463325252UL, a = 0, b = 0;
    for (long i = 0; i < N; i++) {
        r ^= r << 13; r ^= r >> 7; r ^= r << 17;   /* xorshift64 */
        if (r & 1) { a += r >> 3; sink_a = a; }
        else       { b ^= r << 2; sink_b = b; }
    }
    printf("branch_rand done: %lu %lu\n", a, b);
    return 0;
}
