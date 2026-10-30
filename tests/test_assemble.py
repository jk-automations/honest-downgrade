"""The edit: the full Reel and the 15 s cutdown from the same seven clips, dissolves, classic captions, AI label, the
consent-gated real owner photo, the score cut the music model sees, ducking under the honest line, loudness.
Clips here are ffmpeg test patterns (no AI generation)."""
import re, subprocess
import pytest
import honest_core as core
from conftest import FFMPEG, make_clip

DURS = [s[3] for s in core.SHOTS]   # 6, 6, 6, 4, 4, 6, 4


def ladder(tone="heartfelt", honest="Started with $800 and my mom's recipes."):
    p = core.load_preset("taco-truck")
    b = core.make_brief(p["business_name"], p["business_type"], p["true_setup"], honest, p["real_proof"], p["hero_thing"], tone, 1,
                        offer=p["offer"], setting=p["setting"], audience=p["audience"])
    return core.build_ladder(b, core.template_joke(b))


def lufs(path):
    log = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])


def mean_volume(path, a, b):
    log = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-ss", f"{a}", "-t", f"{b - a}", "-i", str(path), "-af", "volumedetect",
                          "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"mean_volume:\s+(-?[\d.]+) dB", log)[-1])


def freezes(path, until):
    log = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-t", f"{until}", "-i", str(path), "-vf", "freezedetect=n=0.001:d=0.5",
                          "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return re.findall(r"freeze_start: ([\d.]+)", log)


def xfades(cmd):
    return [(float(d), float(o)) for d, o in re.findall(r"xfade=transition=fade:duration=([\d.]+):offset=([\d.]+)", cmd)]


def test_full_reel_with_real_owner_photo(clips, owner_photo, tmp_path):
    lad = ladder()
    r = core.assemble(clips, lad, tmp_path / "full.mp4", tmp_path / "w", owner_photo, owner_consent=True)
    info = core.probe(tmp_path / "full.mp4")
    expect = sum(DURS) + core.PHOTO_SECONDS + core.CARD_SECONDS - (5 * 0.3 + 0.8 + 0.6 + 0.6)
    assert info["dur"] == pytest.approx(expect, abs=0.1) and (info["w"], info["h"]) == (360, 640) and info["audio"]
    texts = [c[2] for c in r["full"]["captions"]]
    caps = [x["caption"] for x in lad["rungs"]]
    assert texts == caps[:4] + [lad["rungs"][5]["honest_line"], caps[7]], "brag, downgrades, truth, the honest line, the payoff"
    starts = [c[0] for c in r["full"]["captions"]]
    assert starts == sorted(starts) and all(b > a + 1.0 for a, b, _ in r["full"]["captions"]), "in order, long enough to read"
    (ra, rb), = r["full"]["real"]
    assert all(b <= ra + 1e-6 or a >= rb - 1e-6 for a, b in r["full"]["ai"]), "the AI label never sits on the real photo"
    kinds = [s[0] for s in r["full"]["segments"]]
    assert kinds == ["clip"] * 6 + ["owner", "clip", "card"], "place of work -> REAL photo -> payoff macro -> card"
    assert r["full"]["honest"] and r["full"]["honest"][0][0] == pytest.approx(r["full"]["captions"][4][0])
    assert lufs(tmp_path / "full.mp4") == pytest.approx(-14, abs=1.5)
    assert r["music"].startswith("built-in synth bed (free draft only)")


def test_dissolve_offsets(clips, owner_photo, tmp_path):
    """0.3 s on matched frames (every Veo clip starts where the last one landed), 0.8 s into the real photo,
    0.6 s out of it and into the card. Each xfade starts exactly where the next segment starts on the timeline."""
    r = core.assemble(clips, ladder(), tmp_path / "f.mp4", tmp_path / "w", owner_photo, owner_consent=True)
    cmd = (tmp_path / "w" / "ffmpeg_picture_full.txt").read_text()
    xf = xfades(cmd)
    assert [d for d, _ in xf] == [0.3] * 5 + [0.8, 0.6, 0.6]
    assert [o for _, o in xf] == pytest.approx([s[5] for s in r["full"]["segments"][1:]], abs=0.002)
    assert [o for _, o in xf][:5] == pytest.approx([5.7, 11.4, 17.1, 20.8, 24.5], abs=0.002)
    r = core.assemble(clips, ladder(), tmp_path / "g.mp4", tmp_path / "w2")
    assert [d for d, _ in xfades((tmp_path / "w2" / "ffmpeg_picture_full.txt").read_text())] == [0.3] * 5 + [0.6, 0.6]
    assert [d for d, _ in xfades((tmp_path / "w2" / "ffmpeg_picture_15.txt").read_text())] == [0.6] * 4, "every 15 s join changes angle"


