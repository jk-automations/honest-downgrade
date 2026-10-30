"""The ComfyUI nodes and the whole partner pipeline with the partner nodes MOCKED: Gemini's reply is canned text,
Nano Banana 2 'returns' the sample stills, Veo first/last frame 'returns' a local clip made from the first and last
frames it was given, Sonilo 'returns' a sine tone. Nothing is sent to any API and nothing is paid."""
import json, subprocess, sys, tempfile
from pathlib import Path
import pytest
import honest_core as core

ROOT = Path(core.__file__).parent
PAID = {"GeminiNodeV3", "GeminiNanoBanana2V2", "Veo3FirstLastFrameNode", "SoniloVideoToMusic"}


@pytest.fixture(scope="module")
def nodes(comfy_path):
    import honest_nodes
    return honest_nodes


def _img(nodes, path):
    from PIL import Image
    return nodes._tensor(Image.open(path))


def _brief(nodes, writer=None, **kw):
    p = core.load_preset("taco-truck")
    args = dict(business_name=p["business_name"], business_type=nodes.TYPE_CHOICES[0], offer=p["offer"], setting=p["setting"],
                audience=p["audience"], true_setup=p["true_setup"], honest_line=p["honest_line"],
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
    """Stands in for Veo3FirstLastFrameNode: a clip of the asked length that starts on first_frame and ends on last_frame."""
    def __init__(self, nodes):
        self.nodes, self.calls = nodes, []

    def __call__(self, prompt, first_frame, last_frame, duration, model):
        self.calls.append({"prompt": prompt, "duration": duration, "model": model})
        d = Path(tempfile.mkdtemp())
        self.nodes._pil(first_frame).save(d / "a.png"); self.nodes._pil(last_frame).save(d / "b.png")
        out = core.draft_warp(d / "a.png", d / "b.png", "melt", d / "veo.mp4", secs=duration)
        return self.nodes.VideoFromFile(str(out))


class MockSonilo:
    """Stands in for SoniloVideoToMusic: records the video it was given, returns an AUDIO dict (a sine tone)."""
    def __init__(self):
        self.videos, self.prompts = [], []

    def __call__(self, video, prompt):
        import torch
        p = Path(tempfile.mkdtemp()) / "seen.mp4"; video.save_to(str(p))
        self.videos.append(p); self.prompts.append(prompt)
        sr, secs = 44100, core.probe(p)["dur"]
        t = torch.arange(int(sr * secs)) / sr
        wav = 0.3 * torch.sin(2 * torch.pi * 330 * t)
        return {"waveform": torch.stack([wav, wav])[None], "sample_rate": sr}


def run_pipeline(nodes, stills, writer_reply=None, owner=None, consent=False, with_score=True, music_path="", **brief_kw):
    """The app's graph, in order, with the four partner nodes mocked."""
    brief, wprompt, model = _brief(nodes, **brief_kw)
    lad_node = nodes.HonestLadder()
    need = lad_node.check_lazy_status(brief, None)
    reply = writer_reply(wprompt) if need else None
    ladder, text = lad_node.run(brief, reply)
    nb, veo, son = MockNanoBanana2(nodes, stills), MockVeoFirstLast(nodes), MockSonilo()
    keys = []
    for k in range(1, core.N_RUNGS + 1):
        kp, cap = nodes.HonestRung().run(ladder, k)
        keys.append(nb(kp, k - 1))
    board, check = nodes.HonestBoard().run(ladder, **{f"rung_{k}": t for k, t in enumerate(keys, 1)})
    vids = []
    for k, (a, z, kind, secs) in enumerate(core.SHOTS, 1):
        wp, dev = nodes.HonestWarp().run(ladder, k)
        vids.append(veo(wp, keys[a], keys[z], secs, model))
    score_cut, plan, mprompt = nodes.HonestAssemble().run(ladder, True, True, True, consent, owner_photo=owner,
                                                          **{f"clip_{k}": v for k, v in enumerate(vids, 1)})
    fin = nodes.HonestFinish()
    prompt = {"9": {"inputs": {"plan": ["8", 1], "music_path": music_path, **({"score": ["7", 0]} if with_score else {})}}}
    lazy = fin.check_lazy_status(plan, music_path, None, prompt, "9")
    score = son(score_cut, mprompt) if lazy else None
    reel, cut15, receipt = fin.run(plan, music_path, score, prompt, "9")
    return dict(ladder=json.loads(ladder), text=text, nb=nb, veo=veo, son=son, board=board, check=check, reel=reel, cut15=cut15,
                receipt=json.loads(receipt), need=need, plan=json.loads(plan), lazy=lazy)


def _save(video, name):
    p = Path(tempfile.mkdtemp()) / name
    video.save_to(str(p))
    return p


def test_brief_node_outputs(nodes):
    b, wp, model = _brief(nodes)
    assert json.loads(b)["business_type"] == "food-truck" and model == "veo-3.1-lite" and "JSON only" in wp
    assert set(core.VEO_MODELS) <= set(nodes.HonestBrief.INPUT_TYPES()["required"]["video_model"][0])
    assert nodes.HonestBrief.RETURN_TYPES[2] == core.VEO_MODELS


def test_mocked_partner_pipeline_end_to_end(nodes, stills):
    """Template ladder -> 8 mocked Nano Banana stills -> 7 mocked Veo clips -> Assemble -> mocked Sonilo -> Finish."""
    r = run_pipeline(nodes, stills)
    assert r["need"] == [], "the template writer never calls Gemini"
    assert len(r["nb"].prompts) == 8 and all("No people at all" in p for p in r["nb"].prompts)
    assert "200TH LOCATION" in r["nb"].prompts[0] and "a truck in a gas station parking lot" in r["nb"].prompts[3]
    assert [c["duration"] for c in r["veo"].calls] == [s[3] for s in core.SHOTS] and all(c["model"] == "veo-3.1-lite" for c in r["veo"].calls)
    assert all(s["motion"] in c["prompt"] for s, c in zip(r["ladder"]["shots"], r["veo"].calls))
    assert r["lazy"] == ["score"] and len(r["son"].videos) == 1 and "instrumental" in r["son"].prompts[0]
    assert r["receipt"]["music"].startswith("Sonilo score")
    pf, p15 = _save(r["reel"], "reel.mp4"), _save(r["cut15"], "c15.mp4")
    assert core.probe(pf)["dur"] == pytest.approx(r["plan"]["cuts"]["full"]["total"], abs=0.1)
    assert core.probe(p15)["dur"] == pytest.approx(15.0, abs=0.1)
    assert (core.probe(pf)["w"], core.probe(pf)["h"]) == (720, 1280) and core.probe(pf)["audio"]
    assert r["board"].shape == (1, 550, 8 * 270, 3)
    assert "brag" in r["check"] and "payoff: no sign to check" in r["check"]


def test_consent_blocks_the_run_at_the_node(nodes, stills, owner_photo):
    with pytest.raises(ValueError, match="I have this person's consent"):
        run_pipeline(nodes, stills, owner=_img(nodes, owner_photo), consent=False)
    req = nodes.HonestAssemble.INPUT_TYPES()["required"]["owner_consent"]
    assert req[0] == "BOOLEAN" and req[1]["default"] is False and "I have this person's consent" in req[1]["tooltip"]


def test_owner_photo_with_consent_is_never_shown_to_the_music_model(nodes, stills, textured_photo):
    r = run_pipeline(nodes, stills, owner=_img(nodes, textured_photo), consent=True)
    plan = r["plan"]
    assert plan["owner"] and Path(plan["score_cut"]).name == "score_cut.mp4"
    work = Path(plan["work"])
    assert "owner.png" not in (work / "ffmpeg_picture_full_masked.txt").read_text() and "private.png" in (work / "ffmpeg_picture_full_masked.txt").read_text()
    assert core.probe(r["son"].videos[0])["dur"] == pytest.approx(plan["cuts"]["full"]["total"], abs=0.1)
    assert [s[0] for s in r["receipt"]["full"]["segments"]] == ["clip"] * 6 + ["owner", "clip", "card"]


def test_own_track_skips_the_paid_score(nodes, stills, tmp_path):
    track = tmp_path / "mine.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=200:duration=10", str(track)], check=True)
    r = run_pipeline(nodes, stills, music_path=str(track))
    assert r["lazy"] == [] and r["son"].videos == [] and r["receipt"]["music"] == "your track: mine.wav"


