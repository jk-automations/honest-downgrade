"""Honest Downgrade core: the brag-to-truth ladder (template or Gemini), its checks, the prompts, and the edit.
Pure Python + Pillow + ffmpeg, no ComfyUI imports, so it can be tested on its own. Apache-2.0.

The ladder is eight rungs and every rung lives inside a moving clip (no still-only rung):
brag (impossible scale) -> downgrade 1 (cut the number) -> downgrade 2 (cut the fancy thing) -> truth (the real, humble
setup) -> the sympathy beat: struggle (the 2 a.m. side of the job) -> heirloom (where it started, carrying the honest
line) -> the place of work -> the payoff hero (product macro). The owner's REAL photo, if given with consent, sits
between the place of work and the payoff and is never sent to any model.
The writer (template or Gemini) only writes the joke: the brag, two downgrades, three warps and the sympathy visuals.
The truth, the honest line and the payoff are the business's own facts and are copied in by code, never rewritten."""
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
PRESETS_DIR = ROOT / "presets"
FONT = ROOT / "fonts" / "Inter.ttf"
DEFAULT_PRESET = "taco-truck"

ROLES = ["brag", "downgrade_1", "downgrade_2", "truth", "struggle", "heirloom", "place", "payoff"]
JOKE_ROLES, SYMPATHY_ROLES = ROLES[:3], ["struggle", "heirloom"]
CAPTIONED = ["brag", "downgrade_1", "downgrade_2", "truth", "payoff"]     # must have a caption; heirloom carries the honest line
N_RUNGS = len(ROLES)
TONES = {"heartfelt": "The honest line lands on the heirloom and the music drops under it.",
         "playful": "Joke-forward and bright; the sympathy beat stays, without an honest line."}
VEO_MODELS = ["veo-3.1-lite", "veo-3.1-fast-generate", "veo-3.1-generate"]   # exact Veo3FirstLastFrameNode values
WARP_SECONDS = 6
# The seven moving clips: (first rung, last rung, kind, seconds). warp = wild-card or shock transformation; move = a quiet
# push for the sympathy beat; macro = the payoff hero (first frame = last frame, the motion is a drop, splash or steam).
SHOTS = [(0, 1, "warp", 6), (1, 2, "warp", 6), (2, 3, "warp", 6), (3, 4, "move", 4), (4, 5, "move", 4), (5, 6, "warp", 6),
         (7, 7, "macro", 4)]
N_CLIPS = len(SHOTS)
MAX_CAPTION_WORDS = 12
# Joins (from the approved plumber cut): a short dissolve where the frames match (every Veo clip starts on the frame the
# one before landed on), a longer one where the angle changes (into and out of the real photo, into the end card).
MATCHED_DISSOLVE, ANGLE_DISSOLVE, PHOTO_DISSOLVE = 0.3, 0.6, 0.8
PHOTO_SECONDS, CARD_SECONDS = 3.5, 2.6
BUILD_UP = "First second: slow push-in, anticipation; then the transformation: "

# ---------------------------------------------------------------- the warp menu
# The approved taco Reel's wild cards (creature, pop-up fold, flock burst, push through, melt, mask match-cut) and the
# approved plumber Reel's shock warps (a tool of the trade smashes the frame, a geyser, a tornado of the trade's tools).
# {trade_tool} / {trade_tools} / {material} come from the business type, so the shock warps fit any trade.
DEVICES = {
    "creature": "the most striking object in the frame comes alive as a giant creature, sweeps toward the lens until its body fills the frame, then slides away to reveal",
    "pop-up fold": "the whole scene folds flat like a paper pop-up book and collapses into",
    "flock burst": "a flock of birds bursts off the scene toward the lens, wings fill the frame, then scatter to reveal",
    "push-through door": "the camera glides forward and pushes straight through a doorway into",
    "melt": "the scene melts like warm wax and re-forms as",
    "mask match-cut": "the camera pushes into a dark round shape in the frame until it fills the lens, and the same shape opens out as part of",
    "tool smash": "a giant {trade_tool} swings in from the side and smashes the scene like a pane of glass, the shards fall away to reveal",
    "geyser": "a geyser of {material} erupts from the ground, fills the whole frame, then falls away to reveal",
    "tool tornado": "{trade_tools} lift off and spin into a tornado that fills the frame, then the tornado scatters to reveal",
}
SHOCK_DEVICES = ["tool smash", "geyser", "tool tornado"]
PLACE_DEVICE = "push-through door"       # the ending's push to the place of work (taco recipe), unless already used
MOVES = {3: "the light fades from day to night and the camera drifts slowly in to",
         4: "the camera drifts slowly across, a gentle rack focus, and settles on"}
