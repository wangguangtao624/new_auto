/* 收尾回归: 跑一次完整示例用例 (上电 -> 开设备 -> I2C 校验 -> 抓帧出图检查 -> 关设备 -> 断电)
 * 跑完检查该 case 的独立空间: 运行历史 + 抓帧图片是否都落在 logs/cases/<case>/ 下。
 */
const BASE = "http://127.0.0.1:8765";
const NAME = process.argv[2] || "示例_上电读版本出图";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const before = (await (await fetch(`${BASE}/api/cases/${encodeURIComponent(NAME)}/assets`)).json()).counts;
  console.log("运行前 case 产物:", JSON.stringify(before));

  const r = await fetch(`${BASE}/api/run/${encodeURIComponent(NAME)}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stop_on_fail: true }) });
  const { run_id: runId } = await r.json();
  console.log("run_id =", runId);

  let hit = null;
  for (let i = 0; i < 150; i++) {
    await sleep(2000);
    const h = await (await fetch(`${BASE}/api/history`)).json();
    hit = (h.history || []).find((x) => x.id === runId);
    if (hit) break;
  }
  if (!hit) { console.log("TIMEOUT"); process.exit(1); }

  const d = await (await fetch(`${BASE}/api/history/${runId}`)).json();
  console.log(`\n=== 运行结果: ${hit.ok ? "全部通过 ✓" : `失败 ✗ (failed=${hit.failed})`}  ${hit.started} → ${hit.finished} ===`);
  for (const n of (d.report || {}).nodes || []) {
    console.log(`  ${n.status === "passed" ? "✓" : n.status === "failed" ? "✗" : "–"} ${n.title} (${n.ms}ms)${n.error ? "  " + String(n.error).slice(0, 110) : ""}`);
  }
  console.log("\n--- 关键日志 ---");
  for (const e of d.events || []) {
    if (e.event !== "log") continue;
    if (e.kind === "i2c.seq" || e.result === "fail" || e.kind === "device.check") {
      const f = Object.entries(e.fields || {}).map(([k, v]) => `${k}=${v}`).join("  ");
      console.log(`  [${e.result || "-"}] ${e.text}${f ? "\n        " + f : ""}`);
    }
  }

  const after = await (await fetch(`${BASE}/api/cases/${encodeURIComponent(NAME)}/assets`)).json();
  console.log("\n运行后 case 产物:", JSON.stringify(after.counts));
  console.log("  日志目录:", after.dir + "\\runs");
  console.log("  图片目录:", after.img_dir);
  console.log("  图片:", after.images.map((i) => i.name).slice(0, 6).join(", ") || "(无)");
  process.exit(hit.ok ? 0 : 1);
})();
