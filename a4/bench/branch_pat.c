/* Branch workload, PREDICTABLE: same loop body as branch_rand but the
 * direction follows a fixed period-4 pattern (taken, taken, not, not). */
#include <stdio.h>
#define N 1000000L
static volatile unsigned long sink_a, sink_b;
int main(void) {
    unsigned long r = 88172645463325252UL, a = 0, b = 0;
    for (long i = 0; i < N; i++) {
        r ^= r << 13; r ^= r >> 7; r ^= r << 17;
        if ((i & 2) == 0) { a += r >> 3; sink_a = a; }
        else              { b ^= r << 2; sink_b = b; }
    }
    printf("branch_pat done: %lu %lu\n", a, b);
    return 0;
}
