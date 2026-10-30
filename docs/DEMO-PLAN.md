# Demo plan: a demo video of 2 minutes or less

Everything in this repo so far cost $0: the free draft app, the tests (partner nodes mocked), the real-browser E2E run.
The one paid run below is prepared but **not run**. The founder starts it himself (approved cap: $4.00).

## The paid run (founder only)

```bash
cd /Users/jefe/projects/honest-downgrade && /Users/jefe/ComfyUI/venv/bin/python tools/run_paid_demo.py
```

- Brief: Drip Doctor Plumbing (`docs/examples/plumber-brief.md`, joke 2), the facts behind the approved plumber Reel.
- Models: 8 Nano Banana 2 keyframes (1K), 7 Veo 3.1 **fast** first/last-frame clips (720p, no audio, 36 s), the Sonilo
  score of the score cut. Template writer, so Gemini is never called.
- Estimate from the live price badges: **$3.87** = Veo $2.88 + keyframes $0.67 + Sonilo $0.32. The script refuses
  above $4.00, refuses if a badge price changed, and writes a ledger row to `runs/paid/ledger.jsonl` before it queues.
- Key: read by the script from `~/.config/jk/comfy_api_key`, sent only as `extra_data.api_key_comfy_org`, never printed.
- Owner photo: none by default (the ending is the payoff macro). To add one: `--owner-photo <file> --owner-consent`
  (adds 2.7 s to the Reel and about $0.02 of score).
- Results land in `runs/paid/<time>/`: the Reel, the cutdown, the 8 keyframes on the board, all 7 clips, the ladder,
  the sign check and the ComfyUI history (key removed). Add the real credit charge to the ledger afterwards.
- `--dry-run` prints the same ladder and estimate for $0.

If a clip fails review (a person appears, a sign scrambles, a warp reads flat): change only that clip's seed in the
graph and run again. Fixed seeds mean only that clip is paid again (about $0.32-0.48 for a Veo fast clip), plus the
score, because the cut changed (about $0.32). Any re-roll is new spend over the approved run: ask first.

## The video (target 1:50)

| Time | Picture | Voice-over / caption |
|---|---|---|
| 0:00-0:10 | The approved plumber Reel, from "We have 40 work trucks" through the first truck smash | "Every small business wants a Reel like this." |
| 0:10-0:20 | Cut to ComfyUI, the app opens in App Mode: a plain form | "This is one ComfyUI app. You type the truth about your business." |
| 0:20-0:35 | Type the plumber brief: business type Plumber, the truth, the honest line, the payoff | "The joke is written for you. Your facts are locked: no model can change them." |
| 0:35-0:45 | The ladder text and the board of 8 keyframes, the sign check passing | "Every caption has to be visible in its picture. No people are ever generated." |
| 0:45-1:05 | The 7 clips, fast: tool smash, geyser, pipe tornado, the 2 a.m. van, the old wrench, the push to the door, the macro | "Shock transitions with a one-second build-up. Then it slows down for the part that makes you care." |
| 1:05-1:20 | Add an owner photo, press Run without the consent switch: the clear error. Switch it on | "The only real person is the owner, and only with consent. That photo never goes to any model." |
| 1:20-1:30 | The score cut with the "real photo (kept private)" card, then the waveform dipping under "My dad taught me on weekends." | "The music is scored to the cut and drops when the honest line lands." |
| 1:30-1:50 | The finished Reel, full screen, with sound; the 15 s cutdown thumbnail | "One Run. A full Reel and a 15-second cut. About four dollars." |

Recording notes:
1. Record the App Mode parts from the free draft app if the paid run is not done yet, and label the draft pictures as
   draft on screen. Never press Run in the main app while recording unless that is the founder's paid run.
2. Show the cost line honestly: lite about $2.10, fast about $3.90 per Reel; the draft is $0.
3. Keep the AI label visible in every shot of the generated Reel.
4. The plumber Reel at 0:00 is the approved Flow draft: caption it "made with this recipe, clips drafted in Google Flow".

## Open questions for the founder

1. Run the paid demo (estimate $3.87, cap $4.00), or record with the approved plumber Reel plus the free draft only.
2. Owner photo for the demo: none (default), or a JK-owned photo of someone who consents.
3. Voice-over: founder's own voice, or captions only.
4. Name check before going public: "Drip Doctor Plumbing" and "Tacos El Zorrito Azul" are fictional; a web check for
   real businesses with those names has not been done for Drip Doctor (2026-10-30).

## Proof to keep

The paid run's `runs/paid/<time>/` folder and ledger rows, the credit charge, the E2E screenshot
(`docs/img/app-mode.png`), the draft MP4s in `docs/examples/`, the pytest output.
