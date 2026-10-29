// Turn the API-format graph into a normal ComfyUI workflow with App Mode set up, using ComfyUI's own frontend (so the
// saved file is exactly what the editor writes). Then reload it in a fresh browser, check it opens in App Mode and
// screenshot it as proof. Nothing is queued: POST /prompt is blocked (the partner nodes in the main graph cost money).
// node tools/make_app.mjs <comfy_url> <api.json> <out_workflow.json> <screenshot.png>   (needs the playwright package)
import { chromium } from "playwright";
import fs from "fs";

const [url, apiPath, outPath, shot] = process.argv.slice(2);
const api = JSON.parse(fs.readFileSync(apiPath, "utf8"));
const ids = (cls) => Object.entries(api).filter(([, n]) => n.class_type === cls).map(([k]) => k).sort((a, b) => a - b);
const titled = (t) => Object.entries(api).find(([, n]) => n._meta && n._meta.title === t)[0];
const draft = ids("HonestDraftWarp").length > 0;
const brief = ids("HonestBrief")[0];
const asm = ids("HonestAssemble")[0];
const stills = draft ? [1, 2, 3, 4, 5].map((k) => titled(`Still ${k}`)) : [];
const ending = titled("Real ending photo");
const FIELDS = ["business_name", "family", "true_setup", "honest_line", "real_proof", "hero_thing", "tone", "joke"];
// What a user sees in App Mode. Everything else stays locked in the graph.
const INPUTS = [
  ...FIELDS.map((f) => [brief, f]), ...stills.map((s) => [s, "image"]), [ending, "image"],
  ...(draft ? [] : [[brief, "writer"], [brief, "video_model"]]), [brief, "already_used_warps"], [asm, "music_path"], [asm, "captions"],
];
const OUTPUTS = [titled("Your Reel (30 s)"), titled("Cutdown (15 s)"), titled("Board"), titled("Your ladder"), titled("Sign check")];
const LABELS = { business_name: "Business name", family: "Business family", true_setup: "The truth: your real setup, exactly",
  honest_line: "One honest line (empty = playful)", real_proof: "The payoff: real proof people can see",
  hero_thing: "Payoff still: your best product or work (no people)", tone: "Tone", joke: "Joke ladder",
  writer: "Who writes the joke", video_model: "Video model (lite = cheapest)", already_used_warps: "Warps you already used (never repeated)",
  music_path: "Music you own (optional path)", captions: "Burn in captions" };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1500 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.route("**/prompt", (r) => (r.request().method() === "POST" ? r.abort() : r.continue()));   // never queue
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
const wf = await page.evaluate(async ({ api, INPUTS, OUTPUTS, stills, ending, LABELS, draft }) => {
  await window.app.loadApiJson(api, draft ? "honest-downgrade-draft" : "honest-downgrade");
  const g = window.app.graph;
  if (g.arrange) g.arrange(80);
  for (const node of g.nodes) {
    const a = api[String(node.id)];
    if (a && a._meta && a._meta.title) node.title = a._meta.title;
    // Fixed seeds: a re-run after one failed shot re-uses every finished (already paid) step from ComfyUI's cache.
    for (const w of node.widgets || []) {
      for (const x of [w, ...(w.linkedWidgets || [])]) if (x.value === "randomize" || String(x.name).endsWith("control_after_generate")) x.value = "fixed";
    }
    const si = stills.indexOf(String(node.id));
    for (const w of node.widgets || []) {
      let lab = null;
      if (si >= 0 && w.name === "image") lab = `Rung ${si + 1} still (${["brag", "downgrade 1", "downgrade 2", "truth", "payoff"][si]})`;
      else if (String(node.id) === String(ending) && w.name === "image") lab = "Your REAL ending photo (optional; real people only here)";
      else if (INPUTS.some(([n, name]) => String(n) === String(node.id) && name === w.name)) lab = LABELS[w.name];
      if (lab) { w.label = lab; for (const inp of node.inputs || []) if (inp.widget && inp.widget.name === w.name) inp.label = lab; }
    }
  }
  const w = g.serialize();
  for (const n of w.nodes) if (Array.isArray(n.widgets_values)) n.widgets_values = n.widgets_values.map((v) => (v === "randomize" ? "fixed" : v));
  w.extra = w.extra || {};
  w.extra.linearMode = true;
  w.extra.linearData = { inputs: INPUTS.map(([n, name]) => [Number(n), name]), outputs: OUTPUTS.map(Number) };
  return w;
}, { api, INPUTS, OUTPUTS, stills, ending, LABELS, draft });
const randomized = wf.nodes.filter((n) => (n.widgets_values || []).includes("randomize")).map((n) => n.type);
console.log("seed widgets still on randomize:", JSON.stringify(randomized));
console.log(`nodes ${wf.nodes.length}, links ${wf.links.length}, app inputs ${INPUTS.length}, outputs ${OUTPUTS.length}`);
fs.writeFileSync(outPath, JSON.stringify(wf, null, 1));
// Open the saved file the way a new user would: a fresh browser context (no restored tabs), then load it.
await page.close();
const page2 = await (await browser.newContext({ viewport: { width: 1440, height: 1500 } })).newPage();
page2.on("pageerror", (e) => errors.push(e.message));
await page2.route("**/prompt", (r) => (r.request().method() === "POST" ? r.abort() : r.continue()));
await page2.goto(url, { waitUntil: "load", timeout: 120000 });
await page2.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page2.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, w.extra && w.extra.linearData ? "honest-downgrade" : "x"); }, wf);
await page2.waitForTimeout(4000);
const nodesNow = await page2.evaluate(() => window.app.graph.nodes.length);
const missing = await page2.evaluate(() => window.app.graph.nodes.filter((n) => n.has_errors || n.type === undefined).map((n) => n.type));
try { await page2.click("text=Skip", { timeout: 5000 }); } catch {}   // first-visit App Mode tour
await page2.waitForTimeout(1500);
const text = await page2.evaluate(() => document.body.innerText);
const inApp = /Business name/.test(text) && /The truth: your real setup/.test(text);
await page2.screenshot({ path: shot });
console.log("reloaded nodes", nodesNow, "missing/error nodes", JSON.stringify(missing), "app mode form visible", inApp, "page errors", errors.length, JSON.stringify(errors.slice(0, 3)));
console.log(text.replace(/\n+/g, " | ").slice(0, 1800));
await browser.close();