# The free local draft (no AI video) maps each device to an ffmpeg transition so the animatic still reads as that device.
DRAFT_TRANSITION = {"creature": "slideleft", "pop-up fold": "horzclose", "flock burst": "circleopen", "push-through door": "zoomin",
                    "melt": "dissolve", "mask match-cut": "circleclose", "tool smash": "pixelize", "geyser": "wipeup",
                    "tool tornado": "radial", "move": "fade", "macro": "fade"}

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
        "devices": ["creature", "pop-up fold", "flock burst"],
        "trade_tool": "spatula", "trade_tools": "spatulas, tongs and squeeze bottles", "material": "steam",
        "struggle": "the truck's dark cab at 2 a.m., rain on the windshield, a phone buzzing upside down on the dash, a cold coffee in the cup holder",
        "heirloom": "an old, dented cast-iron pan with a worn wooden handle hanging on a hook inside the truck, warm light on it",
        "place": "the truck's service window glowing at night, a stack of empty paper trays on the ledge and a tip jar stuffed full",
        "hero_motion": "a lime wedge drops onto the dish, juice splashes, steam rises",
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
        "devices": ["geyser", "creature", "pop-up fold"],
        "trade_tool": "rolling pin", "trade_tools": "rolling pins, whisks and baking tins", "material": "flour",
        "struggle": "a small bakery kitchen at 3 a.m., one bare bulb on, dough rising under a cloth, an alarm clock on the shelf",
        "heirloom": "an old, cracked wooden dough bowl worn smooth by years of use, on a floured counter",
        "place": "the bakery's front door at dawn, lights on inside, cooling racks full of loaves seen through the glass",
        "hero_motion": "a dusting of flour falls onto the loaf, the crust crackles, steam rises",
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
        "devices": ["tool smash", "geyser", "tool tornado"],
        "trade_tool": "pipe wrench", "trade_tools": "copper pipes, wrenches and fittings", "material": "water",
        "struggle": "the dark cab of a work van at 2 a.m., rain on the windshield, a phone buzzing upside down on the dash, a cold coffee in the cup holder",
        "heirloom": "an old, worn pipe wrench with tape on its handle hanging inside a van door, next to a newer red one",
        "place": "the front door of a tidy house at dusk, the porch light on, a plain white work van parked at the curb",
        "hero_motion": "a single drop of clean water falls from a new faucet into a dry sink, a tiny splash, light glints on the copper",
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
        "devices": ["mask match-cut", "tool smash", "pop-up fold"],
        "trade_tool": "dental mirror", "trade_tools": "toothbrushes, floss and small dental mirrors", "material": "white foam",
        "struggle": "a small dental office after closing, one desk lamp on, a stack of paperwork and a cold cup of tea",
        "heirloom": "an old brass dental mirror in a worn leather case on a clean white cloth",
        "place": "the practice's front door at opening time, warm light inside, a stack of thank-you cards on the reception counter",
        "hero_motion": "a drop of water falls onto spotless steel instruments laid on a white cloth, a small splash, light glints off the steel",
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
        "devices": ["creature", "geyser", "flock burst"],
        "trade_tool": "grooming brush", "trade_tools": "brushes, combs and fluffy towels", "material": "soap bubbles",
        "struggle": "a grooming van at night, one small light on, a wet towel over the tub edge, a phone buzzing upside down on the seat",
        "heirloom": "an old, worn wooden-handled grooming brush on a folded towel",
        "place": "the grooming van's side door open at the curb in the morning, a row of fresh bows clipped along the door",
        "hero_motion": "a few soap bubbles drift past and pop, a small bow drops onto the towel, the fur catches the light",
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
        "devices": ["pop-up fold", "tool tornado", "flock burst"],
        "trade_tool": "pencil", "trade_tools": "pencils, rulers and paper sheets", "material": "paper sheets",
        "struggle": "a desk at midnight, one lamp on, a tall stack of marked worksheets and a cold mug",
        "heirloom": "an old, worn fountain pen resting on a well-used maths textbook",
        "place": "a quiet desk by a window in the morning, a closed laptop beside a wall of thank-you notes",
        "hero_motion": "a gold star sticker drops onto the solved problem, the page lifts slightly, light catches it",
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
        "devices": ["tool smash", "melt", "tool tornado"],
        "trade_tool": "pair of scissors", "trade_tools": "scissors, combs and hair clips", "material": "flower petals",
        "struggle": "an empty salon at 11 p.m., one light on, a broom leaning on the chair, a stack of bills on the counter",
        "heirloom": "an old pair of silver scissors in a worn leather case on a folded towel",
        "place": "the salon's front door in the morning, lights on inside, an appointment book lying open and full",
        "hero_motion": "a few soft petals drift down past the mirror, the light warms, the styling station gleams",
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
        "devices": ["tool smash", "geyser", "melt"],
        "trade_tool": "kettlebell", "trade_tools": "kettlebells, jump ropes and water bottles", "material": "chalk dust",
        "struggle": "a garage gym at 5 a.m., one bulb on, a mop and a bucket by the rack, a cold coffee on the bench",
        "heirloom": "an old, rusted kettlebell with a worn handle, sitting apart from the new ones",
        "place": "the roll-up garage door opening at sunrise, light pouring onto the rubber floor, a whiteboard covered in tally marks",
        "hero_motion": "a puff of chalk dust drifts across the kettlebells, the morning light rakes across them",
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
        "devices": ["tool tornado", "pop-up fold", "mask match-cut"],
        "trade_tool": "tape gun", "trade_tools": "boxes, tape rolls and tissue paper", "material": "packing peanuts",
        "struggle": "a spare room at 1 a.m., one desk lamp on, a mountain of unpacked boxes and a cold mug",
        "heirloom": "an old, worn notebook with the very first orders handwritten in it",
        "place": "a front door step in the morning, a neat stack of sealed parcels ready for pickup",
        "hero_motion": "a sheet of tissue paper floats down into the gift box, the light warms across it",
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
        "devices": ["pop-up fold", "melt", "flock burst"],
        "trade_tool": "stapler", "trade_tools": "papers, pens and paper clips", "material": "paper sheets",
        "struggle": "a desk at midnight, one lamp on, a closed laptop beside a stack of papers and a cold mug",
        "heirloom": "an old, worn notebook with the very first plans handwritten in it",
        "place": "the front door of a small office in the morning, the light on inside",
        "hero_motion": "",
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
             "No people. No captions, no subtitles, no new text. Sign lettering never changes mid-move: any sign already in "
             "a frame stays still and readable or leaves the frame whole. No real logos.")


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
    """The warp menu for this business type: its own three first, in the order of the approved Reels (taco: creature,
    pop-up fold, flock burst; plumber: tool smash, geyser, tool tornado), then the rest of the menu, minus the ones this
    client already used. The push to the place of work is kept for the ending. The joke variant changes the words, not
    the warps; 'already used' moves a client on to fresh warps."""
    own = BUSINESS_TYPES[brief["business_type"]]["devices"]
    pool = own + [d for d in DEVICES if d not in own and d != PLACE_DEVICE]
    return [d for d in pool if d not in brief["avoid_devices"]]


def device_motion(device, business_type):
    bt = BUSINESS_TYPES[business_type]
    return DEVICES[device].format(trade_tool=bt["trade_tool"], trade_tools=bt["trade_tools"].capitalize()
                                  if DEVICES[device].startswith("{trade_tools}") else bt["trade_tools"], material=bt["material"])