def test_synth_bed_only_in_the_free_draft(nodes, stills):
    r = run_pipeline(nodes, stills, with_score=False)
    assert r["lazy"] == [] and r["receipt"]["music"].startswith("built-in synth bed (free draft only)")
    fin = nodes.HonestFinish()
    linked = {"9": {"inputs": {"score": ["7", 0]}}}
    with pytest.raises(ValueError, match="No music"):   # main app: the score is connected, so no silent fallback to the synth
        fin.run(json.dumps(r["plan"]), "", None, linked, "9")


def test_sign_check_reads_the_sample_signs(nodes, stills):
    import shutil as sh
    if not (sh.which("tesseract") or Path("/opt/homebrew/bin/tesseract").exists()):
        pytest.skip("tesseract not installed (the sign check is optional)")
    lad = core.build_ladder(*(lambda b: (b, core.template_joke(b)))(json.loads(_brief(nodes)[0])))
    from PIL import Image
    lines = nodes.sign_check(lad, [Image.open(s) for s in stills])
    assert "PASS" in lines[0] and "PASS" in lines[1], lines
    wrong = [Image.open(stills[2])] * 8   # a still without the sign must not pass
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
    v = nodes.HonestDraftWarp().run(_img(nodes, stills[7]), _img(nodes, stills[7]), lad, 7, 4)[0]
    assert core.probe(_save(v, "m.mp4"))["dur"] == pytest.approx(4.0, abs=0.1)


