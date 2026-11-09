/* tlb_fs.c - page-size / page-fault benchmark for A3 (native or gem5 guest).
 * No hardcoded page sizes: base page size from sysconf(_SC_PAGESIZE), huge
 * page size from /sys/kernel/mm/transparent_hugepage/hpage_pmd_size.
 * Allocation: anonymous mmap aligned to the huge-page size so THP can
 * assemble huge pages. Base run MADV_NOHUGEPAGE, huge run MADV_HUGEPAGE.
 * Pages are WRITE-touched first (reading untouched anonymous memory hits the
 * shared zero page and allocates nothing), then measured with random reads.
 * Faults: getrusage(RUSAGE_SELF) ru_minflt/ru_majflt (per-process).
 * Actual backing proven from /proc/self/smaps AnonHugePages on the VMA
 * containing the buffer (KernelPageSize keeps showing the base size even for
 * huge-backed VMAs - AnonHugePages is the decisive field).
 * Usage: tlb_fs [MiB] [rounds] [huge]   (default 256 MiB, 4 rounds, huge=0) */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/resource.h>

static void faults(const char *tag) {
    struct rusage ru;
    getrusage(RUSAGE_SELF, &ru);
    printf("%s: minor_faults=%ld major_faults=%ld\n", tag, ru.ru_minflt, ru.ru_majflt);
    fflush(stdout);
}

static unsigned long read_hpage_size(void) {
    FILE *f = fopen("/sys/kernel/mm/transparent_hugepage/hpage_pmd_size", "r");
    unsigned long v = 0;
    if (f) { if (fscanf(f, "%lu", &v) != 1) v = 0; fclose(f); }
    return v;  /* bytes, or 0 if unknown */
}

static void smaps_check(void *start, size_t len) {
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f) { perror("smaps"); return; }
    char line[512];
    unsigned long lo, hi, want = (unsigned long)start;
    int in_vma = 0;
    while (fgets(line, sizeof line, f)) {
        /* VMA headers look like "55f8a00000-55f8b00000 rw-p ..."; requiring
         * two conversions rejects hex-leading field lines like "Anonymous:". */
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2) {
            in_vma = (want >= lo && want < hi);
            if (in_vma && hi - lo < len)
                printf("smaps: note: VMA %lx-%lx smaller than buffer\n", lo, hi);
            continue;
        }
        if (in_vma && (!strncmp(line, "KernelPageSize:", 15) ||
                       !strncmp(line, "MMUPageSize:", 12) ||
                       !strncmp(line, "AnonHugePages:", 14)))
            printf("smaps: %s", line);
    }
    fclose(f);
}

int main(int argc, char **argv) {
    size_t mib = argc > 1 ? (size_t)atol(argv[1]) : 256;
    int rounds = argc > 2 ? atoi(argv[2]) : 4;
    int huge   = argc > 3 ? atoi(argv[3]) : 0;

    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    unsigned long hpage = read_hpage_size();
    unsigned long align = hpage ? hpage : (2UL << 20);
    printf("base_page_size=%zu hpage_pmd_size=%lu\n", page, hpage);

    size_t len = mib << 20;
    char *raw = mmap(NULL, len + align, PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (raw == MAP_FAILED) { perror("mmap"); return 1; }
    char *buf = (char *)(((unsigned long)raw + (align - 1)) & ~(align - 1));

    int adv = huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE;
    if (madvise(buf, len, adv) != 0) {
        perror("madvise");
        fprintf(stderr,
            "FATAL: page-size advice (%s) was NOT applied; continuing would "
            "mislabel the run. Aborting so no wrong-mode data is produced.\n",
            huge ? "MADV_HUGEPAGE" : "MADV_NOHUGEPAGE");
        return 1;
    }

    size_t pages = len / page;
    unsigned long *order = malloc(pages * sizeof *order);
    if (!order) { perror("malloc order"); return 1; }
    for (size_t i = 0; i < pages; i++) order[i] = i;
    for (size_t i = pages - 1; i > 0; i--) {  /* deterministic shuffle */
        size_t j = (size_t)(((unsigned long)i * 6364136223846793005UL + 1442695040888963407UL) >> 33);
        if (i) j %= (i + 1);
        unsigned long t = order[i]; order[i] = order[j]; order[j] = t;
    }

    faults("before");
    /* write-touch: one byte per base page, random order - this is where the
     * allocation (and the minor faults) actually happen */
    for (size_t i = 0; i < pages; i++)
        buf[order[i] * page] = (char)i;
    faults("after_write_touch");
    /* measurement rounds: random-order reads over the allocated pages */
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    volatile long sum = 0;
    for (int r = 0; r < rounds; r++)
        for (size_t i = 0; i < pages; i++)
            sum += buf[order[i] * page];
    clock_gettime(CLOCK_MONOTONIC, &t1);
    faults("after_reads");
    double secs = (double)(t1.tv_sec - t0.tv_sec) + (double)(t1.tv_nsec - t0.tv_nsec) / 1e9;
    printf("read_rounds_wall_seconds=%.4f pages=%zu\n", secs, pages);
    printf("MiB=%zu rounds=%d huge_requested=%d sum=%ld\n", mib, rounds, huge, (long)sum);
    smaps_check(buf, len);
    fflush(stdout);
    return 0;
}