# ---------------------------------------------------------------- the ladder writers
def template_joke(brief):
    """The deterministic offline writer: the ladder template for this variant, filled with the business type's nouns,
    three distinct warps from the menu, and the business type's sympathy visuals (struggle, heirloom)."""
    bt = BUSINESS_TYPES[brief["business_type"]]
    rungs = fill_ladder(bt["slots"], brief["variant"])
    devs = device_order(brief)
    if len(devs) < 3:
        raise ValueError("Not enough unused warp devices left for this client (need 3). Clear some from 'already used'.")
    return {"rungs": rungs, "warps": [{"device": d, "motion": device_motion(d, brief["business_type"])} for d in devs[:3]],
            "sympathy": {"struggle": bt["struggle"], "heirloom": bt["heirloom"]}}


def writer_prompt(brief):
    example = template_joke(brief)
    allowed = device_order(brief)
    f = brief["facts"]
    return f"""You write the joke for an "I'm so sorry I lied" short video ad for a real small business.
Business: {brief['business_name']}, {_a(brief['kind'])}.
What it offers: {brief['offer']}.
Where the work really happens: {brief['setting'] or 'not given'}.
Who it is for: {brief['audience'] or 'not given'}.
The TRUE setup is fixed: "{f['true_setup']}". The real proof, the payoff, is fixed: "{f['real_proof']}".
The owner's honest line is fixed: "{f['honest_line'] or 'none'}".

Write the first three rungs: a brag at impossible scale, downgrade 1 that cuts the number, downgrade 2 that cuts the fancy
thing. Each one gets the next rung closer to the truth. Make the brag something this kind of business would dream of, in its
own world, never borrowed from another trade. Pick three warps, one for each step brag > downgrade 1 > downgrade 2 > truth,
all different. Then the sympathy beat, two quiet pictures that make a viewer feel for the business: "struggle" (the hard,
unseen side of the job, e.g. the 2 a.m. call) and "heirloom" (an object from where it all started that fits the honest line).

Rules:
- "caption": what appears on screen, at most {MAX_CAPTION_WORDS} words, casual ("{example['rungs'][1]['caption']}").
- "visual" and the sympathy pictures: places and things only, never people (no faces, hands, crowds, staff, customers).
  A visual must make its caption literally true at a glance: if the caption says 2 of something, the visual shows exactly
  two. Every number in the caption is in the visual.
- "sign": up to 3 words of sign text that proves the caption, or "". Only the three joke rungs may have signs.
- No real brands, logos, apps or car makers anywhere. No phone screens.
- Warps: pick "device" from {json.dumps(allowed)} (the shock warps hit hardest); "motion" says what the device does, ending
  in a verb phrase that leads into the next frame ("...then scatter to reveal"). Never repeat a device.

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
    """Joke (3 rungs + 3 warps + sympathy visuals, from the template or Gemini) + the business's facts -> the full,
    checked eight-rung ladder and its seven moving clips."""
    f = brief["facts"]
    bt = BUSINESS_TYPES[brief["business_type"]]
    if not isinstance(joke, dict) or not isinstance(joke.get("rungs"), list) or not isinstance(joke.get("warps"), list):
        raise ValueError("The joke must be an object with 'rungs' and 'warps' lists.")
    if len(joke["rungs"]) != 3:
        raise ValueError(f"Need exactly 3 joke rungs (brag, downgrade 1, downgrade 2), got {len(joke['rungs'])}.")
    if len(joke["warps"]) != 3:
        raise ValueError(f"Need exactly 3 joke warps (brag > downgrade 1 > downgrade 2 > truth), got {len(joke['warps'])}.")
    rungs = []
    for role, r in zip(JOKE_ROLES, joke["rungs"]):
        if not isinstance(r, dict):
            raise ValueError(f"{role}: not an object")
        rungs.append({"role": role, "caption": _sentence(str(r.get("caption", ""))), "visual": str(r.get("visual", "")).strip(),
                      "sign": str(r.get("sign") or "").strip().upper()})
    setup = f["true_setup"]
    rungs.append({"role": "truth", "caption": _sentence(f"Ok, it's {setup}" if not setup.lower().startswith(("it", "ok", "we", "our", "just")) else setup),
                  "visual": f"{setup}, exactly as it really is, plain and unbranded, a little humble and full of character", "sign": ""})
    sym = joke.get("sympathy") if isinstance(joke.get("sympathy"), dict) else {}
    honest = f["honest_line"] if brief["tone"] == "heartfelt" else ""
    rungs.append({"role": "struggle", "caption": "", "visual": str(sym.get("struggle") or bt["struggle"]).strip(), "sign": ""})
    rungs.append({"role": "heirloom", "caption": honest, "honest_line": honest,
                  "visual": str(sym.get("heirloom") or bt["heirloom"]).strip(), "sign": ""})
    rungs.append({"role": "place", "caption": "", "visual": bt["place"], "sign": ""})
    rungs.append({"role": "payoff", "caption": _sentence(f["real_proof"]), "visual": brief["hero_thing"], "sign": ""})
    warps = []
    for w in joke["warps"]:
        if not isinstance(w, dict) or not str(w.get("device", "")).strip():
            raise ValueError("Every warp needs a 'device'.")
        d = str(w["device"]).strip().lower()
        warps.append({"device": d, "motion": str(w.get("motion") or (device_motion(d, brief["business_type"]) if d in DEVICES else "")).strip()})
    used = {w["device"] for w in warps} | set(brief["avoid_devices"])
    place_dev = next((d for d in [PLACE_DEVICE] + list(DEVICES) if d not in used), None)
    if place_dev is None:
        raise ValueError("No unused warp left for the push to the place of work. Clear some from 'already used'.")
    warps.append({"device": place_dev, "motion": device_motion(place_dev, brief["business_type"])})
    hero_motion = bt["hero_motion"] or "the light slowly warms across it, a soft glint travels over the surface"
    shots, wi = [], 0
    for k, (a, b, kind, secs) in enumerate(SHOTS):
        if kind == "warp":
            shots.append({"kind": kind, "from": a, "to": b, "secs": secs, **warps[wi]}); wi += 1
        elif kind == "move":
            shots.append({"kind": kind, "from": a, "to": b, "secs": secs, "device": "move", "motion": MOVES[k]})
        else:
            shots.append({"kind": kind, "from": a, "to": b, "secs": secs, "device": "macro", "motion": hero_motion})
    ladder = {"business_name": brief["business_name"], "business_type": brief["business_type"], "kind": brief["kind"],
              "offer": brief["offer"], "setting": brief["setting"], "audience": brief["audience"], "tone": brief["tone"],
              "rungs": rungs, "warps": warps, "shots": shots, "facts": f}
    errs = check_ladder(ladder, brief)
    if errs:
        raise ValueError("The ladder broke the rules:\n- " + "\n- ".join(errs[:20]))
    return ladder


def check_ladder(ladder, brief):
    """All the rules, as a list of problems (empty = good). Same rules for the template and for Gemini."""
    errs = []
    rungs, warps, shots = ladder.get("rungs", []), ladder.get("warps", []), ladder.get("shots", [])
    if [r.get("role") for r in rungs] != ROLES:
        errs.append(f"rungs must be exactly {ROLES}")
    for r in rungs:
        w = r.get("role", "?")
        cap, vis = r.get("caption", ""), r.get("visual", "")
        if not vis.strip() or (w in CAPTIONED and not cap.strip()):
            errs.append(f"{w}: caption and visual must not be empty"); continue
        n = len(_words(cap))
        if n > MAX_CAPTION_WORDS and w in JOKE_ROLES:
            errs.append(f"{w}: caption has {n} words (max {MAX_CAPTION_WORDS})")
        if len(_words(r.get("sign", ""))) > 3:
            errs.append(f"{w}: sign text is more than 3 words")
        if r.get("sign") and w not in JOKE_ROLES:
            errs.append(f"{w}: only the joke rungs may carry sign text (signs scramble mid-move)")
        for b in brands_in(cap + " " + vis + " " + r.get("sign", "")):
            errs.append(f"{w}: real brand '{b}'")
        for p in people_in(vis):   # captions may mention people (the payoff is a real fact); AI stills never show them
            errs.append(f"{w}: the AI still may not show people ('{p}'); real people only in the real owner photo")
        if w in JOKE_ROLES:   # caption truth (B35): every number in the caption is visible in the frame
            seen = numbers_in(vis + " " + r.get("sign", ""))
            for num in sorted(numbers_in(cap) - seen):
                errs.append(f"{w}: caption says {num} but the visual does not show {num}")
    f = brief["facts"]
    if len(rungs) == N_RUNGS:
        if _norm(f["true_setup"]) not in _norm(rungs[3]["caption"]):
            errs.append("truth: the caption must state the real setup word for word")
        if _norm(f["real_proof"]) not in _norm(rungs[7]["caption"]):
            errs.append("payoff: the caption must be the real proof word for word")
        if brief["tone"] == "heartfelt" and rungs[5].get("honest_line") != f["honest_line"]:
            errs.append("heirloom: heartfelt tone needs the business's own honest line, unchanged")
        brag_n, truth_n = max(numbers_in(rungs[0]["caption"]) or {0}), max(numbers_in(rungs[1]["caption"]) or {0})
        if brag_n and truth_n and truth_n >= brag_n:
            errs.append("downgrade 1 must cut the brag's number")
    if len(warps) != 4:
        errs.append(f"need exactly 4 warps (3 joke warps + the push to the place of work), got {len(warps)}")
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
    if len(shots) != N_CLIPS:
        errs.append(f"need {N_CLIPS} moving clips, got {len(shots)}")
    return errs


# ---------------------------------------------------------------- prompts
MOOD = {"struggle": "Quiet, tired, late-night practical light; the unseen hard side of running this business. It should make a "
                    "viewer feel for the owner without showing anyone.",
        "heirloom": "Warm, close and tender, shallow depth of field: an object full of memory from where it all started.",
        "place": "Where the business really works, warm and inviting, with signs of real customers but no people in sight."}


def keyframe_prompt(ladder, k):
    """The still for rung k, filled from the ladder and the business's own inputs (kind, offer, setting)."""
    r = ladder["rungs"][k]
    sign = f' A plain sign in the frame reads exactly "{r["sign"]}", spelled correctly, clean lettering.' if r.get("sign") else ""
    place = "" if r["role"] != "payoff" else " Product or finished-work hero shot, macro close-up."
    world = ""
    if ladder.get("kind"):
        world = f"\nThe business: {_a(ladder['kind'])}" + (f" offering {ladder['offer']}" if ladder.get("offer") else "") + "."
    if r["role"] == "truth" and ladder.get("setting"):
        world += f" Where it really happens: {ladder['setting']}."
    if r["role"] in MOOD:
        world += f" {MOOD[r['role']]}"
    if r["role"] in CAPTIONED:
        must = f"\nThe picture must make this line literally true at a glance: \"{r['caption']}\""
    elif r.get("caption"):
        must = f"\nThe picture quietly fits this true line from the owner: \"{r['caption']}\""
    else:
        must = ""
    return f"{KEYFRAME_HEAD}{place}{world}\nShow: {r['visual']}.{sign}{must}\n{KEYFRAME_TAIL}"


