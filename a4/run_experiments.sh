#!/bin/bash
# MSCS-531 Assignment 4 Part 2 - full experiment sweep.
# Run inside the gem5 v26 container (repo mounted at /gem5):
#   bash /gem5/a4/run_experiments.sh            # all experiments
#   JOBS=4 bash /gem5/a4/run_experiments.sh     # fewer parallel runs
# Each run writes runs/<name>/{stats.txt,config.ini,console.log,latency.json}.
# Latency: a second pass traces a 20k-cycle window from the middle of each
# run, parses it into latency.json and deletes the trace (tens of MB).
set -uo pipefail

A4=/gem5/a4
GEM5=${GEM5:-/gem5/build/X86/gem5.opt}
JOBS=${JOBS:-8}
RUNS=$A4/runs
mkdir -p "$RUNS"
cd "$A4"

echo "==> Building benchmarks (static x86-64, -O2)"
for p in hello int_work fp_work mem_work branch_rand branch_pat; do
  x86_64-linux-gnu-gcc -static -O2 -o bench/$p bench/$p.c || { echo "FAIL compile $p"; exit 1; }
done

# name | cpu | width | bp | bin | bin2 | trace-start-tick
JOBLIST=$A4/jobs.txt
: > "$JOBLIST"
add() { echo "$1|$2|$3|$4|$5|${6:--}|${7:-100000000}" >> "$JOBLIST"; }

# A. Basic pipeline: in-order MinorCPU (single issue, no branch prediction on x86)
add minor_hello minor 1 tournament hello - 20000000
for w in int_work fp_work mem_work branch_rand branch_pat; do add minor_$w minor 1 tournament $w; done

# B. Branch prediction: same workloads, static not-taken vs dynamic predictors
for bp in none local bimode tournament ltage; do
  for w in branch_rand branch_pat int_work; do add o3w4_${bp}_$w o3 4 $bp $w; done
done
for bp in none tournament; do
  for w in branch_rand branch_pat; do add o3w1_${bp}_$w o3 1 $bp $w; done
done

# C. Multiple issue: issue width sweep across instruction mixes
for width in 1 2 4 8; do
  for w in int_work fp_work mem_work branch_rand; do
    n=o3w${width}_tournament_$w
    grep -q "^$n|" "$JOBLIST" || add $n o3 $width tournament $w
  done
done