def test_consent_blocks_the_owner_photo(clips, owner_photo, tmp_path):
    with pytest.raises(ValueError, match="I have this person's consent"):
        core.assemble_picture(clips, ladder(), tmp_path / "w", owner_photo, owner_consent=False)
    assert not (tmp_path / "w" / "picture_full.mp4").exists(), "nothing is rendered before the consent check"
    plan = core.assemble_picture(clips, ladder(), tmp_path / "w2", None, owner_consent=False)   # no photo: no consent needed
    assert plan["owner"] is None and [s[0] for s in plan["cuts"]["full"]["segments"]][-2:] == ["clip", "card"]


def test_score_cut_never_contains_the_owner_photo(clips, owner_photo, tmp_path):
    plan = core.assemble_picture(clips, ladder(), tmp_path / "w", owner_photo, owner_consent=True)
    masked = (tmp_path / "w" / "ffmpeg_picture_full_masked.txt").read_text()
    assert str(owner_photo) not in masked and "private.png" in masked
    assert str(owner_photo) in (tmp_path / "w" / "ffmpeg_picture_full.txt").read_text()
    info = core.probe(plan["score_cut"])
    assert info["dur"] == pytest.approx(plan["cuts"]["full"]["total"], abs=0.1) and info["audio"], "same timeline, whooshes as sound"


def test_cutdown_15s_from_the_same_clips(clips, owner_photo, tmp_path):
    lad = ladder()
    r = core.assemble(clips, lad, tmp_path / "f.mp4", tmp_path / "w", owner_photo, owner_consent=True, out_15=tmp_path / "s.mp4")
    assert core.probe(tmp_path / "s.mp4")["dur"] == pytest.approx(15.0, abs=0.1)
    assert [c[2] for c in r["15"]["captions"]] == [lad["rungs"][0]["caption"], lad["rungs"][3]["caption"], lad["rungs"][5]["honest_line"],
                                                   lad["rungs"][7]["caption"]]
    assert [(s[0], s[1]) for s in r["15"]["segments"]] == [("clip", 0), ("clip", 2), ("clip", 4), ("owner", 0), ("clip", 6), ("card", 0)]
    assert lufs(tmp_path / "s.mp4") == pytest.approx(-14, abs=1.5)
    m = r["plan"]["cuts"]["15"]["map_to_full"]
    full = {(s[0], s[1]): s for s in r["full"]["segments"]}
    assert m[1] == pytest.approx(full[("clip", 2)][5] + r["15"]["segments"][1][2]), "the score is cut where the same picture plays"


def test_no_owner_and_playful(clips, tmp_path):
    lad = ladder("playful")
    r = core.assemble(clips, lad, tmp_path / "p.mp4", tmp_path / "w")
    expect = sum(DURS) + core.CARD_SECONDS - (5 * 0.3 + 0.6 + 0.6)
    assert core.probe(tmp_path / "p.mp4")["dur"] == pytest.approx(expect, abs=0.1)
    assert r["full"]["honest"] == [] and len(r["full"]["captions"]) == 5 and r["full"]["real"] == []
    r = core.assemble(clips, lad, tmp_path / "q.mp4", tmp_path / "w2", captions=False, ai_label=False, credit=False)
    assert r["full"]["captions"] and "overlay" not in (tmp_path / "w2" / "ffmpeg_picture_full.txt").read_text()


