/**
 * UI 布局实测 / 截图工具
 *
 * 用真实 Chromium 打开画布页面, 逐个选中节点并量取关键元素尺寸, 同时截图。
 * 用于验证属性面板里的列表编辑器 (I²C 表格 / device 操作列表) 是否紧凑、
 * 面板拖拽是否生效等布局问题 —— jsdom 不做排版, 量不出来。
 *
 * 用法:
 *   node scripts/ui_probe.cjs                          # 只量尺寸
 *   node scripts/ui_probe.cjs --shot logs/_probe       # 每个节点截一张 logs/_probe_<type>.png
 *   node scripts/ui_probe.cjs --url http://127.0.0.1:8765
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const CHROME = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find((p) => fs.existsSync(p));

const argv = process.argv.slice(2);
const arg = (k, d) => {
  const i = argv.indexOf(k);
  return i >= 0 ? argv[i + 1] : d;
};
const URL = arg("--url", "http://127.0.0.1:8765");
const SHOT = arg("--shot", "");
const TYPES = (arg("--types", "device.check,i2c.seq,power.ctrl")).split(",");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--window-size=1600,1000"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).split("\n")[0].slice(0, 200)));
  page.on("console", (m) => {
    const t = m.text();
    if (m.type() === "error" && !t.includes("favicon") && !t.includes("404")) errs.push("console: " + t.slice(0, 160));
  });
  await page.goto(URL, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector("#palette .pal-item", { timeout: 15000 });
  await new Promise((r) => setTimeout(r, 600));

  for (const type of TYPES) {
    const info = await page.evaluate(async (t) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const nodes = [...document.querySelectorAll("#world .node")];
      const el = nodes.find((n) => (n.querySelector(".node-type") || {}).textContent.includes(t));
      if (!el) return { type: t, found: false };
      el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      await sleep(500);
      const h = (e) => (e ? Math.round(e.getBoundingClientRect().height) : 0);
      const w = (e) => (e ? Math.round(e.getBoundingClientRect().width) : 0);
      const rows = [...document.querySelectorAll(".ops-editor .ops-row")];
      const lists = [...document.querySelectorAll(".ops-editor")].map((e) => ({
        kind: e.dataset.kind, h: h(e), w: w(e) }));
      return {
        type: t, found: true,
        insW: w(document.querySelector("#inspector")),
        insScrollH: document.querySelector("#ins-body").scrollHeight,
        rows: rows.map((r) => ({ h: h(r), w: w(r), kids: r.children.length,
                                 txt: (r.textContent || "").trim().slice(0, 28) })),
        lists,
        dockH: h(document.querySelector("#rundock")),
      };
    }, type);
    console.log(JSON.stringify(info));
    if (SHOT) {
      const p = path.resolve(`${SHOT}_${type}.png`);
      await page.screenshot({ path: p });
      console.log("  截图:", p);
    }
  }
  if (errs.length) console.log("页面错误:\n" + errs.join("\n"));
  else console.log("无页面错误");

  // ---------- v3: 右/下两块面板的可拖拽伸缩 + 运行台三栏 (本 case 空间) ----------
  // 运行台默认是收起的, 先展开 (收起的坞上没有拖拽条)
  if (await page.$eval("#rundock", (e) => e.classList.contains("collapsed"))) {
    await page.click("#dock-toggle");
    await new Promise((r) => setTimeout(r, 400));
  }
  const box = (sel) => page.$eval(sel, (e) => {
    const r = e.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  });
  const measure = () => page.evaluate(() => ({
    insW: Math.round(document.querySelector("#inspector").getBoundingClientRect().width),
    dockBodyH: Math.round(document.querySelector("#dock-body").getBoundingClientRect().height),
    caseTxt: (document.querySelector("#dock-case").textContent || "").trim(),
  }));

  const m0 = await measure();

  // 拖属性台左边缘往左 140px -> 应变宽约 140
  const ir = await box("#ins-resizer");
  await page.mouse.move(ir.x + 4, ir.y + ir.h / 2);
  await page.mouse.down();
  await page.mouse.move(ir.x + 4 - 140, ir.y + ir.h / 2, { steps: 14 });
  await page.mouse.up();
  const m1 = await measure();

  // 拖运行台上边缘往上 90px -> 应变高约 90
  const dr = await box("#dock-resizer");
  await page.mouse.move(dr.x + dr.w / 2, dr.y + 4);
  await page.mouse.down();
  await page.mouse.move(dr.x + dr.w / 2, dr.y + 4 - 90, { steps: 14 });
  await page.mouse.up();
  const m2 = await measure();

  // 双击边缘复位 (两次快速点击; 复位判定用的是 400ms 时间窗)
  const dblClick = async (sel) => {
    const b = await box(sel);
    const x = b.x + 4, y = b.y + Math.min(60, b.h / 2);
    await page.mouse.click(x, y);
    await page.mouse.click(x, y);
  };
  await dblClick("#ins-resizer");
  await dblClick("#dock-resizer");
  await new Promise((r) => setTimeout(r, 300));
  const m3 = await measure();

  // 三栏切换
  const tabs = {};
  for (const tk of ["log", "img", "hist"]) {
    await page.click(`#dock-tabs .dtab[data-dtab="${tk}"]`);
    await new Promise((r) => setTimeout(r, 900));
    tabs[tk] = await page.evaluate((tt) => {
      const pane = tt === "log" ? document.querySelector("#dock-body")
                                : document.querySelector("#dock-" + tt);
      return {
        visible: !!pane && !pane.classList.contains("hidden"),
        chars: pane ? pane.innerText.trim().length : 0,
        sample: pane ? pane.innerText.trim().replace(/\s+/g, " ").slice(0, 70) : "",
      };
    }, tk);
    if (SHOT && tk === "img") {
      // headless 下改过 display 后需要强制一次重排, 否则截到上一帧
      await page.setViewport({ width: 1601, height: 1000 });
      await new Promise((r) => setTimeout(r, 500));
      await page.setViewport({ width: 1600, height: 1000 });
      await new Promise((r) => setTimeout(r, 500));
      const p = path.resolve(`${SHOT}_dock_img.png`);
      await page.screenshot({ path: p });
      console.log("  截图:", p);
    }
  }

  console.log("v3 面板伸缩/分栏实测 " + JSON.stringify({
    初始: m0, 拖宽后: m1, 拖高后: m2, 双击复位: m3, 分栏: tabs,
  }, null, 1));

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
