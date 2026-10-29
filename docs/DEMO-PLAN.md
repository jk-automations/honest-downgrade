# Demo plan: one paid run of the real app (needs founder approval)

Nothing below has been run. Everything so far is $0: the draft app (code-drawn stills, local draft warps) and the tests
(partner nodes mocked).

## Why a paid run would help

The draft proves the app end to end, but a judge sees placeholder drawings and slide-style transitions. One real run shows
what the app is for: photo-real rungs where each caption is literally visible, and real wild-card motion between them.

## The run (taco-truck preset, unchanged)

1. Start a ComfyUI that can reach the Comfy API, with this pack in `custom_nodes`; sign in with the JK Comfy account.
2. Open `workflows/honest-downgrade.json` (App Mode). Keep the preset, `template` writer, `veo-3.1-lite`.
3. Screen-record, press **Run**. Order on screen: ladder text, board with 5 stills and the sign check, 4 warps, the Reel.
4. If a still fails the board (people, a real logo, the caption not visible, a misspelled sign): change only its seed,
   Run again. Fixed seeds: only that still and its two warps are paid again.

## Quote (from the node price badges on 2026-10-29; re-check the badges before spending)

| Item | Qty | Unit | Total |
|---|---|---|---|
| Nano Banana 2, 1K | 5 | ~$0.084 | ~$0.42 |
| Veo 3.1 lite first/last frame, 720p, no audio, 6 s | 4 | $0.18 | $0.72 |
| **One clean run** | | | **~$1.14** |
| Re-roll budget (2 stills + 4 warps) | | | ~$0.90 |
| **Requested cap** | | | **$3.00** |

Optional upgrade after review: Veo 3.1 fast for the 4 warps (+$1.20) only if lite warps look weak.

## Open questions for the founder

1. Approve the $3 cap (one run plus re-rolls) or not.
2. The real ending: the sample business is fictional, so there is no real photo. Options: no ending (Reel is 27.5 s),
   a JK-owned photo of food with no people, or skip.
3. Music: built-in synth bed (no licence needed) or a JK-owned track.
4. Name check: no business named "El Zorrito Azul" found in a web search (2026-10-29), but a taco place called
   "El Zorrito" exists in Acapulco. Keep the name, or pick another before going public.

## Proof to keep

The Reel and cutdown from `output/honest/`, the board and sign check, ComfyUI `/history` JSON for the run (every partner
call and prompt), and the credit charge.
