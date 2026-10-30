# Example brief: an online seller working from a spare room

A fictional online shop with no premises: everything is made and packed at home. Text only: nothing was generated for
it. Type these values into the App Mode form, or call `honest_core.make_brief` with them.

| Field | Value |
|---|---|
| Business name | Little Ember Candles |
| Business type | Online seller (no storefront) |
| What you offer | poured soy candles shipped nationwide |
| Where the work happens | packed at home in a spare room |
| Who it is for | gift buyers who shop online |
| The truth: your real setup | a spare bedroom full of boxes |
| One honest line | The first 30 orders were all my friends. |
| The payoff: real proof | Every order ships within 24 hours. |
| Payoff still | (empty: the type default, a finished candle in its gift box) |
| Tone / joke | heartfelt / joke 1 |

The template writer's ladder for these inputs (printed by `honest_core.ladder_text`):

```
Little Ember Candles: Honest Downgrade (heartfelt)
1. BRAG         Our 200th warehouse just opened.
      ~ warp: tool tornado
2. DOWNGRADE 1  Ok, it's 2 warehouses.
      ~ warp: pop-up fold
3. DOWNGRADE 2  Ok, it's one shelf.
      ~ warp: mask match-cut
4. TRUTH        Ok, it's a spare bedroom full of boxes.
      ~ quiet move (sympathy beat)
5. STRUGGLE     (no caption)
      ~ quiet move (sympathy beat)
6. HEIRLOOM     The first 30 orders were all my friends.
      ~ warp: push-through door
7. PLACE        (no caption)
8. PAYOFF       Every order ships within 24 hours.
      ~ payoff macro (drop, splash, light)
```

The brag still shows "a gleaming grand-opening plaza in front of a giant automated warehouse" with a "200TH WAREHOUSE"
sign, and every still's prompt carries "The business: an online shop offering poured soy candles shipped nationwide."
Pick **Gemini** as the writer for jokes beyond the three templates; the truth, honest line and payoff stay word for word.
