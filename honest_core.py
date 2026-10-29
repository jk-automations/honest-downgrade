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
    "flour cloud": "a cloud of flour puffs up, fills the whole frame, then settles to reveal",
    "water splash": "a burst of clean water splashes across the lens, then drains away to reveal",
    "bubble burst": "a wall of soap bubbles rises across the lens, then pops all at once to reveal",
    "page flip": "the whole frame turns like a giant book page to reveal",
    "chalk dust": "a puff of chalk dust blows across the lens, then clears to reveal",
    "box unfold": "a cardboard box unfolds flat across the lens and refolds into",
}
GENERIC_DEVICES = ["pop-up fold", "flock burst", "push-through window", "melt", "pull-back reveal"]
# The cheap local draft (no AI video) maps each device to an ffmpeg transition so the animatic still reads as that device.
DRAFT_TRANSITION = {"ribbon snake": "slideleft", "steam swirl": "fadewhite", "flying ingredients": "pixelize", "blueprint fold": "vertclose",
                    "paint wave": "wipeup", "tool-belt burst": "circleopen", "towel wipe": "wiperight", "mirror shatter": "pixelize",
                    "petal confetti": "dissolve", "elevator drop": "slideup", "paper-plane swarm": "slideright", "screen pull": "smoothleft",
                    "pop-up fold": "horzclose", "flock burst": "circleopen", "push-through window": "zoomin", "pull-back reveal": "circleclose",
                    "melt": "dissolve", "flour cloud": "fadewhite", "water splash": "wipedown", "bubble burst": "circleopen",
                    "page flip": "slideleft", "chalk dust": "fadewhite", "box unfold": "vertopen"}

# ---------------------------------------------------------------- the joke ladders: three templates for any business
# The same three ladders serve every business. The business type fills the nouns: brag (impossible scale), downgrade 1
# (cut the number), downgrade 2 (cut the fancy thing to one humble thing). Each rung is (caption, visual, sign).
# visual = what the frame must show so the caption is literally true (block B35); the numbers are in the template, so a
# caption's number is always in its visual. sign = short sign text, may be "".
LADDER_TEMPLATES = [
    [("Our 200th {place} just opened.", "a gleaming grand-opening plaza in front of {big_place}, a huge red ribbon across the doors, a banner over the entrance", "200TH {PLACE}"),
     ("Ok, it's 2 {places}.", "exactly 2 {two_places}, side by side, both lit", "2 {PLACES}"),
     ("Ok, it's one {one}.", "{one_visual}", "")],
    [("We have 40 {units}.", "{big_hall} with 40 identical {units} in long rows", "40 {UNITS}"),
     ("Ok, it's 4 {units}.", "exactly 4 {units} {small_spot}", ""),
     ("Ok, no {units}. One {tool}.", "{tool_visual}", "")],
    [("Our crew is 50 strong.", "{crew_hall} with 50 {crew_items} in long rows", "50 {CREW_ITEMS}"),
     ("Ok, it's 5 {crew_items}.", "exactly 5 {crew_items} {crew_spot}", ""),
     ("Ok, no crew. One {solo}.", "{solo_visual}", "")],
]
TEMPLATE_SLOTS = ["place", "places", "big_place", "two_places", "one", "one_visual", "units", "big_hall", "small_spot", "tool",
                  "tool_visual", "crew_items", "crew_hall", "crew_spot", "solo", "solo_visual"]

