/* Memory workload: random reads/writes over an 8 MiB array (far larger than
 * the 32 KiB L1D; there is no L2), so most accesses go to DRAM. */
#include <stdio.h>
#include <stdlib.h>
#define WORDS (1L << 20)      /* 1M x 8 B = 8 MiB */
#define N 300000L
int main(void) {
    unsigned long *arr = malloc(WORDS * sizeof *arr);
    if (!arr) return 1;
    for (long i = 0; i < WORDS; i += 512) arr[i] = (unsigned long)i; /* touch pages */
    unsigned long r = 12345, sum = 0;
    for (long i = 0; i < N; i++) {
        r = r * 6364136223846793005UL + 1442695040888963407UL;
        unsigned long idx = (r >> 20) & (WORDS - 1);
        sum += arr[idx];
        arr[(idx * 7) & (WORDS - 1)] = sum;
    }
    printf("mem_work done: %lu\n", sum);
    free(arr);
    return 0;
}
