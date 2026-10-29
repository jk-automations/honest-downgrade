"""Honest Downgrade for ComfyUI: the "I'm so sorry I lied" trend as an app. A business brags, admits the truth one rung
at a time through wild-card warps, and lands on a real, honest payoff. Clone into ComfyUI/custom_nodes/. Apache-2.0."""
from pathlib import Path

if __package__:  # loaded by ComfyUI as a custom node pack (pytest imports this file without a package)
    from .honest_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:
    NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = {}, {}

BLANK = "honest_blank.png"

# The optional real-ending slot still needs a file: put a flat placeholder into input/ (Assemble skips flat images).
try:
    if not __package__:
        raise ImportError("not running inside ComfyUI")
    import folder_paths
    from PIL import Image
    _blank = Path(folder_paths.get_input_directory()) / BLANK
    if not _blank.exists():
        _blank.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (255, 255, 255)).save(_blank)
except Exception as e:  # never block ComfyUI start-up
    print(f"[Honest Downgrade] could not place the blank placeholder: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
