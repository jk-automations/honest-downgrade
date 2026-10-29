"""The ladder writer: every business type and joke, facts copied word for word, caption truth, no people, no repeated warp."""
import json
import pytest
import honest_core as core

def brief(fam="food-truck", tone="heartfelt", variant=1, honest="Started with $800 in 2019.", avoid=""):
    setup, _, proof = core.BUSINESS_TYPES[fam]["example"]
    offer = "custom cake toppers" if fam == "other" else ""
    return core.make_brief("Test Shop", fam, setup, honest, proof, "", tone, variant, avoid, offer=offer)


@pytest.mark.parametrize("fam", core.TYPE_KEYS)
@pytest.mark.parametrize("variant", [1, 2, 3])
@pytest.mark.parametrize("tone", ["heartfelt", "playful"])
def test_every_business_type_joke_and_tone_builds_a_valid_ladder(fam, variant, tone):
    b = brief(fam, tone, variant)
    lad = core.build_ladder(b, core.template_joke(b))
    assert [r["role"] for r in lad["rungs"]] == core.ROLES
    assert core.check_ladder(lad, b) == []
    devs = [w["device"] for w in lad["warps"]]
    assert len(devs) == 4 and len(set(devs)) == 4, "no repeated warp device"
    assert devs[0] in core.BUSINESS_TYPES[fam]["devices"], "the business type's own wild cards come first"
    setup, _, proof = core.BUSINESS_TYPES[fam]["example"]
    assert setup in lad["rungs"][3]["caption"] and lad["rungs"][4]["caption"] == proof
    assert lad["rungs"][3]["honest_line"] == ("Started with $800 in 2019." if tone == "heartfelt" else "")
    for k in range(5):
        kp = core.keyframe_prompt(lad, k)
        assert lad["rungs"][k]["caption"] in kp and "No people" in kp
    for k in range(4):
        assert lad["warps"][k]["motion"] in core.warp_prompt(lad, k)


def test_jokes_differ_and_rotate_devices():
    lads = [core.build_ladder(brief(variant=v), core.template_joke(brief(variant=v))) for v in (1, 2, 3)]
    assert len({l["rungs"][0]["caption"] for l in lads}) == 3
    assert len({l["warps"][0]["device"] for l in lads}) == 3


def test_facts_are_copied_word_for_word_never_rewritten():
    b = brief()
    lad = core.build_ladder(b, core.template_joke(b))
    assert lad["rungs"][3]["caption"] == "Ok, it's a truck in a gas station parking lot."
    assert lad["facts"] == b["facts"]
    # a writer reply that tries to write the truth and payoff itself is refused: it may only write the joke
    joke = core.template_joke(b)
    joke["rungs"] += [{"caption": "Ok it's a palace", "visual": "a palace"}, {"caption": "Best tacos in the world", "visual": "tacos"}]
    with pytest.raises(ValueError, match="exactly 3 joke rungs"):
        core.build_ladder(b, joke)


def test_no_honest_line_means_playful_never_invented():
    b = brief(tone="heartfelt", honest="")
    assert b["tone"] == "playful"
    assert core.build_ladder(b, core.template_joke(b))["rungs"][3]["honest_line"] == ""


def test_missing_facts_and_brands_are_refused():
    with pytest.raises(ValueError, match="real setup"):
        core.make_brief("Shop", "food-truck", "", "", "proof", "")
    with pytest.raises(ValueError, match="real proof"):
        core.make_brief("Shop", "food-truck", "a truck", "", "", "")
    with pytest.raises(ValueError, match="brand"):
        core.make_brief("Shop", "plumber", "my van", "", "Ask about our Lamborghini detailing.", "")
    with pytest.raises(ValueError, match="brand"):
        core.make_brief("Shop", "online-seller", "my room", "", "proof", "", offer="cases for your iPhone")
    with pytest.raises(ValueError, match="business type"):
        core.make_brief("Shop", "cars", "my van", "", "proof", "")
    with pytest.raises(ValueError, match="offers"):
        core.make_brief("Shop", "other", "my van", "", "proof", "")


def test_already_used_warps_are_never_repeated():
    used = "ribbon snake, steam swirl"
    b = brief(avoid=used)
    devs = [w["device"] for w in core.build_ladder(b, core.template_joke(b))["warps"]]
    assert not {"ribbon snake", "steam swirl"} & set(devs)
    b = brief(avoid=",".join(core.BUSINESS_TYPES["food-truck"]["devices"] + core.GENERIC_DEVICES[:3]))
    with pytest.raises(ValueError, match="Not enough unused warp devices"):
        core.template_joke(b)


def _reply(**patch):
    j = core.template_joke(brief())
    for k, v in patch.items():
        idx, field = k.split("_", 1)
        j["rungs"][int(idx)][field] = v
    return j


def test_caption_truth_numbers_must_be_visible():
    b = brief()
    bad = _reply(**{"1_caption": "Ok, it's 3 locations.", "1_sign": ""})
    with pytest.raises(ValueError, match="caption says 3 but the visual does not show 3"):
        core.build_ladder(b, bad)


def test_ai_stills_never_show_people():
    b = brief()
    with pytest.raises(ValueError, match="may not show people"):
        core.build_ladder(b, _reply(**{"2_visual": "one service window with a smiling cook leaning out"}))
    ok = _reply(**{"2_visual": "one service window, no people, a chalk menu board"})
    assert core.build_ladder(b, ok)["rungs"][2]["visual"].startswith("one service window")
    with pytest.raises(ValueError, match="may not show people"):
        core.build_ladder(core.make_brief("S", "food-truck", "a truck", "", "proof", "the owner holding a plate"), core.template_joke(b))


def test_downgrade_must_cut_the_number():
    with pytest.raises(ValueError, match="cut the brag's number"):
        core.build_ladder(brief(), _reply(**{"1_caption": "Ok, it's 300 locations.", "1_sign": "300"}))


def test_gemini_reply_parsing_and_rules():
    b = brief()
    joke = core.template_joke(b)
    reply = "Sure! Here you go:\n```json\n" + json.dumps(joke) + "\n```"
    assert core.build_ladder(b, core.parse_reply(reply))["warps"][0]["device"] == "ribbon snake"
    dup = json.loads(json.dumps(joke)); dup["warps"][3] = dict(dup["warps"][0])
    with pytest.raises(ValueError, match="device repeats"):
        core.build_ladder(b, dup)
    with pytest.raises(ValueError, match="no readable JSON"):
        core.parse_reply("I can't do that.")
    new = json.loads(json.dumps(joke)); new["warps"][1] = {"device": "salsa tsunami", "motion": "a wave of salsa crashes over the lens and drains to reveal"}
    assert core.build_ladder(b, new)["warps"][1]["device"] == "salsa tsunami"   # invented devices are fine if unique


def test_writer_prompt_carries_the_locked_facts():
    b = brief()
    wp = core.writer_prompt(b)
    assert "a truck in a gas station parking lot" in wp and "The line at 11pm is real." in wp
    assert "JSON only" in wp and "never people" in wp and "ribbon snake" in wp


def test_ladder_text():
    b = brief()
    t = core.ladder_text(core.build_ladder(b, core.template_joke(b)))
    assert "BRAG" in t and "warp: ribbon snake" in t and "Started with $800 in 2019." in t
