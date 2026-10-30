"""The ONE paid demo run of the main app, for the founder to start himself. Plumber brief (Drip Doctor Plumbing),
Nano Banana 2 keyframes, Veo 3.1 fast clips, the Sonilo score. Founder-approved cap: $4.00.

  python3 tools/run_paid_demo.py --dry-run          # $0: builds the graph, checks it against the server, prints the estimate
  python3 tools/run_paid_demo.py                    # pays: appends a ledger row with the estimate, then queues
  python3 tools/run_paid_demo.py --owner-photo me.jpg --owner-consent   # optional real owner photo (consent required)

Safety: the estimate comes from the nodes' own price badges on the live server (it refuses if a badge no longer shows
the price it was written for), a ledger row is written to runs/paid/ledger.jsonl BEFORE anything is queued, and it
refuses if the estimate is over the cap. The Comfy API key is read here from ~/.config/jk/comfy_api_key and sent only
as extra_data.api_key_comfy_org: never printed, logged, saved or committed."""
import argparse, datetime, hashlib, json, shutil, sys, time, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import honest_core as core  # noqa: E402
from build_app import build  # noqa: E402

HARD_CAP = 4.00                       # founder-approved; --cap may only lower it
KEY_FILE = Path.home() / ".config" / "jk" / "comfy_api_key"
LEDGER = ROOT / "runs" / "paid" / "ledger.jsonl"
VIDEO_MODEL = "veo-3.1-fast-generate"
# The plumber brief (docs/examples/plumber-brief.md), the founder's approved plumber Reel's facts.
PLUMBER = dict(business_name="Drip Doctor Plumbing", business_type="Plumber (no storefront)",
               offer="leak repairs, drains and water heater installs", setting="on call across the east side, in homes and small offices",
               audience="homeowners and landlords who need it fixed today", true_setup="a van and a phone that never stops ringing",
               honest_line="My dad taught me on weekends.", real_proof="Same-day callbacks, every time.", hero_thing="",
               tone="heartfelt", joke="joke 2", already_used_warps="", writer="template (offline, free)")
# Unit prices the badges must still show (USD), checked against the live /object_info before any spend.
PRICES = {"veo_fast_720_noaudio_per_s": ("Veo3FirstLastFrameNode", "($ga ? 0.10 : 0.08)", 0.08),
          "nano_banana_2_1k_per_image": ("GeminiNanoBanana2V2", '"1k": 0.0835', 0.0835),
          "sonilo_v2m_per_s": ("SoniloVideoToMusic", '"usd":0.009', 0.009)}


def get(url):
    return json.load(urllib.request.urlopen(url, timeout=120))