# ---------------------------------------------------------------- business types (the preset table)
# One row per kind of small business, storefront or not. kind = how prompts name the business (a business, never a
# person, so image models are not nudged to draw one). offer / setting / audience are the defaults for those inputs.
# example = sample true facts (truth, honest line, payoff) used for tooltips, tests and docs; all fictional.
# devices = the three wild-card warps that fit this business; slots fill LADDER_TEMPLATES.
# No slot or default names people: AI stills show places and things only.
BUSINESS_TYPES = {
    "food-truck": {
        "label": "Food truck", "kind": "food truck", "storefront": False,
        "offer": "street food made to order", "setting": "a truck parked wherever the evening crowd is",
        "audience": "hungry locals and night-shift workers nearby",
        "hero": "the signature dish in a tight close-up, steam rising, on a plain paper tray",
        "example": ("a truck in a gas station parking lot", "Started with $800 and my mom's recipes.", "The line at 11pm is real."),
        "devices": ["ribbon snake", "steam swirl", "flying ingredients"],
        "slots": {"place": "location", "places": "locations", "big_place": "a giant restaurant tower",
                  "two_places": "small identical restaurants on a quiet street", "one": "window",
                  "one_visual": "one small service window in a plain painted wall, a chalk menu board beside it",
                  "units": "tables", "big_hall": "a vast dining hall under chandeliers",
                  "small_spot": "with folding chairs on a sidewalk, string lights above", "tool": "counter",
                  "tool_visual": "one short counter with a napkin holder and a hot-sauce bottle, nothing else",
                  "crew_items": "aprons", "crew_hall": "a huge back-of-house corridor", "crew_spot": "on hooks by a back door",
                  "solo": "spatula", "solo_visual": "one well-worn spatula resting on a seasoned flat-top grill"},
    },
    "bakery": {
        "label": "Bakery", "kind": "bakery", "storefront": True,
        "offer": "bread and pastries baked fresh every morning", "setting": "a small bakery that opens at 6am",
        "audience": "neighbours on the way to work",
        "hero": "a golden loaf just out of the oven, crust cracked, on a wooden board, steam rising",
        "example": ("a rented kitchen from 3am to 7am", "I bake every loaf myself before sunrise.", "We sell out by 9am most days."),
        "devices": ["flour cloud", "steam swirl", "ribbon snake"],
        "slots": {"place": "bakery", "places": "bakeries", "big_place": "a giant glass pastry palace",
                  "two_places": "small identical bakeries on a quiet street", "one": "oven",
                  "one_visual": "one small oven with a single batch of rolls inside, warm light",
                  "units": "ovens", "big_hall": "a vast industrial bakery hall", "small_spot": "in a small tiled room",
                  "tool": "mixing bowl", "tool_visual": "one big mixing bowl dusted with flour on a wooden counter",
                  "crew_items": "aprons", "crew_hall": "a huge flour-dusted corridor", "crew_spot": "on hooks by an oven",
                  "solo": "rolling pin", "solo_visual": "one well-worn wooden rolling pin on a floured counter"},
    },
    "plumber": {
        "label": "Plumber (no storefront)", "kind": "plumbing business", "storefront": False,
        "offer": "leak repairs, drains and new installs", "setting": "on call across town, working in homes and small offices",
        "audience": "homeowners and landlords nearby",
        "hero": "a gleaming new copper pipe fitting under a clean sink, dry and tidy",
        "example": ("a van and a phone that never stops ringing", "My dad taught me on weekends.", "Same-day callbacks, every time."),
        "devices": ["water splash", "tool-belt burst", "blueprint fold"],
        "slots": {"place": "branch", "places": "branches", "big_place": "a giant glass plumbing headquarters tower",
                  "two_places": "small plain workshop garages", "one": "van",
                  "one_visual": "one plain white work van parked on a quiet residential street, a ladder on its roof rack",
                  "units": "work trucks", "big_hall": "a vast depot lot", "small_spot": "parked in a row on a driveway",
                  "tool": "toolbox", "tool_visual": "one well-worn toolbox on a garage floor",
                  "crew_items": "hard hats", "crew_hall": "a huge equipment yard", "crew_spot": "on a workbench",
                  "solo": "wrench", "solo_visual": "one well-worn pipe wrench on a garage floor"},
    },
    "dentist": {
        "label": "Dentist", "kind": "dental practice", "storefront": True,
        "offer": "check-ups, cleanings and fillings", "setting": "a small two-chair practice",
        "audience": "families who keep putting off the dentist",
        "hero": "a spotless dental chair under a bright lamp, instruments laid out neatly on a white cloth",
        "example": ("two chairs above a laundromat", "I opened it with my sister after dental school.", "Most fillings done in 30 minutes."),
        "devices": ["bubble burst", "screen pull", "elevator drop"],
        "slots": {"place": "clinic", "places": "clinics", "big_place": "a giant glass medical tower",
                  "two_places": "small bright clinics on a quiet street", "one": "chair",
                  "one_visual": "one dental chair under a single bright lamp in a small calm room",
                  "units": "dental chairs", "big_hall": "a vast white treatment hall", "small_spot": "in a small bright room",
                  "tool": "mirror", "tool_visual": "one small round dental mirror on a clean white cloth",
                  "crew_items": "white coats", "crew_hall": "a huge white corridor", "crew_spot": "on hooks by a door",
                  "solo": "stool", "solo_visual": "one rolling stool beside a dental chair"},
    },
    "dog-groomer": {
        "label": "Dog groomer (mobile)", "kind": "mobile dog grooming business", "storefront": False,
        "offer": "baths, trims and nail clips for dogs", "setting": "a grooming van that comes to your street",
        "audience": "busy dog owners",
        "hero": "a freshly groomed, fluffy dog sitting on a clean towel, a bow on its collar",
        "example": ("a converted van with one tub", "I quit my office job to do this.", "Every dog goes home with a bow."),
        "devices": ["bubble burst", "towel wipe", "petal confetti"],
        "slots": {"place": "grooming spa", "places": "grooming spas", "big_place": "a giant pet resort tower",
                  "two_places": "small pastel grooming spas", "one": "van",
                  "one_visual": "one small converted grooming van at a curb, its side door open to a tiny tub",
                  "units": "bathtubs", "big_hall": "a vast tiled wash hall", "small_spot": "in a small tiled room",
                  "tool": "hose", "tool_visual": "one coiled hose next to a small folding grooming table",
                  "crew_items": "aprons", "crew_hall": "a huge pet resort corridor", "crew_spot": "on hooks inside a van door",
                  "solo": "brush", "solo_visual": "one well-used slicker brush on a folded towel"},
    },
    "tutor": {
        "label": "Tutor (no storefront)", "kind": "tutoring business", "storefront": False,
        "offer": "one-to-one maths and reading lessons", "setting": "online and at a quiet desk at home",
        "audience": "parents of children who are falling behind",
        "hero": "an open notebook with a fully solved maths problem and a gold star sticker, a pencil beside it",
        "example": ("my laptop and a lot of patience", "I failed maths once, too.", "Every lesson ends with one thing they got right."),
        "devices": ["page flip", "chalk dust", "paper-plane swarm"],
        "slots": {"place": "campus", "places": "campuses", "big_place": "a giant glass learning academy",
                  "two_places": "small brick classroom buildings", "one": "desk",
                  "one_visual": "one small desk with a laptop, a notebook and a pencil cup",
                  "units": "classrooms", "big_hall": "a vast school building", "small_spot": "along one short corridor",
                  "tool": "whiteboard", "tool_visual": "one small whiteboard on an easel with a solved sum on it",
                  "crew_items": "lanyards", "crew_hall": "a huge reception hall", "crew_spot": "on a desk",
                  "solo": "pencil", "solo_visual": "one well-chewed pencil on an open notebook"},
    },
    "salon": {
        "label": "Hair salon", "kind": "hair salon", "storefront": True,
        "offer": "cuts, colour and blow-dries", "setting": "a small salon with room for two",
        "audience": "regulars who like a chat",
        "hero": "a styling station ready for the next appointment, warm light, scissors and a comb laid out",
        "example": ("one chair in my garage", "My grandma cut hair for 40 years.", "Booked out every Saturday."),
        "devices": ["mirror shatter", "petal confetti", "towel wipe"],
        "slots": {"place": "salon", "places": "salons", "big_place": "a giant glass beauty tower",
                  "two_places": "small pastel salons on a quiet street", "one": "chair",
                  "one_visual": "one styling chair in front of a single mirror",
                  "units": "hair dryers", "big_hall": "a vast mirrored hall", "small_spot": "on a small shelf",
                  "tool": "comb", "tool_visual": "one wide-tooth comb on a folded towel",
                  "crew_items": "capes", "crew_hall": "a huge mirrored corridor", "crew_spot": "on hooks by a mirror",
                  "solo": "pair of scissors", "solo_visual": "one pair of scissors on a folded towel"},
    },
    "gym": {
        "label": "Gym", "kind": "small gym", "storefront": True,
        "offer": "small-group strength classes", "setting": "a converted garage unit",
        "audience": "beginners who hate big gyms",
        "hero": "a clean row of kettlebells on a rubber floor in morning light",
        "example": ("a garage with six kettlebells", "I started coaching after my own knee surgery.", "Our 6am class has a waitlist."),
        "devices": ["towel wipe", "elevator drop", "mirror shatter"],
        "slots": {"place": "gym", "places": "gyms", "big_place": "a giant glass fitness tower",
                  "two_places": "small brick gyms", "one": "garage",
                  "one_visual": "one roll-up garage door half open to a rubber floor and a single rack",
                  "units": "machines", "big_hall": "a vast gym hall", "small_spot": "in a small bright room",
                  "tool": "mat", "tool_visual": "one exercise mat rolled out on a wooden floor",
                  "crew_items": "water bottles", "crew_hall": "a huge gym corridor", "crew_spot": "on a bench",
                  "solo": "kettlebell", "solo_visual": "one well-used kettlebell on a rubber floor"},
    },
    "online-seller": {
        "label": "Online seller (no storefront)", "kind": "online shop", "storefront": False,
        "offer": "poured soy candles shipped nationwide", "setting": "packed at home in a spare room",
        "audience": "gift buyers who shop online",
        "hero": "a finished soy candle in its gift box with tissue paper, on a clean table in soft daylight",
        "example": ("a spare bedroom full of boxes", "The first 30 orders were all my friends.", "Every order ships within 24 hours."),
        "devices": ["box unfold", "paper-plane swarm", "screen pull"],
        "slots": {"place": "warehouse", "places": "warehouses", "big_place": "a giant automated warehouse",
                  "two_places": "small plain storage units", "one": "shelf",
                  "one_visual": "one shelf in a spare room, stacked with small boxes",
                  "units": "packing stations", "big_hall": "a vast fulfilment hall", "small_spot": "in a small spare room",
                  "tool": "tape gun", "tool_visual": "one tape gun beside a single half-packed box on a table",
                  "crew_items": "label printers", "crew_hall": "a huge open-plan office", "crew_spot": "on one long desk",
                  "solo": "laptop", "solo_visual": "one laptop on a table with a shipping label beside it"},
    },
    "other": {
        "label": "Other (describe the offer and setting)", "kind": "small business", "storefront": False,
        "offer": "", "setting": "", "audience": "",
        "hero": "",   # built from the offer
        "example": ("a laptop at the end of a table", "I started this on weekends.", "Every message gets a reply the same day."),
        "devices": ["elevator drop", "paper-plane swarm", "screen pull"],
        "slots": {"place": "office", "places": "offices", "big_place": "a giant glass headquarters tower",
                  "two_places": "small plain offices on a quiet street", "one": "room",
                  "one_visual": "one small room with a single desk, a lamp and a chair",
                  "units": "desks", "big_hall": "a vast open-plan office", "small_spot": "pushed together in a small room",
                  "tool": "laptop", "tool_visual": "one laptop on a plain table, a mug beside it",
                  "crew_items": "name badges", "crew_hall": "a huge reception hall", "crew_spot": "on one small desk",
                  "solo": "notebook", "solo_visual": "one well-used notebook and a pen on a plain desk"},
    },
}
TYPE_KEYS = list(BUSINESS_TYPES)
TYPE_CHOICES = [t["label"] for t in BUSINESS_TYPES.values()]


