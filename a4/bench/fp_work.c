/* Floating-point workload: independent FP multiply-add chains plus a divide. */
#include <stdio.h>
#define N 500000L
int main(void) {
    double x = 1.0001, y = 0.9999, s0 = 0, s1 = 0, s2 = 0, s3 = 0;
    for (long i = 0; i < N; i++) {
        double t = (double)i;
        s0 += x * t;
        s1 += y * t + 0.5;
        s2 += (t + 1.0) / (t + 2.0);
        s3 = s3 * 0.999 + x * y;
    }
    printf("fp_work done: %.6f %.6f %.6f %.6f\n", s0, s1, s2, s3);
    return 0;
}
