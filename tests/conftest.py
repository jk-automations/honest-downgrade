import os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
PLACEHOLDER = ROOT / "presets" / "taco-truck" / "placeholder"


def make_clip(path, secs, w=360, h=640, audio=False, freq=440):
    """A dummy warp clip: ffmpeg test pattern (no AI generation)."""
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=24:duration={secs}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={secs}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-shortest"] if audio else []) + [str(path)]
    subprocess.run(cmd, check=True)
    return Path(path)


@pytest.fixture(scope="session")
def clips(tmp_path_factory):
    """Seven dummy clips with the app's clip lengths (warps 6 s, sympathy moves and the payoff macro 4 s)."""
    import honest_core as core
    d = tmp_path_factory.mktemp("clips")
    return [make_clip(d / f"c{k}.mp4", float(s[3]), audio=(k == 2)) for k, s in enumerate(core.SHOTS, 1)]


@pytest.fixture(scope="session")
def stills():
    """The eight sample rung stills (code-drawn placeholders for the taco-truck preset)."""
    if not (PLACEHOLDER / "rung_8.png").exists():
        subprocess.run([sys.executable, str(ROOT / "tools/make_placeholder_stills.py")], check=True)
    return [PLACEHOLDER / f"rung_{k}.png" for k in range(1, 9)]


@pytest.fixture(scope="session")
def owner_photo(tmp_path_factory):
    """Stands in for the owner's real photo (landscape, so the fit + blurred fill is exercised)."""
    from PIL import Image
    p = tmp_path_factory.mktemp("owner") / "real.jpg"
    Image.new("RGB", (1200, 900), (180, 120, 60)).save(p)
    return p


@pytest.fixture(scope="session")
def textured_photo(tmp_path_factory):
    """A photo with detail in it, so a slow push is measurable as motion."""
    from PIL import Image
    p = tmp_path_factory.mktemp("owner_t") / "real_t.png"
    Image.effect_noise((1200, 900), 60).convert("RGB").save(p)
    return p


@pytest.fixture(scope="session")
def comfy_path():
    p = Path(os.environ.get("COMFYUI_DIR", Path.home() / "ComfyUI"))
    if not (p / "comfy_api").exists():
        pytest.skip("ComfyUI not found (set COMFYUI_DIR)")
    sys.path.insert(0, str(p))
    return p