def test_every_rung_moves_no_still_rungs(clips, textured_photo, stills, tmp_path):
    lad = ladder()
    covered = {i for s in lad["shots"] for i in (s["from"], s["to"])}
    assert covered == set(range(core.N_RUNGS)), "every rung is inside a moving clip"
    r = core.assemble(clips, lad, tmp_path / "f.mp4", tmp_path / "w", textured_photo, owner_consent=True)
    assert freezes(tmp_path / "f.mp4", r["full"]["segments"][-1][5]) == [], "no frozen frame anywhere before the end card"
    d = core.draft_warp(stills[7], stills[7], "macro", tmp_path / "macro.mp4", secs=4)
    assert freezes(d, 4) == [], "even a draft clip from one still keeps moving (slow push)"


def test_music_is_levelled_then_ducked_under_the_honest_line(clips, tmp_path):
    track = tmp_path / "owned.wav"   # a steady tone stands in for a track you own: any dip is the ducking
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=50", str(track)], check=True)
    r = core.assemble(clips, ladder(), tmp_path / "m.mp4", tmp_path / "w", music_path=track)
    cmd = (tmp_path / "w" / "ffmpeg_mix_full.txt").read_text()
    lev, duck, fin = cmd.index("loudnorm=I=-27:LRA=3:TP=-6"), cmd.index("sidechaincompress=threshold=0.02:ratio=12:attack=40:release=450"), \
        cmd.index("loudnorm=I=-14:TP=-1")
    assert lev < duck < fin, "level the bed first, duck it, then the final loudness"
    assert r["music"] == "your track: owned.wav"
    assert "sidechaincompress" in (tmp_path / "w" / "ffmpeg_mix_15.txt").read_text()
    (a, b), = r["full"]["honest"]
    before = mean_volume(tmp_path / "m.mp4", a - 4.0, a - 1.0)
    under = mean_volume(tmp_path / "m.mp4", a + 0.6, b - 0.2)
    assert under < before - 4.0, f"the music drops under the honest line ({before} dB -> {under} dB)"


def test_owner_clip_voice_ducks_the_music_too(clips, tmp_path):
    clip = make_clip(tmp_path / "real.mp4", 5.0, audio=True)
    r = core.assemble(clips, ladder(), tmp_path / "v.mp4", tmp_path / "w", clip, owner_consent=True)
    cmd = (tmp_path / "w" / "ffmpeg_mix_full.txt").read_text()
    assert "[voicekey]" in cmd and "[keyh][voicekey]amix" in cmd
    assert [s[0] for s in r["full"]["segments"]].count("owner") == 1 and r["full"]["segments"][6][3] == pytest.approx(4.0)


def test_music_sources_and_errors(clips, tmp_path):
    with pytest.raises(ValueError, match="music_path"):
        core.assemble(clips, ladder(), tmp_path / "x.mp4", tmp_path / "x", music_path=tmp_path / "nope.mp3")
    with pytest.raises(ValueError, match="No music"):
        core.assemble(clips, ladder(), tmp_path / "y.mp4", tmp_path / "y", allow_synth=False)
    with pytest.raises(ValueError, match="7 clips"):
        core.assemble(clips[:4], ladder(), tmp_path / "z.mp4", tmp_path / "z")
    score = tmp_path / "score.wav"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=30", str(score)], check=True)
    r = core.assemble(clips, ladder(), tmp_path / "s.mp4", tmp_path / "s", score_path=score, allow_synth=False)
    assert r["music"].startswith("Sonilo score") and core.probe(tmp_path / "s.mp4")["audio"]


def test_long_clips_still_cut():
    p = core.plan_edit([8] * 7, ladder(), 0, "full")
    assert p["total"] == pytest.approx(7 * 8 + core.CARD_SECONDS - (5 * 0.3 + 0.6 + 0.6))
    p = core.plan_edit([8] * 7, ladder(), core.PHOTO_SECONDS, 15)
    assert p["total"] == pytest.approx(15.0, abs=0.01) and p["segments"][-1][3] >= 2.0


def test_draft_warp_and_board(stills, tmp_path):
    out = core.draft_warp(stills[0], stills[1], "creature", tmp_path / "d.mp4", secs=4)
    info = core.probe(out)
    assert info["dur"] == pytest.approx(4.0, abs=0.1) and (info["w"], info["h"]) == (720, 1280)
    from PIL import Image
    sheet = core.board([Image.open(s) for s in stills], list("abcdefgh"), tmp_path / "b.png")
    assert sheet.size == (8 * 270, 480 + 70)
