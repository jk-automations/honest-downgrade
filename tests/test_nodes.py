"""The ComfyUI nodes and the whole partner pipeline with the partner nodes MOCKED: Gemini's reply is canned text,
Nano Banana 2 'returns' the sample stills, Veo first/last frame 'returns' a local clip made from the first and last
frames it was given. Nothing is sent to any API and nothing is paid."""
import json, subprocess, sys, tempfile
from pathlib import Path
import pytest
import honest_core as core

ROOT = Path(core.__file__).parent


@pytest.fixture(scope="module")
def nodes(comfy_path):
    import honest_nodes
    return honest_nodes


def _img(nodes, path):
    from PIL import Image
    return nodes._tensor(Image.open(path))


def _brief(nodes, writer=None, **kw):
    p = core.load_preset("taco-truck")
    args = dict(business_name=p["business_name"], family=nodes.FAMILY_CHOICES[0], true_setup=p["true_setup"], honest_line=p["honest_line"],
                real_proof=p["real_proof"], hero_thing=p["hero_thing"], tone="heartfelt", joke="joke 1", already_used_warps="",
                video_model="veo-3.1-lite", writer=writer or nodes.WRITERS[0])
    args.update(kw)
    return nodes.HonestBrief().run(**args)


class MockNanoBanana2:
    """Stands in for GeminiNanoBanana2V2: records the prompt, returns the matching sample still."""
    def __init__(self, nodes, stills):
        self.nodes, self.stills, self.prompts = nodes, stills, []

    def __call__(self, prompt, k):
        self.prompts.append(prompt)
        return self.nodes._tensor(__import__("PIL.Image", fromlist=["Image"]).open(self.stills[k]))


class MockVeoFirstLast:
    """Stands in for Veo3FirstLastFrameNode: a 6 s clip that starts on first_frame and ends on last_frame."""
    def __init__(self, nodes):
        self.nodes, self.calls = nodes, []

    def __call__(self, prompt, first_frame, last_frame, duration, model):
        self.calls.append({"prompt": prompt, "duration": duration, "model": model})
        d = Path(tempfile.mkdtemp())
        self.nodes._pil(first_frame).save(d / "a.png"); self.nodes._pil(last_frame).save(d / "b.png")
        out = core.draft_warp(d / "a.png", d / "b.png", "melt", d / "veo.mp4", secs=duration)
        return self.nodes.VideoFromFile(str(out))


def run_pipeline(nodes, stills, writer_reply=None, ending=None, **brief_kw):
    """The app's graph, in order, with the three partner nodes mocked."""
    brief, wprompt, model = _brief(nodes, **brief_kw)
    lad_node = nodes.HonestLadder()
    need = lad_node.check_lazy_status(brief, None)
    reply = writer_reply(wprompt) if need else None
    ladder, text = lad_node.run(brief, reply)
    nb, veo = MockNanoBanana2(nodes, stills), MockVeoFirstLast(nodes)
    keys = []
    for k in range(1, 6):
        kp, cap = nodes.HonestRung().run(ladder, k)
        keys.append(nb(kp, k - 1))
    board, check = nodes.HonestBoard().run(ladder, **{f"rung_{k}": t for k, t in enumerate(keys, 1)})
    vids = []
    for k in range(1, 5):
        wp, dev = nodes.HonestWarp().run(ladder, k)
        vids.append(veo(wp, keys[k - 1], keys[k], core.WARP_SECONDS, model))
    r30, r15, receipt = nodes.HonestAssemble().run(ladder, *vids, True, True, True, "", ending_photo=ending)
    return dict(ladder=json.loads(ladder), text=text, nb=nb, veo=veo, board=board, check=check, r30=r30, r15=r15,
                receipt=json.loads(receipt), need=need)


def _save(video, name):
    p = Path(tempfile.mkdtemp()) / name
    video.save_to(str(p))
    return p


def test_brief_node_outputs(nodes):
    b, wp, model = _brief(nodes)
    assert json.loads(b)["family"] == "food" and model == "veo-3.1-lite" and "JSON only" in wp
    assert set(core.VEO_MODELS) <= set(nodes.HonestBrief.INPUT_TYPES()["required"]["video_model"][0])
    assert nodes.HonestBrief.RETURN_TYPES[2] == core.VEO_MODELS


def test_mocked_partner_pipeline_end_to_end(nodes, stills, ending_photo):
    """Template ladder -> 5 mocked Nano Banana stills -> 4 mocked Veo warps -> Assemble -> 30 s + 15 s MP4s."""
    r = run_pipeline(nodes, stills, ending=_img(nodes, ending_photo))
    assert r["need"] == [], "the template writer never calls Gemini"
    assert len(r["nb"].prompts) == 5 and all("No people at all" in p for p in r["nb"].prompts)
    assert "200TH LOCATION" in r["nb"].prompts[0] and "a truck in a gas station parking lot" in r["nb"].prompts[3]
    assert [c["duration"] for c in r["veo"].calls] == [6] * 4 and all(c["model"] == "veo-3.1-lite" for c in r["veo"].calls)
    devs = [w["device"] for w in r["ladder"]["warps"]]
    assert all(d in c["prompt"] or core.DEVICES[d][:30] in c["prompt"] for d, c in zip(devs, r["veo"].calls))
    p30, p15 = _save(r["r30"], "r30.mp4"), _save(r["r15"], "r15.mp4")
    assert core.probe(p30)["dur"] == pytest.approx(30.0, abs=0.1) and core.probe(p15)["dur"] == pytest.approx(15.0, abs=0.1)
    assert (core.probe(p30)["w"], core.probe(p30)["h"]) == (720, 1280) and core.probe(p30)["audio"]
    assert r["board"].shape == (1, 550, 1350, 3)
    assert "brag" in r["check"] and "payoff: no sign to check" in r["check"]


