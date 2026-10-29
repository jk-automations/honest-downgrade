"""Honest Downgrade ComfyUI nodes. Paid generation is done by ComfyUI's own partner nodes (Gemini, Nano Banana 2,
Veo 3.1 first/last frame); these nodes write and check the ladder, build the prompts, make the free draft warps,
check the sign text and cut the 30 s Reel and the 15 s cutdown."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

try:
    from . import honest_core as core
except ImportError:  # imported directly (tests)
    import honest_core as core

try:
    from comfy_api.input_impl import VideoFromFile
except ImportError:  # older ComfyUI
    from comfy_api.latest._input_impl import VideoFromFile

CAT = "Honest Downgrade"
FAMILY_CHOICES = [f"{k} ({v['label']})" for k, v in core.FAMILIES.items()]
WRITERS = ["template (offline, free)", "Gemini (new jokes for your business)"]
JOKES = ["joke 1", "joke 2", "joke 3"]
PRESET = core.load_preset(core.list_presets()[0]) if core.list_presets() else {}


def _pil(img):
    return Image.fromarray((img[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)).convert("RGB")


def _tensor(pil):
    return torch.from_numpy(np.asarray(pil.convert("RGB"), dtype=np.float32) / 255.0)[None]


def _is_blank(img):
    """An unused optional slot holds the flat placeholder image."""
    return img is None or float(img[0].float().std()) < 0.01


def _out_dir():
    try:
        import folder_paths
        d = Path(folder_paths.get_temp_directory())
    except ImportError:
        d = Path(tempfile.gettempdir())
    d.mkdir(parents=True, exist_ok=True)
    return d


class HonestBrief:
    """The business's true facts and the choices. The facts are locked: no model may rewrite them."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING", core.VEO_MODELS)
    RETURN_NAMES = ("brief", "writer_prompt", "veo_model")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        p = PRESET
        txt = lambda d, tip, ml=False: ("STRING", {"default": d, "multiline": ml, "tooltip": tip})
        fam = next((c for c in FAMILY_CHOICES if c.startswith(p.get("family", "food"))), FAMILY_CHOICES[0])
        return {"required": {
            "business_name": txt(p.get("business_name", ""), "Shown on the end card."),
            "family": (FAMILY_CHOICES, {"default": fam, "tooltip": "Sets the joke ladder and the wild-card warps that fit."}),
            "true_setup": txt(p.get("true_setup", ""), "The truth rung, exactly as it is: 'a truck in a gas station parking lot'."),
            "honest_line": txt(p.get("honest_line", ""), "One true line about how you started ('Started with $800 in 2019.'). Empty = playful tone."),
            "real_proof": txt(p.get("real_proof", ""), "The payoff people can see and check: 'The line at 11pm is real.'"),
            "hero_thing": txt(p.get("hero_thing", ""), "The payoff still: your best product or finished work, no people."),
            "tone": (list(core.TONES), {"default": p.get("tone", "heartfelt")}),
            "joke": (JOKES, {"default": "joke 1", "tooltip": "Three ladders per business family. Pick the one that sounds like you."}),
            "already_used_warps": ("STRING", {"default": "", "tooltip": "Warp devices you used before, comma separated. Never repeated."}),
            "video_model": (core.VEO_MODELS, {"default": "veo-3.1-lite", "tooltip": "Veo 3.1 lite: about $0.03/s at 720p without audio."}),
            "writer": (WRITERS, {"default": WRITERS[0]}),
        }}

    def run(self, business_name, family, true_setup, honest_line, real_proof, hero_thing, tone, joke, already_used_warps,
            video_model, writer):
        brief = core.make_brief(business_name, family, true_setup, honest_line, real_proof, hero_thing, tone,
                                JOKES.index(joke) + 1 if joke in JOKES else 1, already_used_warps, video_model,
                                "gemini" if writer.startswith("Gemini") else "template")
        return (json.dumps(brief), core.writer_prompt(brief), video_model)


