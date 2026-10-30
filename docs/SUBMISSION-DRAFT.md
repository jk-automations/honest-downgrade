# Submission draft: Comfy "Open Source Higgsfield" challenge

Ready for the founder to paste into the form. Repo is public.

**Category:** Most Viral

**Title:** Honest Downgrade: the "I'm so sorry I lied" Reel for any small business

**One line:** Type your business's true facts, press Run, get a scroll-stopping Reel that brags, admits the truth
through shock transitions, makes people feel for you, and ends on your real face and real proof.

## Why it can go viral

- **It rides a format people already share.** "I'm so sorry I lied: it's not 200 locations, it's one truck in a gas
  station lot." The joke is the hook; the honest ending is the reason to share.
- **Hook, hold, want more.** A brag at impossible scale in the first second; a shock transition (the trucks get smashed
  by a giant pipe wrench, a geyser, a tornado of pipes) every few seconds, each with a one-second build-up so the eye
  is waiting for it; then it slows down for a 2 a.m. call in the van and dad's old wrench, and lands on proof people can
  check.
- **Sympathy is designed in.** Every Reel has a quiet beat between the truth and the payoff, and the music drops under
  the owner's honest line. Founder notes on the approved plumber Reel drove this: "always a video, shock factor
  transitions, fitting music, make the audience feel sympathy."
- **Any small business can post one today.** Ten business types (plumber, dentist, groomer, tutor, salon, gym, online
  seller, food truck, bakery, other), with or without a shop. Every client gets fresh transitions: used ones are never
  repeated.

## What it is

One ComfyUI graph in App Mode. Gemini (optional) writes the joke; Nano Banana 2 makes 8 keyframes; Veo 3.1
first/last-frame makes 7 moving clips; Sonilo Video-to-Music scores the cut; our open-source nodes check the facts,
build every prompt, cut the Reel with dissolves, keep the owner's real photo private and consent-gated, and mix the
music so it ducks under the honest line. A free draft version runs the whole thing locally for $0.

## Responsible by design

- Facts locked: the truth, the honest line and the payoff are the business's own words, copied in by code.
- Caption truth: a caption that says "2 locations" must show two; the ladder is rejected otherwise.
- No generated people. The only person is the owner's real photo, used only when "I have this person's consent" is on,
  labelled "Real photo", and never sent to any image, video or music model.
- "AI-generated" label on every generated shot. No real brands.

## Proof

- Approved example: `docs/examples/plumber-v5-approved.mp4` (made with this recipe before the app existed; clips drafted
  in Google Flow; it shows an AI-drafted plumber, which the app itself never generates).
- The app's own output: the free draft `docs/examples/taco-truck-draft-reel.mp4` (pressing Run in App Mode, $0).
  No paid run of the app is shown: the paid graph validates against live ComfyUI, but our Comfy credits ran out.
- Demo video (78 s): `docs/demo/honest-downgrade-demo.mp4`
- Cost per Reel from the node price badges: about $2.10 (Veo 3.1 lite) or $3.90 (Veo 3.1 fast); the draft is $0.
- Tests: 150 passing, partner nodes mocked; a real-browser run of the free draft in App Mode.

## Links and files

- Repo: https://github.com/jk-automations/honest-downgrade
- Workflow: `workflows/honest-downgrade.json` (opens in App Mode); free draft `workflows/honest-downgrade-draft.json`
- Licence: Apache-2.0 (code), SIL OFL (Inter font)
- Team: JK Automations (Justin and Keanu)

## Before submitting (founder checklist)

1. Decide on the paid demo run (`tools/run_paid_demo.py`, estimate $3.87, cap $4.00) and review its Reel.
2. Record the demo video from `docs/DEMO-PLAN.md`.
3. Make the repo public (or attach the workflow files) only after a final secret scan.
4. Confirm the fictional business names are clear of real businesses.
5. Paste the fields above into the challenge form and submit by 9:00 PT.
