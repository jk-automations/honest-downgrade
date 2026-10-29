"""Honest Downgrade core: the brag-to-truth ladder (template or Gemini), its checks, the prompts, and the edit.
Pure Python + Pillow + ffmpeg, no ComfyUI imports, so it can be tested on its own. Apache-2.0.

The ladder is five rungs: brag (impossible scale) -> downgrade 1 (cut the number) -> downgrade 2 (cut the fancy thing)
-> truth (the real, humble setup) -> payoff (real proof). One wild-card warp joins each pair of rungs.
The writer (template or Gemini) only writes the joke: the brag, the two downgrades and the warps. The truth, the honest
line and the payoff are the business's own facts and are copied in by code, never rewritten by a model."""
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PRESETS_DIR = ROOT / "presets"
FONT = ROOT / "fonts" / "Inter.ttf"

ROLES = ["brag", "downgrade_1", "downgrade_2", "truth", "payoff"]
TONES = {"heartfelt": "The honest line leads the turn and the music drops under it.",
         "playful": "Joke-forward and bright, straight from the truth to the payoff."}
VEO_MODELS = ["veo-3.1-lite", "veo-3.1-fast-generate", "veo-3.1-generate"]   # exact Veo3FirstLastFrameNode values
WARP_SECONDS = 6                       # Veo first/last frame takes 4, 6 or 8 s; 4 warps x 6 s + ending + end card = 30 s
MAX_CAPTION_WORDS = 12

# ---------------------------------------------------------------- wild-card warps
# Each device is the surprising thing that fills the frame and carries us to the next rung (block B34).
DEVICES = {
    "ribbon snake": "the ribbon in the frame comes alive as a giant snake, slithers toward the lens until its body fills the frame, then slides away to reveal",
    "steam swirl": "a swirl of steam rises, fills the whole frame, then clears to reveal",
    "flying ingredients": "a burst of flying ingredients (chilies, onions, herbs) sweeps across the lens, then clears to reveal",
    "blueprint fold": "the whole scene folds flat like a blueprint sheet and refolds into",
    "paint wave": "a wave of fresh paint rolls across the frame, then recedes to reveal",
    "tool-belt burst": "tools burst out of a tool belt toward the lens, spin past, then scatter to reveal",
    "towel wipe": "a fluffy towel wipes across the lens, revealing",
    "mirror shatter": "the frame cracks like a mirror and the shards fall away to reveal",
    "petal confetti": "a confetti of flower petals blows across the lens, then settles to reveal",
    "elevator drop": "the camera drops like an elevator, floors flashing past, and stops on",
    "paper-plane swarm": "a swarm of paper planes flies at the lens, then scatters to reveal",
    "screen pull": "the whole frame is pulled away like a screen, revealing behind it",
    "pop-up fold": "the buildings fold flat like a paper pop-up book and collapse into",
    "flock burst": "a flock of birds bursts toward the lens, wings fill the frame, then scatter to reveal",
    "push-through window": "the camera pushes straight through a window into",
    "pull-back reveal": "the camera pulls back fast and wide to reveal",
    "melt": "the scene melts like warm wax and re-forms as",
}
GENERIC_DEVICES = ["pop-up fold", "flock burst", "push-through window", "melt", "pull-back reveal"]
# The cheap local draft (no AI video) maps each device to an ffmpeg transition so the animatic still reads as that device.
DRAFT_TRANSITION = {"ribbon snake": "slideleft", "steam swirl": "fadewhite", "flying ingredients": "pixelize", "blueprint fold": "vertclose",
                    "paint wave": "wipeup", "tool-belt burst": "circleopen", "towel wipe": "wiperight", "mirror shatter": "pixelize",
                    "petal confetti": "dissolve", "elevator drop": "slideup", "paper-plane swarm": "slideright", "screen pull": "smoothleft",
                    "pop-up fold": "horzclose", "flock burst": "circleopen", "push-through window": "zoomin", "pull-back reveal": "circleclose",
                    "melt": "dissolve"}

