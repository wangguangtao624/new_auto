/* new_auto 拖拽式流程画布 (原生 JS + SVG, 无构建依赖) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let REG = [];              // 节点注册表 (来自 /api/nodes)
let canvas = null;         // 当前画布 {name, stop_on_fail, nodes, edges}
let selected = null;       // 选中的节点 id
let pendingConn = null;    // 正在拖的连线 {node, port}

const CANVAS_W = 2400, CANVAS_H = 1600;

/* ---------------- API ---------------- */
async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const jfetch = (p) => api(p);
const jpost = (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
const jput = (p, body) => api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

/* ---------------- 工具 ---------------- */
function spec(type) { return REG.find((n) => n.type === type); }
function nodeById(id) { return canvas.nodes.find((n) => n.id === id); }
function setStatus(msg, cls) {
  const el = $("#status");
  el.textContent = msg || "";
  el.className = "status " + (cls || "");
}
function uid() { return "n" + Math.random().toString(36).slice(2, 7); }
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

/* ---------------- 面板 ---------------- */
function renderPalette() {
  const groups = {};
  REG.forEach((n) => (groups[n.group] ||= []).push(n));
  const root = $("#palette-groups");
  root.innerHTML = "";
  for (const [g, items] of Object.entries(groups)) {
    const div = document.createElement("div");
    div.className = "pal-group";
    div.innerHTML = `<div class="pal-group-name">${esc(g)}</div>`;
    for (const it of items) {
      const el = document.createElement("div");
      el.className = "pal-item";
      el.innerHTML = `<b>${esc(it.title)}</b><span>${esc(it.desc || it.type)}</span>`;
      el.draggable = true;
      el.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/newnode", it.type);
        const ghost = document.createElement("div");
        ghost.className = "drag-ghost";
        ghost.textContent = it.title;
        document.body.appendChild(ghost);
        const mv = (ev) => { ghost.style.left = ev.clientX + 12 + "px"; ghost.style.top = ev.clientY + 12 + "px"; };
        document.addEventListener("mousemove", mv);
        el.addEventListener("dragend", () => { ghost.remove(); document.removeEventListener("mousemove", mv); }, { once: true });
      });
      div.appendChild(el);
    }
    root.appendChild(div);
  }
}

/* ---------------- 画布渲染 ---------------- */
function portPos(node, kind, name) {
  const s = spec(node.type);
  const list = kind === "out" ? Object.keys(s.outputs) : Object.keys(s.inputs);
  const i = list.indexOf(name);
  const n = list.length;
  const yFrac = (i + 1) / (n + 1);
  const x = kind === "out" ? node.x + nodeW(node) : node.x;
  return { x, y: node.y + 30 + yFrac * Math.max(34, nodeH(node) - 46) };
}
function nodeW(node) {
  const s = spec(node.type);
  return Math.max(168, 40 + (s.title.length * 13));
}
function nodeH(node) {
  const s = spec(node.type);
  const ports = Math.max(Object.keys(s.outputs).length, Object.keys(s.inputs).length);
  return 62 + ports * 16;
}

function renderAll() {
  const c = $("#canvas");
  c.innerHTML = "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.id = "wires";
  svg.setAttribute("width", CANVAS_W); svg.setAttribute("height", CANVAS_H);
  c.appendChild(svg);
  canvas.nodes.forEach(renderNode);
  canvas.edges.forEach(renderEdge);
  drawWires();
}

function renderNode(node) {
  const s = spec(node.type);
  const el = document.createElement("div");
  el.className = "node";
  el.id = "node-" + node.id;
  el.style.left = node.x + "px"; el.style.top = node.y + "px";
  el.style.minHeight = nodeH(node) + "px";
  el.innerHTML = `
    <div class="node-head" style="background:${esc(s.color)}">
      <span class="t">${esc(s.title)}</span><span class="g">${esc(s.group)}</span>
    </div>
    <div class="node-type">${esc(node.id)} · ${esc(node.type)}</div>
    <div class="node-status"></div>`;

  // 输出端口
  Object.keys(s.outputs).forEach((port, i, arr) => {
    const p = document.createElement("div");
    p.className = "port out";
    p.dataset.node = node.id; p.dataset.port = port;
    p.style.top = (30 + ((i + 1) / (arr.length + 1)) * Math.max(34, nodeH(node) - 46)) + "px";
    p.innerHTML = `<span class="pl">${esc(s.outputs[port])}</span>`;
    p.addEventListener("mousedown", startConn);
    el.appendChild(p);
  });
  // 输入端口
  Object.keys(s.inputs).forEach((param, i, arr) => {
    const p = document.createElement("div");
    p.className = "port in";
    p.dataset.node = node.id; p.dataset.param = param;
    p.style.top = (30 + ((i + 1) / (arr.length + 1)) * Math.max(34, nodeH(node) - 46)) + "px";
    p.innerHTML = `<span class="pl">${esc(s.inputs[param])}</span>`;
    p.addEventListener("mouseup", finishConn);
    p.addEventListener("mousedown", (e) => e.stopPropagation());
    el.appendChild(p);
  });

  // 拖动节点
  const head = $(".node-head", el);
  head.addEventListener("mousedown", (e) => startMove(e, node, el));
  el.addEventListener("mousedown", () => selectNode(node.id));
  $("#canvas").appendChild(el);
}