class HonestLadder:
    """Brag -> downgrade 1 -> downgrade 2 -> truth -> payoff, with one different wild-card warp per step. The template
    writes it offline; Gemini is asked only when picked (lazy input). Either way it is checked before anything is drawn."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("ladder", "ladder_text")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"brief": ("STRING", {"forceInput": True})},
                "optional": {"writer_reply": ("STRING", {"forceInput": True, "lazy": True})}}

    def check_lazy_status(self, brief, writer_reply=None):
        return ["writer_reply"] if json.loads(brief)["source"] == "gemini" and writer_reply is None else []

    def run(self, brief, writer_reply=None):
        b = json.loads(brief)
        joke = core.parse_reply(writer_reply) if b["source"] == "gemini" else core.template_joke(b)
        ladder = core.build_ladder(b, joke)
        return (json.dumps(ladder), core.ladder_text(ladder))


class HonestRung:
    """One rung: the keyframe prompt (the caption must be literally visible) and its caption."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("keyframe_prompt", "caption")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ladder": ("STRING", {"forceInput": True}), "rung": ("INT", {"default": 1, "min": 1, "max": 5})}}

    def run(self, ladder, rung):
        lad = json.loads(ladder)
        return (core.keyframe_prompt(lad, rung - 1), lad["rungs"][rung - 1]["caption"])


class HonestWarp:
    """One step between rung k and rung k+1: the first/last-frame motion prompt with its wild-card device."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("warp_prompt", "device")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ladder": ("STRING", {"forceInput": True}), "step": ("INT", {"default": 1, "min": 1, "max": 4})}}

    def run(self, ladder, step):
        lad = json.loads(ladder)
        return (core.warp_prompt(lad, step - 1), lad["warps"][step - 1]["device"])


class HonestDraftWarp:
    """Free local draft of a warp: an animatic between the two stills, with an ffmpeg transition that reads like the
    device. Use it to approve the whole Reel before paying for real motion. No AI video, no API."""
    CATEGORY = CAT
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"first_frame": ("IMAGE",), "last_frame": ("IMAGE",), "ladder": ("STRING", {"forceInput": True}),
                             "step": ("INT", {"default": 1, "min": 1, "max": 4}),
                             "seconds": ("INT", {"default": core.WARP_SECONDS, "min": 4, "max": 8, "step": 2})}}

    def run(self, first_frame, last_frame, ladder, step, seconds):
        lad = json.loads(ladder)
        tmp = Path(tempfile.mkdtemp(prefix="honest_draft_"))
        a, b = tmp / "a.png", tmp / "b.png"
        _pil(first_frame).save(a); _pil(last_frame).save(b)
        out = _out_dir() / f"honest_draft_{tmp.name}_{step}.mp4"
        core.draft_warp(a, b, lad["warps"][step - 1]["device"], out, secs=seconds)
        return (VideoFromFile(str(out)),)


def ocr_text(pil):
    """Read sign text with the tesseract CLI if it is installed (optional). None = OCR not available."""
    exe = shutil.which("tesseract") or ("/opt/homebrew/bin/tesseract" if Path("/opt/homebrew/bin/tesseract").exists() else None)
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "k.png"
        pil.save(p)
        r = subprocess.run([exe, str(p), "stdout", "--psm", "11"], capture_output=True, text=True, timeout=60)
        return r.stdout


def sign_check(ladder, images):
    """Sign text check (B20): does each rung's sign read exactly as written? A report, never a silent pass."""
    lines = []
    for k, (r, im) in enumerate(zip(ladder["rungs"], images)):
        if not r.get("sign"):
            lines.append(f"{k + 1}. {r['role']}: no sign to check"); continue
        txt = ocr_text(im)
        if txt is None:
            lines.append(f"{k + 1}. {r['role']}: OCR not installed, check '{r['sign']}' by eye"); continue
        ok = core._norm(r["sign"]) in core._norm(txt)
        lines.append(f"{k + 1}. {r['role']}: sign '{r['sign']}' {'PASS' if ok else 'NOT FOUND (check by eye, re-roll if wrong)'}")
    return lines


class HonestBoard:
    """The five rung stills side by side with their captions (approve this before paying for video), plus the sign
    text check by OCR when tesseract is installed."""
    CATEGORY = CAT
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("board", "check")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ladder": ("STRING", {"forceInput": True})},
                "optional": {f"rung_{k}": ("IMAGE",) for k in range(1, 6)}}

    def run(self, ladder, **rungs):
        lad = json.loads(ladder)
        ims = [_pil(rungs[f"rung_{k}"]) for k in range(1, 6) if rungs.get(f"rung_{k}") is not None]
        if not ims:
            raise ValueError("No rung stills to show.")
        sheet = core.board(ims, [r["caption"] for r in lad["rungs"]][:len(ims)], None)
        return (_tensor(sheet), "\n".join(sign_check(lad, ims)))