def business_type_key(value):
    """'plumber', 'Plumber (no storefront)' or 'online seller' -> the BUSINESS_TYPES key."""
    v = (value or "").strip().lower()
    for k, t in BUSINESS_TYPES.items():
        if v in (k, k.replace("-", " "), t["label"].lower()):
            return k
    raise ValueError(f"Pick a business type: {TYPE_KEYS} (or 'other' and describe the offer and setting).")


def fill_ladder(slots, variant):
    """One of the three ladder templates, filled with a business type's nouns."""
    vals = dict(slots)
    vals.update({k.upper(): v.upper() for k, v in slots.items()})
    return [{"caption": c.format(**vals), "visual": v.format(**vals), "sign": s.format(**vals)}
            for c, v, s in LADDER_TEMPLATES[variant - 1]]


BRANDS = {"ferrari", "lamborghini", "lambo", "porsche", "mclaren", "bugatti", "tesla", "bmw", "mercedes", "audi", "starbucks",
          "mcdonald's", "mcdonalds", "dunkin", "nike", "adidas", "apple", "iphone", "instagram", "tiktok", "youtube", "facebook",
          "google", "coca-cola", "pepsi", "gucci", "rolex", "uber", "doordash", "shell", "chevron", "carhartt", "ikea", "walmart"}