def estimate(g, info, owner_len):
    """USD estimate from the graph + the live price badges. Gemini writer = $0: the template writer never calls it."""
    for name, (cls, needle, _) in PRICES.items():
        badge = (info[cls].get("price_badge") or {}).get("expr", "")
        if needle not in badge:
            sys.exit(f"refusing: the {cls} price badge no longer shows {needle!r} ({name}); re-check prices before spending")
    veo = [n for n in g.values() if n["class_type"] == "Veo3FirstLastFrameNode"]
    nb = [n for n in g.values() if n["class_type"] == "GeminiNanoBanana2V2"]
    for n in veo:
        i = n["inputs"]
        if i["resolution"] != "720p" or i["generate_audio"] is not False:
            sys.exit("refusing: a Veo clip is not 720p without audio; the estimate would be wrong")
    if any(n["inputs"].get("model.resolution") != "1K" for n in nb):
        sys.exit("refusing: a keyframe is not 1K; the estimate would be wrong")
    brief = next(n for n in g.values() if n["class_type"] == "HonestBrief")["inputs"]
    if not brief["writer"].startswith("template") or brief["video_model"] != VIDEO_MODEL:
        sys.exit("refusing: the demo uses the template writer and Veo 3.1 fast only")
    b = core.make_brief(brief["business_name"], brief["business_type"], brief["true_setup"], brief["honest_line"], brief["real_proof"],
                        brief["hero_thing"], brief["tone"], int(brief["joke"].split()[-1]), offer=brief["offer"],
                        setting=brief["setting"], audience=brief["audience"])
    lad = core.build_ladder(b, core.template_joke(b))
    reel = core.plan_edit([n["inputs"]["duration"] for n in veo], lad, owner_len, "full")["total"]
    lines = {"veo_seconds": sum(n["inputs"]["duration"] for n in veo), "keyframes": len(nb), "score_seconds": round(reel, 1)}
    usd = {"veo": lines["veo_seconds"] * PRICES["veo_fast_720_noaudio_per_s"][2],
           "keyframes": lines["keyframes"] * PRICES["nano_banana_2_1k_per_image"][2],
           "sonilo": reel * PRICES["sonilo_v2m_per_s"][2], "gemini_writer": 0.0}
    return round(sum(usd.values()), 3), {k: round(v, 3) for k, v in usd.items()}, lines, lad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8196")
    ap.add_argument("--comfy-base", default=str(ROOT / ".comfy-base"))
    ap.add_argument("--owner-photo", help="a REAL photo of the owner (optional); needs --owner-consent")
    ap.add_argument("--owner-consent", action="store_true", help="I have this person's consent")
    ap.add_argument("--cap", type=float, default=HARD_CAP)
    ap.add_argument("--dry-run", action="store_true", help="$0: estimate and checks only; no key read, no ledger row, no queue")
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    cap = min(a.cap, HARD_CAP)
    base = Path(a.comfy_base)
    owner_name, owner_len = "honest_blank.png", 0.0
    if a.owner_photo:
        if not a.owner_consent:
            sys.exit("refusing: an owner photo needs --owner-consent (I have this person's consent)")
        src = Path(a.owner_photo).expanduser()
        if not src.is_file():
            sys.exit(f"owner photo not found: {src}")
        owner_name, owner_len = f"honest_owner_{uuid.uuid4().hex[:8]}{src.suffix.lower()}", core.PHOTO_SECONDS
        if not a.dry_run:
            shutil.copy(src, base / "input" / owner_name)
    g = build(draft=False, brief=PLUMBER, video_model=VIDEO_MODEL, owner=owner_name, owner_consent=bool(a.owner_photo and a.owner_consent))
    info = get(f"{a.url}/object_info")
    missing = sorted({n["class_type"] for n in g.values()} - set(info))
    if missing:
        sys.exit(f"refusing: the server at {a.url} lacks nodes {missing}")
    paid = sorted({n["class_type"] for n in g.values() if info[n["class_type"]].get("api_node")})
    total, usd, lines, lad = estimate(g, info, owner_len)
    out_dir = ROOT / "runs" / "paid"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "demo-api.json").write_text(json.dumps(g, indent=1) + "\n")
    sha = hashlib.sha256(json.dumps(g, sort_keys=True).encode()).hexdigest()[:16]
    print(core.ladder_text(lad))
    print(f"partner nodes: {paid}")
    print(f"estimate: ${total:.2f} = " + ", ".join(f"{k} ${v:.2f}" for k, v in usd.items()) + f"  ({lines})")
    print(f"cap: ${cap:.2f}   graph: runs/paid/demo-api.json sha {sha}")
    if total > cap:
        sys.exit(f"refusing: estimate ${total:.2f} is over the ${cap:.2f} cap")
    if a.dry_run:
        print("dry run: nothing read, nothing written to the ledger, nothing queued, $0 spent")
        return
    row = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "what": "Honest Downgrade paid demo (plumber)",
           "estimate_usd": total, "breakdown_usd": usd, "units": lines, "cap_usd": cap, "graph_sha": sha, "owner_photo": bool(a.owner_photo),
           "status": "about to queue"}
    with LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")
    key = KEY_FILE.read_text().strip()          # never printed, logged or saved
    body = json.dumps({"prompt": g, "client_id": str(uuid.uuid4()), "extra_data": {"api_key_comfy_org": key}}).encode()
    try:
        pid = json.load(urllib.request.urlopen(urllib.request.Request(f"{a.url}/prompt", data=body,
                                                                      headers={"Content-Type": "application/json"}), timeout=120))["prompt_id"]
    except Exception as e:   # noqa: BLE001
        sys.exit("queue failed: " + str(e).replace(key, "***")[:1500])
    del body
    print("queued", pid, flush=True)
    t0 = time.time()
    while True:
        h = get(f"{a.url}/history/{pid}")
        if pid in h and h[pid].get("status", {}).get("completed") is not None:
            break
        if time.time() - t0 > a.timeout:
            sys.exit("timed out waiting; the run may still finish in ComfyUI (check its queue)")
        time.sleep(10)
    entry = h[pid]
    entry.pop("prompt", None)                    # holds extra_data; never saved
    text = json.dumps(entry, indent=1).replace(key, "***")
    run_dir = out_dir / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir()
    (run_dir / "history.json").write_text(text)
    st = entry["status"]
    copied = []
    for nid, o in entry.get("outputs", {}).items():
        title = g[nid].get("_meta", {}).get("title", nid)
        for kind in ("images", "videos", "gifs"):
            for f in o.get(kind, []):
                src = base / f.get("type", "output") / f.get("subfolder", "") / f["filename"]
                if src.is_file():
                    dst = run_dir / f"{title.replace(' ', '_').replace('(', '').replace(')', '')}_{f['filename']}"
                    shutil.copy(src, dst); copied.append(dst.name)
        if "text" in o and title in ("Your ladder", "Sign check"):
            (run_dir / f"{title.replace(' ', '_')}.txt").write_text("\n".join(map(str, o["text"])) + "\n")
    with LEDGER.open("a") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "prompt_id": pid,
                            "status": st.get("status_str"), "seconds": round(time.time() - t0), "outputs": str(run_dir.relative_to(ROOT)),
                            "note": "check the actual Comfy credit charge and add it here"}) + "\n")
    print(st.get("status_str"), f"in {time.time() - t0:.0f} s ->", run_dir)
    print("\n".join(copied))
    if st.get("status_str") != "success":
        msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
        sys.exit("failed: " + json.dumps(msgs)[:1500].replace(key, "***"))


if __name__ == "__main__":
    main()
