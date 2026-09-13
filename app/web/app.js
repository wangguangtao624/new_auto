/* new_auto 拖拽式流程画布 (原生 JS + SVG, 无构建依赖)
 * v1.0.3: 空白拖拽平移 / 执行流端口(上下游) / 右键新建节点 / 节点单步调试 */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let REG = [];              // 节点注册表
let canvas = null;         // 当前画布
let selected = null;       // 选中节点 id
let pendingConn = null;    // 正在拖的连线 {kind, node, port}
let COM_PORTS = [];        // 本机串口列表

const CANVAS_W = 3000, CANVAS_H = 2000;
const FLOW_IN = "__in", FLOW_OUT = "__out";

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
  const el = $("#status"); el.textContent = msg || ""; el.className = "status " + (cls || "");
}
function uid() { return "n" + Math.random().toString(36).slice(2, 7); }
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function optLabel(p, v) {
  const o = (p.options || []).find((o) => (o.v ?? o) === v);
  return typeof o === "object" ? o.l : v;
}

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
        ghost.className = "drag-ghost"; ghost.textContent = it.title;
        document.body.appendChild(ghost);
        const mv = (ev) => { ghost.style.left = ev.clientX + 12 + "px"; ghost.style.top = ev.clientY + 12 + "px"; };
        document.addEventListener("mousemove", mv);
        el.addEventListener("dragend", () => { ghost.remove(); document.removeEventListener("mousemove", mv); }, { once: true });
      });
      // 双击面板项: 直接放到画布可视区中心
      el.addEventListener("dblclick", () => {
        const w = $("#canvas-wrap");
        addNodeAt(it.type, w.scrollLeft + 200, w.scrollTop + 120);
      });
      div.appendChild(el);
    }
    root.appendChild(div);
  }
}

/* ---------------- 几何 ---------------- */
function nodeW(node) { const s = spec(node.type); return Math.max(172, 46 + s.title.length * 13); }
function nodeH(node) {
  const s = spec(node.type);
  const n = Math.max(Object.keys(s.outputs).length, Object.keys(s.inputs).length, 1);
  return 56 + n * 17 + (s.debug?.length ? 8 : 0);
}
/* 数据端口位置 (执行流端口固定在顶部两角) */
function portPos(node, kind, name) {
  const s = spec(node.type);
  const list = kind === "out" ? Object.keys(s.outputs) : Object.keys(s.inputs);
  const i = list.indexOf(name), n = Math.max(list.length, 1);
  const y = node.y + 52 + ((i + 1) / (n + 1)) * Math.max(30, nodeH(node) - 66);
  return { x: kind === "out" ? node.x + nodeW(node) : node.x, y };
}
const flowPos = (node, kind) => ({
  x: kind === "out" ? node.x + nodeW(node) / 2 + 10 : node.x + nodeW(node) / 2 - 10,
  y: node.y,
});

