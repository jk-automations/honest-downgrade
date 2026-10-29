"""Build the one-graph Honest Downgrade app (ComfyUI API format).

python3 tools/build_app.py                        # -> workflows/honest-downgrade-api.json (partner nodes: Gemini, Nano Banana 2, Veo 3.1)
python3 tools/build_app.py --draft                # -> workflows/honest-downgrade-draft-api.json (free: your 5 stills + local draft warps)
--stills a.png,b.png,...  (draft) the 5 rung stills in ComfyUI/input (default honest_rung_1.png ... honest_rung_5.png)
--ending photo.png        the real ending photo in ComfyUI/input (default: the blank placeholder = no ending)"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import honest_core as core  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--draft", action="store_true")
ap.add_argument("--out")
ap.add_argument("--preset", default="taco-truck")
ap.add_argument("--stills", default=",".join(f"honest_rung_{k}.png" for k in range(1, 6)))
ap.add_argument("--ending", default="honest_blank.png")
ap.add_argument("--writer-model", default="Gemini 3.5 Flash")
a = ap.parse_args()
out = Path(a.out or ROOT / "workflows" / ("honest-downgrade-draft-api.json" if a.draft else "honest-downgrade-api.json"))

g = {}
nid = iter(range(1, 1000))
def node(cls, title=None, **inputs):
    i = str(next(nid)); g[i] = {"class_type": cls, "inputs": inputs}
    if title: g[i]["_meta"] = {"title": title}
    return i
def o(i, k=0): return [i, k]

p = core.load_preset(a.preset)
fam = next(f"{k} ({v['label']})" for k, v in core.FAMILIES.items() if k == p["family"])
# ---------- user inputs ----------
brief = node("HonestBrief", "Your facts", business_name=p["business_name"], family=fam, true_setup=p["true_setup"],
             honest_line=p["honest_line"], real_proof=p["real_proof"], hero_thing=p["hero_thing"], tone=p["tone"], joke="joke 1",
             already_used_warps="", video_model="veo-3.1-lite", writer="template (offline, free)")
ending = node("LoadImage", "Real ending photo", image=a.ending)
# ---------- 1. the ladder (Gemini only runs when picked: the Ladder node asks for its reply lazily) ----------
if a.draft:
    ladder = node("HonestLadder", "Ladder", brief=o(brief, 0))
else:
    wi = {"model.prompt": o(brief, 1), "model.thinking_level": "LOW", "model.max_output_tokens": 8192, "model.seed": 42,
          "model.system_prompt": ""}
    if a.writer_model == "Gemini 3.8 Flash":
        wi["model.video_processing"] = "static"
    writer = node("GeminiNodeV3", "Joke writer (Gemini)", model=a.writer_model, **wi)
    ladder = node("HonestLadder", "Ladder", brief=o(brief, 0), writer_reply=o(writer, 0))
node("PreviewAny", "Your ladder", source=o(ladder, 1))
# ---------- 2. one keyframe still per rung ----------
stills = []
names = a.stills.split(",")
for k in range(1, 6):
    rung = node("HonestRung", f"Rung {k}", ladder=o(ladder), rung=k)
    if a.draft:
        stills.append(node("LoadImage", f"Still {k}", image=names[k - 1]))
    else:
        stills.append(node("GeminiNanoBanana2V2", f"Keyframe {k}", prompt=o(rung, 0), seed=100 + k, response_modalities="IMAGE",
                           model="Nano Banana 2 (Gemini 3.1 Flash Image)",
                           **{"model.aspect_ratio": "9:16", "model.resolution": "1K", "model.thinking_level": "MINIMAL"}))
board = node("HonestBoard", "Board + sign check", ladder=o(ladder), **{f"rung_{k}": o(s) for k, s in enumerate(stills, 1)})
node("PreviewImage", "Board", images=o(board, 0))
node("PreviewAny", "Sign check", source=o(board, 1))
# ---------- 3. one wild-card warp between each pair of rungs (first frame -> last frame) ----------
warps = []
for k in range(1, 5):
    w = node("HonestWarp", f"Warp {k}", ladder=o(ladder), step=k)
    if a.draft:
        v = node("HonestDraftWarp", f"Draft warp {k}", first_frame=o(stills[k - 1]), last_frame=o(stills[k]), ladder=o(ladder),
                 step=k, seconds=core.WARP_SECONDS)
    else:
        v = node("Veo3FirstLastFrameNode", f"Video warp {k}", prompt=o(w, 0),
                 negative_prompt="people, faces, hands, crowd, captions, subtitles, new text, logos, handheld shake, cuts",
                 resolution="720p", aspect_ratio="9:16", duration=core.WARP_SECONDS, seed=200 + k,
                 first_frame=o(stills[k - 1]), last_frame=o(stills[k]), model=o(brief, 2), generate_audio=False)
    node("SaveVideo", f"Save warp {k}", video=o(v), filename_prefix=f"honest/warps/warp_{k}", format="mp4", **{"format.codec": "auto"})
    warps.append(v)
# ---------- 4. the edit ----------
asm = node("HonestAssemble", "Assemble", ladder=o(ladder), captions=True, ai_label=True, credit=True, music_path="",
           ending_photo=o(ending), **{f"warp_{k}": o(v) for k, v in enumerate(warps, 1)})
node("SaveVideo", "Your Reel (30 s)", video=o(asm, 0), filename_prefix="honest/reel_30s", format="mp4", **{"format.codec": "auto"})
node("SaveVideo", "Cutdown (15 s)", video=o(asm, 1), filename_prefix="honest/cutdown_15s", format="mp4", **{"format.codec": "auto"})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(g, indent=1) + "\n")
print(f"{len(g)} nodes -> {out}")