def warp_prompt(ladder, k):
    """Clip k (0-based) of the seven: a warp, a quiet sympathy move, or the payoff macro."""
    s = ladder["shots"][k]
    nxt = ladder["rungs"][s["to"]]
    if s["kind"] == "warp":
        return (f"Start on the first frame. {BUILD_UP}{s['motion']} the last frame: {nxt['visual']}. Land and hold on the last "
                f"frame for the final second. {WARP_TAIL}")
    if s["kind"] == "move":
        return (f"Start on the first frame. A quiet, slow move with no transformation and no flash: {s['motion']} the last frame: "
                f"{nxt['visual']}. {WARP_TAIL}")
    return (f"Macro product hero shot that starts and ends on this frame: {nxt['visual']}. Very slow push-in, stabilized: "
            f"{s['motion']}. {WARP_TAIL}")


def music_prompt(ladder):
    """The score brief for Sonilo Video-to-Music, per tone."""
    if ladder.get("tone") == "heartfelt":
        return ("Warm cinematic commercial score, instrumental only, no vocals. Playful and bouncy at the start with a big hit "
                "on every transformation, then it softens and turns tender for the quiet, honest middle, and rises to a proud, "
                "hopeful ending.")
    return ("Bright, playful commercial score, instrumental only, no vocals. Punchy hits on every transformation, a short "
            "quiet breath in the middle, then a confident, upbeat ending.")


