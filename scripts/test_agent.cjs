#!/usr/bin/env node
/* 测试 AI 助手 (POST /api/agent) 能不能按自然语言生成合法画布
 *
 *   node scripts/test_agent.cjs                    # 跑内置的一组用例
 *   node scripts/test_agent.cjs "帮我上电读版本"     # 只跑一条
 *   node scripts/test_agent.cjs --model deepseek-v4-pro
 *   node scripts/test_agent.cjs --run              # 生成后落盘并真机跑一遍, 跑完删掉
 */
const BASE = process.env.NEW_AUTO_BASE || "http://127.0.0.1:8765";
const RUN = process.argv.includes("--run");
const RUN_PREFIX = "_AI测试_";
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

const VISIBLE = new Set(["power.ctrl", "device.open", "device.check", "device.close",
  "i2c.seq", "fw.download", "flow.delay", "flow.log",
  "fw.soc_reboot", "fw.erase", "fw.crc_check"]);

const CASES = [
  "先给模组上电，打开设备，读一下固件版本寄存器 0x00d8（A2D4），最后断电",
  "上电后打开设备，抓一帧图看看画质，然后断电",
  "下载 release 固件，然后确认能正常出图",
  "上电、打开设备，把 0x00c0 写成 0x0001 再回读校验，最后断电",
];

const argv = process.argv.slice(2);
const mi = argv.indexOf("--model");
const model = mi >= 0 ? argv[mi + 1] : undefined;
const prompts = argv.filter((a) => !a.startsWith("--") && a !== model);
const todo = prompts.length ? prompts : CASES;

async function gen(prompt) {
  const r = await fetch(`${BASE}/api/agent`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, model, history: [] }),
  });
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

function check(canvas) {
  const errs = [];
  const ids = new Set(canvas.nodes.map((n) => n.id));
  for (const n of canvas.nodes) {
    if (!VISIBLE.has(n.type)) errs.push(`节点类型不可见/不存在: ${n.type}`);
    if (typeof n.x !== "number" || typeof n.y !== "number") errs.push(`${n.id} 坐标不是数字`);
  }
  const flowOut = new Map(), flowIn = new Map();
  for (const e of canvas.edges) {
    if (!ids.has(e.from) || !ids.has(e.to)) errs.push(`边引用了不存在的节点: ${e.from}->${e.to}`);
    if (e.kind === "flow") {
      flowOut.set(e.from, (flowOut.get(e.from) || 0) + 1);
      flowIn.set(e.to, (flowIn.get(e.to) || 0) + 1);
    }
  }
  for (const n of canvas.nodes) {
    if ((flowIn.get(n.id) || 0) > 1) errs.push(`${n.id} 有多条入边`);
    if ((flowOut.get(n.id) || 0) > 1) errs.push(`${n.id} 有多条出边`);
  }
  if (canvas.nodes.length && canvas.edges.filter((e) => e.kind === "flow").length
      && (flowIn.get(canvas.nodes[0].id) || 0) !== 0) errs.push("首个节点有入边, 可能成环");
  // 规则 8: 掉电后必须重新 device.open
  const order = []; // 沿 flow 链推执行顺序
  const byId = new Map(canvas.nodes.map((n) => [n.id, n]));
  let cur = canvas.nodes.find((n) => !(flowIn.get(n.id) || 0));
  const seen = new Set();
  while (cur && !seen.has(cur.id)) { seen.add(cur.id); order.push(cur); 
    const nx = canvas.edges.find((e) => e.kind === "flow" && e.from === cur.id); cur = nx && byId.get(nx.to); }
  for (let i = 0; i < order.length; i++) {
    const n = order[i];
    const cut = (n.type === "device.close" && n.params.power_off)
             || (n.type === "power.ctrl" && n.params.action === "off")
             || n.type === "fw.download";
    if (!cut) continue;
    const after = order.slice(i + 1);
    if (after.length && !after.some((m) => m.type === "device.open"))
      errs.push(`掉电来源 ${n.id}(${n.type}) 之后没有再 device.open`);
  }
  return { errs, order };
}

