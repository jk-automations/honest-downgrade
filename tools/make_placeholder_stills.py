"""Draw eight flat-illustration placeholder stills for the taco-truck preset, so the free draft graph, the tests and
the demo run with no AI and no spend. They are code-drawn stand-ins, not generated images and not the approved sample.

python3 tools/make_placeholder_stills.py [--out presets/taco-truck/placeholder] [--input-dir .comfy-base/input]"""
import argparse, math, random, shutil, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 720, 1280
FONT = ROOT / "fonts" / "Inter.ttf"
INK, CREAM, BLUE, RED, GOLD = (32, 28, 40), (246, 236, 214), (52, 92, 160), (196, 58, 48), (232, 176, 72)


def font(size):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default(size)


def sky(top, bottom):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return im, d


def sign(d, box, text, bg=CREAM, fg=INK, size=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=10, fill=bg, outline=INK, width=4)
    f = font(size or int((y1 - y0) * 0.55))
    tw = d.textlength(text, font=f)
    if tw > (x1 - x0) * 0.9:
        f = font(int((size or (y1 - y0) * 0.55) * (x1 - x0) * 0.9 / tw)); tw = d.textlength(text, font=f)
    d.text(((x0 + x1 - tw) / 2, y0 + (y1 - y0 - f.size) / 2 - 4), text, font=f, fill=fg)


def windows(d, x0, y0, x1, y1, cols, rows, lit=(255, 214, 140), dark=(70, 80, 110), seed=1):
    r = random.Random(seed)
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    for i in range(cols):
        for j in range(rows):
            d.rectangle([x0 + i * cw + cw * .2, y0 + j * ch + ch * .25, x0 + (i + 1) * cw - cw * .2, y0 + (j + 1) * ch - ch * .15],
                        fill=lit if r.random() < .6 else dark)


def brag():
    im, d = sky((40, 48, 96), (238, 150, 110))
    d.rectangle([150, 160, 570, 1040], fill=(58, 66, 98), outline=INK, width=5)       # the tower
    windows(d, 170, 200, 550, 820, 6, 14, seed=3)
    d.rectangle([0, 1040, W, H], fill=(196, 186, 170))                                  # plaza
    d.rectangle([250, 860, 470, 1040], fill=(255, 226, 170), outline=INK, width=5)     # doors
    d.line([(360, 860), (360, 1040)], fill=INK, width=4)
    d.line([(180, 960), (540, 960)], fill=RED, width=22)                                # the ribbon
    d.polygon([(360, 945), (320, 915), (320, 1005)], fill=RED); d.polygon([(360, 975), (400, 915), (400, 1005)], fill=RED)
    sign(d, (110, 400, 610, 520), "200TH LOCATION", bg=GOLD)
    for k in range(18):                                                                 # confetti
        x, y = (k * 97) % W, 560 + (k * 211) % 300
        d.rectangle([x, y, x + 12, y + 20], fill=[RED, GOLD, CREAM, BLUE][k % 4])
    return im


def two():
    im, d = sky((120, 170, 220), (250, 220, 190))
    d.rectangle([0, 980, W, H], fill=(170, 160, 150))
    for k, x in enumerate((40, 380)):
        d.rectangle([x, 520, x + 300, 980], fill=(236, 214, 180), outline=INK, width=5)
        for s in range(6):                                                              # striped awning
            d.polygon([(x + s * 50, 600), (x + s * 50 + 50, 600), (x + s * 50 + 50, 660), (x + s * 50, 660)],
                      fill=RED if s % 2 == 0 else CREAM, outline=INK)
        d.rectangle([x + 40, 700, x + 260, 860], fill=(255, 220, 150), outline=INK, width=4)
        d.rectangle([x + 110, 860, x + 190, 980], fill=(120, 80, 60), outline=INK, width=4)
        sign(d, (x + 30, 530, x + 270, 590), "TACOS", bg=BLUE, fg=CREAM)
    sign(d, (160, 400, 560, 490), "2 LOCATIONS", bg=CREAM)
    return im


