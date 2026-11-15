#!/bin/bash
# MSCS-531 Assignment 4 Part 2 - PILOT (bounded smoke + timing, stops on any error)
# Run inside the gem5 container (the one already open in Terminal):
#   bash /gem5/run_pilot.sh
set -uo pipefail

GEM5=/gem5/build/X86/gem5.opt
WORK=/gem5/a4_pilot
mkdir -p "$WORK"
cd "$WORK"

# cross-compiler (no-op if already installed in this container)
command -v x86_64-linux-gnu-gcc >/dev/null 2>&1 || {
  echo "==> installing gcc-x86-64-linux-gnu"
  apt-get update -qq && apt-get install -y -qq gcc-x86-64-linux-gnu || {
    echo "FAIL: compiler install"; exit 1; }
}

echo "==> Writing gem5 config (ilp_exp.py)"
cat > "$WORK/ilp_exp.py" <<'PYEOF'
import argparse
import m5
from m5.objects import *
# gem5 v26: x86 CPUs are X86MinorCPU / X86O3CPU (exported by m5.objects)

p = argparse.ArgumentParser()
p.add_argument('--cpu', choices=['minor', 'o3'], default='minor')
p.add_argument('--width', type=int, default=4)
p.add_argument('--bp', choices=['local', 'bimode', 'tournament', 'ltage'], default='tournament')
p.add_argument('--bin', dest='binary', required=True)
p.add_argument('--bin2', default=None)
p.add_argument('--maxtick', type=int, default=0)
p.add_argument('--outdir', default='m5out')
args = p.parse_args()

system = System()
system.clk_domain = SrcClockDomain(clock='2GHz', voltage_domain=VoltageDomain())
system.mem_mode = 'timing'
system.mem_ranges = [AddrRange('2GB')]
system.membus = SystemXBar()

if args.cpu == 'minor':
    system.cpu = X86MinorCPU()
else:
    system.cpu = X86O3CPU()
    w = args.width
    system.cpu.fetchWidth = w
    system.cpu.decodeWidth = w
    system.cpu.renameWidth = w
    system.cpu.dispatchWidth = w
    system.cpu.issueWidth = w
    system.cpu.wbWidth = w
    system.cpu.commitWidth = w
    # gem5 v26: the direction predictor sits inside a BranchPredictor wrapper
    cond = {'local': LocalBP, 'bimode': BiModeBP, 'tournament': TournamentBP, 'ltage': LTAGE}[args.bp]()
    system.cpu.branchPred = BranchPredictor(conditionalBranchPred=cond)
    if args.bin2:
        system.multi_thread = True  # required for numThreads > 1 (base.cc assert)
        system.cpu.numThreads = 2

# Supported helper wires CPU icache/dcache ports to the L1 caches
system.cpu.addPrivateSplitL1Caches(
    Cache(size='32kB', assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16),
    Cache(size='32kB', assoc=8, tag_latency=1, data_latency=1,
          response_latency=1, mshrs=8, tgts_per_mshr=16))
# x86 page-table walker ports (needed once caches sit between CPU and bus)
system.cpu.mmu.connectWalkerPorts(system.membus.cpu_side_ports,
                                  system.membus.cpu_side_ports)
system.cpu.icache.mem_side = system.membus.cpu_side_ports
system.cpu.dcache.mem_side = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

system.workload = SEWorkload.init_compatible(args.binary)

proc1 = Process()
proc1.cmd = [args.binary]
proc1.pid = 100
if args.bin2:
    proc2 = Process()
    proc2.cmd = [args.bin2]
    proc2.pid = 101
    system.cpu.workload = [proc1, proc2]
else:
    system.cpu.workload = proc1
system.cpu.createThreads()
system.cpu.createInterruptController()

# x86 SE interrupt wiring
for i in range(system.cpu.numThreads):
    system.cpu.interrupts[i].pio = system.membus.mem_side_ports
    system.cpu.interrupts[i].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[i].int_responder = system.membus.mem_side_ports

root = Root(full_system=False, system=system)
m5.instantiate()
event = m5.simulate(args.maxtick) if args.maxtick else m5.simulate()
print('Exiting @ tick %i because %s' % (m5.curTick(), event.getCause()))
PYEOF

echo "==> Writing pilot workloads (tiny, bounded)"
cat > "$WORK/hello.c" <<'CEOF'
#include <stdio.h>
int main(void) { printf("Hello World! gem5 x86 smoke test OK\n"); return 0; }
CEOF
cat > "$WORK/int_work.c" <<'CEOF'
#include <stdio.h>
#define N 2000000L
int main(void) {
    unsigned long a = 1, c = 0;
    for (unsigned long i = 0; i < N; i++) { c += a * 3UL + i; a = (a * 1103515245UL + 12345UL) & 0x7fffffffUL; }
    printf("int pilot done: %lu\n", c);
    return 0;
}
CEOF

echo "==> Cross-compiling (static x86-64)"
x86_64-linux-gnu-gcc -static -O2 -o "$WORK/hello"    "$WORK/hello.c"    || { echo "FAIL: compile hello"; exit 1; }
x86_64-linux-gnu-gcc -static -O2 -o "$WORK/int_work" "$WORK/int_work.c" || { echo "FAIL: compile int_work"; exit 1; }
echo "    compile OK"

fail() { echo "PILOT FAIL at: $1 - paste the file $2"; exit 1; }
# print Hello lines from whichever of the given files exist (gem5 only writes simout with -r)
has_hello() { local f ok=1; for f in "$@"; do [ -f "$f" ] && grep -h "Hello World" "$f" && ok=0; done; return $ok; }

