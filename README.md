# Honest Downgrade

**Type in a small business's true facts. Get the "I'm so sorry I lied" Reel: a big brag, three honest downgrades through
wild-card warps, and a real payoff. 9:16, 30 s plus a 15 s cutdown, captions, AI label. Ready to post.**

A ComfyUI App Mode app. The joke earns attention; the honest ending earns trust.

Built for the Comfy *Open Source Higgsfield* challenge, 2026. Apache-2.0. By JK Automations.

<p align="center"><img src="docs/img/app-mode.png" width="720" alt="Honest Downgrade in ComfyUI App Mode: business name, family, the truth, an honest line, the payoff, tone, joke ladder, a real ending photo, writer, video model and a Run button"></p>

## What it makes

The trend: a business brags ("Our 200th location just opened."), then "admits" the truth one rung at a time
("Ok, it's 2 locations." "Ok, it's one window."), until the real, exact, humble setup ("Ok, it's a truck in a gas station
parking lot."), then lands on proof people can check ("The line at 11pm is real."). Between every two rungs a wild-card
warp carries the camera to the next place: a ribbon that turns into a snake, a building that folds like a pop-up book, a
flock of birds that bursts at the lens.

```
 BRAG ──warp──▶ DOWNGRADE 1 ──warp──▶ DOWNGRADE 2 ──warp──▶ TRUTH ──warp──▶ PAYOFF ──▶ your REAL photo ──▶ end card
 impossible      cut the number       cut the fancy thing    your real setup  your proof   (people live only here)
```

Free draft of the sample business (code-drawn placeholder stills, local draft warps, made by pressing Run in App Mode):
[`docs/examples/taco-truck-draft-reel.mp4`](docs/examples/taco-truck-draft-reel.mp4) ·
[15 s cutdown](docs/examples/taco-truck-draft-cutdown-15s.mp4) · [board](docs/examples/taco-truck-draft-board.png).

## Why it is different

- **Facts are locked.** The writer (template or Gemini) only writes the joke: the brag, two downgrades and the four warps.
  The truth, the honest line and the payoff are the business's own words, copied in by code. A model cannot "improve" them.
- **Caption truth.** Every rung's still is prompted so its caption is literally true in the picture (the frame for
  "2 locations" shows exactly two), and the ladder is rejected if a caption claims a number the visual does not show.
  An OCR pass (tesseract, optional) checks that sign text reads as written.
- **AI changes places and things, never people.** Generated stills and warps are checked for people words and prompted
  with no people. Real people only appear in the real ending photo or clip you upload, labelled "Real photo".
- **No repeated wow.** Four different warp devices per Reel, the business family's own wild cards first, and an
  "already used" list so a business never gets the same trick twice.
- **One app, two cuts.** The 30 s Reel and the 15 s cutdown come from the same four warps; nothing is generated twice.
- **Draft free, pay once.** The draft app runs the whole Reel with your own stills and local draft warps, $0. The main
  app spends only on 5 stills and 4 warps, and fixed seeds mean a re-run only pays for what changed.

## How the graph works

1. **Your facts** (`Honest Downgrade: Your Facts`): business name, family (food and drink, trades and home, beauty and
   fitness, retail and services), the true setup, one honest line, the real proof, the payoff hero, tone, joke 1-3.
2. **Ladder** (`Honest Downgrade: Ladder Writer`): the family's template ladder (offline, free) or **Gemini** (partner node,
   asked lazily, only when picked). Checked before anything is drawn: 5 rungs, facts word for word, caption numbers
   visible, no people, no real brands, 4 distinct warps.
3. **Keyframes:** one **Nano Banana 2** (partner node) still per rung, 9:16, with the caption it must prove.
   `Board + Sign Check` shows all five with captions and the OCR sign result.
4. **Warps:** **Veo 3.1 first/last frame** (partner node) between each pair of rungs, 6 s, 9:16, 720p, no audio, with the
   wild-card motion. Every warp is saved (`output/honest/warps/`).