function renderEdge(edge) { /* 边存数据即可, 线由 drawWires 统一画 */ }

function drawWires(tempLine) {
  const svg = $("#wires");
  if (!svg) return;
  svg.innerHTML = "";
  const draw = (x1, y1, x2, y2, color, edge) => {
    const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
    p.setAttribute("fill", "none"); p.setAttribute("stroke", color); p.setAttribute("stroke-width", 2.2);
    if (edge) {
      p.dataset.from = edge.from; p.dataset.fromPort = edge.fromPort;
      p.dataset.to = edge.to; p.dataset.toParam = edge.toParam;
      p.addEventListener("click", () => {
        canvas.edges = canvas.edges.filter((e) => e !== edge);
        drawWires(); setStatus("已删除连线");
      });
    }
    svg.appendChild(p);
  };
  for (const e of canvas.edges) {
    const a = nodeById(e.from), b = nodeById(e.to);
    if (!a || !b) continue;
    const p1 = portPos(a, "out", e.fromPort), p2 = portPos(b, "in", e.toParam);
    draw(p1.x, p1.y, p2.x, p2.y, "#4a89dc", e);
  }
  if (tempLine) draw(tempLine.x1, tempLine.y1, tempLine.x2, tempLine.y2, "#e8b339");
}

/* ---------------- 交互: 移动 / 选择 / 连线 ---------------- */
function startMove(e, node, el) {
  e.preventDefault(); e.stopPropagation();
  selectNode(node.id);
  const sx = e.clientX, sy = e.clientY, ox = node.x, oy = node.y;
  const mv = (ev) => {
    node.x = Math.max(0, ox + ev.clientX - sx);
    node.y = Math.max(0, oy + ev.clientY - sy);
    el.style.left = node.x + "px"; el.style.top = node.y + "px";
    drawWires();
  };
  const up = () => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up); };
  document.addEventListener("mousemove", mv);
  document.addEventListener("mouseup", up);
}

function selectNode(id) {
  selected = id;
  $$(".node").forEach((n) => n.classList.toggle("sel", n.id === "node-" + id));
  renderInspector();
}

function startConn(e) {
  e.preventDefault(); e.stopPropagation();
  const port = e.currentTarget;
  pendingConn = { node: port.dataset.node, port: port.dataset.port };
  const mv = (ev) => {
    const wrap = $("#canvas-wrap").getBoundingClientRect();
    const cx = ev.clientX - wrap.left + $("#canvas-wrap").scrollLeft;
    const cy = ev.clientY - wrap.top + $("#canvas-wrap").scrollTop;
    const s = portPos(nodeById(pendingConn.node), "out", pendingConn.port);
    drawWires({ x1: s.x, y1: s.y, x2: cx, y2: cy });
  };
  const up = (ev) => {
    document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    const tgt = document.elementFromPoint(ev.clientX, ev.clientY);
    if (tgt && tgt.classList.contains("port") && tgt.classList.contains("in")) {
      const edge = { from: pendingConn.node, fromPort: pendingConn.port,
                     to: tgt.dataset.node, toParam: tgt.dataset.param };
      canvas.edges = canvas.edges.filter(
        (x) => !(x.to === edge.to && x.toParam === edge.toParam));
      canvas.edges.push(edge);
      setStatus(`已连线 ${edge.from}.${edge.fromPort} → ${edge.to}.${edge.toParam}`);
    }
    pendingConn = null; drawWires();
  };
  document.addEventListener("mousemove", mv);
  document.addEventListener("mouseup", up);
}
function finishConn(e) { e.stopPropagation(); }

