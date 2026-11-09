/* Random page-touch benchmark - dTLB stress for A3.
 * Touches one byte per 4KiB page in random order over a large buffer,
 * so nearly every access hits a different page.
 * Usage: tlb_x86 [MiB] [rounds]   (default 256 MiB, 4 rounds) */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    size_t mib   = (argc > 1) ? (size_t)atol(argv[1]) : 256;
    int rounds   = (argc > 2) ? atoi(argv[2]) : 4;
    size_t bytes = mib << 20;
    size_t pages = bytes / 4096;

    volatile char *p = malloc(bytes);
    if (!p) { fprintf(stderr, "alloc failed\n"); return 1; }

    /* fault pages in sequentially first */
    for (size_t i = 0; i < pages; i++) p[i * 4096] = 0;

    unsigned long sum = 0;
    srand(12345);
    for (int r = 0; r < rounds; r++)
        for (size_t t = 0; t < pages; t++) {
            size_t idx = (size_t)rand() % pages;
            sum += p[idx * 4096];
        }

    printf("MiB=%zu rounds=%d sum=%lu\n", mib, rounds, sum);
    return 0;
}
