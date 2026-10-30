"""Honest Downgrade ComfyUI nodes. Paid generation is done by ComfyUI's own partner nodes (Gemini, Nano Banana 2,
Veo 3.1 first/last frame, Sonilo Video-to-Music); these nodes write and check the ladder, build the prompts, make the
free draft clips, check the sign text, cut the full Reel and the 15 s cutdown, and mix the music."""
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
TYPE_CHOICES = core.TYPE_CHOICES
WRITERS = ["template (offline, free)", "Gemini (new jokes for your business)"]
JOKES = ["joke 1", "joke 2", "joke 3"]
PRESET = core.load_preset(core.DEFAULT_PRESET) if core.DEFAULT_PRESET in core.list_presets() else {}


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
    """The business's true facts and the choices, for any small business (shop or not). The business type picks the
    joke ladder's nouns and the wild cards; offer, setting and audience fill the prompts. The facts are locked: no model
    may rewrite them. Defaults are the sample taco truck; type your own."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING", core.VEO_MODELS)
    RETURN_NAMES = ("brief", "writer_prompt", "veo_model")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        p = PRESET
        txt = lambda d, tip, ml=False: ("STRING", {"default": d, "multiline": ml, "tooltip": tip})
        bt = core.BUSINESS_TYPES[core.business_type_key(p.get("business_type", core.TYPE_KEYS[0]))]
        return {"required": {
            "business_name": txt(p.get("business_name", ""), "Shown on the end card."),
            "business_type": (TYPE_CHOICES, {"default": bt["label"], "tooltip": "Any small business, shop or not: sets the nouns "
                              "of the joke ladder and the wild-card warps that fit. 'Other' works for anything; describe the offer."}),
            "offer": txt(p.get("offer", ""), "What you sell or do, in your words: 'leak repairs and new installs', 'one-to-one "
                         "maths lessons', 'poured soy candles'. Empty = the business type's default."),
            "setting": txt(p.get("setting", ""), "Where the work really happens: 'at customers' homes', 'online', 'a two-chair "
                           "practice'. Empty = the business type's default."),
            "audience": txt(p.get("audience", ""), "Who it is for: 'busy dog owners', 'beginners who hate big gyms'. "
                            "Steers the joke writer. Empty = the business type's default."),
            "true_setup": txt(p.get("true_setup", ""), "The truth rung, exactly as it is: 'a van and a phone that never stops "
                              "ringing', 'one chair in my garage', 'a truck in a gas station parking lot'."),
            "honest_line": txt(p.get("honest_line", ""), "One true line about how you started ('Started with $800 in 2019.'). Empty = playful tone."),
            "real_proof": txt(p.get("real_proof", ""), "The payoff people can see and check: 'Same-day callbacks, every time.', "
                              "'Booked out every Saturday.'"),
            "hero_thing": txt(p.get("hero_thing", ""), "The payoff still: your best product or finished work, no people. "
                              "Empty = built from the business type and offer."),
            "tone": (list(core.TONES), {"default": p.get("tone", "heartfelt")}),
            "joke": (JOKES, {"default": "joke 1", "tooltip": "Three joke ladders (places, capacity, crew), filled for your "
                     "business type. Pick the one that sounds like you."}),
            "already_used_warps": ("STRING", {"default": "", "tooltip": "Warp devices you used before, comma separated. Never repeated."}),
            "video_model": (core.VEO_MODELS, {"default": "veo-3.1-lite", "tooltip": "Veo 3.1 lite: about $0.03/s at 720p without audio."}),
            "writer": (WRITERS, {"default": WRITERS[0]}),
        }}

    def run(self, business_name, business_type, offer, setting, audience, true_setup, honest_line, real_proof, hero_thing, tone,
            joke, already_used_warps, video_model, writer):
        brief = core.make_brief(business_name, business_type, true_setup, honest_line, real_proof, hero_thing, tone,
                                JOKES.index(joke) + 1 if joke in JOKES else 1, already_used_warps, video_model,
                                "gemini" if writer.startswith("Gemini") else "template", offer, setting, audience)
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
        return {"required": {"ladder": ("STRING", {"forceInput": True}), "rung": ("INT", {"default": 1, "min": 1, "max": core.N_RUNGS})}}

    def run(self, ladder, rung):
        lad = json.loads(ladder)
        return (core.keyframe_prompt(lad, rung - 1), lad["rungs"][rung - 1]["caption"])


class HonestWarp:
    """One of the seven moving clips: a wild-card or shock warp (with a 1 s build-up), a quiet sympathy move, or the
    payoff macro. Gives the first/last-frame motion prompt and its device."""
    CATEGORY = CAT
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("warp_prompt", "device")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ladder": ("STRING", {"forceInput": True}), "step": ("INT", {"default": 1, "min": 1, "max": core.N_CLIPS})}}

    def run(self, ladder, step):
        lad = json.loads(ladder)
        return (core.warp_prompt(lad, step - 1), lad["shots"][step - 1]["device"])


class HonestDraftWarp:
    """Free local draft of a clip: a slow push on each still and an ffmpeg transition that reads like the device, so
    every rung still moves. Use it to approve the whole Reel before paying for real motion. No AI video, no API."""
    CATEGORY = CAT
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"first_frame": ("IMAGE",), "last_frame": ("IMAGE",), "ladder": ("STRING", {"forceInput": True}),
                             "step": ("INT", {"default": 1, "min": 1, "max": core.N_CLIPS}),
                             "seconds": ("INT", {"default": core.WARP_SECONDS, "min": 4, "max": 8, "step": 2})}}

    def run(self, first_frame, last_frame, ladder, step, seconds):
        lad = json.loads(ladder)
        tmp = Path(tempfile.mkdtemp(prefix="honest_draft_"))
        a, b = tmp / "a.png", tmp / "b.png"
        _pil(first_frame).save(a); _pil(last_frame).save(b)
        out = _out_dir() / f"honest_draft_{tmp.name}_{step}.mp4"
        core.draft_warp(a, b, lad["shots"][step - 1]["device"], out, secs=seconds)
        return (VideoFromFile(str(out)),)


def ocr_text(pil):
    """Read sign text with the tesseract CLI if it is installed (optional). None = OCR not available.
    Whole frame first (page and sparse modes), then overlapping horizontal bands, enlarged: a sign in a busy scene
    (a tower full of windows) is often only found once the clutter around it is cropped away."""
    from PIL import ImageOps
    exe = shutil.which("tesseract") or ("/opt/homebrew/bin/tesseract" if Path("/opt/homebrew/bin/tesseract").exists() else None)
    if not exe:
        return None
    run = lambda p, psm: subprocess.run([exe, str(p), "stdout", "--psm", psm], capture_output=True, text=True, timeout=60).stdout
    out = []
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "k.png"
        pil.convert("RGB").save(p)
        out += [run(p, "3"), run(p, "12")]
        g = pil.convert("L")
        h = max(32, g.height // 8)
        for y in range(0, g.height - h // 2, h // 2):
            band = ImageOps.autocontrast(g.crop((0, y, g.width, min(g.height, y + h))))
            band.resize((band.width * 2, band.height * 2)).save(p)
            out.append(run(p, "6"))
    return "\n".join(out)


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
                "optional": {f"rung_{k}": ("IMAGE",) for k in range(1, core.N_RUNGS + 1)}}

    def run(self, ladder, **rungs):
        lad = json.loads(ladder)
        ims = [_pil(rungs[f"rung_{k}"]) for k in range(1, core.N_RUNGS + 1) if rungs.get(f"rung_{k}") is not None]
        if not ims:
            raise ValueError("No rung stills to show.")
        sheet = core.board(ims, [r["caption"] or r["role"].replace("_", " ") for r in lad["rungs"]][:len(ims)], None)
        return (_tensor(sheet), "\n".join(sign_check(lad, ims)))


CONSENT_LABEL = "I have this person's consent"


class HonestAssemble:
    """The edit, picture first: the seven clips joined with dissolves, the owner's REAL photo (only with consent, never
    sent to any model) between the place of work and the payoff, the end card, classic captions and labels. Gives the
    score cut (the same Reel with the photo swapped for a private card) for the music model, and the plan."""
    CATEGORY = CAT
    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("score_cut", "plan", "music_prompt")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        req = {"ladder": ("STRING", {"forceInput": True})}
        req.update({f"clip_{k}": ("VIDEO",) for k in range(1, core.N_CLIPS + 1)})
        req.update({"captions": ("BOOLEAN", {"default": True}),
                    "ai_label": ("BOOLEAN", {"default": True, "tooltip": "Keep this on when you post."}),
                    "credit": ("BOOLEAN", {"default": True}),
                    "owner_consent": ("BOOLEAN", {"default": False, "label_on": "YES", "label_off": "NO",
                                                  "tooltip": CONSENT_LABEL + ": required when you add the owner photo (the person in "
                                                             "it said yes to this ad). Without it the run stops with an error."})})
        return {"required": req,
                "optional": {"owner_photo": ("IMAGE", {"tooltip": "The face of the company: a REAL photo of the owner at work. Shown "
                                                       "with a 'Real photo' label, never sent to any image, video or music model. "
                                                       "Empty slot = the ending is the payoff alone."}),
                             "owner_clip": ("VIDEO", {"tooltip": "Or a REAL clip of the owner instead of a photo (same consent rule)."})}}

    def run(self, ladder, captions=True, ai_label=True, credit=True, owner_consent=False, owner_photo=None, owner_clip=None, **clips):
        lad = json.loads(ladder)
        tmp = Path(tempfile.mkdtemp(prefix="honest_", dir=_out_dir()))
        paths = []
        for k in range(1, core.N_CLIPS + 1):
            p = tmp / f"clip_{k}.mp4"; clips[f"clip_{k}"].save_to(str(p)); paths.append(p)
        owner = None
        if owner_clip is not None:
            owner = tmp / "owner.mp4"; owner_clip.save_to(str(owner))
        elif not _is_blank(owner_photo):
            owner = tmp / "owner.png"; _pil(owner_photo).save(owner)
        if owner is not None and not owner_consent:
            raise ValueError(core.CONSENT_ERROR)
        plan = core.assemble_picture(paths, lad, tmp, owner, owner_consent, captions, ai_label, credit)
        return (VideoFromFile(plan["score_cut"]), json.dumps(plan), plan["music_prompt"])


class HonestFinish:
    """The music: your own track if you give one; else the Sonilo score (asked lazily, so a track of your own never pays
    for a score); else, in the free draft only, the built-in synth bed. The bed is levelled first, ducked under every
    honest or spoken line, whooshes on every warp, -14 LUFS. Gives the full Reel and the 15 s cutdown."""
    CATEGORY = CAT
    RETURN_TYPES = ("VIDEO", "VIDEO", "STRING")
    RETURN_NAMES = ("reel", "cutdown_15s", "receipt")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"plan": ("STRING", {"forceInput": True}),
                             "music_path": ("STRING", {"default": "", "tooltip": "Optional: a track you OWN or licensed. It replaces the "
                                                       "score. Never a copyrighted song."})},
                "optional": {"score": ("AUDIO", {"lazy": True, "tooltip": "The Sonilo Video-to-Music score of the score cut."})},
                "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    @staticmethod
    def _score_linked(prompt, unique_id):
        return bool(prompt) and "score" in (prompt.get(str(unique_id), {}).get("inputs", {}))

    def check_lazy_status(self, plan, music_path, score=None, prompt=None, unique_id=None):
        return ["score"] if self._score_linked(prompt, unique_id) and score is None and not music_path.strip() else []

    def run(self, plan, music_path, score=None, prompt=None, unique_id=None):
        pl = json.loads(plan)
        work = Path(pl["work"])
        music = Path(music_path.strip()).expanduser() if music_path.strip() else None
        if music and not music.is_file():
            raise ValueError(f"music_path does not exist: {music}")
        score_path = None
        if score is not None and music is None:
            score_path = core.save_wav(work / "score.wav", score["waveform"].cpu().numpy(), score["sample_rate"])
        out = _out_dir()
        full, short = out / f"{work.name}_reel.mp4", out / f"{work.name}_15s.mp4"
        # the synth bed is for the free draft only: the main app (score connected) never falls back to it
        receipt = core.finish(pl, full, short, score_path, music, allow_synth=not self._score_linked(prompt, unique_id))
        return (VideoFromFile(str(full)), VideoFromFile(str(short)), json.dumps(receipt, indent=1))


NODE_CLASS_MAPPINGS = {"HonestBrief": HonestBrief, "HonestLadder": HonestLadder, "HonestRung": HonestRung, "HonestWarp": HonestWarp,
                       "HonestDraftWarp": HonestDraftWarp, "HonestBoard": HonestBoard, "HonestAssemble": HonestAssemble,
                       "HonestFinish": HonestFinish}
NODE_DISPLAY_NAME_MAPPINGS = {"HonestBrief": "Honest Downgrade: Your Facts", "HonestLadder": "Honest Downgrade: Ladder Writer",
                              "HonestRung": "Honest Downgrade: Rung", "HonestWarp": "Honest Downgrade: Warp",
                              "HonestDraftWarp": "Honest Downgrade: Free Draft Warp", "HonestBoard": "Honest Downgrade: Board + Sign Check",
                              "HonestAssemble": "Honest Downgrade: Assemble (picture)",
                              "HonestFinish": "Honest Downgrade: Music + Finish"}
