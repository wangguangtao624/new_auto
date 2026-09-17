#!/usr/bin/env node
/* 真实浏览器里跑一遍「AI 助手 → 生成画布 → 应用到画布」全流程
 *
 *   node scripts/test_ai_ui.cjs
 *   node scripts/test_ai_ui.cjs --prompt "上电后抓一帧图, 然后断电" --shot logs/_ai
 *
 * 注意: 点「应用到画布」会覆盖当前画布, 所以本脚本只验证到按钮出现为止,
 *       除非加 --apply (会先用 BEFORE 快照占位提示)。
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const CHROME = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find((p) => fs.existsSync(p));

const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const URL = arg("--url", "http://127.0.0.1:8765");
const SHOT = arg("--shot", "");
const PROMPT = arg("--prompt", "先上电, 打开设备, 读一下固件版本寄存器 0x00d8, 最后断电");
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

(async () => {
  if (!CHROME) { console.error("找不到 Chrome/Edge"); process.exit(1); }
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--window-size=1600,1000"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).split("\n")[0].slice(0, 200)));
  page.on("console", (m) => { if (m.type() === "error") errs.push("console: " + m.text().slice(0, 160)); });

  const results = [];
  const t = (name, ok, extra = "") => { results.push(`${ok ? "✓" : "✗"} ${name}${extra ? "  " + extra : ""}`); return ok; };

  await page.goto(URL, { waitUntil: "networkidle2", timeout: 60000 });
  await sleep(800);

  // 切到 AI 助手 tab
  await page.click('button[data-tab="ai"]');
  await sleep(600);
  t("AI 助手面板可打开", await page.$eval("#tab-ai", (e) => !e.classList.contains("hidden")));

  const models = await page.$$eval("#ai-model option", (os) => os.map((o) => o.value));
  t("模型下拉已填充", models.length > 0, `(${models.length} 个: ${models.join(", ")})`);
  const cur = await page.$eval("#ai-model", (s) => s.value);
  t("默认模型可用", !!cur, `(${cur})`);

  await page.$eval("#ai-input", (el, p) => { el.value = p; }, PROMPT);
  const t0 = Date.now();
  await page.click("#ai-send");
  console.log(`  已发送, 等待 AI 生成… ("${PROMPT}")`);

  // 等「应用到画布」按钮出现
  const deadline = Date.now() + 180000;
  let ok = false;
  while (Date.now() < deadline) {
    await sleep(1500);
    ok = !!(await page.$(".ai-apply"));
    if (ok) break;
  }
  const ms = Date.now() - t0;
  t("AI 返回并生成画布", ok, ok ? `(${(ms / 1000).toFixed(1)}s)` : "(超时 180s)");

  const bubbles = await page.$$eval("#ai-history .ai-msg", (ds) =>
    ds.map((d) => d.className.replace("ai-msg ", "") + ": " + d.textContent.replace(/\s+/g, " ").slice(0, 120)));
  for (const b of bubbles) console.log("    " + b);
  if (ok) {
    const label = await page.$eval(".ai-apply", (b) => b.textContent);
    console.log("    按钮: " + label);
  }
  t("无页面 JS 错误", errs.length === 0, errs.length ? "\n    " + errs.join("\n    ") : "");

  if (SHOT) {
    const p = path.resolve(`${SHOT}_ai.png`);
    await page.screenshot({ path: p });
    console.log("  截图:", p);
  }
  await browser.close();
  console.log("\n===== AI 助手 UI 测试 =====");
  results.forEach((r) => console.log("  " + r));
  const bad = results.filter((r) => r.startsWith("✗")).length;
  console.log(`  结果: ${results.length - bad}/${results.length} 通过`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