# AI changes places and things, never people: real people appear only in the real ending photo or clip.
PEOPLE = ["person", "people", "man", "men", "woman", "women", "crowd", "chef", "chefs", "cook", "customer", "customers", "owner",
          "worker", "workers", "staff", "face", "faces", "hand", "hands", "kid", "kids", "child", "girl", "boy", "guy", "lady",
          "barber", "stylist", "trainer", "client", "clients", "employee", "employees", "family", "couple", "selfie",
          "patient", "patients", "student", "students", "pupil", "pupils"]
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


def _a(noun):
    return ("an " if noun[:1].lower() in "aeiou" else "a ") + noun


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
def make_brief(business_name, business_type, true_setup, honest_line, real_proof, hero_thing="", tone="heartfelt", variant=1,
               avoid_devices="", model="veo-3.1-lite", source="template", offer="", setting="", audience=""):
    """The business's inputs -> the brief every later step reads. business_type picks the preset row (nouns for the joke
    ladder, the wild cards that fit); offer / setting / audience are the business's own words (empty = the type's
    defaults) and fill the writer prompt, the keyframe prompts and the default payoff still."""
    key = business_type_key(business_type)
    bt = BUSINESS_TYPES[key]
    facts = {"true_setup": true_setup.strip().rstrip("."), "real_proof": real_proof.strip(), "honest_line": honest_line.strip()}
    ex = bt["example"]
    if not facts["true_setup"]:
        raise ValueError(f"Tell us the real setup (the truth rung), e.g. '{ex[0]}'.")
    if not facts["real_proof"]:
        raise ValueError(f"Give one real proof people can see (the payoff), e.g. '{ex[2]}'")
    tone = tone if tone in TONES else "heartfelt"
    if tone == "heartfelt" and not facts["honest_line"]:
        tone = "playful"   # the honest beat needs a true line from the business; we never invent one
    ctx = {"offer": (offer or "").strip().rstrip(".") or bt["offer"], "setting": (setting or "").strip().rstrip(".") or bt["setting"],
           "audience": (audience or "").strip().rstrip(".") or bt["audience"]}
    if key == "other" and not ctx["offer"]:
        raise ValueError("For 'other', say what the business offers (e.g. 'wedding photo albums', 'bike repairs').")
    for k, v in list(facts.items()) + list(ctx.items()) + [("business_name", business_name), ("hero_thing", hero_thing)]:
        if brands_in(v):
            raise ValueError(f"{k} names a real brand ({', '.join(brands_in(v))}). Use plain, unbranded words.")
    hero = hero_thing.strip() or bt["hero"] or f"{ctx['offer']}: the finished result in a clean, bright close-up, on a plain table in soft daylight"
    avoid = sorted({d.strip().lower() for d in avoid_devices.split(",") if d.strip()})
    return {"business_name": business_name.strip() or "Your Business", "business_type": key, "kind": bt["kind"], **ctx,
            "facts": facts, "hero_thing": hero, "tone": tone, "variant": max(1, min(3, int(variant))),
            "avoid_devices": avoid, "model": model, "source": source}