function brief(canvas) {
  const byId = new Map(canvas.nodes.map((n) => [n.id, n]));
  const flowIn = new Map();
  for (const e of canvas.edges) if (e.kind === "flow") flowIn.set(e.to, (flowIn.get(e.to) || 0) + 1);
  let cur = canvas.nodes.find((n) => !(flowIn.get(n.id) || 0));
  const out = []; const seen = new Set();
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    let extra = "";
    if (cur.type === "i2c.seq") {
      const ops = cur.params.ops || [];
      extra = ops.map((o) => `${o.op}@${o.addr}/${o.mode}${o.expect ? "→" + o.expect : ""}`).join(", ");
    } else if (cur.type === "device.check") {
      extra = (cur.params.ops || []).map((o) => o.op).join(",") + (cur.params.ini ? ` ini=${cur.params.ini}` : "");
    } else if (cur.type === "fw.download") {
      extra = `tier=${cur.params.tier}`;
    } else if (cur.type === "power.ctrl") {
      extra = `action=${cur.params.action}`;
    } else if (cur.type === "device.open") {
      extra = cur.params.ini ? `ini=${cur.params.ini}` : "ini=继承";
    }
    out.push(`    ${cur.id.padEnd(7)} ${cur.type.padEnd(14)} ${extra}`);
    const nx = canvas.edges.find((e) => e.kind === "flow" && e.from === cur.id);
    cur = nx && byId.get(nx.to);
  }
  const uncovered = canvas.nodes.filter((n) => !seen.has(n.id));
  for (const n of uncovered) out.push(`    ${n.id.padEnd(7)} ${n.type.padEnd(14)} (不在执行链上)`);
  return out.join("\n");
}

async function runCanvas(canvas, label) {
  const name = RUN_PREFIX + label.replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 16);
  const put = await fetch(`${BASE}/api/canvases/${encodeURIComponent(name)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({}, canvas, { name })),
  });
  if (!put.ok) { console.log(`  ✗ 落盘失败 HTTP ${put.status}`); return false; }
  const rr = await fetch(`${BASE}/api/run/${encodeURIComponent(name)}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stop_on_fail: false }),
  });
  if (!rr.ok) { console.log(`  ✗ 启动运行失败 HTTP ${rr.status}`); return false; }
  const { run_id } = await rr.json();
  let rep = null;
  for (let i = 0; i < 150; i++) {
    await sleep(2000);
    try {
      const d = await (await fetch(`${BASE}/api/history/${run_id}`)).json();
      // 注意: report.ended 在这套服务里从不赋值 —— 只能靠 done 事件判定结束
      const finished = (d.events || []).some((e) => e.event === "done");
      if (finished && d.report) { rep = d.report; break; }
    } catch { /* 继续等 */ }
  }
  if (!rep) { console.log("  ✗ 真机运行超时"); }
  else {
    console.log(`  真机运行 run_id=${run_id}`);
    for (const n of rep.nodes || [])
      console.log(`    ${n.status === "passed" ? "✔" : "✘"} ${n.id.padEnd(7)} ${n.type.padEnd(14)} ${(n.ms || 0) + "ms"}${n.error ? "  " + n.error : ""}`);
    console.log(`  ${rep.ok ? "✓ 真机全部通过" : "✗ 真机有失败"}`);
  }
  // 清场
  await fetch(`${BASE}/api/canvases/${encodeURIComponent(name)}`, { method: "DELETE" });
  await fetch(`${BASE}/api/cases/${encodeURIComponent(name)}/clear`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ what: "all" }),
  }).catch(() => {});
  return !!(rep && rep.ok);
}

(async () => {
  let pass = 0, fail = 0;
  for (const p of todo) {
    console.log(`\n${"─".repeat(70)}\n▸ ${p}`);
    let j;
    const t0 = Date.now();
    try { j = await gen(p); }
    catch (e) { console.log(`  ✗ 调用失败: ${e.message}`); fail++; continue; }
    const ms = Date.now() - t0;
    const c = j.canvas;
    console.log(`  模型=${j.model}  ${ms}ms  画布="${c.name}"  ${c.nodes.length} 节点 / ${c.edges.length} 边`);
    console.log(brief(c));
    const { errs } = check(c);
    if (c._notes && c._notes.length) console.log(`  ⚠ 模型备注: ${c._notes.join("; ")}`);
    if (errs.length) { console.log(`  ✗ 结构问题:\n     - ${errs.join("\n     - ")}`); fail++; continue; }
    console.log("  ✓ 结构合法");
    if (RUN) {
      const ok = await runCanvas(c, c.name || "ai");
      if (ok) pass++; else fail++;
    } else pass++;
  }
  console.log(`\n${"=".repeat(70)}\n结果: ${pass} 通过 / ${fail} 失败 (共 ${todo.length} 条)${RUN ? "  [含真机运行]" : ""}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
