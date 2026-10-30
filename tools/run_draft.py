"""Run the FREE draft graph on a running ComfyUI and copy the results out. It refuses any graph that contains a
partner (paid API) node, so it can never spend money.

python3 tools/run_draft.py --url http://127.0.0.1:8196 --comfy-base .comfy-base [--graph workflows/honest-downgrade-draft-api.json]
                           [--out docs/examples] [--ending honest_blank.png]"""
import argparse, json, shutil, sys, time, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8196")
ap.add_argument("--comfy-base", default=str(ROOT / ".comfy-base"))
ap.add_argument("--graph", default=str(ROOT / "workflows/honest-downgrade-draft-api.json"))
ap.add_argument("--out", default=str(ROOT / "runs/draft"))
ap.add_argument("--prefix", default="honest-downgrade-draft")
ap.add_argument("--timeout", type=int, default=900)
a = ap.parse_args()

g = json.loads(Path(a.graph).read_text())
info = json.load(urllib.request.urlopen(f"{a.url}/object_info", timeout=60))
paid = sorted({n["class_type"] for n in g.values() if info.get(n["class_type"], {}).get("api_node")})
if paid:
    sys.exit(f"refusing: this graph has partner (paid) nodes {paid}; run_draft.py only runs the free draft")
pid = json.load(urllib.request.urlopen(urllib.request.Request(
    f"{a.url}/prompt", data=json.dumps({"prompt": g, "client_id": str(uuid.uuid4())}).encode(),
    headers={"Content-Type": "application/json"}), timeout=60))["prompt_id"]
print("queued", pid, flush=True)
t0 = time.time()
while True:
    h = json.load(urllib.request.urlopen(f"{a.url}/history/{pid}", timeout=60))
    if pid in h and h[pid].get("status", {}).get("completed") is not None:
        break
    if time.time() - t0 > a.timeout:
        sys.exit("timed out")
    time.sleep(3)
st = h[pid]["status"]
if st.get("status_str") != "success":
    print(json.dumps(st, indent=1)[:4000]); sys.exit("draft run failed")
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
base = Path(a.comfy_base)
copied = []
for nid, o in h[pid]["outputs"].items():
    title = g[nid].get("_meta", {}).get("title", nid)
    for kind in ("images", "videos", "gifs"):
        for f in o.get(kind, []):
            src = base / f.get("type", "output") / f.get("subfolder", "") / f["filename"]
            if title == "Your Reel":
                dst = out / f"{a.prefix}-reel.mp4"
            elif "15 s" in title:
                dst = out / f"{a.prefix}-15s.mp4"
            elif title == "Board":
                dst = out / f"{a.prefix}-board.png"
            else:
                continue
            shutil.copy(src, dst); copied.append(dst)
    if "text" in o and title in ("Your ladder", "Sign check"):
        (out / f"{a.prefix}-{'ladder' if 'ladder' in title else 'sign-check'}.txt").write_text("\n".join(map(str, o["text"])) + "\n")
(out / f"{a.prefix}-history.json").write_text(json.dumps(h[pid], indent=1))
print(f"done in {time.time() - t0:.0f} s")
print("\n".join(map(str, copied)))