# D. SMT: two threads sharing one width-4 (and width-8) O3 core
for pair in int_work+fp_work int_work+mem_work fp_work+fp_work int_work+int_work \
            mem_work+mem_work branch_rand+int_work; do
  a=${pair%+*}; b=${pair#*+}
  add smt_w4_${a}+${b} o3 4 tournament $a $b
done
for pair in int_work+fp_work int_work+int_work; do
  a=${pair%+*}; b=${pair#*+}
  add smt_w8_${a}+${b} o3 8 tournament $a $b
done

run_one() {
  IFS='|' read -r name cpu width bp bin bin2 tstart <<< "$1"
  out=$RUNS/$name
  if [ -s "$out/stats.txt" ] && grep -q "simInsts" "$out/stats.txt"; then
    echo "skip $name (done)"; return 0
  fi
  rm -rf "$out"; mkdir -p "$out"
  extra=(); [ "$bin2" != "-" ] && extra=(--bin2 "$A4/bench/$bin2")
  start=$(date +%s)
  $GEM5 --outdir="$out" "$A4/ilp_exp.py" --cpu $cpu --width $width --bp $bp \
        --bin "$A4/bench/$bin" "${extra[@]}" > "$out/console.log" 2>&1
  rc=$?
  echo "wall_seconds=$(( $(date +%s) - start ))" >> "$out/console.log"
  rm -f "$out"/config.dot*
  if [ $rc -ne 0 ]; then echo "FAIL $name (rc=$rc) - see $out/console.log"; return 1; fi
  echo "done $name ($(( $(date +%s) - start ))s)"
}

# Latency: re-simulate each run up to its midpoint, then trace a
# 20,000-cycle window (10M ticks) inside the program's main loop
# (an early fixed window lands in identical libc start-up code).
lat_one() {
  IFS='|' read -r name cpu width bp bin bin2 tstart <<< "$1"
  out=$RUNS/$name
  [ -s "$out/stats.txt" ] || return 0
  grep -q '"window_start_tick"' "$out/latency.json" 2>/dev/null && { echo "skip lat $name"; return 0; }
  total=$(awk '$1=="simTicks"{print $2; exit}' "$out/stats.txt")
  mid=$(( (total / 2) / 500 * 500 ))
  [ "$name" = minor_hello ] || [ $mid -gt 0 ] || return 0
  if [ "$cpu" = o3 ]; then flags=O3PipeView; kind=o3; else flags=MinorTrace,MinorExecute; kind=minor; fi
  extra=(); [ "$bin2" != "-" ] && extra=(--bin2 "$A4/bench/$bin2")
  tmp=$out/lat_tmp; rm -rf "$tmp"; mkdir -p "$tmp"
  $GEM5 --outdir="$tmp" --debug-flags=$flags --debug-start=$mid --debug-file=trace.txt \
        "$A4/ilp_exp.py" --cpu $cpu --width $width --bp $bp --bin "$A4/bench/$bin" \
        "${extra[@]}" --maxtick $(( mid + 10000000 )) > "$tmp/console.log" 2>&1 \
    || { echo "FAIL lat $name"; return 1; }
  python3 "$A4/latency.py" $kind "$tmp/trace.txt" --json "$out/latency.json" \
      --window $mid $(( mid + 10000000 )) > /dev/null || echo "WARN lat parse $name"
  rm -rf "$tmp"
  echo "lat $name (window @ tick $mid)"
}
export -f run_one lat_one
export A4 GEM5 RUNS

n=$(wc -l < "$JOBLIST")
echo "==> Running $n gem5 jobs, $JOBS at a time"
xargs -P "$JOBS" -I{} bash -c 'run_one "$@"' _ {} < "$JOBLIST"

echo "==> Measuring latency (mid-run 20k-cycle trace windows)"
xargs -P "$JOBS" -I{} bash -c 'lat_one "$@"' _ {} < "$JOBLIST"

echo "==> Collecting results"
python3 "$A4/collect.py" "$RUNS" "$A4/results"

echo "==> Pipeline visualization (gem5 util/o3-pipeview.py + MinorTrace)"
VIZ=$A4/results/pipeview
mkdir -p "$VIZ"
mid_of() { awk '$1=="simTicks"{print int($2/2/500)*500; exit}' "$RUNS/$1/stats.txt"; }
viz_o3() {  # name width bp bin  (200 cycles from the middle of that run)
  m=$(mid_of $1)
  $GEM5 --outdir="$VIZ/$1" --debug-flags=O3PipeView --debug-start=$m \
        --debug-file=trace.txt "$A4/ilp_exp.py" --cpu o3 --width $2 --bp $3 \
        --bin "$A4/bench/$4" --maxtick $(( m + 100000 )) > "$VIZ/$1.console.log" 2>&1
  # -c 500 = ticks per cycle at 2 GHz
  python3 /gem5/util/o3-pipeview.py -c 500 -w 100 -o "$VIZ/$1.txt" "$VIZ/$1/trace.txt"
  python3 /gem5/util/o3-pipeview.py -c 500 -w 100 --color -o "$VIZ/$1.color.txt" "$VIZ/$1/trace.txt"
  rm -rf "$VIZ/$1"
}
viz_o3 o3w4_tournament_int_work 4 tournament int_work
viz_o3 o3w4_none_branch_rand    4 none       branch_rand
viz_o3 o3w1_tournament_int_work 1 tournament int_work
# MinorCPU: cycle-by-cycle stage contents (Fetch1/Fetch2/Decode/Execute), 50 cycles
m=$(mid_of minor_int_work)
$GEM5 --outdir="$VIZ/minor" --debug-flags=MinorTrace,MinorExecute --debug-start=$m \
      --debug-file=trace.txt "$A4/ilp_exp.py" --cpu minor --bin "$A4/bench/int_work" \
      --maxtick $(( m + 25000 )) > "$VIZ/minor_int_work.console.log" 2>&1
grep -v "^\s*$" "$VIZ/minor/trace.txt" > "$VIZ/minor_int_work_50cycles.txt"
rm -rf "$VIZ/minor"

echo "==> Charts"
python3 -c "import matplotlib" 2>/dev/null || pip install -q --break-system-packages matplotlib \
  || apt-get install -y -qq python3-matplotlib
python3 "$A4/charts.py" "$A4/results" || echo "WARN charts failed"
echo "==== SWEEP COMPLETE ===="
