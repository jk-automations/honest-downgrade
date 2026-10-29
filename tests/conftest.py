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
def warps(tmp_path_factory):
    d = tmp_path_factory.mktemp("warps")
    return [make_clip(d / f"w{k}.mp4", 6.0, audio=(k == 2)) for k in range(1, 5)]


@pytest.fixture(scope="session")
def stills():
    """The five sample rung stills (code-drawn placeholders for the taco-truck preset)."""
    if not (PLACEHOLDER / "rung_5.png").exists():
        subprocess.run([sys.executable, str(ROOT / "tools/make_placeholder_stills.py")], check=True)
    return [PLACEHOLDER / f"rung_{k}.png" for k in range(1, 6)]


@pytest.fixture(scope="session")
def ending_photo(tmp_path_factory):
    from PIL import Image
    p = tmp_path_factory.mktemp("end") / "real.jpg"
    Image.new("RGB", (1080, 1920), (180, 120, 60)).save(p)
    return p


@pytest.fixture(scope="session")
def comfy_path():
    p = Path(os.environ.get("COMFYUI_DIR", Path.home() / "ComfyUI"))
    if not (p / "comfy_api").exists():
        pytest.skip("ComfyUI not found (set COMFYUI_DIR)")
    sys.path.insert(0, str(p))
    return p
