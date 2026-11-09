#!/bin/bash
# MSCS-531 Assignment 3 - runs all cache and TLB experiments in gem5.
#   docker run --rm -it -v "$HOME/gem5-assignment:/gem5" -w /gem5 \
#     ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0 \
#     bash -c 'apt-get update -qq && apt-get install -y -qq gcc-x86-64-linux-gnu && bash a3/run_experiments.sh' 
# Smaller/faster matrix: add -e N=128 after 'docker run --rm -it'.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
GEM5="${GEM5:-/gem5/build/X86/gem5.opt}"
OUT="$DIR/out"
N="${N:-160}"
mkdir -p "$OUT"

fail() { echo ""; echo "FAILED: $1"; echo "No further runs attempted. Send the full terminal output back."; exit 1; }

echo "== Compiling benchmarks (static x86-64) =="
x86_64-linux-gnu-gcc -O2 -static -o "$DIR/mm_x86"  "$DIR/mm.c"        || fail "compile mm.c"
x86_64-linux-gnu-gcc -O2 -static -o "$DIR/tlb_x86" "$DIR/tlb_stress.c" || fail "compile tlb_stress.c"

run() {  # run <label> <binary> <prog-args...> -- <gem5-script opts...>
  local label="$1"; local bin="$2"; shift 2
  local prog_args=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do prog_args+=("$1"); shift; done
  [ $# -gt 0 ] && shift   # drop the --
  echo "== Running $label =="
  "$GEM5" --outdir="$OUT/$label" "$DIR/a3_sim.py" --binary "$DIR/$bin" "${prog_args[@]}" "$@" \
      > "$OUT/$label.stdout.log" 2>&1 || fail "$label: gem5 exited nonzero - see out/$label.stdout.log"
  [ -f "$OUT/$label/stats.txt" ] || fail "$label: no stats.txt produced - see out/$label.stdout.log"
  grep -q "Exiting @ tick" "$OUT/$label.stdout.log" || fail "$label: simulation did not exit cleanly - see out/$label.stdout.log"
  echo "   ok ($(grep -m1 '^simSeconds' "$OUT/$label/stats.txt" | awk '{print $2}') sim-seconds)"
}

echo "== Baseline first: verifying the setup end-to-end before the sweep =="
run mm_baseline mm_x86 "$N" --
echo "== Baseline OK. Continuing the sweep =="

echo "== Part 2a/2b: cache experiments (matrix multiply, N=$N) =="
run mm_l1d_32k         mm_x86 "$N" -- --l1d_size=32KiB
run mm_l1d_128k        mm_x86 "$N" -- --l1d_size=128KiB
run mm_l1d_assoc8      mm_x86 "$N" -- --l1d_assoc=8
run mm_line32          mm_x86 "$N" -- --cacheline_size=32
run mm_line128         mm_x86 "$N" -- --cacheline_size=128
run mm_l2_1m           mm_x86 "$N" -- --l2_size=1MiB
run mm_tuned           mm_x86 "$N" -- --l1d_size=128KiB --l1d_assoc=8 --cacheline_size=128 --l2_size=1MiB

echo "== Part 2c: TLB experiments (random page touch, 256MiB) =="
run tlb_default tlb_x86 256 4 --
run tlb_small   tlb_x86 256 4 -- --dtb_size=16 --itb_size=16
run tlb_large   tlb_x86 256 4 -- --dtb_size=256 --itb_size=256

echo "== Collecting metrics =="
{
echo "run,sim_seconds,cpu_cycles,l1d_miss_rate,l1d_avg_miss_latency_ns,l1d_est_amat_ns,l1i_miss_rate,l2_miss_rate,dtb_accesses,dtb_misses,dtb_miss_rate,itb_accesses,itb_misses,l1d_overall_hits,l1d_overall_misses,l1d_overall_miss_latency_ticks"
for d in "$OUT"/*/; do
  s="$d/stats.txt"; [ -f "$s" ] || continue
  g() { grep -m1 "^$2" "$s" 2>/dev/null | awk -v f="$1" '{print $f}'; }
  freq=$(g 2 'simFreq'); freq=${freq:-1000000000000}
  sim=$(g 2 'simSeconds'); cyc=$(g 2 'system.cpu.numCycles')
  dh=$(g 2 'system.cpu.dcache.overallHits::total'); dm=$(g 2 'system.cpu.dcache.overallMisses::total')
  dmr=$(g 2 'system.cpu.dcache.overallMissRate::total')
  dml=$(g 2 'system.cpu.dcache.overallAvgMissLatency::total')
  dmsl=$(g 2 'system.cpu.dcache.overallMissLatency::total')
  imr=$(g 2 'system.cpu.icache.overallMissRate::total'); l2mr=$(g 2 'system.l2cache.overallMissRate::total')
  dra=$(g 2 'system.cpu.mmu.dtb.rdAccesses'); dwa=$(g 2 'system.cpu.mmu.dtb.wrAccesses')
  drm=$(g 2 'system.cpu.mmu.dtb.rdMisses');   dwm=$(g 2 'system.cpu.mmu.dtb.wrMisses')
  ira=$(g 2 'system.cpu.mmu.itb.exAccesses'); irm=$(g 2 'system.cpu.mmu.itb.exMisses')
  tacc=$(( ${dra:-0} + ${dwa:-0} )); tmiss=$(( ${drm:-0} + ${dwm:-0} ))
  if [ "$tacc" -gt 0 ]; then trate=$(awk "BEGIN{printf \"%.6f\", $tmiss/$tacc}"); else trate=NA; fi
  # ticks -> ns using this run's own simFreq (ns = ticks * 1e9 / simFreq)
  ns_per_tick=$(awk "BEGIN{print 1e9/$freq}")
  dml_ns=$(awk "BEGIN{printf \"%.3f\", ${dml:-0}*$ns_per_tick}")
  # Estimated AMAT = hitRate x modeled hit time + missRate x measured avg miss latency.
  # Modeled hit time = max(tag_latency, data_latency) = 2 cycles; cycle time read
  # from this run's config.ini (system.clk_domain.clock is in ticks per cycle).
  # (gem5 v26 never accumulates overallHitLatency, so no measured hit latency exists.)
  clk_ticks=$(grep -m1 '^clock=' "$d/config.ini" 2>/dev/null | cut -d= -f2); clk_ticks=${clk_ticks:-1000}
  hit_ns=$(awk "BEGIN{print 2*$clk_ticks*$ns_per_tick}")
  est_amat=$(awk "BEGIN{printf \"%.3f\", (1-${dmr:-0})*$hit_ns + ${dmr:-0}*$dml_ns}")
  echo "$(basename "$d"),${sim:-NA},${cyc:-NA},${dmr:-NA},$dml_ns,$est_amat,${imr:-NA},${l2mr:-NA},$tacc,$tmiss,$trate,${ira:-0},${irm:-0},${dh:-NA},${dm:-NA},${dmsl:-NA}"
done
} | tee "$OUT/results.csv"

echo "== DONE. Send back: the a3/out folder plus screenshots =="