def ladder_text(ladder):
    lines = [f"{ladder['business_name']}: Honest Downgrade ({ladder['tone']})"]
    for k, r in enumerate(ladder["rungs"]):
        lines.append(f"{k + 1}. {r['role'].replace('_', ' ').upper():<12} {r['caption'] or '(no caption)'}")
        for s in ladder.get("shots", []):
            if s["from"] == k:
                lines.append(f"{'':<6}~ " + {"warp": f"warp: {s['device']}", "move": "quiet move (sympathy beat)",
                                             "macro": "payoff macro (drop, splash, light)"}[s["kind"]])
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


def private_card(path, W, H):
    """What the music model sees in place of the owner's photo: the photo itself never leaves the machine."""
    card = Image.new("RGB", (W, H), (34, 30, 27)); d = ImageDraw.Draw(card)
    fo = _font(W // 20)
    txt = "real photo (kept private)"
    d.text(((W - d.textlength(txt, font=fo)) / 2, H * .47), txt, font=fo, fill=(150, 140, 130))
    card.save(path)


def _push(W, H, fps, secs, zoom=0.10, fit=False):
    """A slow push-in on a still (Ken Burns), so no rung and no photo is ever a frozen frame. fit=True keeps the whole
    picture (a real photo is never cropped) on a blurred fill of itself."""
    n = max(1, int(round(secs * fps)))
    big = f"{W * 2}:{H * 2}"
    z = f"zoompan=z='1+{zoom}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}"
    if fit:
        return (f"split[pa][pb];[pa]scale={big}:force_original_aspect_ratio=increase,crop={big},boxblur=40:2,eq=brightness=-0.08[pbg];"
                f"[pb]scale={big}:force_original_aspect_ratio=decrease[pfg];[pbg][pfg]overlay=(W-w)/2:(H-h)/2,setsar=1,{z}")
    return f"scale={big}:force_original_aspect_ratio=increase,crop={big},setsar=1,{z}"


# ---------------------------------------------------------------- the cheap local draft warp (no AI video, $0)
def draft_warp(first_png, last_png, device, out, secs=WARP_SECONDS, W=720, H=1280, fps=24):
    """A free animatic clip between two stills: a slow push-in on the first still, an ffmpeg transition chosen to read
    like the device, a slow push-in on the last still. Always moving, never a frozen frame. For drafts and tests only;
    the real clip is generated motion (Veo first/last frame)."""
    ffmpeg, _ = _ff()
    t = DRAFT_TRANSITION.get(device, "dissolve")
    td, half = min(1.6, secs / 3), secs / 2
    fmt = f"fps={fps},format=yuv420p"
    fc = (f"[0:v]{_push(W, H, fps, secs, 0.12)},{fmt}[a];[1:v]{_push(W, H, fps, secs, 0.12)},{fmt}[b];"
          f"[a][b]xfade=transition={t}:duration={td:.2f}:offset={half - td / 2:.2f}[v]")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", f"{secs}", "-i", str(first_png),
                    "-loop", "1", "-framerate", str(fps), "-t", f"{secs}", "-i", str(last_png), "-filter_complex", fc,
                    "-map", "[v]", "-t", f"{secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)], check=True)
    return Path(out)


# ---------------------------------------------------------------- the edit: the full Reel and the 15 s cutdown
CONSENT_ERROR = ("The owner photo is blocked: tick \"I have this person's consent\" (owner_consent) to use it. Only use a photo "
                 "of someone who said yes to being in this ad. Or clear the photo: the ending is then the payoff alone.")


def _whoosh_time(d):
    """Where a warp's transformation peaks inside its clip: after the 1 s build-up, about a third of the way through."""
    return 1.0 + 0.35 * (d - 1.0)


def plan_edit(durs, ladder, owner_len=0.0, length="full"):
    """The edit decision list. durs: the 7 clip lengths. owner_len: seconds of the real owner photo/clip (0 = none).
    Returns segments (kind, idx, t_in, t_out, dissolve into the next, start on the output), captions, the honest
    windows (the music ducks there), the label windows and the whoosh times. 'full' plays every clip whole;
    '15' is brag, truth, the sympathy beat, the owner, the payoff and the card, cut from the same clips."""
    if len(durs) != N_CLIPS:
        raise ValueError(f"need {N_CLIPS} clips, got {len(durs)}")
    honest = ladder["rungs"][5].get("honest_line", "")
    cap = [r["caption"] for r in ladder["rungs"]]
    if length == "full":
        segs = [["clip", k, 0.0, durs[k], MATCHED_DISSOLVE] for k in range(6)]
        segs[5][4] = PHOTO_DISSOLVE if owner_len else ANGLE_DISSOLVE
        if owner_len:
            segs.append(["owner", 0, 0.0, owner_len, ANGLE_DISSOLVE])
        segs.append(["clip", 6, 0.0, durs[6], ANGLE_DISSOLVE])
        segs.append(["card", 0, 0.0, CARD_SECONDS, 0.0])
    elif str(length) == "15":
        segs = [["clip", 0, 0.0, min(3.5, durs[0]), ANGLE_DISSOLVE], ["clip", 2, max(0.0, durs[2] - 2.5), durs[2], ANGLE_DISSOLVE],
                ["clip", 4, 0.0, durs[4], PHOTO_DISSOLVE if owner_len else ANGLE_DISSOLVE]]
        if owner_len:
            segs.append(["owner", 0, 0.0, min(2.5, owner_len), ANGLE_DISSOLVE])
        segs.append(["clip", 6, 0.0, min(4.0, durs[6]), ANGLE_DISSOLVE])
        body = sum(s[3] - s[2] - s[4] for s in segs)
        card = 15.0 - body
        if card < 2.0:   # shorten the payoff, keep a readable card
            segs[-1][3] -= 2.0 - card; card = 2.0
        segs.append(["card", 0, 0.0, min(4.0, card), 0.0])
    else:
        raise ValueError("length must be 'full' or 15")
    t = 0.0
    for s in segs:
        s.append(round(t, 3)); t += s[3] - s[2] - s[4]
    total = round(t, 3)
    at = lambda kind, idx=0: next(s for s in segs if s[0] == kind and s[1] == idx)
    st = lambda s: s[5]
    ln = lambda s: s[3] - s[2]
    caps, honest_w = [], []
    if length == "full":
        c = [at("clip", k) for k in range(7)]
        caps = [(0.2, st(c[0]) + 0.45 * ln(c[0]), cap[0]),
                (st(c[0]) + 0.78 * ln(c[0]), st(c[1]) + 0.45 * ln(c[1]), cap[1]),
                (st(c[1]) + 0.78 * ln(c[1]), st(c[2]) + 0.45 * ln(c[2]), cap[2]),
                (st(c[2]) + 0.78 * ln(c[2]), st(c[3]) + 0.85 * ln(c[3]), cap[3])]
        if honest:
            caps.append((st(c[4]) + 0.15 * ln(c[4]), st(c[5]) + 0.25 * ln(c[5]), honest))
        caps.append((st(c[6]) + 0.3, total - 0.3, cap[7]))
    else:
        c0, c2, c4, c6 = at("clip", 0), at("clip", 2), at("clip", 4), at("clip", 6)
        caps = [(0.2, st(c0) + ln(c0) - 0.5, cap[0]), (st(c2) + 0.6, st(c4) + 0.5, cap[3])]
        if honest:
            caps.append((st(c4) + 0.6, st(c4) + ln(c4) - 0.2, honest))
        caps.append((st(c6) + 0.3, total - 0.3, cap[7]))
    caps = [(round(a, 3), round(b, 3), txt) for a, b, txt in caps]
    honest_w = [(a, b) for a, b, txt in caps if honest and txt == honest]
    card_s = st(segs[-1])
    real, prev_x = [], 0.0
    for s in segs:
        if s[0] == "owner":   # the label switches halfway through each dissolve, so the two labels never overlap
            real.append((round(st(s) + prev_x / 2, 3), round(st(s) + ln(s) - s[4] / 2, 3)))
        prev_x = s[4]
    ai = []
    for s in segs:
        if s[0] == "clip":
            a, b = st(s), st(s) + ln(s)
            for ra, rb in real:
                b = ra if a < ra < b else b
                a = rb if a < rb < b else a
            ai.append((round(a, 3), round(b, 3)))
    whoosh = []
    for s in segs:
        if s[0] == "clip" and ladder["shots"][s[1]]["kind"] == "warp":
            wt = _whoosh_time(durs[s[1]])
            if s[2] <= wt <= s[3]:
                whoosh.append(round(st(s) + wt - s[2], 3))
    return {"length": str(length), "segments": [tuple(s) for s in segs], "total": total, "captions": caps, "honest": honest_w,
            "ai": ai, "real": real, "whoosh": whoosh, "card_start": card_s}


def _map_to_full(cut, full):
    """For each segment of the cutdown: where the same picture plays in the full Reel (so the score is cut with it)."""
    out = []
    for kind, idx, a, b, x, start in cut["segments"]:
        m = next(s for s in full["segments"] if s[0] == kind and s[1] == idx)
        out.append(round(m[5] + (a - m[2]), 3))
    return out


def render_picture(cut, clips, owner, owner_is_clip, out, work, W, H, fps=24, captions=True, ai_label=True, card_png=None,
                   mask_owner=False):
    """Video only: every segment moving (clips play, the owner photo and the card get a slow push), joined with
    dissolves, then labels and classic captions. mask_owner=True swaps the owner for a private card (the score cut)."""
    ffmpeg, _ = _ff()
    work = Path(work); ov = work / "ov"; ov.mkdir(parents=True, exist_ok=True)
    sc = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},format=yuv420p,settb=AVTB"
    inp, fc = [], []
    for i, (kind, idx, a, b, x, start) in enumerate(cut["segments"]):
        L = b - a
        if kind == "clip" or (kind == "owner" and owner_is_clip and not mask_owner):
            inp += ["-i", str(clips[idx] if kind == "clip" else owner)]
            fc.append(f"[{i}:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,{sc}[v{i}]")
        else:
            if kind == "owner" and mask_owner:
                still = ov / "private.png"; private_card(still, W, H); fit, zoom = False, 0.03
            elif kind == "owner":
                still, fit, zoom = owner, True, 0.08
            else:
                still, fit, zoom = card_png, False, 0.03
            inp += ["-loop", "1", "-framerate", str(fps), "-t", f"{L:.3f}", "-i", str(still)]
            fc.append(f"[{i}:v]{_push(W, H, fps, L, zoom, fit)},trim=duration={L:.3f},setpts=PTS-STARTPTS,format=yuv420p,settb=AVTB[v{i}]")
    acc, acc_len = "v0", cut["segments"][0][3] - cut["segments"][0][2]
    for i in range(1, len(cut["segments"])):
        x = cut["segments"][i - 1][4]
        L = cut["segments"][i][3] - cut["segments"][i][2]
        fc.append(f"[{acc}][v{i}]xfade=transition=fade:duration={x:.3f}:offset={acc_len - x:.3f}[x{i}]")
        acc, acc_len = f"x{i}", acc_len + L - x
    idx, base = len(cut["segments"]), acc
    if ai_label:
        label_png(ov / "ai.png", "AI-generated", W)
        label_png(ov / "real.png", "Real footage" if owner_is_clip else "Real photo", W)
        inp += ["-i", str(ov / "ai.png")]
        en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cut["ai"])
        fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='{en}'[l0]"); base = "l0"; idx += 1
        if cut["real"] and not mask_owner:
            inp += ["-i", str(ov / "real.png")]
            a, b = cut["real"][0]
            fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='between(t,{a:.3f},{b:.3f})'[l1]"); base = "l1"; idx += 1
    if captions:
        for k, (a, b, txt) in enumerate(cut["captions"]):
            p = ov / f"cap_{cut['length']}_{k:02d}.png"
            text_png(p, txt, max(30, W // 14), W)
            inp += ["-i", str(p)]
            fc.append(f"[{base}][{idx}:v]overlay=(W-w)/2:H*0.16:enable='between(t,{a:.3f},{b:.3f})'[c{k}]"); base = f"c{k}"; idx += 1
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + ["-filter_complex", ";".join(fc), "-map", f"[{base}]", "-an", "-t", f"{cut['total']:.3f}",
           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(fps), str(out)]
    (work / f"ffmpeg_picture_{cut['length']}{'_masked' if mask_owner else ''}.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    return Path(out)


def _whoosh_chain(times, total, label="w"):
    fc, names = [], []
    for k, m in enumerate(times):
        ms = int(max(0.0, m - 0.45) * 1000)
        fc.append(f"anoisesrc=color=pink:amplitude=0.5:d=0.9:r=48000,bandpass=f=1200:width_type=o:w=2,afade=t=in:d=0.45,"
                  f"afade=t=out:st=0.45:d=0.45,volume=0.5,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay={ms}|{ms}[{label}{k}]")
        names.append(f"[{label}{k}]")
    return fc, names


def assemble_picture(clips, ladder, work, owner_path=None, owner_consent=False, captions=True, ai_label=True, credit=True,
                     fps=24, W=None, H=None):
    """Step 1 of the edit: the full Reel and the 15 s cutdown as pictures (no music yet), plus the score cut: the full
    Reel with the owner photo swapped for a private card and only the whooshes as sound. The score cut is what the
    music model sees, so the real photo never leaves the machine. Returns the plan the finish step reads."""
    if len(clips) != N_CLIPS:
        raise ValueError(f"need {N_CLIPS} clips (every rung is a moving clip), got {len(clips)}")
    owner = Path(owner_path) if owner_path else None
    if owner is not None:
        if not owner.is_file():
            raise ValueError(f"owner photo not found: {owner}")
        if not owner_consent:
            raise ValueError(CONSENT_ERROR)
    ffmpeg, _ = _ff()
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    info = [probe(c) for c in clips]
    W = W or (info[0]["w"] - info[0]["w"] % 2); H = H or (info[0]["h"] - info[0]["h"] % 2)
    owner_is_clip = owner is not None and owner.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm")
    owner_len = (min(4.0, probe(owner)["dur"]) if owner_is_clip else PHOTO_SECONDS) if owner is not None else 0.0
    durs = [i["dur"] for i in info]
    full, short = plan_edit(durs, ladder, owner_len, "full"), plan_edit(durs, ladder, owner_len, 15)
    short["map_to_full"] = _map_to_full(short, full)
    card = work / "endcard.png"
    end_card(card, W, H, [ladder["business_name"], ladder["facts"].get("honest_line") or ladder["rungs"][3]["caption"],
                          "AI-made places, real owner" if owner else "AI-generated places"], credit)
    for cut, name in ((full, "picture_full.mp4"), (short, "picture_15.mp4")):
        cut["picture"] = str(render_picture(cut, clips, owner, owner_is_clip, work / name, work, W, H, fps, captions, ai_label, card))
    masked = Path(full["picture"])
    if owner is not None:
        masked = render_picture(full, clips, owner, owner_is_clip, work / "picture_full_masked.mp4", work, W, H, fps, captions, ai_label,
                                card, mask_owner=True)
    fc, names = _whoosh_chain(full["whoosh"], full["total"])
    fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{full['total']:.3f}[sil]")
    fc.append("[sil]" + "".join(names) + f"amix=inputs={len(names) + 1}:duration=first:normalize=0[a]")
    score_cut = work / "score_cut.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(masked), "-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", f"{full['total']:.3f}", str(score_cut)], check=True)
    return {"work": str(work), "size": [W, H], "fps": fps, "durs": durs, "owner": str(owner) if owner else None,
            "owner_is_clip": owner_is_clip, "owner_consent": bool(owner_consent), "score_cut": str(score_cut),
            "music_prompt": music_prompt(ladder), "tone": ladder.get("tone"), "cuts": {"full": full, "15": short}}


def _bed_expr(total):
    """A simple, original synth bed (pad chords + soft kick, 96 BPM), generated here so it carries no licence.
    Free draft only, when there is no Sonilo score and no track of your own."""
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]
    def pick(i):
        return "+".join(f"if(eq(floor(mod(t/2.5,4)),{k}),{c[i]},0)" for k, c in enumerate(chords))
    pad = "+".join(f"0.06*sin(2*PI*({pick(i)})*t)" for i in range(3))
    x = "mod(t,0.625)"
    kick = f"0.35*sin(2*PI*(50+60*exp(-30*{x}))*{x})*exp(-9*{x})"
    hat = "0.02*(random(0)-0.5)*exp(-40*mod(t+0.3125,0.625))"
    return f"({pad})+({kick}+{hat})"


DUCK = "sidechaincompress=threshold=0.02:ratio=12:attack=40:release=450"
LEVEL_BED = "loudnorm=I=-27:LRA=3:TP=-6"
FINAL_LOUDNESS = "loudnorm=I=-14:TP=-1"


def _full_bed(source, total, out, loop):
    """The music for the full Reel as a plain WAV: the score / your track (looped if it is a track and too short) or the
    free-draft synth bed."""
    ffmpeg, _ = _ff()
    if source is None:
        args = ["-f", "lavfi", "-i", f"aevalsrc='{_bed_expr(total)}':s=48000:d={total:.3f}"]
    else:
        args = (["-stream_loop", "-1"] if loop else []) + ["-i", str(source)]
    subprocess.run([ffmpeg, "-v", "error", "-y"] + args + ["-af", f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"apad,atrim=0:{total:.3f}", "-ac", "2", "-ar", "48000", str(out)], check=True)
    return Path(out)


def _cut_bed(full_bed, cut, out):
    """The cutdown's music: the full Reel's music sliced where the same pictures play, joined with the same dissolves,
    so every hit stays on its picture."""
    ffmpeg, _ = _ff()
    fc = []
    segs = cut["segments"]
    fc.append(f"[0:a]asplit={len(segs)}" + "".join(f"[s{i}]" for i in range(len(segs))))
    for i, (s, m) in enumerate(zip(segs, cut["map_to_full"])):
        fc.append(f"[s{i}]atrim={m:.3f}:{m + s[3] - s[2]:.3f},asetpts=PTS-STARTPTS[m{i}]")
    acc = "m0"
    for i in range(1, len(segs)):
        fc.append(f"[{acc}][m{i}]acrossfade=d={segs[i - 1][4]:.3f}[c{i}]"); acc = f"c{i}"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(full_bed), "-filter_complex", ";".join(fc), "-map", f"[{acc}]",
                    "-ar", "48000", str(out)], check=True)
    return Path(out)