5. **Assemble** (`Honest Downgrade: Assemble`): the warps, your real ending photo or clip, the end card; classic captions
   (bold white, dark stroke, high in the frame), "AI-generated" label on AI shots, "Real photo" on yours, a music drop under
   the honest line, a soft whoosh on every warp, -14 LUFS, H.264. Sound is a built-in original synth bed, or a track you own.

`workflows/honest-downgrade.json` is the main app. `workflows/honest-downgrade-draft.json` is the free draft: you give the
five stills (any local model, or photos), `Free Draft Warp` makes animatic warps with ffmpeg, the rest is identical.

## Install

Needs ComfyUI 0.42+ with frontend 1.41+ (App Mode), `ffmpeg` on PATH, optional `tesseract` for the sign check. No model
downloads, no GPU: generation runs on Comfy's partner API (main app) or not at all (draft app).

```bash
cd ComfyUI/custom_nodes
git clone <this repo> honest-downgrade
```

Restart ComfyUI and open `workflows/honest-downgrade.json`. It opens in App Mode. Partner nodes need a Comfy account with
credits: click **Sign in to run**, or send an API key in `extra_data.api_key_comfy_org` from a script. Never commit a key.

## Cost (main app, one Reel)

| Step | Price (from the nodes' own price badges, 2026-10-29) |
|---|---|
| Nano Banana 2, 1K: 5 stills × about $0.084 | about $0.42 |
| Veo 3.1 lite, 720p, no audio: 4 warps × 6 s × $0.03/s | about $0.72 |
| Gemini joke writer (only when picked) | a few cents |
| **Total** | **about $1.15** |

`fast` is $0.08/s without audio (about $1.92 of video), full Veo $0.20/s (about $4.80).

## Plug into JK Studio

This app is JK Studio workflow **W13 Honest Downgrade** as one ComfyUI graph. The node pack's core
(`honest_core.py`, no ComfyUI imports) can be called from a JK Studio runner: `make_brief` → `build_ladder` → prompts →
your chosen image/video route → `assemble`. The ladder families, the warp devices (block B34), the caption-truth check (B35)
and the music drop (B36) follow the W13 card. Local-first: run the draft app first; the paid route is for approved shots.

## For developers

```bash
python3 tools/build_app.py && python3 tools/build_app.py --draft       # API-format graphs
python3 tools/check_graph.py workflows/honest-downgrade-api.json --url http://127.0.0.1:8196   # checks, never queues
node tools/make_app.mjs http://127.0.0.1:8196 workflows/honest-downgrade-api.json workflows/honest-downgrade.json docs/img/app-mode.png
python3 tools/make_placeholder_stills.py --input-dir <ComfyUI>/input  # the 5 sample stills for the draft app
python3 tools/run_draft.py --url http://127.0.0.1:8196                 # queue the FREE draft graph (refuses paid nodes)
node tools/e2e_draft.mjs http://127.0.0.1:8196 workflows/honest-downgrade-draft.json shot.png   # press Run in the real UI
PYTHONPATH=<pytest dir> <ComfyUI venv>/bin/python -m pytest            # tests; partner nodes are mocked
```

`make_app.mjs` and `e2e_draft.mjs` need the `playwright` npm package. Both block any `/prompt` that contains a partner node.

## Licences and credits

| Part | Licence |
|---|---|
| Code, workflows, preset, placeholder stills, built-in synth bed | Apache-2.0 (this repo) |
| Font: Inter | SIL OFL 1.1 (`fonts/OFL.txt`) |
| ffmpeg (called, not bundled) | LGPL/GPL, per your build |
| tesseract (optional, called) | Apache-2.0 |
| Gemini, Nano Banana 2, Veo 3.1 (partner nodes) | Google and Comfy API terms apply to what you generate |
| Your music (optional) | must be yours or licensed; never a copyrighted song |

The sample business "Tacos El Zorrito Azul" and all its facts are fictional. Keep the AI label on when you post.