class HonestAssemble:
    """The edit: the four warps, then your real ending photo (real people live only here), the end card. Classic
    captions, 'AI-generated' label on the AI shots, 'Real photo' on yours, music drop on the honest line, -14 LUFS.
    Two files from the same shots: the 30 s Reel and the 15 s cutdown."""
    CATEGORY = CAT
    RETURN_TYPES = ("VIDEO", "VIDEO", "STRING")
    RETURN_NAMES = ("reel_30s", "cutdown_15s", "receipt")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ladder": ("STRING", {"forceInput": True}),
                             "warp_1": ("VIDEO",), "warp_2": ("VIDEO",), "warp_3": ("VIDEO",), "warp_4": ("VIDEO",),
                             "captions": ("BOOLEAN", {"default": True}),
                             "ai_label": ("BOOLEAN", {"default": True, "tooltip": "Keep this on when you post."}),
                             "credit": ("BOOLEAN", {"default": True}),
                             "music_path": ("STRING", {"default": "", "tooltip": "Optional: a track you OWN or licensed. Empty = the "
                                                       "built-in synth bed (original, no licence needed). Never a copyrighted song."})},
                "optional": {"ending_photo": ("IMAGE", {"tooltip": "Your REAL photo for the payoff (owner, customers, the line). "
                                                        "Empty slot = no ending, the AI payoff still closes the Reel."}),
                             "ending_clip": ("VIDEO", {"tooltip": "Or a REAL clip instead of a photo."})}}

    def run(self, ladder, warp_1, warp_2, warp_3, warp_4, captions=True, ai_label=True, credit=True, music_path="",
            ending_photo=None, ending_clip=None):
        lad = json.loads(ladder)
        tmp = Path(tempfile.mkdtemp(prefix="honest_"))
        clips = []
        for k, v in enumerate([warp_1, warp_2, warp_3, warp_4], 1):
            p = tmp / f"warp_{k}.mp4"; v.save_to(str(p)); clips.append(p)
        ending = None
        if ending_clip is not None:
            ending = tmp / "ending.mp4"; ending_clip.save_to(str(ending))
        elif not _is_blank(ending_photo):
            ending = tmp / "ending.png"; _pil(ending_photo).save(ending)
        music = Path(music_path.strip()).expanduser() if music_path.strip() else None
        if music and not music.is_file():
            raise ValueError(f"music_path does not exist: {music}")
        out = _out_dir()
        r30 = core.assemble(clips, lad, out / f"honest_{tmp.name}_30s.mp4", tmp, ending, 30, captions, ai_label, credit, music)
        r15 = core.assemble(clips, lad, out / f"honest_{tmp.name}_15s.mp4", tmp, ending, 15, captions, ai_label, credit, music)
        return (VideoFromFile(str(out / f"honest_{tmp.name}_30s.mp4")), VideoFromFile(str(out / f"honest_{tmp.name}_15s.mp4")),
                json.dumps({"reel_30s": r30, "cutdown_15s": r15}, indent=1))


NODE_CLASS_MAPPINGS = {"HonestBrief": HonestBrief, "HonestLadder": HonestLadder, "HonestRung": HonestRung, "HonestWarp": HonestWarp,
                       "HonestDraftWarp": HonestDraftWarp, "HonestBoard": HonestBoard, "HonestAssemble": HonestAssemble}
NODE_DISPLAY_NAME_MAPPINGS = {"HonestBrief": "Honest Downgrade: Your Facts", "HonestLadder": "Honest Downgrade: Ladder Writer",
                              "HonestRung": "Honest Downgrade: Rung", "HonestWarp": "Honest Downgrade: Warp",
                              "HonestDraftWarp": "Honest Downgrade: Free Draft Warp", "HonestBoard": "Honest Downgrade: Board + Sign Check",
                              "HonestAssemble": "Honest Downgrade: Assemble"}
