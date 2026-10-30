"""Honest Downgrade challenge demo (<2 min): the App Mode form -> free draft run -> the approved plumber Reel."""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "/Users/jefe/projects/honest-downgrade")
from honest_core import text_png, end_card
from PIL import Image

R = Path("/Users/jefe/projects/honest-downgrade"); W = R / "docs/demo/work"; W.mkdir(parents=True, exist_ok=True)
OUT = R / "docs/demo/honest-downgrade-demo.mp4"
PLUMBER = R / "docs/examples/plumber-v5-approved.mp4"
DRAFT = R / "docs/examples/taco-truck-draft-reel.mp4"
VW, VH = 1080, 1920


def card(name, lines, secs):
    end_card(W / f"{name}.png", VW, VH, lines, credit=False)
    return ("img", W / f"{name}.png", secs)


def shot(img, secs, title):
    """A UI screenshot fitted on a dark 9:16 canvas with a caption above it."""
    bg = Image.new("RGB", (VW, VH), (26, 22, 19)); im = Image.open(img).convert("RGB")
    s = min((VW - 80) / im.width, (VH - 520) / im.height); im = im.resize((int(im.width * s), int(im.height * s)))
    bg.paste(im, ((VW - im.width) // 2, 380)); t = W / f"t_{img.stem}.png"; text_png(t, title, 64, VW)
    cap = Image.open(t); bg.paste(cap, (0, 160), cap); p = W / f"s_{img.stem}.png"; bg.save(p)
    return ("img", p, secs)


parts = [
    card("intro", ["Honest Downgrade", "Brag. Admit the truth. Win them over.", "An open-source ComfyUI app"], 3.5),
    shot(R / "docs/img/app-mode-main.png", 5.0, "Type your true facts, press Run"),
    card("draft", ["Free draft", "made by the app, $0", "placeholder stills, real timing"], 2.5),
    ("vid", DRAFT, [(0, 14)]),
    card("real", ["The real thing", "a plumber Reel made with this workflow", "shock warps, sympathy beat, real owner, score"], 3.0),
    ("vid", PLUMBER, [(0, 46.6)]),
    card("end", ["Honest Downgrade", "github.com/jk-automations/honest-downgrade", "Apache-2.0 · AI-generated video"], 3.5),
]
ins, fc, labels, n = [], [], [], 0
norm = f"scale={VW}:{VH}:force_original_aspect_ratio=decrease,pad={VW}:{VH}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p"
for p in parts:
    if p[0] == "img":
        ins += ["-loop", "1", "-t", str(p[2]), "-i", str(p[1]), "-f", "lavfi", "-t", str(p[2]), "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append(f"[{n}:v]{norm},fade=t=in:d=0.3[v{len(labels)}];[{n + 1}:a]anull[a{len(labels)}]"); labels.append(len(labels)); n += 2
    else:
        for a, b in p[2]:
            ins += ["-ss", str(a), "-t", str(b - a), "-i", str(p[1])]
            fc.append(f"[{n}:v]{norm},fade=t=in:d=0.25[v{len(labels)}];[{n}:a]aresample=48000,afade=t=in:d=0.2,afade=t=out:st={b - a - 0.25:.2f}:d=0.25[a{len(labels)}]")
            labels.append(len(labels)); n += 1
fc.append("".join(f"[v{i}][a{i}]" for i in labels) + f"concat=n={len(labels)}:v=1:a=1[cv][ca];[ca]loudnorm=I=-14:TP=-1[aout]")
subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[cv]", "-map", "[aout]",
                "-c:v", "libx264", "-crf", "22", "-preset", "slow", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(OUT)], check=True)
print(OUT)
