"""Build the one-graph Honest Downgrade app (ComfyUI API format).

python3 tools/build_app.py                        # -> workflows/honest-downgrade-api.json (partner nodes: Gemini, Nano Banana 2, Veo 3.1, Sonilo)
python3 tools/build_app.py --draft                # -> workflows/honest-downgrade-draft-api.json (free: your 8 stills + local draft clips)
--stills a.png,b.png,...  (draft) the 8 rung stills in ComfyUI/input (default honest_rung_1.png ... honest_rung_8.png)
--owner photo.png         the owner's real photo in ComfyUI/input (default: the blank placeholder = no photo)"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import honest_core as core  # noqa: E402

NEGATIVE = ("people, faces, hands, crowd, captions, subtitles, new text, scrambled sign lettering, logos, handheld shake, cuts")


def build(draft=False, preset=core.DEFAULT_PRESET, stills=None, owner="honest_blank.png", writer_model="Gemini 3.5 Flash",
          brief=None, video_model="veo-3.1-lite", owner_consent=False, keyframe_resolution="1K"):
    """The app graph as a dict. brief: optional overrides for the 'Your facts' node (any HonestBrief input)."""
    g = {}
    nid = iter(range(1, 1000))

    def node(cls, title=None, **inputs):
        i = str(next(nid)); g[i] = {"class_type": cls, "inputs": inputs}
        if title:
            g[i]["_meta"] = {"title": title}
        return i

    def o(i, k=0):
        return [i, k]

    p = core.load_preset(preset)
    btype = core.BUSINESS_TYPES[core.business_type_key(p["business_type"])]["label"]
    facts = dict(business_name=p["business_name"], business_type=btype, offer=p.get("offer", ""), setting=p.get("setting", ""),
                 audience=p.get("audience", ""), true_setup=p["true_setup"], honest_line=p["honest_line"], real_proof=p["real_proof"],
                 hero_thing=p["hero_thing"], tone=p["tone"], joke="joke 1", already_used_warps="", video_model=video_model,
                 writer="template (offline, free)")
    facts.update(brief or {})
    # ---------- user inputs (defaults = the preset; the sample is the taco truck, any business type works) ----------
    b = node("HonestBrief", "Your facts", **facts)
    owner_img = node("LoadImage", "Owner photo (real)", image=owner)
    # ---------- 1. the ladder (Gemini only runs when picked: the Ladder node asks for its reply lazily) ----------
    if draft:
        ladder = node("HonestLadder", "Ladder", brief=o(b, 0))
    else:
        wi = {"model.prompt": o(b, 1), "model.thinking_level": "LOW", "model.max_output_tokens": 8192, "model.seed": 42,
              "model.system_prompt": ""}
        if writer_model == "Gemini 3.8 Flash":
            wi["model.video_processing"] = "static"
        writer = node("GeminiNodeV3", "Joke writer (Gemini)", model=writer_model, **wi)
        ladder = node("HonestLadder", "Ladder", brief=o(b, 0), writer_reply=o(writer, 0))
    node("PreviewAny", "Your ladder", source=o(ladder, 1))
    # ---------- 2. one keyframe still per rung (8) ----------
    keys = []
    names = stills or [f"honest_rung_{k}.png" for k in range(1, core.N_RUNGS + 1)]
    for k in range(1, core.N_RUNGS + 1):
        rung = node("HonestRung", f"Rung {k}", ladder=o(ladder), rung=k)
        if draft:
            keys.append(node("LoadImage", f"Still {k}", image=names[k - 1]))
        else:
            keys.append(node("GeminiNanoBanana2V2", f"Keyframe {k}", prompt=o(rung, 0), seed=100 + k, response_modalities="IMAGE",
                             model="Nano Banana 2 (Gemini 3.1 Flash Image)",
                             **{"model.aspect_ratio": "9:16", "model.resolution": keyframe_resolution, "model.thinking_level": "MINIMAL"}))
    board = node("HonestBoard", "Board + sign check", ladder=o(ladder), **{f"rung_{k}": o(s) for k, s in enumerate(keys, 1)})
    node("PreviewImage", "Board", images=o(board, 0))
    node("PreviewAny", "Sign check", source=o(board, 1))
    # ---------- 3. seven moving clips: every rung moves (warps, the quiet sympathy moves, the payoff macro) ----------
    clips = []
    for k, (a, z, kind, secs) in enumerate(core.SHOTS, 1):
        w = node("HonestWarp", f"Clip {k} prompt", ladder=o(ladder), step=k)
        if draft:
            v = node("HonestDraftWarp", f"Draft clip {k}", first_frame=o(keys[a]), last_frame=o(keys[z]), ladder=o(ladder),
                     step=k, seconds=secs)
        else:
            v = node("Veo3FirstLastFrameNode", f"Video clip {k} ({kind})", prompt=o(w, 0), negative_prompt=NEGATIVE,
                     resolution="720p", aspect_ratio="9:16", duration=secs, seed=200 + k,
                     first_frame=o(keys[a]), last_frame=o(keys[z]), model=o(b, 2), generate_audio=False)
        node("SaveVideo", f"Save clip {k}", video=o(v), filename_prefix=f"honest/clips/clip_{k}", format="mp4", **{"format.codec": "auto"})
        clips.append(v)
    # ---------- 4. the edit: picture, then music ----------
    asm = node("HonestAssemble", "Assemble", ladder=o(ladder), captions=True, ai_label=True, credit=True, owner_consent=owner_consent,
               owner_photo=o(owner_img), **{f"clip_{k}": o(v) for k, v in enumerate(clips, 1)})
    if draft:
        fin = node("HonestFinish", "Music + finish", plan=o(asm, 1), music_path="")
    else:
        score = node("SoniloVideoToMusic", "Score (Sonilo)", video=o(asm, 0), prompt=o(asm, 2), seed=7)
        fin = node("HonestFinish", "Music + finish", plan=o(asm, 1), music_path="", score=o(score, 0))
    node("SaveVideo", "Your Reel", video=o(fin, 0), filename_prefix="honest/reel", format="mp4", **{"format.codec": "auto"})
    node("SaveVideo", "Cutdown (15 s)", video=o(fin, 1), filename_prefix="honest/cutdown_15s", format="mp4", **{"format.codec": "auto"})
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--preset", default=core.DEFAULT_PRESET)
    ap.add_argument("--stills", default=",".join(f"honest_rung_{k}.png" for k in range(1, core.N_RUNGS + 1)))
    ap.add_argument("--owner", default="honest_blank.png")
    ap.add_argument("--writer-model", default="Gemini 3.5 Flash")
    a = ap.parse_args()
    out = Path(a.out or ROOT / "workflows" / ("honest-downgrade-draft-api.json" if a.draft else "honest-downgrade-api.json"))
    g = build(a.draft, a.preset, a.stills.split(","), a.owner, a.writer_model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, indent=1) + "\n")
    print(f"{len(g)} nodes -> {out}")


if __name__ == "__main__":
    main()