/* ---------------- 属性面板 ---------------- */
function renderInspector() {
  const body = $("#ins-body");
  const node = nodeById(selected);
  if (!node) {
    body.className = "ins-empty";
    body.innerHTML = "点击节点编辑参数<br>拖动输出圆点 → 输入圆点连线";
    return;
  }
  const s = spec(node.type);
  body.className = "";
  let html = `<div class="ins-node-type">${esc(node.type)}</div>`;
  for (const p of s.params) {
    const v = node.params[p.name] !== undefined ? node.params[p.name] : (p.default ?? "");
    if (p.type === "choice") {
      html += `<div class="field"><label>${esc(p.label)}</label><select data-param="${esc(p.name)}">` +
        p.options.map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("") +
        `</select></div>`;
    } else if (p.type === "bool") {
      html += `<div class="field"><label>${esc(p.label)}</label>` +
        `<input type="checkbox" data-param="${esc(p.name)}" ${v ? "checked" : ""}></div>`;
    } else if (p.type === "int" || p.type === "float") {
      html += `<div class="field"><label>${esc(p.label)}</label>` +
        `<input type="number" step="${p.type === "float" ? "0.1" : "1"}" data-param="${esc(p.name)}" value="${esc(v)}"></div>`;
    } else {
      html += `<div class="field"><label>${esc(p.label)}${p.hex ? " (十六进制)" : ""}</label>` +
        `<input type="text" data-param="${esc(p.name)}" value="${esc(v)}"></div>`;
    }
  }
  if (!s.params.length) html += `<div class="field"><label>该节点无参数</label></div>`;
  if (Object.keys(s.inputs).length)
    html += `<div class="ins-conn">输入端口: ${Object.values(s.inputs).map(esc).join("、")}<br>连线值优先于参数</div>`;
  body.innerHTML = html;

  $$("[data-param]", body).forEach((input) => {
    const apply = () => {
      let v;
      if (input.type === "checkbox") v = input.checked;
      else if (input.type === "number") v = parseFloat(input.value) || 0;
      else v = input.value;
      node.params[input.dataset.param] = v;
    };
    input.addEventListener("change", apply);
    input.addEventListener("input", apply);
  });
}

/* ---------------- 画布 CRUD ---------------- */
async function refreshCanvasList(selectName) {
  const { canvases } = await jfetch("/api/canvases");
  const sel = $("#canvas-list");
  sel.innerHTML = canvases.map((n) => `<option>${esc(n)}</option>`).join("");
  if (selectName && canvases.includes(selectName)) sel.value = selectName;
  return sel.value;
}

async function loadCanvas(name) {
  canvas = await jfetch("/api/canvases/" + encodeURIComponent(name));
  $("#chk-stopfail").checked = canvas.stop_on_fail !== false;
  renderAll(); renderInspector();
  setStatus(`已加载画布: ${name}`, "ok");
}

async function saveCanvas() {
  canvas.stop_on_fail = $("#chk-stopfail").checked;
  await jput("/api/canvases/" + encodeURIComponent(canvas.name), canvas);
  await refreshCanvasList(canvas.name);
  setStatus(`画布已保存: ${canvas.name}`, "ok");
}

/* ---------------- 运行与报告 ---------------- */
function clearStatusBadges() {
  $$(".node").forEach((n) => {
    n.classList.remove("st-pass", "st-fail", "st-skip");
    const st = $(".node-status", n);
    if (st) { st.textContent = ""; st.className = "node-status"; }
  });
}
function markNode(id, status, outputs, error) {
  const el = $("#node-" + id);
  if (!el) return;
  el.classList.add("st-" + (status === "passed" ? "pass" : status === "failed" ? "fail" : "skip"));
  const st = $(".node-status", el);
  if (st) {
    const tag = status === "passed" ? "✓" : status === "failed" ? "✗" : "–";
    let extra = "";
    if (outputs && Object.keys(outputs).length)
      extra = " " + Object.entries(outputs).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ");
    st.className = "node-status st-" + (status === "passed" ? "pass" : status === "failed" ? "fail" : "skip");
    st.textContent = tag + " " + (error ? error.slice(0, 90) : extra.slice(0, 110));
  }
}

async function runCanvas() {
  await saveCanvas();
  clearStatusBadges();
  setStatus("运行中…");
  const btn = $("#btn-run"); btn.disabled = true;
  try {
    const report = await jpost("/api/run/" + encodeURIComponent(canvas.name),
                               { stop_on_fail: $("#chk-stopfail").checked });
    for (const n of report.nodes) markNode(n.id, n.status, n.outputs, n.error);
    showReport(report);
    setStatus(report.ok ? "运行完成: 全部通过 ✓" : "运行失败 ✗", report.ok ? "ok" : "err");
  } catch (e) {
    setStatus("运行出错: " + e.message, "err");
    alert("运行出错: " + e.message);
  } finally { btn.disabled = false; }
}