def window():
    im, d = sky((206, 196, 180), (190, 178, 160))
    for y in range(0, H, 60):                                                           # plain painted brick wall
        for x in range(-60 if (y // 60) % 2 else 0, W, 120):
            d.rectangle([x, y, x + 116, y + 56], fill=(214, 204, 186), outline=(190, 178, 160))
    d.rectangle([170, 430, 550, 760], fill=(255, 210, 140), outline=INK, width=8)      # the one service window
    d.rectangle([170, 760, 550, 800], fill=(150, 150, 150), outline=INK, width=4)
    d.rectangle([560, 520, 690, 820], fill=(40, 52, 44), outline=(120, 90, 60), width=8)  # chalk menu board
    f = font(24)
    for k, t in enumerate(["MENU", "pastor", "asada", "pollo", "horchata"]):
        d.text((578, 540 + k * 52), t, font=f, fill=(236, 236, 224))
    d.rectangle([0, 1040, W, H], fill=(150, 140, 130))
    return im


def truck():
    im, d = sky((22, 26, 54), (70, 60, 90))
    d.rectangle([0, 900, W, H], fill=(70, 70, 76))                                      # the parking lot
    for x in range(40, W, 160):
        d.line([(x, 980), (x + 60, 1200)], fill=(220, 220, 200), width=6)
    d.rectangle([0, 230, W, 300], fill=(226, 226, 226), outline=INK, width=4)           # plain, unbranded canopy
    for x in (60, 640):
        d.rectangle([x, 300, x + 24, 900], fill=(200, 200, 200), outline=INK, width=3)
    d.rectangle([100, 700, 150, 900], fill=(210, 210, 210), outline=INK, width=4)       # a plain pump
    d.rounded_rectangle([200, 560, 650, 940], radius=30, fill=BLUE, outline=INK, width=6)  # the truck
    d.rectangle([260, 620, 520, 780], fill=(255, 214, 130), outline=INK, width=5)      # lit service window
    d.polygon([(240, 620), (540, 620), (560, 580), (220, 580)], fill=CREAM, outline=INK)
    d.rectangle([540, 620, 630, 760], fill=(160, 200, 230), outline=INK, width=4)
    for x in (300, 560):
        d.ellipse([x - 55, 890, x + 55, 1000], fill=INK); d.ellipse([x - 25, 920, x + 25, 970], fill=(170, 170, 170))
    for k in range(9):                                                                  # string lights
        d.ellipse([230 + k * 45, 590, 244 + k * 45, 604], fill=GOLD)
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse([200, 520, 600, 860], fill=(90, 60, 20))
    return _add(im, glow)


def _add(im, glow):
    from PIL import ImageChops
    return ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(60)))


def tacos():
    im, d = sky((60, 40, 30), (30, 22, 18))
    d.rounded_rectangle([60, 560, 660, 1060], radius=26, fill=(236, 224, 200), outline=INK, width=5)  # paper tray
    for k, x in enumerate((110, 290, 470)):
        d.pieslice([x, 620, x + 170, 980], 90, 270, fill=(232, 196, 120), outline=INK, width=5)       # tortilla
        d.pieslice([x + 10, 630, x + 180, 990], 270, 90, fill=(232, 196, 120), outline=INK, width=5)
        d.ellipse([x + 30, 650, x + 150, 760], fill=(196, 90, 50))                                     # al pastor
        for j in range(6):
            d.ellipse([x + 30 + j * 18, 640 + (j % 2) * 20, x + 46 + j * 18, 656 + (j % 2) * 20], fill=(80, 160, 70))
    d.pieslice([520, 880, 660, 1020], 180, 360, fill=(140, 200, 80), outline=INK, width=4)             # lime
    steam = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(steam)
    for k in range(3):
        pts = [(200 + k * 160 + 30 * math.sin(t / 20), 600 - t * 3) for t in range(0, 120)]
        sd.line(pts, fill=(255, 255, 255, 110), width=14)
    im = Image.alpha_composite(im.convert("RGBA"), steam.filter(ImageFilter.GaussianBlur(6))).convert("RGB")
    return im