# ---------------------------------------------------------------- the four business families (W13 card)
# Each family: the default truth/proof wording when a field is left empty, the hero for the payoff still, the wild
# cards that fit, and three joke ladders (brag, downgrade 1 = cut the number, downgrade 2 = cut the fancy thing).
# visual = what the frame must show so the caption is literally true (block B35). sign = short sign text, may be "".
FAMILIES = {
    "food": {
        "label": "Food and drink",
        "hero": "the signature dish in a tight close-up, steam rising, on a plain paper tray",
        "devices": ["ribbon snake", "steam swirl", "flying ingredients"],
        "ladders": [
            [("Our 200th location just opened.", "a gleaming grand-opening plaza of a giant restaurant tower, a huge red ribbon across the doors, a banner over the entrance", "200TH LOCATION"),
             ("Ok, it's 2 locations.", "two small identical storefront restaurants side by side on a quiet street, both lit", "2 LOCATIONS"),
             ("Ok, it's one window.", "one small service window in a plain painted wall, a chalk menu board beside it", "")],
            [("We seat 500 a night.", "a vast dining hall with 500 empty set tables and chandeliers, a sign on the wall", "500 SEATS"),
             ("Ok, it's 5 tables.", "five small tables with folding chairs on a sidewalk, string lights above", ""),
             ("Ok, no tables. One counter.", "one short counter with a napkin holder and a hot-sauce bottle, nothing else", "")],
            [("Our kitchen has 40 grills.", "an enormous stainless steel kitchen with 40 identical grills in long rows", "40 GRILLS"),
             ("Ok, it's 4 burners.", "a small stove with exactly four burners, a single pan on one of them", ""),
             ("Ok, it's one flat-top grill.", "one well-seasoned flat-top grill with a spatula resting on it", "")],
        ],
    },
    "trades": {
        "label": "Trades and home",
        "hero": "the finished work in a clean, bright close-up",
        "devices": ["blueprint fold", "paint wave", "tool-belt burst"],
        "ladders": [
            [("We just finished this mansion.", "a huge white mansion with columns and a fountain, a finished-project sign on the lawn", "PROJECT COMPLETE"),
             ("Ok, it's 2 rooms.", "two finished rooms seen through one doorway, fresh paint, drop cloths folded", ""),
             ("Ok, no mansion. One wall.", "one freshly finished wall with a ladder leaning against it", "")],
            [("Our fleet has 50 trucks.", "a lot with 50 identical unbranded white work trucks lined up in rows", "50 TRUCKS"),
             ("Ok, it's 5 trucks.", "five plain work trucks parked in a row", ""),
             ("Ok, no fleet. One ladder rack.", "one roof ladder rack on a plain vehicle roof, a single ladder strapped on", "")],
            [("Our crew is 50 people strong.", "a huge equipment yard with 50 hard hats hanging on hooks in rows", "50 HARD HATS"),
             ("Ok, it's 5 hard hats.", "five hard hats on a workbench", ""),
             ("Ok, no yard. One toolbox.", "one well-worn toolbox on a garage floor", "")],
        ],
    },
    "beauty": {
        "label": "Beauty and fitness",
        "hero": "the room ready for the next session, warm light, everything in its place",
        "devices": ["towel wipe", "mirror shatter", "petal confetti"],
        "ladders": [
            [("Welcome to our 5-floor spa.", "a five-floor glass wellness tower with a glowing sign at the entrance", "5 FLOORS"),
             ("Ok, it's 2 floors.", "a two-floor building with plants in the windows", ""),
             ("Ok, no spa. One room.", "one calm room with a single treatment chair and a mirror", "")],
            [("We have 40 machines.", "a huge gym hall with 40 identical machines in rows, all empty", "40 MACHINES"),
             ("Ok, it's 4 machines.", "four machines in a small bright room", ""),
             ("Ok, no machines. One mat.", "one exercise mat rolled out on a wooden floor", "")],
            [("Our juice bar never closes.", "a giant neon-lit juice bar counter with 30 blenders in a row", "JUICE BAR"),
             ("Ok, it's 2 blenders.", "two blenders on a small counter", ""),
             ("Ok, no juice bar. One water jug.", "one big water jug with paper cups beside it on a side table", "")],
        ],
    },
    "retail": {
        "label": "Retail and services",
        "hero": "the product or the finished work on a clean table, in soft daylight",
        "devices": ["elevator drop", "paper-plane swarm", "screen pull"],
        "ladders": [
            [("Welcome to our HQ tower.", "a 60-floor glass headquarters tower at dusk, a big sign at the top", "HQ"),
             ("Ok, it's 2 floors.", "a two-floor office building on a small street", ""),
             ("Ok, no tower. One room.", "one small room with a single desk, a lamp and a chair", "")],
            [("Our team is 300 people.", "a huge open-plan office with 300 empty identical desks in rows", "300 DESKS"),
             ("Ok, it's 3 desks.", "three desks pushed together in a small room", ""),
             ("Ok, it's 2 chairs.", "two chairs at one shared desk, two coffee mugs", "")],
            [("Our lobby has its own fountain.", "a marble lobby with a huge fountain in the middle and a reception desk", "LOBBY"),
             ("Ok, it's a hallway.", "a narrow hallway with a single potted plant", ""),
             ("Ok, no lobby. One doormat.", "one doormat in front of a plain door", "")],
        ],
    },
}
FAMILY_KEYS = list(FAMILIES)

