/* Matrix multiply (ijk order) - cache-stress benchmark for A3.
 * Column-wise access of b gives poor spatial locality.
 * Usage: mm_x86 [N]   (default N=160) */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    int N = (argc > 1) ? atoi(argv[1]) : 160;
    double *a = malloc((size_t)N * N * sizeof(double));
    double *b = malloc((size_t)N * N * sizeof(double));
    double *c = malloc((size_t)N * N * sizeof(double));
    if (!a || !b || !c) { fprintf(stderr, "alloc failed\n"); return 1; }

    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            a[i * N + j] = (double)(i + j);
            b[i * N + j] = (double)(i - j);
            c[i * N + j] = 0.0;
        }

    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            double s = 0.0;
            for (int k = 0; k < N; k++)
                s += a[i * N + k] * b[k * N + j];
            c[i * N + j] = s;
        }

    double checksum = 0.0;
    for (int i = 0; i < N * N; i++) checksum += c[i];
    printf("N=%d checksum=%f\n", N, checksum);
    free(a); free(b); free(c);
    return 0;
}
