// Real-browser end-to-end run of the FREE draft app: open workflows/honest-downgrade-draft.json in the ComfyUI
// frontend, press Run in App Mode like a user, wait for the Reel, screenshot the result. Any /prompt that contains a
// partner (paid) node is aborted, so this can never spend money.
// node tools/e2e_draft.mjs <comfy_url> <workflow.json> <screenshot.png>
import { chromium } from "playwright";
import fs from "fs";

const [url, wfPath, shot] = process.argv.slice(2);
const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
const PAID = ["Veo3FirstLastFrameNode", "GeminiNanoBanana2V2", "GeminiNodeV3", "GeminiNode", "GeminiNanoBanana2"];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1500 } });
const errors = [];
let queued = null;
page.on("pageerror", (e) => errors.push(e.message));
await page.route("**/prompt", async (r) => {
  if (r.request().method() !== "POST") return r.continue();
  const body = JSON.parse(r.request().postData() || "{}");
  const paid = Object.values(body.prompt || {}).filter((n) => PAID.includes(n.class_type));
  if (paid.length) { console.log("ABORT: paid node in prompt"); return r.abort(); }
  const resp = await r.fetch(); queued = (await resp.json()).prompt_id; return r.fulfill({ response: resp });
});
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "honest-downgrade-draft"); }, wf);
await page.waitForTimeout(3000);
try { await page.click("text=Skip", { timeout: 4000 }); } catch {}
const t0 = Date.now();
await page.getByRole("button", { name: "Run", exact: true }).last().click();
let status = null;
while (Date.now() - t0 < 600000) {
  await page.waitForTimeout(3000);
  if (!queued) continue;
  const h = await (await fetch(`${url}/history/${queued}`)).json();
  if (h[queued] && h[queued].status && h[queued].status.completed !== undefined) { status = h[queued].status.status_str; break; }
}
await page.waitForTimeout(5000);
await page.screenshot({ path: shot });
const vids = await page.evaluate(() => [...document.querySelectorAll("video")].map((v) => v.currentSrc || v.src));
console.log(JSON.stringify({ prompt_id: queued, status, seconds: Math.round((Date.now() - t0) / 1000), videos_on_page: vids.length, page_errors: errors.slice(0, 3) }));
await browser.close();
