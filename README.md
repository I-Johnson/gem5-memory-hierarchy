# Exploring Memory Hierarchy Design in gem5

MSCS-531 Assignment 3 (Computer Architecture), University of the Cumberlands.
Johnson Subedi.

Experiment code, configurations, and measured results. The written report
(analysis, graphs, discussion) is submitted through the course LMS.

## Contents

- `a3_sim.py` - gem5 v26 SE-mode configuration (x86 TimingSimpleCPU, two-level
  cache) with CLI options for cache size, associativity, cache line size, and
  TLB sizes
- `mm.c` - matrix-multiply cache-stress benchmark
- `tlb_stress.c` - random page-touch dTLB stress benchmark
- `run_experiments.sh` - runs the baseline, 7 cache/TLB variations, and the
  tuned combination; collects metrics into `results.csv`
- `results.csv` - metrics for all 11 gem5 runs
- `stats/` - raw gem5 `stats.txt` output for every run (one `<run>.stats.txt` file per configuration)
- `tlb_fs.c` + `native_run.sh` - native Linux page-size / page-fault
  experiment (base 4 KiB vs huge pages via madvise; faults from getrusage;
  actual backing proven from /proc/self/smaps AnonHugePages)
- `screenshot-*.png` - terminal screenshots: gem5 run outputs and results,
  the gem5 configuration, the native experiment, and the Hello World
  smoke test

## Reproduce

Requires Docker and the gem5 v26 all-dependencies image
(`ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0`) with a built x86
`gem5.opt` in the mounted directory - see the header of `run_experiments.sh`.

## Notes and limitations

- gem5 SE mode uses functional address translation with demand-mapped memory:
  no real page faults and no page-size variation. The TLB miss counts are real
  measurements, but SE models no page-walk timing, so the three TLB
  configurations show identical simulated times.
- `l1d_est_amat_ns` is a documented estimate: gem5 v26 never accumulates
  `overallHitLatency`, so the hit term is modeled (2-cycle hit latency), not
  measured.
- The page-fault and huge-page results come from the native Linux experiment
  (ARM host), not from gem5; the two are not directly comparable.
- The Assignment 2 "Hello, World!" program was rerun on November 8, 2026 as a
  smoke test of the toolchain; it is not one of the Part 2 measurements.