BRANDS = {"ferrari", "lamborghini", "lambo", "porsche", "mclaren", "bugatti", "tesla", "bmw", "mercedes", "audi", "starbucks",
          "mcdonald's", "mcdonalds", "dunkin", "nike", "adidas", "apple", "iphone", "instagram", "tiktok", "youtube", "facebook",
          "google", "coca-cola", "pepsi", "gucci", "rolex", "uber", "doordash", "shell", "chevron", "carhartt", "ikea", "walmart"}
# AI changes places and things, never people: real people appear only in the real ending photo or clip.
PEOPLE = ["person", "people", "man", "men", "woman", "women", "crowd", "chef", "chefs", "cook", "customer", "customers", "owner",
          "worker", "workers", "staff", "face", "faces", "hand", "hands", "kid", "kids", "child", "girl", "boy", "guy", "lady",
          "barber", "stylist", "trainer", "client", "clients", "employee", "employees", "family", "couple", "selfie"]
NEGATED_PEOPLE = re.compile(r"\b(no|without|empty of|free of)\s+(people|persons?|faces?|hands?|one|crowds?|customers?|staff)\b", re.I)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100}

KEYFRAME_HEAD = ("Vertical 9:16 photo-real commercial still, the first or last frame of a short ad. Warm, clean, cinematic light; "
                 "one consistent look across the whole series. Keep the top fifth of the frame calm (sky, wall or ceiling) with no "
                 "signs in it: the caption goes there.")
KEYFRAME_TAIL = ("No people at all: no faces, no hands, no silhouettes. No real brand logos or trademarks, no phone screens or "
                 "app interfaces, no captions or subtitles. Vehicles, signs and packaging are plain and unbranded.")
WARP_TAIL = ("One continuous shot from the first frame to the last frame, smooth gimbal motion, no handheld shake, no cuts. "
             "No people. No captions, no subtitles, no new text; only signs already in the frames. No real logos.")


# ---------------------------------------------------------------- presets
def list_presets():
    return sorted(p.name for p in PRESETS_DIR.iterdir() if (p / "preset.json").exists()) if PRESETS_DIR.exists() else []


def load_preset(name):
    return json.loads((PRESETS_DIR / name / "preset.json").read_text())


# ---------------------------------------------------------------- small text helpers
def _words(s):
    return re.findall(r"[A-Za-z0-9$']+", s)


def _norm(s):
    return " ".join(w.lower() for w in _words(s))


