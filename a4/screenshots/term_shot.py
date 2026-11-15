#!/usr/bin/env python3
"""Run real commands and render their output as terminal-window PNGs.

Usage (inside the gem5 container): term_shot.py SPEC.json OUTDIR
SPEC = [{"file": "A04_hello.png", "title": "...", "steps": [{"cmd": "...",
         "max": 40, "host_output": "<optional pre-captured text>"}]}]
Each step's command runs in bash from /gem5/a4 and its real stdout+stderr
(ANSI colours kept) is drawn under a prompt line, like a terminal window.
"""
import json
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
CAP_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
CAP_I = "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"
CAP_SIZE, CAP_LH = 24, 32
SIZE, LH, PAD, BAR = 15, 20, 18, 34
MAXCOL = 112   # wrap width: keeps text >= 7pt when the image spans a page
MAXLINES = 47  # taller captures are split into parts so none breaks across a page
BG, FG = (30, 30, 30), (220, 220, 220)
PROMPT_USER, PROMPT_PATH = (110, 200, 110), (110, 160, 240)
ANSI = {30: (60, 60, 60), 31: (230, 90, 90), 32: (110, 200, 110),
        33: (225, 200, 90), 34: (100, 150, 240), 35: (200, 120, 220),
        36: (90, 200, 210), 37: (220, 220, 220)}
for k in range(8):
    ANSI[90 + k] = tuple(min(255, c + 30) for c in ANSI[30 + k])
SGR = re.compile(r"\x1b\[([0-9;]*)m")
OTHER_ESC = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]")


def segments(line):
    """Split a line into (text, colour, bold) runs following SGR codes."""
    out, col, bold, pos = [], FG, False, 0
    for m in SGR.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], col, bold))
        for c in (m.group(1) or "0").split(";"):
            c = int(c or 0)
            if c == 0:
                col, bold = FG, False
            elif c == 1:
                bold = True
            elif c in ANSI:
                col = ANSI[c]
        pos = m.end()
    out.append((line[pos:], col, bold))
    return out


def visible_len(line):
    return len(SGR.sub("", line))


def wrap(segs):
    """Soft-wrap a list of (text, colour, bold) runs at MAXCOL columns.
    Continuation lines are indented 2 spaces; no characters are dropped."""
    out, cur, n = [], [], 0
    for text, col, bold in segs:
        while text:
            room = MAXCOL - n
            take, text = text[:room], text[room:]
            cur.append((take, col, bold))
            n += len(take)
            if n >= MAXCOL and text:
                out.append(cur)
                cur, n = [("  ", FG, False)], 2
    out.append(cur)
    return out


def run(cmd):
    p = subprocess.run(["bash", "-lc", cmd], cwd="/gem5/a4",
                       capture_output=True, text=True, errors="replace")
    return (p.stdout + p.stderr).rstrip("\n")


def build_lines(shot):
    lines = []  # each: list of (text, colour, bold)
    for st in shot["steps"]:
        prompt = st.get("prompt", "root@9c69c3bde160:/gem5/a4#")
        user, _, path = prompt.partition(":")
        lines += wrap([(user, PROMPT_USER, True), (":" + path, PROMPT_PATH, True),
                       (" " + st["cmd"], FG, False)])
        text = st["host_output"] if "host_output" in st else run(st["cmd"])
        text = OTHER_ESC.sub("", text.replace("\t", "    "))
        body = text.split("\n") if text else []
        mx = st.get("max", 40)
        if len(body) > mx:
            more = len(body) - mx
            body = body[:mx] + [f"\x1b[90m... ({more} more lines)\x1b[0m"]
        for b in body:
            lines += wrap(segments(b))
    return lines


def caption_band(width, label, title):
    """APA-style figure label (bold) and title (italic) above the image, on
    white, so the label can never land on a different page from its figure."""
    fb, fi = ImageFont.truetype(CAP_B, CAP_SIZE), ImageFont.truetype(CAP_I, CAP_SIZE)
    rows = [(label, fb)]
    words, cur = (title or "").split(), ""
    for w in words:
        t = (cur + " " + w).strip()
        if fi.getlength(t) > width and cur:
            rows.append((cur, fi)); cur = w
        else:
            cur = t
    if cur:
        rows.append((cur, fi))
    band = Image.new("RGB", (width, len(rows) * CAP_LH + 14), "white")
    d = ImageDraw.Draw(band)
    for i, (t, font) in enumerate(rows):
        d.text((0, i * CAP_LH), t, font=font, fill=(20, 20, 20))
    return band


def draw(lines, title, path, label=None, caption=None):
    f, fb = ImageFont.truetype(FONT, SIZE), ImageFont.truetype(FONT_B, SIZE)
    cw = f.getlength("M")
    width = int(MAXCOL * cw) + 2 * PAD          # same width for every capture
    height = BAR + PAD + len(lines) * LH + PAD
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, BAR], fill=(52, 52, 56))
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse([14 + i * 22, 11, 26 + i * 22, 23], fill=c)
    d.text(((width - f.getlength(title)) / 2, 8), title, font=f, fill=(190, 190, 190))
    y = BAR + PAD
    for l in lines:
        x = PAD
        for text, col, bold in l:
            if text:
                d.text((x, y), text, font=fb if bold else f, fill=col)
                x += len(text) * cw
        y += LH
    if label:
        band = caption_band(width, label, caption)
        full = Image.new("RGB", (width, band.height + img.height), "white")
        full.paste(band, (0, 0)); full.paste(img, (0, band.height))
        img = full
    img.save(path)


def render(shot, outdir):
    """Write one PNG, or name_p1.png, name_p2.png ... when taller than MAXLINES."""
    lines = build_lines(shot)
    title = shot.get("title", "root@9c69c3bde160: /gem5/a4 - gem5 v26 container")
    parts = [lines[i:i + MAXLINES] for i in range(0, len(lines), MAXLINES)]
    stem = shot["file"][:-4]
    names = []
    for k, part in enumerate(parts, 1):
        name = shot["file"] if len(parts) == 1 else f"{stem}_p{k}.png"
        t = title if len(parts) == 1 else f"{title} ({k}/{len(parts)})"
        label = shot.get("label")
        if label and k > 1:
            label = f"{label} (continued)"
        draw(part, t, f"{outdir}/{name}", label, shot.get("caption") if k == 1 else None)
        names.append(name)
    return names


if __name__ == "__main__":
    spec, outdir = json.load(open(sys.argv[1])), sys.argv[2]
    for shot in spec:
        print("wrote", ", ".join(render(shot, outdir)))