echo; echo "==> GATE 1: config smoke - hello under MinorCPU (caches, interrupts, walker ports)"
$GEM5 --outdir="$WORK/out_hello_minor" "$WORK/ilp_exp.py" --cpu minor --bin "$WORK/hello" \
  > "$WORK/out_hello_minor_console.log" 2>&1 || fail "gate1 gem5 run" "$WORK/out_hello_minor_console.log"
has_hello "$WORK/out_hello_minor/simout" "$WORK/out_hello_minor_console.log" \
  || fail "gate1 no hello output" "$WORK/out_hello_minor_console.log"
echo "    GATE 1 PASS: MinorCPU hello ran and printed"

echo; echo "==> GATE 2: O3CPU config path (width/branch-predictor params)"
$GEM5 --outdir="$WORK/out_hello_o3" "$WORK/ilp_exp.py" --cpu o3 --width 4 --bp tournament --bin "$WORK/hello" \
  > "$WORK/out_hello_o3_console.log" 2>&1 || fail "gate2 gem5 run" "$WORK/out_hello_o3_console.log"
has_hello "$WORK/out_hello_o3/simout" "$WORK/out_hello_o3_console.log" \
  || fail "gate2 no hello output" "$WORK/out_hello_o3_console.log"
echo "    GATE 2 PASS: O3CPU hello ran and printed"

echo; echo "==> GATE 3: SMT wiring - two threads on one O3 core (hello + hello)"
$GEM5 --outdir="$WORK/out_smt_hello" "$WORK/ilp_exp.py" --cpu o3 --width 4 --bp tournament \
  --bin "$WORK/hello" --bin2 "$WORK/hello" \
  > "$WORK/out_smt_hello_console.log" 2>&1 || fail "gate3 gem5 run" "$WORK/out_smt_hello_console.log"
n=$(cat "$WORK/out_smt_hello/simout" "$WORK/out_smt_hello_console.log" 2>/dev/null | grep -c "Hello World")
[ "${n:-0}" -ge 2 ] || fail "gate3 expected 2 hello outputs, got ${n:-0}" "$WORK/out_smt_hello_console.log"
echo "    GATE 3 PASS: SMT ran both threads to completion"

echo; echo "==> GATE 4: timing pilot - int_work (2M iterations) under O3, wall + simulated time"
start=$(date +%s)
$GEM5 --outdir="$WORK/out_int_o3" "$WORK/ilp_exp.py" --cpu o3 --width 4 --bp tournament --bin "$WORK/int_work" \
  > "$WORK/out_int_o3_console.log" 2>&1 || fail "gate4 gem5 run" "$WORK/out_int_o3_console.log"
end=$(date +%s)
echo "    wall time: $((end-start)) s"
grep -E '^(simSeconds|simTicks|simInsts|system.cpu.ipc|system.cpu.numCycles)' "$WORK/out_int_o3/stats.txt" | head -8
echo "    GATE 4 PASS"

echo; echo "==> GATE 5: trace format validation + fetch-to-commit latency (hello, 2M ticks)"
mkdir -p "$WORK/out_trace"
$GEM5 --debug-flags=MinorTrace,MinorExecute --debug-file="$WORK/out_trace/trace.txt" \
  --outdir="$WORK/out_trace" "$WORK/ilp_exp.py" --cpu minor --bin "$WORK/hello" --maxtick 2000000 \
  > "$WORK/out_trace_console.log" 2>&1 || fail "gate5 gem5 run" "$WORK/out_trace_console.log"
echo "    trace lines: $(wc -l < "$WORK/out_trace/trace.txt")"
echo "    sample commit lines (for format validation):"
grep -m3 "Committing inst" "$WORK/out_trace/trace.txt" \
  || fail "gate5 no commit records in trace - format differs" "$WORK/out_trace/trace.txt"
if python3 - "$WORK/out_trace/trace.txt" <<'LATEOF'
import re, sys, statistics
idpat   = re.compile(r'^(\d+):.*?\b(\d+/\d+\.\d+/\d+/\d+(?:\.\d+)?)\b')
commit  = re.compile(r'^\d+:.*Committing inst:')
discard = re.compile(r'^\d+:.*Discarding inst')
first, commit_tick, squashed = {}, {}, set()
with open(sys.argv[1]) as f:
    for line in f:
        m = idpat.match(line)
        if not m:
            continue
        tick, iid = int(m.group(1)), m.group(2)
        first.setdefault(iid, tick)
        if commit.match(line):
            commit_tick.setdefault(iid, tick)
        elif discard.match(line):
            squashed.add(iid)
lat = [(commit_tick[k]-first[k])/500.0 for k in commit_tick if k not in squashed]
if lat:
    print(f"    committed instructions measured: {len(lat)} (squashed excluded: {len(squashed)})")
    print(f"    avg fetch-to-commit latency: {statistics.mean(lat):.1f} cycles, min {min(lat):.0f}, max {max(lat):.0f}")
else:
    print("    no committed instructions found in trace window")
    sys.exit(1)
LATEOF
then
  echo "    GATE 5 PASS"
else
  fail "gate5 latency extraction" "$WORK/out_trace/trace.txt"
fi

echo; echo "==== PILOT COMPLETE - all 5 gates passed ===="
echo "Full log: tee this run into a4_pilot/pilot_run.log for the report."