def type_brief(business_type, business_name="Sample Business", **kw):
    """A brief from a business type's own example facts (docs, tests, quick tries)."""
    setup, honest, proof = BUSINESS_TYPES[business_type_key(business_type)]["example"]
    args = dict(true_setup=setup, honest_line=honest, real_proof=proof)
    args.update(kw)
    return make_brief(business_name, business_type, **args)


def device_order(brief):
    """Every device that fits this business type, its own wild cards first, rotated by the joke variant, minus the ones
    this client already used. The template writer takes the first four."""
    own = BUSINESS_TYPES[brief["business_type"]]["devices"]
    pool = own + [d for d in GENERIC_DEVICES if d not in own]
    k = (brief["variant"] - 1) % len(own)
    pool = pool[k:len(own)] + pool[:k] + pool[len(own):]
    return [d for d in pool if d not in brief["avoid_devices"]]


# ---------------------------------------------------------------- the ladder writers
def template_joke(brief):
    """The deterministic offline writer: the ladder template for this variant, filled with the business type's nouns,
    and four distinct warps."""
    rungs = fill_ladder(BUSINESS_TYPES[brief["business_type"]]["slots"], brief["variant"])
    devs = device_order(brief)
    if len(devs) < 4:
        raise ValueError("Not enough unused warp devices left for this client (need 4). Clear some from 'already used'.")
    return {"rungs": rungs, "warps": [{"device": d, "motion": DEVICES[d]} for d in devs[:4]]}