/* ---------------- 画布渲染 ---------------- */
function renderAll() {
  const c = $("#canvas");
  c.innerHTML = "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.id = "wires";
  svg.setAttribute("width", CANVAS_W); svg.setAttribute("height", CANVAS_H);
  svg.innerHTML = `<defs><marker id="arrow-flow" viewBox="0 0 10 10" refX="9" refY="5"
      markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#e8b339"/></marker></defs>`;
  c.appendChild(svg);
  canvas.nodes.forEach(renderNode);
  drawWires();
  if (selected) selectNode(selected, true);
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
      <button class="node-run" title="单步调试此节点">▶</button>
      <span class="t">${esc(s.title)}</span><span class="g">${esc(s.group)}</span>
    </div>
    <div class="node-type">${esc(node.id)} · ${esc(node.type)}</div>
    <div class="node-status"></div>`;

  $(".node-run", el).addEventListener("mousedown", (e) => e.stopPropagation());
  $(".node-run", el).addEventListener("click", (e) => { e.stopPropagation(); runSingleNode(node); });

  // 执行流端口 (顶部两角, 方块金色) —— 明确上下游
  const fin = mkPort(el, "flow-in", "入", "执行流入 (上游 →)");
  fin.style.left = "-7px"; fin.style.top = "-5px";
  fin.dataset.node = node.id;
  fin.addEventListener("mouseup", finishConn);
  fin.addEventListener("mousedown", (e) => e.stopPropagation());
  const fout = mkPort(el, "flow-out", "出", "执行流出 (→ 下游)");
  fout.style.right = "-7px"; fout.style.top = "-5px";
  fout.dataset.node = node.id;
  fout.addEventListener("mousedown", startConn);

  // 数据端口
  Object.keys(s.outputs).forEach((port, i, arr) => {
    const p = mkPort(el, "port out", s.outputs[port]);
    p.dataset.node = node.id; p.dataset.port = port;
    p.style.top = (52 + ((i + 1) / (arr.length + 1)) * Math.max(30, nodeH(node) - 66)) + "px";
    p.addEventListener("mousedown", startConn);
  });
  Object.keys(s.inputs).forEach((param, i, arr) => {
    const p = mkPort(el, "port in", s.inputs[param]);
    p.dataset.node = node.id; p.dataset.param = param;
    p.style.top = (52 + ((i + 1) / (arr.length + 1)) * Math.max(30, nodeH(node) - 66)) + "px";
    p.addEventListener("mouseup", finishConn);
    p.addEventListener("mousedown", (e) => e.stopPropagation());
  });

  $(".node-head", el).addEventListener("mousedown", (e) => startMove(e, node, el));
  el.addEventListener("mousedown", () => selectNode(node.id));
  $("#canvas").appendChild(el);
}
function mkPort(el, cls, label, tip) {
  const p = document.createElement("div");
  p.className = cls;
  if (tip) p.title = tip;
  p.innerHTML = `<span class="pl">${esc(label)}</span>`;
  el.appendChild(p);
  return p;
}

function drawWires(tempLine) {
  const svg = $("#wires");
  if (!svg) return;
  $$("#wires path.edge", svg).forEach((p) => p.remove());
  const draw = (x1, y1, x2, y2, kind, edge) => {
    const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
    if (kind === "flow") {
      p.setAttribute("stroke", "#e8b339"); p.setAttribute("stroke-width", 3);
      p.setAttribute("marker-end", "url(#arrow-flow)");
    } else {
      p.setAttribute("stroke", "#4a89dc"); p.setAttribute("stroke-width", 2);
    }
    p.setAttribute("fill", "none"); p.classList.add("edge");
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
    const kind = e.kind || "data";
    let p1, p2;
    if (kind === "flow") { p1 = flowPos(a, "out"); p2 = flowPos(b, "in"); }
    else { p1 = portPos(a, "out", e.fromPort); p2 = portPos(b, "in", e.toParam); }
    draw(p1.x, p1.y, p2.x, p2.y, kind, e);
  }
  if (tempLine) draw(tempLine.x1, tempLine.y1, tempLine.x2, tempLine.y2, tempLine.kind);
}

/* ---------------- 交互: 移动 / 平移 / 选择 / 连线 ---------------- */
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

/* 空白处按住拖动 = 平移画布 */
function initPanning() {
  const wrap = $("#canvas-wrap");
  wrap.addEventListener("mousedown", (e) => {
    const onBg = e.target.id === "canvas-wrap" || e.target.id === "canvas"
      || e.target.tagName === "svg" || e.target.tagName === "defs";
    if (!onBg || e.button !== 0) return;
    selectNode(null);
    hideMenu();
    const sx = e.clientX, sy = e.clientY, sl = wrap.scrollLeft, st = wrap.scrollTop;
    wrap.classList.add("panning");
    const mv = (ev) => {
      wrap.scrollLeft = sl - (ev.clientX - sx);
      wrap.scrollTop = st - (ev.clientY - sy);
    };
    const up = () => {
      wrap.classList.remove("panning");
      document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", mv);
    document.addEventListener("mouseup", up);
  });
}

function selectNode(id) {
  selected = id;
  $$(".node").forEach((n) => n.classList.toggle("sel", n.id === "node-" + id));
  renderInspector();
}

function startConn(e) {
  e.preventDefault(); e.stopPropagation();
  const port = e.currentTarget;
  const isFlow = port.classList.contains("flow-out");
  pendingConn = { kind: isFlow ? "flow" : "data",
                  node: isFlow ? port.dataset.node : port.dataset.node,
                  port: isFlow ? FLOW_OUT : port.dataset.port };
  const mv = (ev) => {
    const wrap = $("#canvas-wrap").getBoundingClientRect();
    const cx = ev.clientX - wrap.left + $("#canvas-wrap").scrollLeft;
    const cy = ev.clientY - wrap.top + $("#canvas-wrap").scrollTop;
    const a = nodeById(pendingConn.node);
    const s = isFlow ? flowPos(a, "out") : portPos(a, "out", pendingConn.port);
    drawWires({ x1: s.x, y1: s.y, x2: cx, y2: cy, kind: pendingConn.kind });
  };
  const up = (ev) => {
    document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    const tgt = document.elementFromPoint(ev.clientX, ev.clientY);
    const okTarget = tgt && (tgt.classList.contains("in") || tgt.classList.contains("flow-in"));
    if (okTarget) {
      const isFlowT = tgt.classList.contains("flow-in");
      if (pendingConn.kind === "flow" && isFlowT) {
        canvas.edges = canvas.edges.filter((x) =>
          !(x.kind === "flow" && x.from === pendingConn.node && x.to === tgt.dataset.node));
        canvas.edges.push({ from: pendingConn.node, fromPort: FLOW_OUT,
                            to: tgt.dataset.node, toParam: FLOW_IN, kind: "flow" });
        setStatus(`执行流: ${pendingConn.node} → ${tgt.dataset.node}`);
      } else if (pendingConn.kind === "data" && !isFlowT) {
        const edge = { from: pendingConn.node, fromPort: pendingConn.port,
                       to: tgt.dataset.node, toParam: tgt.dataset.param, kind: "data" };
        canvas.edges = canvas.edges.filter((x) =>
          !(x.to === edge.to && x.toParam === edge.toParam && (x.kind || "data") === "data"));
        canvas.edges.push(edge);
        setStatus(`数据: ${edge.from}.${edge.fromPort} → ${edge.to}.${edge.toParam}`);
      } else {
        setStatus("连线类型不匹配: 金色执行流端口只能连金色, 蓝色数据端口只能连蓝色");
      }
    }
    pendingConn = null; drawWires();
  };
  document.addEventListener("mousemove", mv);
  document.addEventListener("mouseup", up);
}
function finishConn(e) { e.stopPropagation(); }

/* ---------------- 右键菜单: 新建节点 ---------------- */
function hideMenu() { $("#ctx-menu")?.remove(); }
function showMenu(x, y, canvasX, canvasY) {
  hideMenu();
  const menu = document.createElement("div");
  menu.id = "ctx-menu";
  let html = `<div class="ctx-title">添加节点</div>`;
  const groups = {};
  REG.forEach((n) => (groups[n.group] ||= []).push(n));
  for (const [g, items] of Object.entries(groups)) {
    html += `<div class="ctx-group">${esc(g)}</div>`;
    for (const it of items)
      html += `<div class="ctx-item" data-type="${esc(it.type)}">${esc(it.title)}</div>`;
  }
  menu.innerHTML = html;
  menu.addEventListener("click", (e) => {
    const type = e.target.dataset?.type;
    if (!type) return;
    addNodeAt(type, canvasX, canvasY);
    hideMenu();
  });
  document.body.appendChild(menu);
  // 防止超出视口
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, innerWidth - r.width - 8) + "px";
  menu.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
}
function initContextMenu() {
  const wrap = $("#canvas-wrap");
  wrap.addEventListener("contextmenu", (e) => {
    if (e.target.closest(".node") || e.target.closest(".port") || e.target.closest(".flow-in")
        || e.target.closest(".flow-out")) return;
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const cx = e.clientX - rect.left + wrap.scrollLeft;
    const cy = e.clientY - rect.top + wrap.scrollTop;
    showMenu(e.clientX, e.clientY, Math.max(0, cx - 80), Math.max(0, cy - 16));
  });
  document.addEventListener("mousedown", (e) => {
    if (!e.target.closest("#ctx-menu")) hideMenu();
  });
}
function addNodeAt(type, x, y) {
  const s = spec(type);
  const params = {};
  s.params.forEach((p) => { if (p.default !== null && p.default !== undefined) params[p.name] = p.default; });
  const node = { id: uid(), type, x, y, params };
  canvas.nodes.push(node);
  renderAll(); selectNode(node.id);
  setStatus(`已添加节点: ${s.title} (${node.id})`);
}

/* ---------------- 属性面板 ---------------- */
async function renderInspector() {
  const body = $("#ins-body");
  const node = nodeById(selected);
  if (!node) {
    body.className = "ins-empty";
    body.innerHTML = "点击节点编辑参数<br>金色端口=执行流(上下游)<br>蓝色端口=数据传值<br>空白处右键=新建节点<br>空白处按住拖动=平移画布";
    return;
  }
  const s = spec(node.type);
  body.className = "";
  let html = `<div class="ins-node-type">${esc(node.type)}</div>`;
  for (const p of s.params) {
    const v = node.params[p.name] !== undefined ? node.params[p.name] : (p.default ?? "");
    if (p.type === "port") {
      let opts = `<option value="">默认 (config: ${esc(canvas._cfg_relay || "config.json")})</option>` +
        COM_PORTS.map((c) => `<option value="${esc(c.port)}" ${c.port === v ? "selected" : ""}>${esc(c.port)} · ${esc(c.desc)}</option>`).join("");
      html += `<div class="field"><label>${esc(p.label)} <a href="javascript:void(0)" class="refresh-ports">刷新</a></label>` +
        `<select data-param="${esc(p.name)}">${opts}</select></div>`;
    } else if (p.type === "choice") {
      const opts = (p.options || []).map((o) => {
        const val = typeof o === "object" ? o.v : o;
        const lab = typeof o === "object" ? o.l : o;
        return `<option value="${esc(val)}" ${val === v ? "selected" : ""}>${esc(lab)}</option>`;
      }).join("");
      html += `<div class="field"><label>${esc(p.label)}</label><select data-param="${esc(p.name)}">${opts}</select></div>`;
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

  // 调试区
  html += `<div class="ins-debug"><div class="ins-conn" style="margin-top:10px">调试</div>`;
  html += `<button class="dbg-run" id="ins-run-node">▶ 运行此节点</button>`;
  for (const d of s.debug || [])
    html += `<button class="dbg-btn" data-dbg="${esc(d.name)}">${esc(d.label)}</button>`;
  html += `<div id="dbg-result" class="dbg-result"></div></div>`;
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
  $(".refresh-ports", body)?.addEventListener("click", async () => {
    await loadPorts(); renderInspector(); setStatus("串口列表已刷新");
  });
  $("#ins-run-node", body)?.addEventListener("click", () => runSingleNode(node));
  $$(".dbg-btn", body).forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.dbg;
      const out = $("#dbg-result");
      out.textContent = "执行中…"; out.className = "dbg-result";
      try {
        const r = await jpost("/api/debug", { type: node.type, action, params: node.params });
        out.textContent = r.report || JSON.stringify(r.outputs || r, null, 1);
        out.className = "dbg-result ok";
        if (r.ports) {
          out.textContent += "\n" + r.ports.map((p) =>
            `${p.port}  ${p.relay ? "✔ 继电器响应" : "✘ 无继电器"}${p.error ? " (" + p.error + ")" : ""}`
            + (p.channels?.length ? `  可用通道:${p.channels.map((c) => c.ch).join(",")}` : "")).join("\n");
        }
      } catch (e) {
        out.textContent = "失败: " + e.message; out.className = "dbg-result err";
      }
    });
  });
}

/* ---------------- 单节点调试 ---------------- */
async function runSingleNode(node) {
  const el = $("#node-" + node.id);
  const st = el ? $(".node-status", el) : null;
  if (st) { st.className = "node-status"; st.textContent = "⏳ 调试中…"; }
  setStatus(`调试节点 ${node.id} (${spec(node.type).title})…`);
  try {
    const r = await jpost("/api/run_node", { type: node.type, params: node.params });
    markNode(node.id, "passed", r.outputs);
    setStatus(`节点 ${node.id} 调试通过 ✓`, "ok");
  } catch (e) {
    markNode(node.id, "failed", null, e.message);
    setStatus(`节点 ${node.id} 调试失败 ✗`, "err");
  }
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
  el.classList.remove("st-pass", "st-fail", "st-skip");
  el.classList.add("st-" + (status === "passed" ? "pass" : status === "failed" ? "fail" : "skip"));
  const st = $(".node-status", el);
  if (st) {
    const tag = status === "passed" ? "✓" : status === "failed" ? "✗" : "–";
    let extra = "";
    if (outputs && Object.keys(outputs).length)
      extra = " " + Object.entries(outputs)
        .filter(([k]) => k !== "ok")
        .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ");
    st.className = "node-status st-" + (status === "passed" ? "pass" : status === "failed" ? "fail" : "skip");
    st.textContent = tag + " " + (error ? error.slice(0, 90) : extra.slice(0, 110));
  }
}
async function runCanvas() {
  await saveCanvas();
  clearStatusBadges();
  setStatus("运行中…");
  $("#btn-run").disabled = true;
  try {
    const report = await jpost("/api/run/" + encodeURIComponent(canvas.name),
                               { stop_on_fail: $("#chk-stopfail").checked });
    for (const n of report.nodes) markNode(n.id, n.status, n.outputs, n.error);
    showReport(report);
    setStatus(report.ok ? "运行完成: 全部通过 ✓" : "运行失败 ✗", report.ok ? "ok" : "err");
  } catch (e) {
    setStatus("运行出错: " + e.message, "err");
    alert("运行出错: " + e.message);
  } finally { $("#btn-run").disabled = false; }
}
function showReport(report) {
  $("#runlog").classList.remove("hidden");
  const sum = $("#runlog-summary");
  sum.textContent = report.ok ? " ✓ 全部通过" : " ✗ 存在失败";
  sum.className = report.ok ? "ok" : "err";
  $("#runlog-body").innerHTML = report.nodes.map((n) => `
    <div class="rl-node">
      <span class="st-${n.status}">${n.status === "passed" ? "✓" : n.status === "failed" ? "✗" : "–"}</span>
      <b>${esc(n.title)}</b><span style="color:var(--dim)">(${n.ms}ms)</span>
      ${n.error ? `<div class="rl-err">${esc(n.error)}</div>` : ""}
      ${n.outputs && Object.keys(n.outputs).filter((k) => k !== "ok").length
        ? `<div class="rl-outs">${Object.entries(n.outputs).filter(([k]) => k !== "ok")
            .map(([k, v]) => `${esc(k)}=${esc(typeof v === "object" ? JSON.stringify(v) : String(v))}`).join("  ")}</div>` : ""}
    </div>`).join("");
}

/* ---------------- 初始化 ---------------- */
async function loadPorts() {
  try { COM_PORTS = (await jfetch("/api/ports")).ports; } catch { COM_PORTS = []; }
}
async function init() {
  REG = (await jfetch("/api/nodes")).nodes;
  await loadPorts();
  renderPalette();

  const c = $("#canvas");
  const svg = $("#wires");
  c.appendChild(svg);
  svg.setAttribute("width", CANVAS_W); svg.setAttribute("height", CANVAS_H);

  initPanning();
  initContextMenu();

  $("#canvas-wrap").addEventListener("dragover", (e) => e.preventDefault());
  $("#canvas-wrap").addEventListener("drop", (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("text/newnode");
    if (!type) return;
    const wrap = $("#canvas-wrap");
    const x = e.clientX - wrap.getBoundingClientRect().left + wrap.scrollLeft - 86;
    const y = e.clientY - wrap.getBoundingClientRect().top + wrap.scrollTop - 14;
    addNodeAt(type, Math.max(0, x), Math.max(0, y));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Delete" && selected && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
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
  const names = $$("#canvas-list option").map((o) => o.textContent);
  const preferred = names.includes("demo_上电读版本出图") ? "demo_上电读版本出图" : names[0];
  $("#canvas-list").value = preferred;
  await loadCanvas(preferred);
}
init().catch((e) => { setStatus("初始化失败: " + e.message, "err"); console.error(e); });