function showReport(report) {
  $("#runlog").classList.remove("hidden");
  const sum = $("#runlog-summary");
  sum.textContent = report.ok ? " ✓ 全部通过" : " ✗ 存在失败";
  sum.className = report.ok ? "ok" : "err";
  const body = $("#runlog-body");
  body.innerHTML = report.nodes.map((n) => `
    <div class="rl-node">
      <span class="st-${n.status}">${n.status === "passed" ? "✓" : n.status === "failed" ? "✗" : "–"}</span>
      <b>${esc(n.title)}</b>
      <span style="color:var(--dim)">(${n.ms}ms)</span>
      ${n.error ? `<div class="rl-err">${esc(n.error)}</div>` : ""}
      ${n.outputs && Object.keys(n.outputs).length
        ? `<div class="rl-outs">${Object.entries(n.outputs).map(([k, v]) => `${esc(k)}=${esc(JSON.stringify(v))}`).join("  ")}</div>` : ""}
    </div>`).join("");
}

/* ---------------- 初始化 ---------------- */
async function init() {
  const { nodes } = await jfetch("/api/nodes");
  REG = nodes;
  renderPalette();

  // 把 SVG 线层放进画布容器坐标系
  const c = $("#canvas");
  const svg = $("#wires");
  c.appendChild(svg);
  svg.setAttribute("width", CANVAS_W); svg.setAttribute("height", CANVAS_H);

  $("#canvas-wrap").addEventListener("dragover", (e) => e.preventDefault());
  $("#canvas-wrap").addEventListener("drop", (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("text/newnode");
    if (!type) return;
    const wrap = $("#canvas-wrap").getBoundingClientRect();
    const x = e.clientX - wrap.left + $("#canvas-wrap").scrollLeft - 80;
    const y = e.clientY - wrap.top + $("#canvas-wrap").scrollTop - 20;
    const s = spec(type);
    const params = {};
    s.params.forEach((p) => { if (p.default !== null && p.default !== undefined) params[p.name] = p.default; });
    const node = { id: uid(), type, x: Math.max(0, x), y: Math.max(0, y), params };
    canvas.nodes.push(node);
    renderAll();
    selectNode(node.id);
    setStatus(`已添加节点: ${s.title}`);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Delete" && selected && document.activeElement.tagName !== "INPUT"
        && document.activeElement.tagName !== "SELECT") {
      canvas.nodes = canvas.nodes.filter((n) => n.id !== selected);
      canvas.edges = canvas.edges.filter((e2) => e2.from !== selected && e2.to !== selected);
      selected = null; renderAll(); renderInspector();
      setStatus("已删除节点");
    }
  });

  $("#canvas-list").addEventListener("change", () => loadCanvas($("#canvas-list").value));
  $("#btn-new").addEventListener("click", async () => {
    const name = prompt("新画布名称 (即 case 名):");
    if (!name) return;
    canvas = { name, stop_on_fail: true,
               nodes: [{ id: "n1", type: "relay.on", x: 60, y: 60, params: { channel: 0 } }],
               edges: [] };
    await saveCanvas();
    await refreshCanvasList(name);
    await loadCanvas(name);
  });
  $("#btn-rename").addEventListener("click", async () => {
    const name = prompt("重命名为:", canvas.name);
    if (!name || name === canvas.name) return;
    await jfetch; // noop
    const old = canvas.name;
    canvas.name = name;
    await jput("/api/canvases/" + encodeURIComponent(name), canvas);
    await api("/api/canvases/" + encodeURIComponent(old), { method: "DELETE" });
    await refreshCanvasList(name);
    setStatus(`已重命名为 ${name}`, "ok");
  });
  $("#btn-delete").addEventListener("click", async () => {
    if (!confirm(`删除画布 ${canvas.name}?`)) return;
    await api("/api/canvases/" + encodeURIComponent(canvas.name), { method: "DELETE" });
    await refreshCanvasList();
    await loadCanvas($("#canvas-list").value);
  });
  $("#btn-save").addEventListener("click", saveCanvas);
  $("#btn-run").addEventListener("click", runCanvas);
  $("#btn-gencode").addEventListener("click", async () => {
    await saveCanvas();
    const r = await jpost("/api/gencode/" + encodeURIComponent(canvas.name));
    setStatus(`用例代码已生成: ${r.file}`, "ok");
    alert("用例代码已生成:\n" + r.file + "\n\n运行: python app/cases/" + canvas.name + ".py");
  });

  await refreshCanvasList();
  await loadCanvas($("#canvas-list").value);
}

init().catch((e) => { setStatus("初始化失败: " + e.message, "err"); console.error(e); });
