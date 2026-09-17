/* 真机验证: i2c.seq 每条指令自带位宽模式 + 回读值与期待值校验
 * 临时画布 -> 运行 -> 拉取逐字段事件, 检查:
 *   1) 不同行用不同 mode (A2D4 / A1D1 / A2D2) 都生效
 *   2) 有 expect 的行做 (回读 & 掩码) >> 右移 == 期待值 比对
 *   3) expect 留空的行不断言
 * 用完删除临时画布。
 */
const BASE = "http://127.0.0.1:8765";
const NAME = "_验证I2C逐条模式";

const canvas = {
  name: NAME,
  stop_on_fail: false,
  nodes: [
    { id: "n1", type: "power.ctrl", x: 0, y: 0,
      params: { action: "on", channel: 0, port: "", off_seconds: 15, wait_after_on: 8 } },
    { id: "n2", type: "i2c.seq", x: 260, y: 0,
      params: { slave: "0x40", on_fail: "continue", ops: [
        { op: "read",  addr: "0x00d8", mode: "A2D4", value: "", expect: "0x04", mask: "0x00FF0000", shift: "16", slave: "" },
        { op: "read",  addr: "0x00c0", mode: "A2D4", value: "", expect: "",     mask: "0xFFFFFFFF", shift: "0",  slave: "" },
        { op: "read",  addr: "0x00d8", mode: "A1D1", value: "", expect: "",     mask: "0xFFFFFFFF", shift: "0",  slave: "" },
        { op: "read",  addr: "0x00d8", mode: "A2D4", value: "", expect: "0x9",  mask: "0xFFFFFFFF", shift: "0",  slave: "" },
        { op: "write", addr: "0x00c0", mode: "A2D2", value: "0x0001", expect: "", mask: "0xFFFFFFFF", shift: "0", slave: "" },
        { op: "read",  addr: "0x00c0", mode: "A2D2", value: "", expect: "",     mask: "0xFFFFFFFF", shift: "0",  slave: "" },
      ] } },
    { id: "n3", type: "power.ctrl", x: 520, y: 0,
      params: { action: "off", channel: 0, port: "", off_seconds: 15, wait_after_on: 8 } },
  ],
  edges: [
    { from: "n1", fromPort: "__out", to: "n2", toParam: "__in", kind: "flow" },
    { from: "n2", fromPort: "__out", to: "n3", toParam: "__in", kind: "flow" },
  ],
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  let r = await fetch(`${BASE}/api/canvases/${encodeURIComponent(NAME)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(canvas) });
  if (!r.ok) throw new Error("PUT canvas failed " + r.status);

  r = await fetch(`${BASE}/api/run/${encodeURIComponent(NAME)}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stop_on_fail: false }) });
  const { run_id: runId } = await r.json();
  console.log("run_id =", runId, " (等真机跑完…)");

  let hit = null;
  for (let i = 0; i < 90; i++) {
    await sleep(2000);
    const h = await (await fetch(`${BASE}/api/history`)).json();
    hit = (h.history || []).find((x) => x.id === runId);
    if (hit) break;
  }
  if (!hit) { console.log("TIMEOUT"); process.exit(1); }

  const d = await (await fetch(`${BASE}/api/history/${runId}`)).json();
  console.log(`\n=== 总结果: ${hit.ok ? "全部通过 ✓" : `存在失败 ✗ (failed=${hit.failed})`} ===\n`);
  let n = 0;
  for (const e of d.events || []) {
    if (e.event !== "log") continue;
    const f = Object.entries(e.fields || {}).map(([k, v]) => `${k}=${v}`).join("  ");
    if (e.kind === "i2c.seq" || /读|写/.test(e.text || "")) {
      n++;
      console.log(`[${String(e.result || "-").padEnd(4)}] ${e.text}`);
      if (f) console.log(`        ${f}`);
    }
  }
  console.log(`\n共 ${n} 条 I²C 日志`);

  // 清理临时画布
  await fetch(`${BASE}/api/canvases/${encodeURIComponent(NAME)}`, { method: "DELETE" });
  console.log("临时画布已删除");
})();