def test_blank_owner_slot_is_skipped(nodes, clips):
    import torch
    from comfy_api.input_impl import VideoFromFile
    lad = nodes.HonestLadder().run(_brief(nodes)[0])[0]
    vids = {f"clip_{k}": VideoFromFile(str(c)) for k, c in enumerate(clips, 1)}
    _, plan, _ = nodes.HonestAssemble().run(lad, True, True, True, False, owner_photo=torch.ones(1, 64, 64, 3), **vids)
    assert json.loads(plan)["owner"] is None


def _graph(tmp_path, *args):
    out = tmp_path / "g.json"
    subprocess.run([sys.executable, str(ROOT / "tools/build_app.py"), "--out", str(out), *args], check=True)
    return json.loads(out.read_text())


def test_partner_graph(tmp_path):
    g = _graph(tmp_path)
    by = lambda cls: sorted((k for k, v in g.items() if v["class_type"] == cls), key=int)
    kfs, veos = by("GeminiNanoBanana2V2"), by("Veo3FirstLastFrameNode")
    assert len(kfs) == 8 and len(veos) == 7 and len(by("GeminiNodeV3")) == 1 and len(by("SoniloVideoToMusic")) == 1
    assert len(by("SaveVideo")) == 7 + 2
    brief = by("HonestBrief")[0]
    for k, v in enumerate(veos):
        i = g[v]["inputs"]
        a, z, kind, secs = core.SHOTS[k]
        assert i["aspect_ratio"] == "9:16" and i["duration"] == secs and i["generate_audio"] is False and i["resolution"] == "720p"
        assert i["model"] == [brief, 2]
        assert i["first_frame"][0] == kfs[a] and i["last_frame"][0] == kfs[z], "each clip joins its two rungs"
    for k in kfs:
        assert g[k]["inputs"]["model.aspect_ratio"] == "9:16" and g[g[k]["inputs"]["prompt"][0]]["class_type"] == "HonestRung"
    lad = by("HonestLadder")[0]
    assert g[g[lad]["inputs"]["writer_reply"][0]]["class_type"] == "GeminiNodeV3"
    asm_id = by("HonestAssemble")[0]
    asm = g[asm_id]["inputs"]
    assert [g[asm[f"clip_{k}"][0]]["class_type"] for k in range(1, 8)] == ["Veo3FirstLastFrameNode"] * 7
    assert asm["owner_consent"] is False
    owner = asm["owner_photo"][0]
    assert g[owner]["class_type"] == "LoadImage"
    users = [(k, n["class_type"]) for k, n in g.items() for v in n["inputs"].values() if isinstance(v, list) and v[:1] == [owner]]
    assert users == [(asm_id, "HonestAssemble")], "the real photo goes to the edit only, never to a model"
    son = g[by("SoniloVideoToMusic")[0]]["inputs"]
    assert son["video"] == [asm_id, 0] and son["prompt"] == [asm_id, 2], "the score is made from the score cut"
    fin = g[by("HonestFinish")[0]]["inputs"]
    assert fin["score"] == [by("SoniloVideoToMusic")[0], 0] and fin["plan"] == [asm_id, 1]


def test_draft_graph_has_no_paid_nodes(tmp_path):
    g = _graph(tmp_path, "--draft")
    classes = {v["class_type"] for v in g.values()}
    assert not classes & PAID
    assert sum(v["class_type"] == "HonestDraftWarp" for v in g.values()) == 7
    fin = next(v for v in g.values() if v["class_type"] == "HonestFinish")["inputs"]
    assert "score" not in fin, "the free draft has no score: your track, else the synth bed"