def mix_and_mux(cut, bed, out, work, owner=None, owner_is_clip=False):
    """The sound for one cut: level the music bed first, duck it under every honest/spoken line (sidechain), add a soft
    whoosh on every warp, fade out, -14 LUFS, then mux onto the picture (video copied, not re-encoded)."""
    ffmpeg, _ = _ff()
    T = cut["total"]
    inp = ["-i", cut["picture"], "-i", str(bed)]
    fc = [f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=0:{T:.3f},{LEVEL_BED},aresample=48000[bedn]"]
    win = "+".join(f"between(t,{a - 0.2:.3f},{b:.3f})" for a, b in cut["honest"]) or "0"
    fc.append(f"aevalsrc='0.08*sin(2*PI*150*t)*({win})':s=48000:d={T:.3f},aformat=sample_fmts=fltp:channel_layouts=stereo[keyh]")
    key, extra_mix = "keyh", []
    if owner is not None and owner_is_clip and cut["real"] and probe(owner)["audio"]:   # the owner's own voice ducks the music too
        seg = next(s for s in cut["segments"] if s[0] == "owner")
        ms = int(seg[5] * 1000)
        inp += ["-i", str(owner)]
        fc.append(f"[2:a]atrim={seg[2]:.3f}:{seg[3]:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"adelay={ms}|{ms},apad,atrim=0:{T:.3f},asplit[voice][voicekey]")
        fc.append("[keyh][voicekey]amix=inputs=2:duration=first:normalize=0[key]"); key = "key"
        extra_mix = ["[voice]"]
    fc.append(f"[bedn][{key}]{DUCK}[duck]")
    wfc, names = _whoosh_chain(cut["whoosh"], T)
    fc += wfc
    ins = ["[duck]"] + names + extra_mix
    fc.append("".join(ins) + f"amix=inputs={len(ins)}:duration=first:normalize=0,afade=t=out:st={max(0.0, T - 1.2):.3f}:d=1.2,"
              f"{FINAL_LOUDNESS},aresample=48000,atrim=0:{T:.3f}[aout]")
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + ["-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.3f}", "-movflags", "+faststart", str(out)]
    (Path(work) / f"ffmpeg_mix_{cut['length']}.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    return Path(out)


def finish(plan, out_full, out_15, score_path=None, music_path=None, allow_synth=True):
    """Step 2 of the edit: music. Your own track wins if given; else the Sonilo score; else (free draft only) the
    built-in synth bed. The same full-length bed is cut for the 15 s version."""
    work = Path(plan["work"])
    full, short = plan["cuts"]["full"], plan["cuts"]["15"]
    if music_path:
        mp = Path(music_path)
        if not mp.is_file():
            raise ValueError(f"music_path does not exist: {mp}")
        source, label, loop = mp, f"your track: {mp.name}", True
    elif score_path:
        source, label, loop = Path(score_path), "Sonilo score (Video-to-Music, scored on the score cut)", False
    elif allow_synth:
        source, label, loop = None, "built-in synth bed (free draft only)", False
    else:
        raise ValueError("No music: connect the Sonilo score or give a track you own.")
    bed = _full_bed(source, full["total"], work / "bed_full.wav", loop)
    bed15 = _cut_bed(bed, short, work / "bed_15.wav")
    owner = Path(plan["owner"]) if plan.get("owner") else None
    mix_and_mux(full, bed, out_full, work, owner, plan["owner_is_clip"])
    mix_and_mux(short, bed15, out_15, work, owner, plan["owner_is_clip"])
    receipt = {"music": label, "chain": [LEVEL_BED, DUCK, FINAL_LOUDNESS], "owner": plan.get("owner"),
               "owner_consent": plan.get("owner_consent"), "score_cut": plan["score_cut"]}
    for name, cut, out in (("full", full, out_full), ("15", short, out_15)):
        receipt[name] = {k: cut[k] for k in ("total", "segments", "captions", "honest", "ai", "real", "whoosh")}
        receipt[name]["file"] = str(out)
    (work / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def assemble(clips, ladder, out_full, work, owner_path=None, owner_consent=False, out_15=None, captions=True, ai_label=True,
             credit=True, music_path=None, score_path=None, allow_synth=True):
    """Both steps in one call (scripts and tests): pictures, then music. Returns the receipt."""
    plan = assemble_picture(clips, ladder, work, owner_path, owner_consent, captions, ai_label, credit)
    out_15 = out_15 or Path(out_full).with_name(Path(out_full).stem + "_15s.mp4")
    return finish(plan, out_full, out_15, score_path, music_path, allow_synth) | {"plan": plan}


def save_wav(path, waveform, sample_rate):
    """A ComfyUI AUDIO waveform ([batch, channels, samples] floats) -> 16-bit WAV, no extra libraries."""
    import numpy as np
    a = np.asarray(waveform)
    a = a[0] if a.ndim == 3 else a
    a = np.clip(a.T, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(int(sample_rate))
        w.writeframes((a * 32767).astype("<i2").tobytes())
    return Path(path)


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
