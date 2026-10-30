# Example brief: a plumber with no storefront

A fictional service business that works in other people's homes and has no shop. Text only: nothing was generated
for it. Type these values into the App Mode form, or call `honest_core.make_brief` with them.

| Field | Value |
|---|---|
| Business name | Drip Doctor Plumbing |
| Business type | Plumber (no storefront) |
| What you offer | leak repairs, drains and water heater installs |
| Where the work happens | on call across the east side, in homes and small offices |
| Who it is for | homeowners and landlords who need it fixed today |
| The truth: your real setup | a van and a phone that never stops ringing |
| One honest line | My dad taught me on weekends. |
| The payoff: real proof | Same-day callbacks, every time. |
| Payoff still | (empty: the type default, a new copper fitting under a clean sink) |
| Tone / joke | heartfelt / joke 2 |

The template writer's ladder for these inputs (printed by `honest_core.ladder_text`):

```
Drip Doctor Plumbing: Honest Downgrade (heartfelt)
1. BRAG         We have 40 work trucks.
      ~ warp: tool smash
2. DOWNGRADE 1  Ok, it's 4 work trucks.
      ~ warp: geyser
3. DOWNGRADE 2  Ok, no work trucks. One toolbox.
      ~ warp: tool tornado
4. TRUTH        Ok, it's a van and a phone that never stops ringing.
      ~ quiet move (sympathy beat)
5. STRUGGLE     (no caption)
      ~ quiet move (sympathy beat)
6. HEIRLOOM     My dad taught me on weekends.
      ~ warp: push-through door
7. PLACE        (no caption)
8. PAYOFF       Same-day callbacks, every time.
      ~ payoff macro (drop, splash, light)
```

The brag still's prompt starts "The business: a plumbing business offering leak repairs, drains and water heater
installs." and shows "a vast depot lot with 40 identical work trucks in long rows" with a "40 WORK TRUCKS" sign. The
truth still adds "Where it really happens: on call across the east side, in homes and small offices." No storefront
and no people appear in any AI still. The sympathy beat is the type's template: the van cab at 2 a.m., then an old
taped pipe wrench, carrying the honest line. The owner's real photo (optional, with consent) is the business's own.
This is the brief behind the approved plumber Reel ([`plumber-v5-approved.mp4`](plumber-v5-approved.mp4)) and the paid demo
(`tools/run_paid_demo.py`).
