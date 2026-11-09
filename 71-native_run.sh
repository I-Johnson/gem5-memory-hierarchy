#!/bin/bash
# native_run.sh - runs INSIDE the already-pulled gem5 Docker image (no pull).
# Native (not gem5) page-size / page-fault experiment for A3.
# Writes a3/native/native_vm_results.txt on the Mac via the existing mount.
# set -euo pipefail: any failure (compile, benchmark, madvise abort) makes the
# whole script exit non-zero BEFORE printing the "Saved" line - a "Saved"
# message means the results file is complete.
set -euo pipefail
DIR=/gem5/a3/native
OUT="$DIR/native_vm_results.txt"
mkdir -p "$DIR"

fail() { echo ""; echo "FAILED: $1"; echo "Send the full terminal output back."; exit 1; }

{
echo "== environment =="
uname -a
uname -m
echo "getconf PAGESIZE: $(getconf PAGESIZE)"
echo "THP enabled: $(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo THP_NODE_MISSING)"
echo "THP hpage_pmd_size: $(cat /sys/kernel/mm/transparent_hugepage/hpage_pmd_size 2>/dev/null || echo HPAGE_SIZE_MISSING)"

echo "== compiling benchmark (native) =="
cc -O2 -Wall -o "$DIR/tlb_fs" "$DIR/tlb_fs.c" || fail "compile tlb_fs.c"

echo "== RUN A: base pages (MADV_NOHUGEPAGE) =="
"$DIR/tlb_fs" 256 4 0 || fail "run A (base pages)"
echo ""
echo "== RUN B: huge pages requested (MADV_HUGEPAGE) =="
"$DIR/tlb_fs" 256 4 1 || fail "run B (huge pages)"
echo ""
echo "== DONE =="
} 2>&1 | tee "$OUT"

grep -q "== DONE ==" "$OUT" || fail "results file incomplete - do not use partial output"
echo "Saved to a3/native/native_vm_results.txt"
