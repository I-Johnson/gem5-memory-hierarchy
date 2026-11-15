#!/usr/bin/env python3
"""Per-instruction latency from a gem5 debug trace window.

Usage: latency.py o3|minor TRACE [--json OUT]

o3    : trace made with --debug-flags=O3PipeView. For every instruction
        that retired inside the window, latency = retire - fetch, plus the
        average time spent between consecutive stages
        (fetch, decode, rename, dispatch, issue, complete, retire).
minor : trace made with --debug-flags=MinorTrace,MinorExecute. MinorCPU ids
        look like T/S.P/L/F.E (thread/stream.prediction/line/fetch.exec).
        For each committed instruction:
          fetch_to_commit  = commit tick - first tick its fetch line (T/S.P/L)
                             appears (Fetch1 line request)
          fetch2_to_commit = commit tick - first tick the instruction itself
                             (T/S.P/L/F) appears (Fetch2 decomposition)
        Squashed (Discarding inst) instructions are excluded.

Clock is 2 GHz -> 500 ticks per cycle.
"""
import json
import re
import statistics
import sys

TICKS_PER_CYCLE = 500
O3_STAGES = ["fetch", "decode", "rename", "dispatch", "issue", "complete",
             "retire"]


def summarize(vals):
    if not vals:
        return None
    vals = sorted(vals)
    return {
        "n": len(vals),
        "mean": round(statistics.mean(vals), 2),
        "median": vals[len(vals) // 2],
        "p90": vals[int(len(vals) * 0.9)],
        "min": vals[0],
        "max": vals[-1],
    }


def o3(path):
    insts, cur = [], {}
    squashed = 0
    with open(path, errors="replace") as f:
        for line in f:
            if not line.startswith("O3PipeView:"):
                continue
            parts = line.rstrip("\n").split(":")
            stage = parts[1]
            if stage == "fetch":
                cur = {"fetch": int(parts[2])}
            elif stage == "retire":
                cur["retire"] = int(parts[2])
                if cur.get("retire", 0) and "fetch" in cur:
                    insts.append(cur)
                else:
                    squashed += 1
                cur = {}
            elif cur:
                cur[stage] = int(parts[2])
    lat = [(i["retire"] - i["fetch"]) / TICKS_PER_CYCLE for i in insts]
    stage_avg = {}
    for a, b in zip(O3_STAGES, O3_STAGES[1:]):
        d = [(i[b] - i[a]) / TICKS_PER_CYCLE for i in insts
             if i.get(a) and i.get(b)]
        if d:
            stage_avg[f"{a}->{b}"] = round(statistics.mean(d), 2)
    return {"fetch_to_retire": summarize(lat), "stage_avg_cycles": stage_avg,
            "squashed_in_window": squashed}


ID = re.compile(r"\b(\d+/\d+\.\d+/\d+)(?:/(\d+)(?:\.\d+)?)?\b")
TICK = re.compile(r"^\s*(\d+):")


def minor(path):
    line_first, inst_first, commit = {}, {}, {}
    discarded = set()
    with open(path, errors="replace") as f:
        for line in f:
            m = TICK.match(line)
            if not m:
                continue
            tick = int(m.group(1))
            is_commit = "Committing inst" in line
            is_discard = "Discarding inst" in line
            for lid, fseq in ID.findall(line):
                line_first.setdefault(lid, tick)
                if fseq:
                    key = f"{lid}/{fseq}"
                    inst_first.setdefault(key, tick)
                    if is_commit:
                        commit.setdefault(key, (tick, lid))
                    elif is_discard:
                        discarded.add(key)
    f2c, f1c = [], []
    for key, (tick, lid) in commit.items():
        if key in discarded:
            continue
        f2c.append((tick - inst_first[key]) / TICKS_PER_CYCLE)
        f1c.append((tick - line_first[lid]) / TICKS_PER_CYCLE)
    return {"fetch_to_commit": summarize(f1c),
            "fetch2_to_commit": summarize(f2c),
            "squashed_in_window": len(discarded)}


if __name__ == "__main__":
    kind, path = sys.argv[1], sys.argv[2]
    res = o3(path) if kind == "o3" else minor(path)
    if "--window" in sys.argv:
        i = sys.argv.index("--window")
        res["window_start_tick"] = int(sys.argv[i + 1])
        res["window_end_tick"] = int(sys.argv[i + 2])
    out = json.dumps(res, indent=1)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fo:
            fo.write(out + "\n")
    print(out)
