"""tools/run_paid_demo.py without spending: the estimate from the price badges, the $4 cap, the refusals, and that a dry
run never reads the key, never writes the ledger and never queues."""
import json, sys
from pathlib import Path
import pytest
import honest_core as core

ROOT = Path(core.__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
import run_paid_demo as demo  # noqa: E402

BADGES = {"Veo3FirstLastFrameNode": '$contains($m, "fast") ? ($r = "1080p" ? ($ga ? 0.12 : 0.10) : ($ga ? 0.10 : 0.08))',
          "GeminiNanoBanana2V2": '$prices := {"1k": 0.0835, "2k": 0.1217, "4k": 0.1848};',
          "SoniloVideoToMusic": '{"type":"usd","usd":0.009,"format":{"suffix":"/second"}}'}


def fake_info(g, badges=BADGES):
    info = {}
    for n in g.values():
        c = n["class_type"]
        info[c] = {"api_node": c in badges or c == "GeminiNodeV3", "price_badge": {"expr": badges.get(c, "")}}
    return info


def test_estimate_is_under_the_cap_and_itemised():
    g = demo.build(draft=False, brief=demo.PLUMBER, video_model=demo.VIDEO_MODEL)
    total, usd, lines, lad = demo.estimate(g, fake_info(g), 0.0)
    assert lines["veo_seconds"] == sum(s[3] for s in core.SHOTS) == 36 and lines["keyframes"] == 8
    assert usd["veo"] == pytest.approx(36 * 0.08) and usd["keyframes"] == pytest.approx(8 * 0.0835)
    assert usd["sonilo"] == pytest.approx(lines["score_seconds"] * 0.009, abs=0.01) and usd["gemini_writer"] == 0
    assert total <= demo.HARD_CAP and total == pytest.approx(3.87, abs=0.05)
    assert [r["caption"] for r in lad["rungs"]][:2] == ["We have 40 work trucks.", "Ok, it's 4 work trucks."]
    assert [w["device"] for w in lad["warps"]][:3] == ["tool smash", "geyser", "tool tornado"], "the approved plumber shock warps"


def test_refuses_when_a_price_badge_changed():
    g = demo.build(draft=False, brief=demo.PLUMBER, video_model=demo.VIDEO_MODEL)
    badges = dict(BADGES, SoniloVideoToMusic='{"type":"usd","usd":0.02}')
    with pytest.raises(SystemExit, match="price badge"):
        demo.estimate(g, fake_info(g, badges), 0.0)


def test_dry_run_reads_no_key_writes_no_ledger_queues_nothing(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(demo, "KEY_FILE", tmp_path / "must-not-be-read")
    monkeypatch.setattr(demo, "LEDGER", tmp_path / "ledger.jsonl")
    def fake_get(url):
        calls.append(url)
        assert url.endswith("/object_info"), url
        return fake_info(demo.build(draft=False, brief=demo.PLUMBER, video_model=demo.VIDEO_MODEL))
    monkeypatch.setattr(demo, "get", fake_get)
    monkeypatch.setattr(demo.urllib.request, "urlopen", lambda *a, **k: pytest.fail("nothing may be sent"))
    monkeypatch.setattr(sys, "argv", ["run_paid_demo.py", "--dry-run"])
    demo.main()
    out = capsys.readouterr().out
    assert "estimate: $3.8" in out and "$0 spent" in out and not (tmp_path / "ledger.jsonl").exists()


def test_over_the_cap_and_photo_without_consent_are_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(demo, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(demo, "get", lambda url: fake_info(demo.build(draft=False, brief=demo.PLUMBER, video_model=demo.VIDEO_MODEL)))
    monkeypatch.setattr(sys, "argv", ["run_paid_demo.py", "--cap", "2.00"])
    with pytest.raises(SystemExit, match="over the \\$2.00 cap"):
        demo.main()
    assert not (tmp_path / "ledger.jsonl").exists(), "a refused run writes nothing"
    monkeypatch.setattr(sys, "argv", ["run_paid_demo.py", "--cap", "9"])
    assert min(9, demo.HARD_CAP) == 4.0, "--cap can only lower the founder's $4"
    photo = tmp_path / "me.jpg"; photo.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["run_paid_demo.py", "--owner-photo", str(photo), "--dry-run"])
    with pytest.raises(SystemExit, match="owner-consent"):
        demo.main()
