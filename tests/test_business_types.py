"""Any small business, not only food and not only shops: the business-type preset table, the ladder templates filled
from it, and the prompts filled from the business's own offer / setting / audience. Nothing taco or food leaks into a
non-food business. The taco truck stays the sample and the default demo."""
import json
import re
import pytest
import honest_core as core

FOOD_TYPES = {"food-truck", "bakery"}
NON_FOOD = [k for k in core.TYPE_KEYS if k not in FOOD_TYPES]
NO_STOREFRONT = [k for k, t in core.BUSINESS_TYPES.items() if not t["storefront"] and k not in FOOD_TYPES]
FOOD_WORDS = ["taco", "tacos", "al pastor", "zorrito", "food", "foods", "dish", "dishes", "kitchen", "recipe", "recipes", "menu",
              "grill", "grills", "flat-top", "steam", "salsa", "chili", "chilies", "ingredient", "ingredients", "restaurant",
              "restaurants", "cilantro", "lime", "tray", "napkin", "hot-sauce", "sauce", "burner", "burners", "dining", "eat",
              "eaters", "hungry", "chef", "cook", "bake", "baked", "bakery", "bread", "loaf", "flour", "pastry", "pastries",
              "oven", "ovens", "11pm", "mom's recipes"]
STOREFRONT_WORDS = ["storefront", "shop window", "service window", "street-front"]


def words_in(text, words):
    return sorted({w for w in words if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text, re.I)})


def every_output(b):
    """Everything the planner and the prompt builders produce for one brief, as one string."""
    lad = core.build_ladder(b, core.template_joke(b))
    parts = [json.dumps(b), json.dumps(lad), core.writer_prompt(b), core.ladder_text(lad)]
    parts += [core.keyframe_prompt(lad, k) for k in range(core.N_RUNGS)] + [core.warp_prompt(lad, k) for k in range(core.N_CLIPS)]
    return "\n".join(parts), lad


def test_preset_table_covers_varied_businesses():
    assert len(core.BUSINESS_TYPES) >= 8
    assert {"food-truck", "bakery", "plumber", "dentist", "dog-groomer", "tutor", "salon", "gym", "online-seller", "other"} <= set(core.TYPE_KEYS)
    assert {"plumber", "tutor", "online-seller", "dog-groomer"} <= set(NO_STOREFRONT), "service businesses with no storefront"
    for k, t in core.BUSINESS_TYPES.items():
        assert set(core.TEMPLATE_SLOTS) <= set(t["slots"]), k
        assert len(t["devices"]) == 3 and all(d in core.DEVICES and d in core.DRAFT_TRANSITION for d in t["devices"]), k
        assert core.PLACE_DEVICE not in t["devices"], "the push to the place of work is kept for the ending"
        assert core.business_type_key(t["label"]) == k and core.business_type_key(k) == k
        for v in list(t["slots"].values()) + [t["hero"], t["struggle"], t["heirloom"], t["place"], t["hero_motion"], t["trade_tool"],
                                              t["trade_tools"], t["material"]]:
            assert not core.people_in(v) and not core.brands_in(v), (k, v)


@pytest.mark.parametrize("key", NON_FOOD)
@pytest.mark.parametrize("variant", [1, 2, 3])
def test_no_food_or_taco_words_leak_into_non_food_businesses(key, variant):
    offer = "wedding photo albums" if key == "other" else ""
    text, lad = every_output(core.type_brief(key, f"Sample {key}", variant=variant, offer=offer))
    assert words_in(text, FOOD_WORDS) == [], f"{key}: food words leaked"
    assert core.check_ladder(lad, core.type_brief(key, f"Sample {key}", variant=variant, offer=offer)) == []


@pytest.mark.parametrize("key", NO_STOREFRONT)
def test_no_storefront_assumed_for_businesses_without_one(key):
    offer = "wedding photo albums" if key == "other" else ""
    for v in (1, 2, 3):
        text, _ = every_output(core.type_brief(key, variant=v, offer=offer))
        assert words_in(text, STOREFRONT_WORDS) == [], key


@pytest.mark.parametrize("key", NON_FOOD)
def test_prompts_are_filled_from_the_business_inputs(key):
    offer, setting, audience = "boiler servicing and gas safety checks", "in basements and plant rooms", "small landlords"
    b = core.type_brief(key, "Northside Co", offer=offer, setting=setting, audience=audience)
    lad = core.build_ladder(b, core.template_joke(b))
    wp = core.writer_prompt(b)
    assert offer in wp and setting in wp and audience in wp and core.BUSINESS_TYPES[key]["kind"] in wp
    kps = [core.keyframe_prompt(lad, k) for k in range(core.N_RUNGS)]
    assert all(offer in kp for kp in kps), "every still knows what the business offers"
    assert setting in kps[3] and all(setting not in kp for k, kp in enumerate(kps) if k != 3), "the real setting only in the truth still"
    # empty inputs fall back to the business type's defaults
    d = core.type_brief(key, offer="wedding photo albums" if key == "other" else "")
    assert d["setting"] == core.BUSINESS_TYPES[key]["setting"] and d["audience"] == core.BUSINESS_TYPES[key]["audience"]


