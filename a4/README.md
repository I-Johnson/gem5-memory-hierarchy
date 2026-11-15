# Assignment 4 - Exploring Instruction-Level Parallelism in gem5

MSCS-531 Assignment 4 Part 2 (Computer Architecture), University of the Cumberlands.
Johnson Subedi.

Experiment code, gem5 configuration, raw statistics and measured results for
Part 2. The written report (Part 1 literature review, Part 2 analysis and
screenshots) is submitted through the course LMS.

All 46 simulations were run on gem5 v26.0.0.0 (x86, SE mode, `gem5.opt`) in the
`ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0` container.

## Contents

| Path | What it is |
|---|---|
| `ilp_exp.py` | gem5 configuration: in-order pipeline (`--cpu minor`), superscalar out-of-order (`--cpu o3 --width N`), branch predictor (`--bp none/local/bimode/tournament/ltage`), SMT (`--bin2`) |
| `bench/` | Workloads: `int_work.c` (integer ALU), `fp_work.c` (floating point), `mem_work.c` (random access over 8 MiB), `branch_rand.c` (unpredictable branch), `branch_pat.c` (same loop, predictable pattern), `hello.c` |
| `run_experiments.sh` | Builds the workloads and runs the whole sweep (8 jobs in parallel), the latency pass, pipeline views and charts |
| `latency.py` | Per-instruction latency from a gem5 debug trace (`O3PipeView` for O3, `MinorTrace` for MinorCPU) |
| `collect.py`, `charts.py` | Turn `runs/*/stats.txt` into `results/results.csv`, `results/summary.md` and the charts |
| `results/summary.md` | **All result tables** (pipeline, branch prediction, issue width, SMT) |
| `results/results.csv` | Every metric for every run |
| `results/chart_*.png` | Charts: IPC vs issue width, branch predictors, latency, SMT |
| `results/pipeview/` | Pipeline visualization: gem5 `util/o3-pipeview.py` timelines (`.color.txt` for a terminal) and a MinorCPU cycle-by-cycle stage trace |
| `runs/<name>/` | Raw gem5 output per run: `stats.txt`, `config.ini`, `console.log`, `latency.json` |
| `gem5-patch/` | `StaticNotTakenBP` - the static "no prediction" baseline added to gem5 (see Troubleshooting 5) |
| `pilot/` | The earlier 5-gate pilot (smoke tests) and its logs |

## Machine configuration

2 GHz core; 32 KiB 8-way L1I and L1D (1-cycle tag/data); no L2; DDR3-1600 main memory.

- **Basic pipeline - `X86MinorCPU`:** in-order, single issue. Its stages are Fetch1 (line fetch), Fetch2 (instruction decomposition and branch prediction), Decode (micro-ops) and Execute. Execute holds the functional units, the memory stage (load/store queue) and writeback/commit.
- **Superscalar - `X86O3CPU`:** out-of-order. Fetch, decode, rename, dispatch, issue, writeback, commit and squash widths are all set to W = 1, 2, 4 or 8.
- **SMT:** 2 hardware threads on one O3 core, using gem5's default policies (partitioned ROB, IQ and LSQ; round-robin fetch and commit).

## Key results

Full tables are in [`results/summary.md`](results/summary.md).

**Basic pipeline (MinorCPU).**
- Throughput ranges from 0.68 IPC (`branch_pat`) to 0.066 IPC (`mem_work`).
- Average fetch-to-commit latency is 13-15 cycles for integer and branch code, 30 cycles for floating point and 87 cycles for `mem_work`, where 94% of D-cache accesses miss and go to DRAM.

**Branch prediction (O3, W=4).**

| Workload | Static not-taken: IPC | Static not-taken: mispredict | Tournament: IPC | Tournament: mispredict |
|---|---:|---:|---:|---:|
| `int_work` | 0.72 | 49% | 2.13 | 0.08% |
| `branch_pat` | 1.02 | 28% | 1.92 | 0.04% |
| `branch_rand` | 0.84 | 28% | 0.91 | 9.6% |

- `int_work` runs 2.96x faster with the tournament predictor.
- The plain 2-bit local predictor cannot learn the period-4 pattern in `branch_pat`. It mispredicts 17.6% and reaches only 1.25 IPC.
- Bimode, tournament and LTAGE all learn the pattern.
- No predictor can learn the random branch in `branch_rand`.

**Multiple issue (tournament).**