def struggle():
    """The truck's cab at 2 a.m.: rain on the windshield, a phone buzzing upside down on the dash, a cold coffee."""
    im, d = sky((12, 14, 26), (30, 30, 48))
    d.polygon([(0, 260), (W, 220), (W, 760), (0, 800)], fill=(26, 34, 52))                  # the windshield
    r = random.Random(7)
    for k in range(140):                                                                     # rain drops
        x, y = r.randint(0, W), r.randint(240, 780)
        d.ellipse([x, y, x + 6, y + 10], fill=(90, 110, 150))
    for k in range(5):                                                                       # far street lights, blurred later
        d.ellipse([60 + k * 140, 420, 100 + k * 140, 460], fill=(230, 170, 80))
    d.rectangle([0, 800, W, H], fill=(20, 20, 24))                                           # the dash
    d.rounded_rectangle([250, 850, 470, 900], radius=12, fill=(10, 10, 12), outline=(80, 140, 220), width=4)   # phone, upside down
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse([210, 800, 510, 960], fill=(30, 60, 110))
    d.rectangle([540, 880, 610, 1010], fill=(150, 110, 80), outline=INK, width=4)            # cold coffee cup
    d.ellipse([-200, 1000, 420, 1500], outline=(50, 50, 56), width=40)                       # steering wheel edge
    return _add(im.filter(ImageFilter.GaussianBlur(1.2)), glow)


def heirloom():
    """An old, dented cast-iron pan with a worn wooden handle on a hook inside the truck, warm light."""
    im, d = sky((70, 50, 34), (40, 28, 20))
    for x in range(0, W, 90):                                                                # plank wall
        d.line([(x, 0), (x, H)], fill=(56, 40, 28), width=4)
    d.ellipse([340, 300, 380, 340], fill=(150, 150, 150), outline=INK, width=4)              # the hook
    d.rectangle([340, 330, 380, 610], fill=(120, 80, 50), outline=INK, width=4)              # worn wooden handle
    d.ellipse([140, 580, 580, 1020], fill=(40, 40, 44), outline=(20, 20, 20), width=10)      # the pan
    d.ellipse([190, 630, 530, 970], fill=(58, 56, 60))
    d.arc([240, 680, 480, 920], 200, 320, fill=(110, 110, 116), width=6)                     # a worn shine
    d.ellipse([440, 700, 470, 730], fill=(30, 30, 32))                                       # a dent
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse([100, 200, 620, 1100], fill=(80, 50, 20))
    return _add(im, glow)


def place():
    """The truck's service window glowing at night, empty paper trays on the ledge, a tip jar stuffed full."""
    im, d = sky((16, 18, 36), (40, 34, 56))
    d.rounded_rectangle([60, 300, 660, 1100], radius=30, fill=BLUE, outline=INK, width=6)  # the side of the truck
    d.rectangle([140, 420, 580, 720], fill=(255, 214, 130), outline=INK, width=6)          # the glowing window
    d.rectangle([110, 720, 610, 760], fill=(200, 200, 200), outline=INK, width=4)          # the ledge
    for k in range(4):                                                                       # stacked empty trays
        d.rounded_rectangle([150, 700 - k * 10, 330, 722 - k * 10], radius=6, fill=(236, 224, 200), outline=INK, width=2)
    d.rectangle([450, 620, 540, 720], fill=(200, 230, 240), outline=INK, width=4)          # the tip jar
    for k in range(6):
        d.rectangle([458 + (k % 3) * 26, 640 + (k // 3) * 30, 478 + (k % 3) * 26, 664 + (k // 3) * 30], fill=(110, 170, 90))
    for k in range(9):
        d.ellipse([110 + k * 60, 380, 126 + k * 60, 396], fill=GOLD)                       # string lights
    d.rectangle([0, 1100, W, H], fill=(60, 60, 66))
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse([60, 300, 660, 900], fill=(90, 60, 20))
    return _add(im, glow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "presets/taco-truck/placeholder"))
    ap.add_argument("--input-dir", help="also copy them into this ComfyUI input dir as honest_rung_1.png ... honest_rung_8.png")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, f in enumerate([brag, two, window, truck, struggle, heirloom, place, tacos], 1):
        p = out / f"rung_{k}.png"; f().save(p); paths.append(p)
    if a.input_dir:
        for k, p in enumerate(paths, 1):
            shutil.copy(p, Path(a.input_dir) / f"honest_rung_{k}.png")
    print("\n".join(map(str, paths)))


if __name__ == "__main__":
    sys.exit(main())