def test_other_builds_its_payoff_from_the_offer():
    b = core.type_brief("other", offer="wedding photo albums")
    assert b["hero_thing"].startswith("wedding photo albums")
    lad = core.build_ladder(b, core.template_joke(b))
    assert "wedding photo albums" in core.keyframe_prompt(lad, 7)


def test_the_ladder_nouns_follow_the_business_type():
    caps = lambda key, v: [r["caption"] for r in core.template_joke(core.type_brief(key, variant=v, offer="photo albums"))["rungs"]]
    assert caps("plumber", 1) == ["Our 200th branch just opened.", "Ok, it's 2 branches.", "Ok, it's one van."]
    assert caps("tutor", 2) == ["We have 40 classrooms.", "Ok, it's 4 classrooms.", "Ok, no classrooms. One whiteboard."]
    assert caps("online-seller", 3)[2] == "Ok, no crew. One laptop."
    assert len({caps(k, 1)[2] for k in core.TYPE_KEYS}) >= 7, "the humble rung differs by business"


def test_food_detector_works_on_the_food_sample():
    text, _ = every_output(core.type_brief("food-truck"))
    assert words_in(text, FOOD_WORDS), "sanity: the detector does see food words in the food truck's own ladder"


def test_taco_truck_is_still_the_default_demo():
    p = core.load_preset("taco-truck")
    assert core.list_presets()[0] == "taco-truck" and p["business_name"] == "Tacos El Zorrito Azul"
    b = core.make_brief(p["business_name"], p["business_type"], p["true_setup"], p["honest_line"], p["real_proof"], p["hero_thing"],
                        p["tone"], 1, offer=p["offer"], setting=p["setting"], audience=p["audience"])
    lad = core.build_ladder(b, core.template_joke(b))
    # the shipped demo Reel and the placeholder stills show exactly these captions and signs
    assert [r["caption"] for r in lad["rungs"]] == ["Our 200th location just opened.", "Ok, it's 2 locations.", "Ok, it's one window.",
                                                    "Ok, it's a truck in a gas station parking lot.", "",
                                                    "Started with $800 and my mom's recipes.", "", "The line at 11pm is real."]
    assert [r["sign"] for r in lad["rungs"][:2]] == ["200TH LOCATION", "2 LOCATIONS"]
    assert [w["device"] for w in lad["warps"]] == ["creature", "pop-up fold", "flock burst", "push-through door"]


def test_brief_node_takes_any_business_type(comfy_path):
    import honest_nodes as nodes
    req = nodes.HonestBrief.INPUT_TYPES()["required"]
    assert req["business_type"][0] == core.TYPE_CHOICES and req["business_type"][1]["default"] == "Food truck"
    for f in ("offer", "setting", "audience"):
        assert f in req
    b, wp, _ = nodes.HonestBrief().run("Drip Doctor", "Plumber (no storefront)", "", "", "", "a van and one ladder", "My dad taught me.",
                                       "Same-day callbacks, every time.", "", "heartfelt", "joke 2", "", "veo-3.1-lite", nodes.WRITERS[0])
    lad, text = nodes.HonestLadder().run(b)
    assert json.loads(b)["business_type"] == "plumber" and "plumbing business" in wp
    assert "We have 40 work trucks." in text and words_in(lad + text + wp, FOOD_WORDS) == []


@pytest.mark.parametrize("name", ["plumber-brief.md", "online-candles-brief.md"])
def test_example_briefs_in_docs_match_the_code(name):
    """docs/examples/*-brief.md: the ladder printed there is what the code makes from the table's inputs."""
    from pathlib import Path
    md = (Path(core.__file__).parent / "docs" / "examples" / name).read_text()
    row = dict(re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|$", md, re.M))
    tone, joke = (s.strip() for s in row["Tone / joke"].split("/"))
    b = core.make_brief(row["Business name"], row["Business type"], row["The truth: your real setup"], row["One honest line"],
                        row["The payoff: real proof"], "", tone, int(joke.split()[-1]), offer=row["What you offer"],
                        setting=row["Where the work happens"], audience=row["Who it is for"])
    text, lad = every_output(b)
    assert core.ladder_text(lad) in md
    assert words_in(text, FOOD_WORDS) == []
