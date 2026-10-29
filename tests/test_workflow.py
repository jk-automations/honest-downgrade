"""The shipped App Mode workflows (made by tools/make_app.mjs in the real ComfyUI frontend)."""
import json
from pathlib import Path
import pytest

WF_DIR = Path(__file__).resolve().parent.parent / "workflows"


def load(name):
    wf = json.loads((WF_DIR / name).read_text())
    return wf, {n["id"]: n for n in wf["nodes"]}


@pytest.mark.parametrize("name", ["honest-downgrade.json", "honest-downgrade-draft.json"])
def test_opens_in_app_mode_with_the_form(name):
    wf, nodes = load(name)
    assert wf["extra"]["linearMode"] is True
    names = [(nodes[i]["type"], w) for i, w in wf["extra"]["linearData"]["inputs"]]
    for w in ("business_name", "family", "true_setup", "honest_line", "real_proof", "hero_thing", "tone", "joke", "already_used_warps"):
        assert ("HonestBrief", w) in names
    assert ("HonestAssemble", "music_path") in names and ("LoadImage", "image") in names
    outs = sorted(nodes[i]["title"] for i in wf["extra"]["linearData"]["outputs"])
    assert outs == ["Board", "Cutdown (15 s)", "Sign check", "Your Reel (30 s)", "Your ladder"]
    assert not any("randomize" in (n.get("widgets_values") or []) for n in wf["nodes"]), "a re-run must reuse paid steps"


def test_partner_app():
    wf, nodes = load("honest-downgrade.json")
    types = [n["type"] for n in wf["nodes"]]
    assert types.count("Veo3FirstLastFrameNode") == 4 and types.count("GeminiNanoBanana2V2") == 5 and types.count("GeminiNodeV3") == 1
    for n in wf["nodes"]:
        if n["type"] == "Veo3FirstLastFrameNode":
            ins = {i["name"]: i for i in n["inputs"]}
            assert ins["model"]["link"] is not None and ins["first_frame"]["link"] and ins["last_frame"]["link"]


def test_draft_app_is_free():
    wf, nodes = load("honest-downgrade-draft.json")
    types = {n["type"] for n in wf["nodes"]}
    assert not types & {"Veo3FirstLastFrameNode", "GeminiNanoBanana2V2", "GeminiNodeV3"}
    assert sum(n["type"] == "LoadImage" for n in wf["nodes"]) == 6   # 5 rung stills + the real ending photo