def _has_word(text, word):
    return re.search(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", text, re.I) is not None


def _sentence(s):
    s = s.strip()
    return s if not s or s[-1] in ".!?" else s + "."


def numbers_in(text):
    """Numbers a caption claims, as ints ('2 locations', 'five tables', '200th')."""
    out = {int(n) for n in re.findall(r"\b(\d+)(?:st|nd|rd|th)?\b", text.replace(",", ""), re.I)}
    out |= {v for w, v in NUMBER_WORDS.items() if _has_word(text, w)}
    return out


def people_in(text):
    t = NEGATED_PEOPLE.sub(" ", text)
    return sorted({w for w in PEOPLE if _has_word(t, w)})


def brands_in(text):
    return sorted(b for b in BRANDS if _has_word(text, b))


# ---------------------------------------------------------------- the brief
def make_brief(business_name, family, true_setup, honest_line, real_proof, hero_thing="", tone="heartfelt", variant=1,
               avoid_devices="", model="veo-3.1-lite", source="template"):
    fam = family.split(" ")[0].strip().lower() if family else ""
    fam = {"food": "food", "trades": "trades", "beauty": "beauty", "retail": "retail"}.get(fam)
    if fam is None:
        raise ValueError(f"Pick a business family: {FAMILY_KEYS}.")
    facts = {"true_setup": true_setup.strip().rstrip("."), "real_proof": real_proof.strip(), "honest_line": honest_line.strip()}
    if not facts["true_setup"]:
        raise ValueError("Tell us the real setup (the truth rung), e.g. 'a truck in a gas station parking lot'.")
    if not facts["real_proof"]:
        raise ValueError("Give one real proof people can see (the payoff), e.g. 'The line at 11pm is real.'")
    tone = tone if tone in TONES else "heartfelt"
    if tone == "heartfelt" and not facts["honest_line"]:
        tone = "playful"   # the honest beat needs a true line from the business; we never invent one
    for k, v in list(facts.items()) + [("business_name", business_name), ("hero_thing", hero_thing)]:
        if brands_in(v):
            raise ValueError(f"{k} names a real brand ({', '.join(brands_in(v))}). Use plain, unbranded words.")
    avoid = sorted({d.strip().lower() for d in avoid_devices.split(",") if d.strip()})
    return {"business_name": business_name.strip() or "Your Business", "family": fam, "facts": facts,
            "hero_thing": hero_thing.strip() or FAMILIES[fam]["hero"], "tone": tone, "variant": max(1, min(3, int(variant))),
            "avoid_devices": avoid, "model": model, "source": source}


def device_order(brief):
    """Every device that fits this family, family wild cards first, rotated by the joke variant, minus the ones this
    client already used. The template writer takes the first four."""
    fam = FAMILIES[brief["family"]]
    pool = fam["devices"] + [d for d in GENERIC_DEVICES if d not in fam["devices"]]
    k = (brief["variant"] - 1) % len(fam["devices"])
    pool = pool[k:len(fam["devices"])] + pool[:k] + pool[len(fam["devices"]):]
    return [d for d in pool if d not in brief["avoid_devices"]]


# ---------------------------------------------------------------- the ladder writers
def template_joke(brief):
    """The deterministic offline writer: the family's ladder for this variant and four distinct warps."""
    fam = FAMILIES[brief["family"]]
    rungs = [{"caption": c, "visual": v, "sign": s} for c, v, s in fam["ladders"][brief["variant"] - 1]]
    devs = device_order(brief)
    if len(devs) < 4:
        raise ValueError("Not enough unused warp devices left for this client (need 4). Clear some from 'already used'.")
    return {"rungs": rungs, "warps": [{"device": d, "motion": DEVICES[d]} for d in devs[:4]]}


def writer_prompt(brief):
    fam = FAMILIES[brief["family"]]
    example = template_joke(brief)
    allowed = device_order(brief)
    f = brief["facts"]
    return f"""You write the joke for an "I'm so sorry I lied" short video ad for a real small business.
Business: {brief['business_name']} ({fam['label']}).
The TRUE setup, the last rung, is fixed: "{f['true_setup']}". The real proof, the payoff, is fixed: "{f['real_proof']}".

Write the first three rungs: a brag at impossible scale, downgrade 1 that cuts the number, downgrade 2 that cuts the fancy
thing. Each one gets the next rung closer to the truth. Then pick four wild-card warps, one for each step between the five rungs
(brag > downgrade 1 > downgrade 2 > truth > payoff), all different.

Rules:
- "caption": what appears on screen, at most {MAX_CAPTION_WORDS} words, casual ("Ok, it's 2 locations.").
- "visual": a place or a thing only, never people (no faces, hands, crowds, staff, customers). It must make the caption
  literally true at a glance: if the caption says 2 locations, the visual shows exactly two. Every number in the caption is in the visual.
- "sign": up to 3 words of sign text that proves the caption, or "".
- No real brands, logos, apps or car makers anywhere.
- Warps: pick "device" from {json.dumps(allowed)} or invent a new one; "motion" says what the device does, ending in a verb
  phrase that leads into the next frame ("...then scatter to reveal"). Never repeat a device.

Reply with JSON only, exactly this shape:
{json.dumps(example, indent=1)}
"""


def parse_reply(text):
    """Gemini's reply -> dict. Tolerates code fences and chatter around the JSON."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    a, b = t.find("{"), t.rfind("}")
    if 0 <= a < b:
        try:
            return json.loads(t[a:b + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("The writer's reply had no readable JSON. Run again, or switch the writer to the template.")


def build_ladder(brief, joke):
    """Joke (3 rungs + 4 warps, from the template or Gemini) + the business's facts -> the full checked ladder."""
    f = brief["facts"]
    if not isinstance(joke, dict) or not isinstance(joke.get("rungs"), list) or not isinstance(joke.get("warps"), list):
        raise ValueError("The joke must be an object with 'rungs' and 'warps' lists.")
    if len(joke["rungs"]) != 3:
        raise ValueError(f"Need exactly 3 joke rungs (brag, downgrade 1, downgrade 2), got {len(joke['rungs'])}.")
    rungs = []
    for role, r in zip(ROLES, joke["rungs"]):
        if not isinstance(r, dict):
            raise ValueError(f"{role}: not an object")
        rungs.append({"role": role, "caption": _sentence(str(r.get("caption", ""))), "visual": str(r.get("visual", "")).strip(),
                      "sign": str(r.get("sign") or "").strip().upper()})
    setup = f["true_setup"]
    rungs.append({"role": "truth", "caption": _sentence(f"Ok, it's {setup}" if not setup.lower().startswith(("it", "ok", "we", "our", "just")) else setup),
                  "visual": f"{setup}, exactly as it really is, plain and unbranded, a little humble and full of character", "sign": "",
                  "honest_line": f["honest_line"] if brief["tone"] == "heartfelt" else ""})
    rungs.append({"role": "payoff", "caption": _sentence(f["real_proof"]), "visual": brief["hero_thing"], "sign": ""})
    warps = []
    for w in joke["warps"]:
        if not isinstance(w, dict) or not str(w.get("device", "")).strip():
            raise ValueError("Every warp needs a 'device'.")
        d = str(w["device"]).strip().lower()
        warps.append({"device": d, "motion": str(w.get("motion") or DEVICES.get(d, "")).strip()})
    ladder = {"business_name": brief["business_name"], "family": brief["family"], "tone": brief["tone"], "rungs": rungs,
              "warps": warps, "facts": f}
    errs = check_ladder(ladder, brief)
    if errs:
        raise ValueError("The ladder broke the rules:\n- " + "\n- ".join(errs[:20]))
    return ladder


def check_ladder(ladder, brief):
    """All the rules, as a list of problems (empty = good). Same rules for the template and for Gemini."""
    errs = []
    rungs, warps = ladder.get("rungs", []), ladder.get("warps", [])
    if [r.get("role") for r in rungs] != ROLES:
        errs.append(f"rungs must be exactly {ROLES}")
    for r in rungs:
        w = r.get("role", "?")
        cap, vis = r.get("caption", ""), r.get("visual", "")
        if not cap.strip() or not vis.strip():
            errs.append(f"{w}: caption and visual must not be empty"); continue
        n = len(_words(cap))
        if n > MAX_CAPTION_WORDS and w not in ("truth", "payoff"):
            errs.append(f"{w}: caption has {n} words (max {MAX_CAPTION_WORDS})")
        if len(_words(r.get("sign", ""))) > 3:
            errs.append(f"{w}: sign text is more than 3 words")
        for b in brands_in(cap + " " + vis + " " + r.get("sign", "")):
            errs.append(f"{w}: real brand '{b}'")
        for p in people_in(vis):   # captions may mention people (the payoff is a real fact); AI stills never show them
            errs.append(f"{w}: the AI still may not show people ('{p}'); real people only in the real ending photo")
        if w in ROLES[:3]:   # caption truth (B35): every number in the caption is visible in the frame
            seen = numbers_in(vis + " " + r.get("sign", ""))
            for num in sorted(numbers_in(cap) - seen):
                errs.append(f"{w}: caption says {num} but the visual does not show {num}")
    f = brief["facts"]
    if len(rungs) == 5:
        if _norm(f["true_setup"]) not in _norm(rungs[3]["caption"]):
            errs.append("truth: the caption must state the real setup word for word")
        if _norm(f["real_proof"]) not in _norm(rungs[4]["caption"]):
            errs.append("payoff: the caption must be the real proof word for word")
        if brief["tone"] == "heartfelt" and rungs[3].get("honest_line") != f["honest_line"]:
            errs.append("truth: heartfelt tone needs the business's own honest line, unchanged")
        brag_n, truth_n = max(numbers_in(rungs[0]["caption"]) or {0}), max(numbers_in(rungs[1]["caption"]) or {0})
        if brag_n and truth_n and truth_n >= brag_n:
            errs.append("downgrade 1 must cut the brag's number")
    if len(warps) != 4:
        errs.append(f"need exactly 4 warps (one per step between 5 rungs), got {len(warps)}")
    devs = [w.get("device", "") for w in warps]
    if len(set(devs)) != len(devs):
        errs.append(f"a warp device repeats: {devs}")
    for d in devs:
        if d in brief.get("avoid_devices", []):
            errs.append(f"warp '{d}' was already used for this client")
    for w in warps:
        if not w.get("motion"):
            errs.append(f"warp '{w.get('device')}' needs a motion description")
        for p in people_in(w.get("motion", "")):
            errs.append(f"warp '{w.get('device')}' shows people ('{p}')")
    return errs


# ---------------------------------------------------------------- prompts
def keyframe_prompt(ladder, k):
    r = ladder["rungs"][k]
    sign = f' A plain sign in the frame reads exactly "{r["sign"]}", spelled correctly, clean lettering.' if r.get("sign") else ""
    place = "" if r["role"] != "payoff" else " Product or finished-work hero shot."
    return (f"{KEYFRAME_HEAD}{place}\nShow: {r['visual']}.{sign}\nThe picture must make this line literally true at a glance: "
            f"\"{r['caption']}\"\n{KEYFRAME_TAIL}")


def warp_prompt(ladder, k):
    """Warp k joins rung k and rung k+1 (0-based)."""
    w, nxt = ladder["warps"][k], ladder["rungs"][k + 1]
    return (f"Start on the first frame. Then {w['motion']} the last frame: {nxt['visual']}. Land and hold on the last frame for "
            f"the final second. {WARP_TAIL}")


def ladder_text(ladder):
    lines = [f"{ladder['business_name']}: Honest Downgrade ({ladder['tone']})"]
    for k, r in enumerate(ladder["rungs"]):
        lines.append(f"{k + 1}. {r['role'].replace('_', ' ').upper():<12} {r['caption']}")
        if r.get("honest_line"):
            lines.append(f"{'':<16}{r['honest_line']}")
        if k < len(ladder["warps"]):
            lines.append(f"{'':<6}~ warp: {ladder['warps'][k]['device']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- media helpers
def _ff():
    return shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg", shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def probe(path):
    _, fp = _ff()
    out = json.loads(subprocess.check_output([fp, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    dur = float(v.get("duration") or out["format"]["duration"])
    return {"w": int(v["width"]), "h": int(v["height"]), "dur": dur, "audio": any(s["codec_type"] == "audio" for s in out["streams"])}


def _font(size):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default(size)


def text_png(path, txt, size, w, pad=48):
    """Classic W13 caption: bold white, dark stroke, centred, wrapped."""
    f = _font(size)
    d = ImageDraw.Draw(Image.new("RGBA", (w, 10)))
    lines, cur = [], ""
    for wd in txt.split():
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=f) > w - 2 * pad and cur:
            lines.append(cur); cur = wd
        else:
            cur = trial
    lines.append(cur)
    img = Image.new("RGBA", (w, int(size * 1.25 * len(lines)) + 16), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        d.text(((w - d.textlength(ln, font=f)) / 2, 4 + k * size * 1.25), ln, font=f, fill="white",
               stroke_width=max(3, size // 10), stroke_fill=(10, 10, 10))
    img.save(path)
    return img.size


def label_png(path, txt, W):
    f = _font(max(16, W // 34))
    tw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(txt, font=f))
    lab = Image.new("RGBA", (tw + 24, max(16, W // 34) + 18), (0, 0, 0, 120))
    ImageDraw.Draw(lab).text((12, 7), txt, font=f, fill="white")
    lab.save(path)


def end_card(path, W, H, lines, credit=True):
    card = Image.new("RGB", (W, H), (26, 22, 19)); d = ImageDraw.Draw(card)
    rows = [(lines[0], W // 11, .38)] + [(ln, W // 22, .38 + .075 * (k + 1)) for k, ln in enumerate(lines[1:]) if ln]
    if credit:
        rows.append(("made with Honest Downgrade for ComfyUI", W // 38, .90))
    for txt, size, y in rows:
        fo = _font(size)
        if d.textlength(txt, font=fo) > W * .88:
            fo = _font(max(10, int(size * W * .88 / d.textlength(txt, font=fo))))
        d.text(((W - d.textlength(txt, font=fo)) / 2, H * y), txt, font=fo, fill=(245, 236, 222))
    card.save(path)


# ---------------------------------------------------------------- the cheap local draft warp (no AI video, $0)
def draft_warp(first_png, last_png, device, out, secs=WARP_SECONDS, W=720, H=1280, fps=24):
    """A free animatic warp between two stills: hold the first frame, an ffmpeg transition chosen to read like the
    device, hold the last frame. For drafts and tests only; the real warp is generated motion (Veo first/last frame)."""
    ffmpeg, _ = _ff()
    t = DRAFT_TRANSITION.get(device, "dissolve")
    td, half = min(1.6, secs / 3), secs / 2
    sc = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},format=yuv420p"
    fc = (f"[0:v]{sc}[a];[1:v]{sc}[b];[a][b]xfade=transition={t}:duration={td:.2f}:offset={half - td / 2:.2f}[v]")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-loop", "1", "-t", f"{secs}", "-i", str(first_png), "-loop", "1", "-t", f"{secs}",
                    "-i", str(last_png), "-filter_complex", fc, "-map", "[v]", "-t", f"{secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", str(fps), str(out)], check=True)
    return Path(out)


# ---------------------------------------------------------------- the edit: 30 s master and 15 s cutdown
def plan_cut(durs, ladder, ending_len=0.0, length=30, end_min=2.0, card_max=3.5):
    """The edit decision list. durs: the 4 warp clip lengths. Returns segments [(kind, idx, t_in, t_out)] and captions
    [(start, end, text)] on the output timeline. 30 s: every warp in full, the real ending, the end card.
    15 s: brag, one warp, truth, payoff, end card, cut from the same clips (no new generation)."""
    cap = [r["caption"] for r in ladder["rungs"]]
    honest = ladder["rungs"][3].get("honest_line", "")
    segs, caps = [], []
    if length == 30:
        d = list(durs)
        ending_len = min(3.5, ending_len)
        over = sum(d) + ending_len + end_min - length
        if over > 0:   # trim the heads of warps 2-4: their first frame repeats the landing of the warp before
            cut = min(over / 3, min(d[1:]) / 3)
            heads = [0.0, cut, cut, cut]
        else:
            heads = [0.0] * 4
        t = 0.0
        starts = []
        for k in range(4):
            segs.append(("warp", k, heads[k], d[k])); starts.append(t); t += d[k] - heads[k]
        lens = [d[k] - heads[k] for k in range(4)]
        if ending_len:
            segs.append(("ending", 0, 0.0, ending_len))
        end_at = t + ending_len
        card = max(end_min, min(card_max, length - end_at))
        segs.append(("card", 0, 0.0, card))
        for k in range(4):   # rung k lands at the end of warp k-1 and leaves halfway through warp k
            a = 0.25 if k == 0 else starts[k] - 0.5
            b = starts[k] + (0.45 if k == 3 and honest else 0.55) * lens[k]
            caps.append((a, b, cap[k]))
        if honest:
            caps.append((caps[-1][1], starts[3] + lens[3] - 0.7, honest))
        caps.append((starts[3] + lens[3] - 0.6, end_at + card - 0.4, cap[4]))   # the payoff stays up over the end card
        return segs, caps, end_at
    if length == 15:
        a_len, b_len = min(3.0, durs[0] * 0.5), min(2.0, durs[2] * 0.4)
        ending_len = min(2.0, ending_len)
        segs = [("warp", 0, 0.0, a_len), ("warp", 2, durs[2] - b_len, durs[2]), ("warp", 3, 0.0, durs[3])]
        t3 = a_len + b_len
        if ending_len:
            segs.append(("ending", 0, 0.0, ending_len))
        end_at = t3 + durs[3] + ending_len
        card = max(end_min, min(4.0, length - end_at))
        segs.append(("card", 0, 0.0, card))
        caps = [(0.25, a_len - 0.1, cap[0]), (a_len + 0.2, t3 + 0.5 * durs[3], cap[3]), (t3 + durs[3] - 0.6, end_at + card - 0.4, cap[4])]
        return segs, caps, end_at
    raise ValueError("length must be 30 or 15")


def _bed_expr(total, drop):
    """A simple, original synth bed (pad chords + soft kick, 96 BPM), generated here so it carries no licence. The
    kick stops and the pad dips under the honest line (the music drop, block B36)."""
    a, b = drop if drop else (-1, -1)
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]
    def pick(i):
        return "+".join(f"if(eq(floor(mod(t/2.5,4)),{k}),{c[i]},0)" for k, c in enumerate(chords))
    pad = "+".join(f"0.06*sin(2*PI*({pick(i)})*t)" for i in range(3))
    x = "mod(t,0.625)"
    kick = f"0.35*sin(2*PI*(50+60*exp(-30*{x}))*{x})*exp(-9*{x})"
    hat = "0.02*(random(0)-0.5)*exp(-40*mod(t+0.3125,0.625))"
    inside = f"between(t,{a:.2f},{b:.2f})"
    return f"({pad})*(1-0.55*{inside})+({kick}+{hat})*(1-{inside})"


def assemble(clips, ladder, out, work, ending_path=None, length=30, captions=True, ai_label=True, credit=True,
             music_path=None, music_db=-6.0, fps=24, W=None, H=None):
    """Cut the warps (+ the optional real ending photo or clip) into one 9:16 H.264 MP4 with classic captions, an
    'AI-generated' label on the AI shots, a 'Real' label on the real ending, an end card, sound and -14 LUFS loudness.
    Sound: your own licensed track (music_path) or the built-in synth bed, plus a soft whoosh at every warp."""
    ffmpeg, _ = _ff()
    work = Path(work); ov = work / "ov"; ov.mkdir(parents=True, exist_ok=True)
    info = [probe(c) for c in clips]
    if len(clips) != 4:
        raise ValueError(f"need 4 warp clips, got {len(clips)}")
    W = W or (info[0]["w"] - info[0]["w"] % 2); H = H or (info[0]["h"] - info[0]["h"] % 2)
    ending = None
    if ending_path:
        ending = Path(ending_path)
        if not ending.is_file():
            raise ValueError(f"ending file not found: {ending}")
    is_video_end = ending is not None and ending.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm")
    end_len = (probe(ending)["dur"] if is_video_end else 6.0) if ending is not None else 0.0
    segs, caps, end_at = plan_cut([i["dur"] for i in info], ladder, ending_len=end_len, length=length)
    total = sum(b - a for _, _, a, b in segs)
    b = ladder["business_name"]
    end_card(ov / "endcard.png", W, H, [b, ladder["facts"].get("honest_line") or ladder["rungs"][3]["caption"],
                                         "AI-made places, real ending" if ending else "AI-generated places"], credit)
    inp, fc = [], []
    for c in clips:
        inp += ["-i", str(c)]
    n_in = len(clips)
    end_idx = card_idx = None
    if ending is not None:
        inp += (["-i", str(ending)] if is_video_end else ["-loop", "1", "-t", "6", "-i", str(ending)]); end_idx = n_in; n_in += 1
    inp += ["-loop", "1", "-t", f"{length}", "-i", str(ov / "endcard.png")]; card_idx = n_in; n_in += 1
    sc = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},format=yuv420p"
    labels = []
    t = 0.0
    seg_times = []
    for k, (kind, idx, a, bb) in enumerate(segs):
        src = idx if kind == "warp" else (end_idx if kind == "ending" else card_idx)
        fc.append(f"[{src}:v]trim=start={a:.3f}:end={bb:.3f},setpts=PTS-STARTPTS,{sc},settb=AVTB[s{k}]")
        seg_times.append((kind, t, t + bb - a)); t += bb - a
    fc.append("".join(f"[s{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[base]")
    base, extra, idx = "base", [], n_in
    if ai_label:
        label_png(ov / "ai.png", "AI-generated", W)
        label_png(ov / "real.png", "Real photo" if not is_video_end else "Real footage", W)
        ai_end = next(s for s in seg_times if s[0] != "warp")[1]
        extra += ["-i", str(ov / "ai.png")]
        fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='lt(t,{ai_end:.3f})'[l0]"); base = "l0"; idx += 1
        labels.append(("AI-generated", 0.0, ai_end))
        if ending is not None:
            es = next(s for s in seg_times if s[0] == "ending")
            extra += ["-i", str(ov / "real.png")]
            fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='between(t,{es[1]:.3f},{es[2]:.3f})'[l1]"); base = "l1"; idx += 1
            labels.append(("Real", es[1], es[2]))
    cues = caps if captions else []
    cap_size = max(30, W // 14)
    for k, (a, bb, txt) in enumerate(cues):
        text_png(ov / f"cap{k:02d}.png", txt, cap_size, W)
        extra += ["-i", str(ov / f"cap{k:02d}.png")]
        fc.append(f"[{base}][{idx}:v]overlay=(W-w)/2:H*0.16:enable='between(t,{a:.3f},{bb:.3f})'[c{k}]"); base = f"c{k}"; idx += 1
    # ---- sound
    warp_mids = [s[1] + (s[2] - s[1]) / 2 for s in seg_times if s[0] == "warp"]
    drop = None
    if ladder.get("tone") == "heartfelt" and ladder["rungs"][3].get("honest_line"):
        hl = [c for c in cues or caps if c[2] == ladder["rungs"][3]["honest_line"]]
        drop = (hl[0][0] - 0.3, hl[0][1]) if hl else None
    if music_path:
        mp = Path(music_path)
        if not mp.is_file():
            raise ValueError(f"music_path does not exist: {mp}")
        extra += ["-stream_loop", "-1", "-i", str(mp)]
        vol = f"volume='{10 ** (music_db / 20):.3f}*(1-0.7*between(t,{drop[0]:.2f},{drop[1]:.2f}))':eval=frame" if drop else f"volume={music_db}dB"
        fc.append(f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,{vol}[bed]")
        idx += 1
    else:
        fc.append(f"aevalsrc='{_bed_expr(total, drop)}':s=48000:d={total:.3f},aformat=sample_fmts=fltp:channel_layouts=stereo[bed]")
    mix = ["[bed]"]
    for k, m in enumerate(warp_mids):
        fc.append(f"anoisesrc=color=pink:amplitude=0.5:d=0.9:r=48000,bandpass=f=1200:width_type=o:w=2,afade=t=in:d=0.45,"
                  f"afade=t=out:st=0.45:d=0.45,volume=0.5,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"adelay={int(max(0, m - 0.45) * 1000)}|{int(max(0, m - 0.45) * 1000)}[w{k}]")
        mix.append(f"[w{k}]")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0,afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2,"
              f"loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000,atrim=0:{total:.3f}[aout]")
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + extra + ["-filter_complex", ";".join(fc), "-map", f"[{base}]", "-map", "[aout]",
           "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    (work / f"ffmpeg_cmd_{length}.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    receipt = {"length": length, "total": round(total, 3), "size": [W, H], "segments": segs, "captions": cues, "labels": labels,
               "music": str(music_path) if music_path else "built-in synth bed", "drop": drop, "ending": str(ending) if ending else None}
    (work / f"receipt_{length}.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def board(images, captions, out, tw=270, th=480):
    """All rung stills side by side with their captions: the draft board you approve before any paid video."""
    sheet = Image.new("RGB", (len(images) * tw, th + 70), (24, 21, 18)); d = ImageDraw.Draw(sheet)
    f = _font(15)
    for k, (im, cap) in enumerate(zip(images, captions)):
        im = im.convert("RGB"); im.thumbnail((tw, th), Image.LANCZOS)
        sheet.paste(im, (k * tw + (tw - im.width) // 2, (th - im.height) // 2))
        words, line, y = cap.split(), "", th + 8
        for wd in words:
            if d.textlength(line + " " + wd, font=f) > tw - 16 and line:
                d.text((k * tw + 8, y), line, font=f, fill=(240, 232, 220)); y += 19; line = wd
            else:
                line = (line + " " + wd).strip()
        d.text((k * tw + 8, y), line, font=f, fill=(240, 232, 220))
    if out:
        sheet.save(out)
    return sheet
