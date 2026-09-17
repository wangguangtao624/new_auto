#!/usr/bin/env node
/* 通过本地服务跑一个画布(case)并打印逐节点日志 —— 真机回归用
 *
 *   node scripts/run_case.cjs "gujian xiazai"
 *   node scripts/run_case.cjs "示例_上电读版本出图" --timeout 600
 */
const BASE = process.env.NEW_AUTO_BASE || "http://127.0.0.1:8765";

const argv = process.argv.slice(2);
const name = argv.find((a) => !a.startsWith("--"));
const ti = argv.indexOf("--timeout");
const TIMEOUT_S = ti >= 0 ? Number(argv[ti + 1]) : 420;

const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

async function jget(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return r.json();
}

(async () => {
  if (!name) { console.error("用法: node scripts/run_case.cjs <画布名> [--timeout 秒]"); process.exit(2); }
  console.log(`=== 运行画布: ${name} ===`);
  const r = await fetch(`${BASE}/api/run/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stop_on_fail: false }),
  });
  if (!r.ok) { console.error("启动失败:", r.status, await r.text()); process.exit(1); }
  const { run_id } = await r.json();
  console.log("run_id =", run_id);

  const t0 = Date.now();
  let last = 0;
  let done = false;
  while (!done) {
    if ((Date.now() - t0) / 1000 > TIMEOUT_S) { console.log(`\n!! 超时 ${TIMEOUT_S}s`); break; }
    await sleep(2000);
    let d;
    try { d = await jget(`/api/history/${run_id}`); } catch { continue; }
    const evs = d.events || [];
    for (; last < evs.length; last++) {
      const e = evs[last];
      if (e.event === "progress") continue;
      const t = new Date().toTimeString().slice(0, 8);
      if (e.event === "log") {
        const f = Object.entries(e.fields || {}).map(([k, v]) => `${k}=${v}`).join(" ");
        console.log(`[${t}] ${(e.level || "info").toUpperCase().padEnd(5)} ${e.text || ""}${f ? " | " + f : ""}`);
      } else if (e.event === "start") {
        console.log(`[${t}] ▶ 节点 ${e.id} ${e.title || ""}`);
      } else if (e.event === "finish") {
        const en = e.entry || {};
        console.log(`[${t}] ${en.status === "passed" ? "✔" : "✘"} ${en.id} ${en.title || ""} ${en.ms || 0}ms${en.error ? "  " + en.error : ""}`);
      } else if (e.event === "done") {
        done = true;
      } else if (e.event === "start_total") {
        console.log(`[${t}] 共 ${e.total} 个节点`);
      }
    }
    // 注意: report.ended 在这套服务里从不赋值, 结束只能靠上面的 done 事件判定
  }

  const fin = await jget(`/api/history/${run_id}`);
  const rep = fin.report || {};
  const bad = (rep.nodes || []).filter((n) => n.status !== "passed");
  console.log(`\n===== 结论: ${rep.ok ? "全部通过" : "有失败"} | 节点 ${(rep.nodes || []).length} 个, 失败 ${bad.length} 个 =====`);
  for (const n of bad) console.log(`  ✘ ${n.id} ${n.type} ${n.title || ""} — ${n.error || "(无错误信息)"}`);
  process.exit(rep.ok ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(1); });
