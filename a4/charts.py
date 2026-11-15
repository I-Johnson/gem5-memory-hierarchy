#!/usr/bin/env python3
"""Charts for the report from results/results.csv -> results/*.png"""
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

res = sys.argv[1] if len(sys.argv) > 1 else "results"
rows = {r["name"]: r for r in csv.DictReader(open(os.path.join(res, "results.csv")))}


def g(name, key):
    r = rows.get(name)
    try:
        return float(r[key]) if r and r[key] != "" else 0.0
    except ValueError:
        return 0.0


plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})
BLUE, ORANGE, GREEN, RED, PURPLE = ("#2a6fdb", "#e8832a", "#2e9e5b",
                                    "#d64545", "#7b5cc4")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(res, name), dpi=160)
    plt.close(fig)


# 1. Issue width sweep (IPC)
wls = ["int_work", "fp_work", "mem_work", "branch_rand"]
fig, ax = plt.subplots(figsize=(7, 4))
for wl, c in zip(wls, [BLUE, ORANGE, GREEN, RED]):
    xs = ["Minor\n(in-order)", "O3 W=1", "O3 W=2", "O3 W=4", "O3 W=8"]
    ys = [g(f"minor_{wl}", "ipc")] + [g(f"o3w{w}_tournament_{wl}", "ipc")
                                     for w in (1, 2, 4, 8)]
    ax.plot(xs, ys, marker="o", label=wl, color=c)
ax.set_ylabel("IPC (instructions per cycle)")
ax.set_title("Throughput vs issue width")
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.3)
save(fig, "chart_issue_width_ipc.png")

# 2. Branch prediction: IPC and mispredict rate per predictor (width 4)
bps = ["none", "local", "bimode", "tournament", "ltage"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
wl3 = ["branch_rand", "branch_pat", "int_work"]
bw = 0.26
for i, (wl, c) in enumerate(zip(wl3, [RED, BLUE, GREEN])):
    xs = [j + (i - 1) * bw for j in range(len(bps))]
    a1.bar(xs, [g(f"o3w4_{bp}_{wl}", "ipc") for bp in bps], bw, label=wl, color=c)
    a2.bar(xs, [100 * g(f"o3w4_{bp}_{wl}", "mispredict_rate") for bp in bps], bw,
           label=wl, color=c)
for a, t, yl in ((a1, "IPC by branch predictor (O3, W=4)", "IPC"),
                 (a2, "Conditional mispredict rate", "% of conditional branches")):
    a.set_xticks(range(len(bps)))
    a.set_xticklabels(["none\n(static NT)" if b == "none" else b for b in bps])
    a.set_title(t)
    a.set_ylabel(yl)
    a.grid(axis="y", alpha=0.3)
a1.legend(frameon=False)
save(fig, "chart_branch_prediction.png")

# 3. Latency vs width
fig, ax = plt.subplots(figsize=(7, 4))
for wl, c in zip(wls, [BLUE, ORANGE, GREEN, RED]):
    xs = ["Minor", "W=1", "W=2", "W=4", "W=8"]
    ys = [g(f"minor_{wl}", "latency_mean_cycles")] + [
        g(f"o3w{w}_tournament_{wl}", "latency_mean_cycles") for w in (1, 2, 4, 8)]
    ax.plot(xs, ys, marker="o", label=wl, color=c)
ax.set_yscale("log")
ax.set_ylabel("Avg fetch-to-commit latency (cycles, log)")
ax.set_title("Instruction latency vs issue width")
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.3)
save(fig, "chart_latency.png")

# 4. SMT: alone vs together
pairs = [n for n in rows if n.startswith("smt_w4_")]
labels, alone_sum, smt = [], [], []
for n in sorted(pairs):
    a, b = n[len("smt_w4_"):].split("+")
    labels.append(f"{a.replace('_work','')}+{b.replace('_work','')}")
    ca, cb = g(f"o3w4_tournament_{a}", "cycles"), g(f"o3w4_tournament_{b}", "cycles")
    alone_sum.append((ca + cb) / 1e6)
    smt.append(g(n, "cycles") / 1e6)
fig, ax = plt.subplots(figsize=(8, 4))
x = range(len(labels))
ax.bar([i - 0.2 for i in x], alone_sum, 0.4, label="run back-to-back (1 thread)", color=BLUE)
ax.bar([i + 0.2 for i in x], smt, 0.4, label="run together (SMT, 2 threads)", color=ORANGE)
ax.set_xticks(list(x))
ax.set_xticklabels(labels, rotation=15)
ax.set_ylabel("Million cycles to finish both")
ax.set_title("SMT on one width-4 O3 core")
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.3)
save(fig, "chart_smt.png")
print("charts written to", res)
