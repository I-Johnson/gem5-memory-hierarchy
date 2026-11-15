#!/usr/bin/env python3
"""Add an APA-style label (bold) and title (italic) above each report chart,
so the label stays on the same page as the chart in exported PDFs.
Usage: caption_charts.py RESULTS_DIR OUT_DIR"""
import sys

from PIL import Image, ImageDraw, ImageFont

B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
I = "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"
CHARTS = [
    ("chart_branch_prediction.png", "Figure 1",
     "Throughput and Conditional Mispredict Rate by Branch Predictor (O3, Width 4)"),
    ("chart_issue_width_ipc.png", "Figure 2",
     "Throughput (IPC) vs. Issue Width for Four Workloads"),
    ("chart_latency.png", "Figure 3",
     "Average Fetch-to-Commit Latency vs. Issue Width (Log Scale)"),
    ("chart_smt.png", "Figure 4",
     "Cycles to Finish Both Programs: Back to Back vs. SMT (O3, Width 4)"),
]

src, out = sys.argv[1], sys.argv[2]
for name, label, title in CHARTS:
    img = Image.open(f"{src}/{name}").convert("RGB")
    w = img.width
    size = round(w * 0.023)          # ~11 pt when the chart spans the page
    fb, fi = ImageFont.truetype(B, size), ImageFont.truetype(I, size)
    rows, cur = [(label, fb)], ""
    for word in title.split():
        t = (cur + " " + word).strip()
        if fi.getlength(t) > w and cur:
            rows.append((cur, fi)); cur = word
        else:
            cur = t
    rows.append((cur, fi))
    lh = round(size * 1.35)
    full = Image.new("RGB", (w, len(rows) * lh + size // 2 + img.height), "white")
    d = ImageDraw.Draw(full)
    for k, (t, f) in enumerate(rows):
        d.text((0, k * lh), t, font=f, fill=(20, 20, 20))
    full.paste(img, (0, len(rows) * lh + size // 2))
    full.save(f"{out}/{name.replace('.png', '_captioned.png')}")
    print("wrote", name)