def writer_prompt(brief):
    example = template_joke(brief)
    allowed = device_order(brief)
    f = brief["facts"]
    return f"""You write the joke for an "I'm so sorry I lied" short video ad for a real small business.
Business: {brief['business_name']}, {_a(brief['kind'])}.
What it offers: {brief['offer']}.
Where the work really happens: {brief['setting'] or 'not given'}.
Who it is for: {brief['audience'] or 'not given'}.
The TRUE setup, the last rung, is fixed: "{f['true_setup']}". The real proof, the payoff, is fixed: "{f['real_proof']}".

Write the first three rungs: a brag at impossible scale, downgrade 1 that cuts the number, downgrade 2 that cuts the fancy
thing. Each one gets the next rung closer to the truth. Make the brag something this kind of business would dream of, in its
own world, never borrowed from another trade. Then pick four wild-card warps, one for each step between the five
rungs (brag > downgrade 1 > downgrade 2 > truth > payoff), all different.

Rules:
- "caption": what appears on screen, at most {MAX_CAPTION_WORDS} words, casual ("{example['rungs'][1]['caption']}").
- "visual": a place or a thing only, never people (no faces, hands, crowds, staff, customers). It must make the caption
  literally true at a glance: if the caption says 2 of something, the visual shows exactly two. Every number in the caption is in the visual.
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
    ladder = {"business_name": brief["business_name"], "business_type": brief["business_type"], "kind": brief["kind"],
              "offer": brief["offer"], "setting": brief["setting"], "audience": brief["audience"], "tone": brief["tone"],
              "rungs": rungs, "warps": warps, "facts": f}
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
    """The still for rung k, filled from the ladder and the business's own inputs (kind, offer, setting)."""
    r = ladder["rungs"][k]
    sign = f' A plain sign in the frame reads exactly "{r["sign"]}", spelled correctly, clean lettering.' if r.get("sign") else ""
    place = "" if r["role"] != "payoff" else " Product or finished-work hero shot."
    world = ""
    if ladder.get("kind"):
        world = f"\nThe business: {_a(ladder['kind'])}" + (f" offering {ladder['offer']}" if ladder.get("offer") else "") + "."
    if r["role"] == "truth" and ladder.get("setting"):
        world += f" Where it really happens: {ladder['setting']}."
    return (f"{KEYFRAME_HEAD}{place}{world}\nShow: {r['visual']}.{sign}\nThe picture must make this line literally true at a glance: "
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
