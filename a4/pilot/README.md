# Assignment 4 - Exploring Instruction-Level Parallelism in gem5

MSCS-531 Assignment 4 Part 2 (Computer Architecture), University of the Cumberlands.
Johnson Subedi.

Experiment code, configurations, and measured results. The written report
(Part 1 literature review, Part 2 analysis, screenshots and charts) is
submitted through the course LMS.

> Status: pilot complete (all 5 validation gates pass). The full experiment
> sweep - branch-prediction comparison, issue-width sweep across integer /
> floating-point / memory benchmarks, and SMT resource analysis - is added
> to this folder as it runs.

## Contents

- `ilp_exp.py` - gem5 v26 SE-mode configuration (x86). Options:
  - `--cpu minor` - MinorCPU, the in-order pipelined core (Fetch1 -> Fetch2 ->
    Decode -> Execute, with memory access and writeback inside Execute)
  - `--cpu o3 --width N` - O3CPU superscalar, with fetch/decode/rename/
    dispatch/issue/writeback/commit width all set to `N`
  - `--bp local|bimode|tournament|ltage` - conditional branch predictor
  - `--bin2 <prog>` - second hardware thread on the same O3 core (SMT)
  - `--maxtick` - bound the simulation length
  - Memory system: 32 KiB 8-way private L1I/L1D, DDR3-1600, 2 GHz clock
- `hello.c` - Hello World smoke-test program
- `int_work.c` - integer ALU workload (2M-iteration multiply/add LCG loop)
- `run_pilot.sh` - writes the config and workloads, cross-compiles them
  (static x86-64) and runs the 5 validation gates below
- `stats/` - raw gem5 `stats.txt` for every pilot run
- `configs/` - the gem5 `config.ini` generated for every pilot run
- `logs/pilot_run.log` - full output of the passing pilot run
- `logs/minor_trace_excerpt.txt` - MinorCPU `MinorTrace,MinorExecute` debug
  trace around the first committed instructions (cycle-by-cycle pipeline view)
- `logs/gate1_failed_before_fix.log` - the original Gate 1 failure (see
  Troubleshooting)

## Pilot results

| Gate | Run | Result |
|---|---|---|
| 1 | Hello World on MinorCPU (caches, interrupts, page-walker ports) | Pass - printed "Hello World! gem5 x86 smoke test OK" |
| 2 | Hello World on O3CPU, width 4, tournament predictor | Pass |
| 3 | SMT: two Hello World threads on one O3 core | Pass - both threads ran to completion |
| 4 | `int_work` on O3CPU, width 4, tournament | Pass - 18,132,425 instructions, 12,159,218 cycles, **IPC 1.491**, 6.08 ms simulated (38 s wall) |
| 5 | MinorCPU pipeline trace of Hello World (first 2M ticks) | Pass - 196 committed instructions measured, average fetch-to-commit latency 15.3 cycles |

Note on Gate 5: the latency script matches each instruction's first and
commit trace lines by instruction ID. Some instructions show a 0-cycle
minimum because their earlier pipeline-stage lines use a different ID
format, so the average is a lower bound until the parser is refined.

## Troubleshooting

Problems found while bringing up the configuration on gem5 v26, and fixes:

1. **`TypeError: 'module' object is not callable`** at `MinorCPU()`
   (`logs/gate1_failed_before_fix.log`). In gem5 v26, `MinorCPU` / `O3CPU`
   resolve to Python modules, not classes. A follow-up attempt to import the
   class directly failed with `ImportError: cannot import name 'MinorCPU'`.
   Fix: use the ISA-specific classes `X86MinorCPU` and `X86O3CPU`
   (`src/arch/x86/X86CPU.py`).
2. **Branch predictor assignment.** In v26 `O3CPU.branchPred` is a
   `BranchPredictor` wrapper; the direction predictor goes in its
   `conditionalBranchPred` parameter
   (`BranchPredictor(conditionalBranchPred=TournamentBP())`), not directly
   in `branchPred`.
3. **False Gate 1 failure.** The simulation printed Hello World, but the
   check grepped `simout`, which gem5 only writes when stdout redirection
   (`-r`) is on. `grep` exits with an error on a missing file even when it
   matches in another file. Fix: only search files that exist.
4. **SMT abort:** `base.cc:502: Assertion 'system->multiThread || numThreads == 1' failed`.
   Fix: set `system.multi_thread = True` whenever the core has more than one
   hardware thread.

## Reproduce

Requires Docker and the gem5 v26 all-dependencies image
(`ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0`) with a built x86
`gem5.opt` at `/gem5/build/X86/gem5.opt` in the mounted gem5 directory.
Copy `run_pilot.sh` to the gem5 root, then inside the container:

```bash
bash /gem5/run_pilot.sh 2>&1 | tee pilot_run.log
```

The script installs the x86-64 cross-compiler if needed and stops at the
first failing gate.
