"""The edit: 30 s Reel and 15 s cutdown from the same four warps, classic captions, AI label, real-ending label,
music drop, loudness. Warps here are ffmpeg test patterns (no AI generation)."""
import json, re, subprocess
import pytest
import honest_core as core
from conftest import FFMPEG, make_clip


def ladder(tone="heartfelt", honest="Started with $800 and my mom's recipes."):
    p = core.load_preset("taco-truck")
    b = core.make_brief(p["business_name"], p["family"], p["true_setup"], honest, p["real_proof"], p["hero_thing"], tone, 1)
    return core.build_ladder(b, core.template_joke(b))


def lufs(path):
    log = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])


def test_reel_30s_with_real_ending(warps, ending_photo, tmp_path):
    lad = ladder()
    r = core.assemble(warps, lad, tmp_path / "r30.mp4", tmp_path / "w", ending_photo, 30)
    info = core.probe(tmp_path / "r30.mp4")
    assert info["dur"] == pytest.approx(30.0, abs=0.1) and (info["w"], info["h"]) == (360, 640) and info["audio"]
    texts = [c[2] for c in r["captions"]]
    assert texts == [x["caption"] for x in lad["rungs"][:4]] + [lad["rungs"][3]["honest_line"], lad["rungs"][4]["caption"]]
    starts = [c[0] for c in r["captions"]]
    assert starts == sorted(starts), "captions come in ladder order"
    assert all(b > a + 1.0 for a, b, _ in r["captions"]), "every caption is up long enough to read"
    assert [l[0] for l in r["labels"]] == ["AI-generated", "Real"]
    assert r["labels"][0][2] == pytest.approx(24.0, abs=0.01), "AI label covers every AI shot and stops at the real ending"
    assert r["drop"] and r["drop"][0] < r["captions"][4][0] + 0.01, "music drops under the honest line"
    assert len(list((tmp_path / "w" / "ov").glob("cap*.png"))) == 6
    cmd = (tmp_path / "w" / "ffmpeg_cmd_30.txt").read_text()
    assert "concat=n=6" in cmd and "loudnorm=I=-14" in cmd and "libx264" in cmd and "aevalsrc" in cmd
    assert lufs(tmp_path / "r30.mp4") == pytest.approx(-14, abs=1.5)


def test_cutdown_15s_from_the_same_shots(warps, ending_photo, tmp_path):
    lad = ladder()
    r = core.assemble(warps, lad, tmp_path / "r15.mp4", tmp_path / "w", ending_photo, 15)
    assert core.probe(tmp_path / "r15.mp4")["dur"] == pytest.approx(15.0, abs=0.1)
    assert [c[2] for c in r["captions"]] == [lad["rungs"][0]["caption"], lad["rungs"][3]["caption"], lad["rungs"][4]["caption"]]
    used = {(s[0], s[1]) for s in r["segments"]}
    assert used == {("warp", 0), ("warp", 2), ("warp", 3), ("ending", 0), ("card", 0)}, "brag, one warp, truth, payoff, card"
    assert lufs(tmp_path / "r15.mp4") == pytest.approx(-14, abs=1.5)


def test_no_ending_and_playful(warps, tmp_path):
    lad = ladder("playful")
    r = core.assemble(warps, lad, tmp_path / "p.mp4", tmp_path / "w", None, 30)
    assert core.probe(tmp_path / "p.mp4")["dur"] == pytest.approx(27.5, abs=0.1), "4 x 6 s warps + 3.5 s end card"
    assert r["drop"] is None and len(r["captions"]) == 5 and [l[0] for l in r["labels"]] == ["AI-generated"]
    r = core.assemble(warps, lad, tmp_path / "q.mp4", tmp_path / "w2", None, 15, captions=False, ai_label=False, credit=False)
    assert r["captions"] == [] and r["labels"] == [] and core.probe(tmp_path / "q.mp4")["dur"] == pytest.approx(15.0, abs=0.1)


def test_real_ending_clip_and_owned_music(warps, tmp_path):
    clip = make_clip(tmp_path / "real.mp4", 5.0, audio=True)
    track = tmp_path / "owned.wav"   # stands in for a track you own
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=4", str(track)], check=True)
    r = core.assemble(warps, ladder(), tmp_path / "m.mp4", tmp_path / "w", clip, 30, music_path=track)
    cmd = (tmp_path / "w" / "ffmpeg_cmd_30.txt").read_text()
    assert r["music"] == str(track) and "-stream_loop -1" in cmd and "aevalsrc" not in cmd
    assert core.probe(tmp_path / "m.mp4")["dur"] == pytest.approx(30.0, abs=0.1)
    with pytest.raises(ValueError, match="music_path"):
        core.assemble(warps, ladder(), tmp_path / "x.mp4", tmp_path / "x", None, 30, music_path=tmp_path / "nope.mp3")
    with pytest.raises(ValueError, match="4 warp clips"):
        core.assemble(warps[:3], ladder(), tmp_path / "x.mp4", tmp_path / "x", None, 30)


def test_long_warps_are_trimmed_at_the_head_to_fit_30s():
    segs, caps, end_at = core.plan_cut([8, 8, 8, 8], ladder(), ending_len=6, length=30)
    assert sum(b - a for _, _, a, b in segs) == pytest.approx(30.0, abs=0.01)
    assert segs[0][2] == 0 and all(s[2] > 0 for s in segs[1:4]), "warp 1 is whole; later warps lose their repeated first frames"
    assert all(s[3] == 8 for s in segs[:4]), "every warp keeps its landing frame"


def test_draft_warp_and_board(stills, tmp_path):
    out = core.draft_warp(stills[0], stills[1], "ribbon snake", tmp_path / "d.mp4", secs=4)
    info = core.probe(out)
    assert info["dur"] == pytest.approx(4.0, abs=0.1) and (info["w"], info["h"]) == (720, 1280)
    from PIL import Image
    sheet = core.board([Image.open(s) for s in stills], ["a", "b", "c", "d", "e"], tmp_path / "b.png")
    assert sheet.size == (5 * 270, 480 + 70)