def test_sign_check_reads_the_sample_signs(nodes, stills):
    import shutil as sh
    if not (sh.which("tesseract") or Path("/opt/homebrew/bin/tesseract").exists()):
        pytest.skip("tesseract not installed (the sign check is optional)")
    lad = core.build_ladder(*(lambda b: (b, core.template_joke(b)))(json.loads(_brief(nodes)[0])))
    from PIL import Image
    lines = nodes.sign_check(lad, [Image.open(s) for s in stills])
    assert "PASS" in lines[0] and "PASS" in lines[1], lines
    wrong = [Image.open(stills[2])] * 5   # a still without the sign must not pass
    assert "NOT FOUND" in nodes.sign_check(lad, wrong)[0]


def test_mocked_gemini_writer_is_asked_lazily(nodes, stills):
    asked = []
    def gemini(prompt):
        asked.append(prompt)
        j = core.template_joke(json.loads(_brief(nodes)[0]))
        j["rungs"][0] = {"caption": "We have 900 food trucks.", "visual": "a desert lot with 900 identical plain food trucks in rows", "sign": "900 TRUCKS"}
        return "```json\n" + json.dumps(j) + "\n```"
    r = run_pipeline(nodes, stills, writer_reply=gemini, writer=nodes.WRITERS[1])
    assert r["need"] == ["writer_reply"] and len(asked) == 1 and "a truck in a gas station parking lot" in asked[0]
    assert r["ladder"]["rungs"][0]["caption"] == "We have 900 food trucks."
    assert r["ladder"]["rungs"][3]["caption"] == "Ok, it's a truck in a gas station parking lot.", "facts survive the writer"
    with pytest.raises(ValueError, match="no readable JSON"):
        nodes.HonestLadder().run(_brief(nodes, writer=nodes.WRITERS[1])[0], "sorry, no")


def test_draft_warp_node(nodes, stills, tmp_path):
    lad = nodes.HonestLadder().run(_brief(nodes)[0])[0]
    v = nodes.HonestDraftWarp().run(_img(nodes, stills[0]), _img(nodes, stills[1]), lad, 1, 4)[0]
    assert core.probe(_save(v, "d.mp4"))["dur"] == pytest.approx(4.0, abs=0.1)


def test_blank_ending_slot_is_skipped(nodes, warps):
    import torch
    from comfy_api.input_impl import VideoFromFile
    lad = nodes.HonestLadder().run(_brief(nodes)[0])[0]
    vids = [VideoFromFile(str(w)) for w in warps]
    _, _, receipt = nodes.HonestAssemble().run(lad, *vids, True, True, True, "", ending_photo=torch.ones(1, 64, 64, 3))
    assert json.loads(receipt)["reel_30s"]["ending"] is None


def _graph(tmp_path, *args):
    out = tmp_path / "g.json"
    subprocess.run([sys.executable, str(ROOT / "tools/build_app.py"), "--out", str(out), *args], check=True)
    return json.loads(out.read_text())


def test_partner_graph(tmp_path):
    g = _graph(tmp_path)
    by = lambda cls: [k for k, v in g.items() if v["class_type"] == cls]
    kfs, veos = by("GeminiNanoBanana2V2"), by("Veo3FirstLastFrameNode")
    assert len(kfs) == 5 and len(veos) == 4 and len(by("GeminiNodeV3")) == 1 and len(by("SaveVideo")) == 6
    brief = by("HonestBrief")[0]
    for k, v in enumerate(sorted(veos, key=int)):
        i = g[v]["inputs"]
        assert i["aspect_ratio"] == "9:16" and i["duration"] == 6 and i["generate_audio"] is False and i["resolution"] == "720p"
        assert i["model"] == [brief, 2]
        assert i["first_frame"][0] == sorted(kfs, key=int)[k] and i["last_frame"][0] == sorted(kfs, key=int)[k + 1], "consecutive rungs"
    for k in kfs:
        assert g[k]["inputs"]["model.aspect_ratio"] == "9:16" and g[g[k]["inputs"]["prompt"][0]]["class_type"] == "HonestRung"
    lad = by("HonestLadder")[0]
    assert g[g[lad]["inputs"]["writer_reply"][0]]["class_type"] == "GeminiNodeV3"
    asm = g[by("HonestAssemble")[0]]["inputs"]
    assert [g[asm[f"warp_{k}"][0]]["class_type"] for k in range(1, 5)] == ["Veo3FirstLastFrameNode"] * 4
    assert g[asm["ending_photo"][0]]["class_type"] == "LoadImage"


def test_draft_graph_has_no_paid_nodes(tmp_path):
    g = _graph(tmp_path, "--draft")
    classes = {v["class_type"] for v in g.values()}
    assert not classes & {"GeminiNodeV3", "GeminiNanoBanana2V2", "Veo3FirstLastFrameNode"}
    assert sum(v["class_type"] == "HonestDraftWarp" for v in g.values()) == 4