| Workload | W=1 IPC | W=8 IPC | Notes |
|---|---:|---:|---|
| `fp_work` | 0.72 | 4.46 | Superscalar shines: 6.2x, from independent FP chains |
| `int_work` | 0.65 | 2.14 | Flat from W=4: the multiply/LCG dependency chain limits it |
| `branch_rand` | 0.67 | 1.00 | Mispredict-bound |
| `mem_work` | 0.078 | 0.077 | Memory-bound: width does not help at all |

**SMT (W=4).** The result depends on the mix:
- **2 memory-bound threads finish 1.72x faster** than running them one after the other, because one thread's DRAM stalls are hidden by the other.
- **`branch_rand` + `int` gives 1.46x.**
- **Compute-bound pairs are slower**: int+int is 0.61x and int+fp is 0.65x. Partitioning halves each thread's ROB and IQ, and 2.45M ROB-full events show the contention.
- **int+mem is 0.81x**: the memory thread fills the store queue (16M SQ-full events) and starves the integer thread.

## Troubleshooting log

Problems hit while bringing the experiments up on gem5 v26, and how each was resolved:

1. **`TypeError: 'module' object is not callable`** at `MinorCPU()`. A follow-up attempt failed with `ImportError: cannot import name 'MinorCPU'`.
   - Cause: in v26, `MinorCPU` / `O3CPU` name Python modules, not classes.
   - Fix: use the ISA classes `X86MinorCPU` / `X86O3CPU`.
2. **Branch predictor parameter:** `O3CPU.branchPred` is now a `BranchPredictor` wrapper.
   - Fix: pass the direction predictor as `BranchPredictor(conditionalBranchPred=TournamentBP())`.
3. **False "no Hello World output" failure.**
   - Cause: the check grepped `simout`, which gem5 writes only with `-r`. `grep` exits with an error on a missing file even when another file matches.
   - Fix: search only files that exist.
4. **SMT abort: `Assertion 'system->multiThread || numThreads == 1' failed`.**
   - Fix: set `system.multi_thread = True` when the core has 2 threads.
5. **gem5 has no static branch predictor**, which the "without prediction" comparison needs.
   - On x86, MinorCPU makes **zero** predictor lookups: Fetch2 sees macro-ops before Decode splits them into micro-ops. The in-order pipeline therefore effectively runs with no prediction, and the with/without comparison was done on O3.
   - First attempt: a 1-entry BTB with no RAS. This still produced 1.86M BTB hits, so it was not a real "no prediction" baseline.
   - Fix: added `StaticNotTakenBP` to gem5 (`gem5-patch/`), a conditional predictor that always predicts not-taken and never learns, then rebuilt `gem5.opt`. Verified: `condPredictedTaken = 0`.
6. **Width-1 O3 panic: `TimeBuffer out-of-bounds access! Wire index 6 is outside valid range [-5, +5]`.**
   - Fix: `forwardComSize = backComSize = 10` for all O3 runs.
   - Single-thread cycle counts were identical with 5 and 10 (`int_work` W=4: 6,162,485 both times), so this only sizes the inter-stage buffers. One SMT case (int+int) did change, so every O3 run was redone with the final setting.
   - Each configuration was then re-run to confirm the result repeats exactly.
7. **Wrong latency window.**
   - Cause: the first sweep traced a fixed window 200k cycles into each run. For the slower configurations that window was still in libc start-up code, which is identical across programs, so every MinorCPU workload reported the same latency.
   - Fix: re-simulate each run to its midpoint and trace 20,000 cycles of the program's own main loop.

## Reproduce

Requires Docker, the container image above, and a built x86 `gem5.opt` with the patch from `gem5-patch/` applied:

```bash
git apply static-not-taken-bp.patch
scons build/X86/gem5.opt -j6
```

Copy this folder to `/gem5/a4` in the gem5 checkout, then inside the container run:

```bash
bash /gem5/a4/run_experiments.sh
```

The sweep takes about 25 minutes on 8 parallel jobs. Runs that already have a `stats.txt` are skipped.

## Metric definitions

- **Throughput:** IPC = committed instructions / cycles (`system.cpu.ipc`). For SMT runs it is also reported per thread (`commitStats0/1.ipc`).
- **Latency:** the average number of cycles from fetch to commit (MinorCPU) or fetch to retire (O3) per committed instruction. It is measured over a 20,000-cycle window in the middle of each run; squashed instructions are excluded.
- **Mispredict rate:** `branchPred.condIncorrect / branchPred.condPredicted`.
