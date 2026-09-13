/* new_auto 拖拽式流程画布 (原生 JS + SVG, 无构建依赖)
 * v1.0.4: 无限画布(平移/缩放/居中) + 连线状态机(点击连接/拖线吸附/兼容高亮)
 *         + 四大模块分组 + 跨画布复制粘贴 */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let REG = [];              // 节点注册表
let canvas = null;         // 当前画布 {name, stop_on_fail, nodes, edges, view}
let selected = null;       // 选中节点 id
let COM_PORTS = [];        // 本机串口列表

/* 无限画布视图: 世界坐标 -> 屏幕 = pan + world*z */
const view = { x: 0, y: 0, z: 1 };
const ZOOM_MIN = 0.3, ZOOM_MAX = 2.5;

/* 连线状态机: null | {kind, dir:'out'|'in', node, port, moved, armed} */
let conn = null;
let clipboard = null;

const GROUP_ORDER = ["电源模块", "设备模块", "I²C 模块", "检查模块", "固件模块", "流程工具"];
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

/* ---------------- 视图 (平移/缩放/居中) ---------------- */
function applyView() {
  $("#world").style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.z})`;
  $("#zoom-val").textContent = Math.round(view.z * 100) + "%";
}
function toWorld(cx, cy) {
  const r = $("#canvas-wrap").getBoundingClientRect();
  return { x: (cx - r.left - view.x) / view.z, y: (cy - r.top - view.y) / view.z };
}
function zoomAt(cx, cy, factor) {
  const nz = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, view.z * factor));
  if (nz === view.z) return;
  const r = $("#canvas-wrap").getBoundingClientRect();
  const mx = cx - r.left, my = cy - r.top;
  view.x = mx - (mx - view.x) * (nz / view.z);
  view.y = my - (my - view.y) * (nz / view.z);
  view.z = nz;
  applyView();
}
function fitView() {
  const wrap = $("#canvas-wrap");
  if (!canvas?.nodes?.length) {
    view.x = wrap.clientWidth / 2 - 90; view.y = wrap.clientHeight / 2 - 40; view.z = 1;
    applyView(); return;
  }
  let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
  for (const n of canvas.nodes) {
    minX = Math.min(minX, n.x); minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x + nodeW(n)); maxY = Math.max(maxY, n.y + nodeH(n));
  }
  const pad = 70;
  const z = Math.min(ZOOM_MAX,
    Math.min((wrap.clientWidth - pad * 2) / Math.max(1, maxX - minX),
             (wrap.clientHeight - pad * 2) / Math.max(1, maxY - minY), 1.25));
  view.z = Math.max(ZOOM_MIN, z);
  view.x = wrap.clientWidth / 2 - ((minX + maxX) / 2) * view.z;
  view.y = wrap.clientHeight / 2 - ((minY + maxY) / 2) * view.z;
  applyView();
}

/* ---------------- 面板 ---------------- */
function visibleRegistry() { return REG.filter((n) => !n.hidden); }

function renderPalette() {
  const groups = {};
  visibleRegistry().forEach((n) => (groups[n.group] ||= []).push(n));
  const root = $("#palette-groups");
  root.innerHTML = "";
  const order = [...GROUP_ORDER, ...Object.keys(groups).filter((g) => !GROUP_ORDER.includes(g))];
  for (const g of order) {
    const items = groups[g];
    if (!items) continue;
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
      el.addEventListener("dblclick", () => {
        const wrap = $("#canvas-wrap");
        const p = toWorld(wrap.getBoundingClientRect().left + wrap.clientWidth / 2,
                          wrap.getBoundingClientRect().top + wrap.clientHeight / 2);
        addNodeAt(it.type, Math.round(p.x - 80), Math.round(p.y - 20));
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
function portPos(node, kind, name) {
  const s = spec(node.type);
  const list = kind === "out" ? Object.keys(s.outputs) : Object.keys(s.inputs);
  const i = list.indexOf(name), n = Math.max(list.length, 1);
  const y = node.y + 52 + ((i + 1) / (n + 1)) * Math.max(30, nodeH(node) - 66);
  return { x: kind === "out" ? node.x + nodeW(node) : node.x, y };
}
const flowPos = (node, kind) => ({
  x: kind === "out" ? node.x + nodeW(node) : node.x,
  y: node.y + 21,
});

/* 丝滑连线: 前向用横向贝塞尔, 后向(目标在左侧)按垂直距离外扩, 避免怪异小回环 */
function edgePath(x1, y1, x2, y2) {
  const dx = x2 - x1, dy = Math.abs(y2 - y1);
  let off;
  if (dx >= -20) {
    off = Math.max(36, Math.min(190, dx * 0.55 + dy * 0.08));
  } else {
    off = Math.max(60, Math.min(190, Math.abs(dx) * 0.18 + dy * 0.35 + 40));
  }
  return `M ${x1} ${y1} C ${x1 + off} ${y1}, ${x2 - off} ${y2}, ${x2} ${y2}`;
}

/* ---------------- 画布渲染 (世界坐标) ---------------- */
function renderAll() {
  const w = $("#world");
  [...w.querySelectorAll(".node")].forEach((n) => n.remove());
  canvas.nodes.forEach(renderNode);
  drawWires();
  if (selected) selectNode(selected, true);
  applyView();
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

  // 执行流端口 (标题栏两侧, 金色方块): 左=接上游, 右=接下游
  const fin = mkPort(el, "flow-in", "", "执行流入 —— 上游节点连这里");
  fin.style.left = "-7px"; fin.style.top = "15px";
  fin.dataset.node = node.id; fin.dataset.flow = "in";
  const fout = mkPort(el, "flow-out", "", "执行流出 —— 连到下游节点");
  fout.style.right = "-7px"; fout.style.top = "15px";
  fout.dataset.node = node.id; fout.dataset.flow = "out";
  fin.addEventListener("mousedown", (e) => startConn(e, "in"));
  fout.addEventListener("mousedown", (e) => startConn(e, "out"));

  // 数据端口 (两侧蓝色圆点)
  Object.keys(s.outputs).forEach((port, i, arr) => {
    const p = mkPort(el, "port out", s.outputs[port]);
    p.dataset.node = node.id; p.dataset.port = port; p.dataset.dir = "out";
    p.style.top = (52 + ((i + 1) / (arr.length + 1)) * Math.max(30, nodeH(node) - 66)) + "px";
    p.addEventListener("mousedown", (e) => startConn(e, "out"));
  });
  Object.keys(s.inputs).forEach((param, i, arr) => {
    const p = mkPort(el, "port in", s.inputs[param]);
    p.dataset.node = node.id; p.dataset.port = param; p.dataset.dir = "in";
    p.style.top = (52 + ((i + 1) / (arr.length + 1)) * Math.max(30, nodeH(node) - 66)) + "px";
    p.addEventListener("mousedown", (e) => startConn(e, "in"));
  });

  $(".node-head", el).addEventListener("mousedown", (e) => startMove(e, node, el));
  el.addEventListener("mousedown", () => selectNode(node.id));
  $("#world").appendChild(el);
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
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", edgePath(x1, y1, x2, y2));
    if (kind === "flow") {
      p.setAttribute("stroke", "#e8b339"); p.setAttribute("stroke-width", 3);
      p.setAttribute("marker-end", "url(#arrow-flow)");
    } else {
      p.setAttribute("stroke", "#4a89dc"); p.setAttribute("stroke-width", 2);
    }
    p.setAttribute("fill", "none"); p.classList.add("edge");
    if (edge) {
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

/* ---------------- 连线状态机 ---------------- */
function connElems(kind, dir) {
  // 兼容端口元素: kind=flow -> 对侧 flow 端口; data -> 对侧数据端口
  if (kind === "flow") return $$(`.flow-${dir === "out" ? "in" : "out"}`);
  return $$(`.port.${dir === "out" ? "in" : "out"}`);
}
function portCenter(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}
function clearConnFx() {
  $$(".port.pulse, .flow-in.pulse, .flow-out.pulse").forEach((p) => p.classList.remove("pulse", "snap"));
}
function startConn(e, dir) {
  e.preventDefault(); e.stopPropagation();
  const port = e.currentTarget;
  const isFlow = port.classList.contains("flow-in") || port.classList.contains("flow-out");
  const kind = isFlow ? "flow" : "data";
  // 若已有武装(armed)连线且此端口兼容 -> 直接完成"点两下"连线
  if (conn?.armed) {
    const okKind = conn.kind === kind;
    const okDir = (conn.dir === "out" && dir === "in") || (conn.dir === "in" && dir === "out");
    if (okKind && okDir && port.dataset.node !== conn.node) {
      completeConn(port);
      return;
    }
    if (!okKind || !okDir) setStatus("端口类型不匹配: 金色执行流连金色, 蓝色数据连蓝色", "err");
    cancelConn();
    if (conn === null && false) return;
  }
  conn = { kind, dir, node: port.dataset.node,
           port: isFlow ? (dir === "out" ? FLOW_OUT : FLOW_IN) : port.dataset.port,
           moved: false, armed: false, sx: e.clientX, sy: e.clientY,
           srcEl: port };
  // 兼容端口呼吸提示
  clearConnFx();
  connElems(kind, dir).forEach((p) => {
    if (p.dataset.node !== port.dataset.node) p.classList.add("pulse");
  });
  setStatus(dir === "out"
    ? "拖到目标端口松手, 或再点一下目标端口完成连线 (Esc 取消)"
    : "反向连线: 拖到上游输出端口, 或点一下上游端口 (Esc 取消)");
  attachConnDrag();
}

function attachConnDrag() {
  const mv = (ev) => {
    if (!conn) return;
    if (Math.hypot(ev.clientX - conn.sx, ev.clientY - conn.sy) > 4) conn.moved = true;
    const a = nodeById(conn.node);
    let p1;
    if (conn.kind === "flow") p1 = flowPos(a, conn.dir === "out" ? "out" : "in");
    else p1 = portPos(a, conn.dir, conn.port);
    const m = toWorld(ev.clientX, ev.clientY);
    // 拖动方向: 从入端口反向拉时, 线仍画 出->入
    const [x1, y1, x2, y2] = conn.dir === "out" ? [p1.x, p1.y, m.x, m.y] : [m.x, m.y, p1.x, p1.y];
    drawWires({ x1, y1, x2, y2, kind: conn.kind });
    // 吸附: 高亮最近的兼容端口
    $$(".port.snap, .flow-in.snap, .flow-out.snap").forEach((p) => p.classList.remove("snap"));
    let best = null, bestD = 48;
    for (const el of connElems(conn.kind, conn.dir)) {
      if (el.dataset.node === conn.node) continue;
      const c = portCenter(el);
      const d = Math.hypot(c.x - ev.clientX, c.y - ev.clientY);
      if (d < bestD) { bestD = d; best = el; }
    }
    if (best) best.classList.add("snap");
    conn.hoverEl = best;
  };
  const up = (ev) => {
    document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    if (!conn) return;
    const target = conn.hoverEl;
    if (target) { completeConn(target); return; }
    if (!conn.moved) {
      // 原地松手 = 点两下模式的第一下: 保持武装, 等待点击目标端口
      conn.armed = true;
      setStatus("已选起点 —— 现在点击目标端口完成连线 (Esc 取消)");
      return;
    }
    cancelConn();
  };
  document.addEventListener("mousemove", mv);
  document.addEventListener("mouseup", up);
}

function completeConn(targetEl) {
  const isFlowT = targetEl.classList.contains("flow-in") || targetEl.classList.contains("flow-out");
  const tNode = targetEl.dataset.node;
  let edge = null;
  if (conn.kind === "flow" && isFlowT && conn.dir === "out") {
    edge = { from: conn.node, fromPort: FLOW_OUT, to: tNode, toParam: FLOW_IN, kind: "flow" };
  } else if (conn.kind === "flow" && isFlowT && conn.dir === "in") {
    edge = { from: tNode, fromPort: FLOW_OUT, to: conn.node, toParam: FLOW_IN, kind: "flow" };
  } else if (conn.kind === "data" && !isFlowT && conn.dir === "out") {
    edge = { from: conn.node, fromPort: conn.port, to: tNode, toParam: targetEl.dataset.port, kind: "data" };
  } else if (conn.kind === "data" && !isFlowT && conn.dir === "in") {
    edge = { from: tNode, fromPort: targetEl.dataset.port, to: conn.node, toParam: conn.port, kind: "data" };
  }
  cancelConn();
  if (!edge) { setStatus("连线失败: 端口类型不匹配 (金连金, 蓝连蓝)", "err"); return; }
  if (edge.from === edge.to) { setStatus("不能连接到节点自身", "err"); return; }
  // 同类同参只保留一条
  canvas.edges = canvas.edges.filter((x) =>
    !((x.kind || "data") === edge.kind && x.to === edge.to && x.toParam === edge.toParam
      && x.from === edge.from && x.fromPort === edge.fromPort));
  canvas.edges.push(edge);
  drawWires();
  setStatus(edge.kind === "flow"
    ? `执行流: ${edge.from} → ${edge.to}`
    : `数据: ${edge.from}.${edge.fromPort} → ${edge.to}.${edge.toParam}`, "ok");
}

function cancelConn() {
  conn = null;
  clearConnFx();
  drawWires();
  setStatus("");
}

/* ---------------- 交互: 移动节点 / 平移 / 缩放 ---------------- */
function startMove(e, node, el) {
  e.preventDefault(); e.stopPropagation();
  selectNode(node.id);
  const sx = e.clientX, sy = e.clientY, ox = node.x, oy = node.y;
  const mv = (ev) => {
    node.x = ox + (ev.clientX - sx) / view.z;
    node.y = oy + (ev.clientY - sy) / view.z;
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

/* ---------------- 右键菜单 ---------------- */
function hideMenu() { $("#ctx-menu")?.remove(); }
function showMenu(screenX, screenY, worldX, worldY) {
  hideMenu();
  const menu = document.createElement("div");
  menu.id = "ctx-menu";
  let html = `<div class="ctx-title">添加节点</div>`;
  const groups = {};
  visibleRegistry().forEach((n) => (groups[n.group] ||= []).push(n));
  const order = [...GROUP_ORDER, ...Object.keys(groups).filter((g) => !GROUP_ORDER.includes(g))];
  for (const g of order) {
    const items = groups[g];
    if (!items) continue;
    html += `<div class="ctx-group">${esc(g)}</div>`;
    for (const it of items)
      html += `<div class="ctx-item" data-type="${esc(it.type)}">${esc(it.title)}</div>`;
  }
  menu.innerHTML = html;
  menu.addEventListener("click", (e) => {
    const type = e.target.dataset?.type;
    if (!type) return;
    addNodeAt(type, Math.round(worldX), Math.round(worldY));
    hideMenu();
  });
  document.body.appendChild(menu);
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(screenX, innerWidth - r.width - 8) + "px";
  menu.style.top = Math.min(screenY, innerHeight - r.height - 8) + "px";
}
function initCanvasEvents() {
  const wrap = $("#canvas-wrap");

  // 平移: 空白左键拖动 / 任意位置中键拖动
  wrap.addEventListener("mousedown", (e) => {
    const onBg = e.target.id === "canvas-wrap" || e.target.id === "world"
      || e.target.id === "wires" || e.target.tagName === "svg" || e.target.tagName === "defs";
    if (!(e.button === 1 || (e.button === 0 && onBg))) return;
    if (e.button === 0) selectNode(null);
    hideMenu();
    if (conn?.armed) cancelConn();
    const sx = e.clientX, sy = e.clientY, ox = view.x, oy = view.y;
    wrap.classList.add("panning");
    const mv = (ev) => {
      view.x = ox + (ev.clientX - sx);
      view.y = oy + (ev.clientY - sy);
      applyView();
    };
    const up = () => {
      wrap.classList.remove("panning");
      document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", mv);
    document.addEventListener("mouseup", up);
  });

  // 缩放: 滚轮以鼠标为中心
  wrap.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });

  // 右键新建
  wrap.addEventListener("contextmenu", (e) => {
    if (e.target.closest(".node") || e.target.closest(".port")
        || e.target.closest(".flow-in") || e.target.closest(".flow-out")) return;
    e.preventDefault();
    const p = toWorld(e.clientX, e.clientY);
    showMenu(e.clientX, e.clientY, p.x - 86, p.y - 16);
  });
  document.addEventListener("mousedown", (e) => {
    if (!e.target.closest("#ctx-menu")) hideMenu();
  });

  // 拖放添加
  wrap.addEventListener("dragover", (e) => e.preventDefault());
  wrap.addEventListener("drop", (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("text/newnode");
    if (!type) return;
    const p = toWorld(e.clientX, e.clientY);
    addNodeAt(type, Math.round(p.x - 86), Math.round(p.y - 14));
  });

  // 缩放按钮
  $("#zoom-in").addEventListener("click", () => {
    const r = wrap.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1.2);
  });
  $("#zoom-out").addEventListener("click", () => {
    const r = wrap.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1 / 1.2);
  });
  $("#zoom-fit").addEventListener("click", fitView);

  // Esc 取消连线
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && conn) cancelConn();
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

/* ---------------- 复制 / 粘贴 ---------------- */
function initClipboard() {
  document.addEventListener("keydown", (e) => {
    const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
    if (typing || !canvas) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c" && selected) {
      const n = nodeById(selected);
      clipboard = JSON.parse(JSON.stringify(n));
      setStatus(`已复制节点 ${n.id} (${spec(n.type).title}), 切换画布后 Ctrl+V 粘贴`, "ok");
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v" && clipboard) {
      const wrap = $("#canvas-wrap");
      const p = toWorld(wrap.getBoundingClientRect().left + wrap.clientWidth / 2,
                        wrap.getBoundingClientRect().top + wrap.clientHeight / 2);
      const node = JSON.parse(JSON.stringify(clipboard));
      node.id = uid();
      node.x = Math.round(p.x - nodeW(node) / 2);
      node.y = Math.round(p.y - 30);
      canvas.nodes.push(node);
      renderAll(); selectNode(node.id);
      setStatus(`已粘贴为 ${node.id}`, "ok");
    } else if (e.key === "Delete" && selected
               && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      canvas.nodes = canvas.nodes.filter((n) => n.id !== selected);
      canvas.edges = canvas.edges.filter((e2) => e2.from !== selected && e2.to !== selected);
      selected = null; renderAll(); renderInspector();
      setStatus("已删除节点");
    }
  });
}

/* ---------------- 属性面板 ---------------- */
async function renderInspector() {
  const body = $("#ins-body");
  const node = nodeById(selected);
  if (!node) {
    body.className = "ins-empty";
    body.innerHTML = "添加节点: 面板拖入 / 空白处右键<br><br>"
      + "<b>连线</b>: 点一下起点端口 → 再点一下目标端口<br>"
      + "(或按住端口拖线, 会自动吸附)<br>"
      + "金色方块 = 执行流(上下游)<br>蓝色圆点 = 数据传值<br><br>"
      + "空白拖动=平移 · 滚轮=缩放 · Delete=删除";
    return;
  }
  const s = spec(node.type);
  body.className = "";
  let html = `<div class="ins-node-type">${esc(node.type)}</div>`;
  for (const p of s.params) {
    const v = node.params[p.name] !== undefined ? node.params[p.name] : (p.default ?? "");
    if (p.type === "port") {
      const opts = `<option value="">默认 (config)</option>` +
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
    } else if (p.type === "textarea") {
      html += `<div class="field"><label>${esc(p.label)}</label>` +
        `<textarea data-param="${esc(p.name)}" rows="6" style="width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:6px 8px;font:11.5px/1.6 Consolas,monospace;resize:vertical">${esc(v)}</textarea></div>`;
    } else {
      html += `<div class="field"><label>${esc(p.label)}${p.hex ? " (十六进制)" : ""}</label>` +
        `<input type="text" data-param="${esc(p.name)}" value="${esc(v)}"></div>`;
    }
  }
  if (!s.params.length) html += `<div class="field"><label>该节点无参数</label></div>`;

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
  const st = $(".node-status", $("#node-" + node.id));
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
  if (canvas.view && typeof canvas.view.z === "number") {
    Object.assign(view, canvas.view);
    applyView();
  } else {
    fitView();          // 新画布: 内容自动居中
  }
  setStatus(`已加载画布: ${name} (空白拖动平移, 滚轮缩放)`, "ok");
}
async function saveCanvas() {
  canvas.stop_on_fail = $("#chk-stopfail").checked;
  canvas.view = { x: Math.round(view.x), y: Math.round(view.y), z: +view.z.toFixed(3) };
  await jput("/api/canvases/" + encodeURIComponent(canvas.name), canvas);
  await refreshCanvasList(canvas.name);
  setStatus(`画布已保存: ${canvas.name}`, "ok");
}

/* ---------------- 运行与报告 ---------------- */
function markNode(id, status, outputs, error) {
  const el = $("#node-" + id);
  if (!el) return;
  el.classList.remove("st-pass", "st-fail", "st-skip", "st-run");
  const cls = status === "passed" ? "pass" : status === "failed" ? "fail"
            : status === "running" ? "run" : "skip";
  el.classList.add("st-" + cls);
  const st = $(".node-status", el);
  if (st) {
    const tag = status === "passed" ? "✓" : status === "failed" ? "✗"
              : status === "running" ? "⏳" : "–";
    let extra = "";
    if (outputs && Object.keys(outputs).length)
      extra = " " + Object.entries(outputs)
        .filter(([k]) => k !== "ok")
        .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ");
    st.className = "node-status st-" + cls;
    st.textContent = tag + " " + (error ? error.slice(0, 90) : extra.slice(0, 110));
  }
}
function clearStatusBadges() {
  $$(".node").forEach((n) => {
    n.classList.remove("st-pass", "st-fail", "st-skip", "st-run");
    const st = $(".node-status", n);
    if (st) { st.textContent = ""; st.className = "node-status"; }
  });
}

/* ---------------- 运行监控坞 ---------------- */
let pollTimer = null, seenLogs = 0;

function dockOpen() { $("#rundock").classList.remove("collapsed"); }
function dockSetDot(cls, info) {
  $("#dock-dot").className = cls;
  $("#dock-info").textContent = info || "";
}
function dockLog(t, cls, text) {
  const body = $("#dock-body");
  const line = document.createElement("div");
  line.className = "dl " + (cls || "");
  line.innerHTML = `<span class="t">[${esc(t)}]</span>${esc(text)}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}
function dockClear() { $("#dock-body").innerHTML = ""; seenLogs = 0; }

async function runCanvas() {
  await saveCanvas();
  clearStatusBadges();
  dockClear();
  dockOpen();
  dockSetDot("running", "启动中…");
  $("#btn-run").disabled = true;
  try {
    const { run_id } = await jpost("/api/run/" + encodeURIComponent(canvas.name),
                                   { stop_on_fail: $("#chk-stopfail").checked });
    setStatus("运行中… (下方监控窗口实时查看)");
    dockSetDot("running", "运行中…");
    await pollRun(run_id);
  } catch (e) {
    dockSetDot("fail", "启动失败");
    dockLog(timeStr(), "fail", "启动失败: " + e.message);
    setStatus("运行出错: " + e.message, "err");
  } finally { $("#btn-run").disabled = false; }
}
const timeStr = () => new Date().toTimeString().slice(0, 8);

async function pollRun(runId) {
  return new Promise((resolve) => {
    pollTimer = setInterval(async () => {
      try {
        const r = await jfetch("/api/runs/" + runId);
        const rep = r.report;
        // 实时日志 (增量)
        for (; seenLogs < rep.log.length; seenLogs++) {
          const l = rep.log[seenLogs];
          dockLog(l.t, l.cls, l.text);
        }
        // 节点状态徽章
        for (const n of rep.nodes) markNode(n.id, n.status, n.outputs, n.error);
        if (r.current) markNode(r.current, "running");
        const done = rep.nodes.filter((n) => n.status !== "skipped").length;
        dockSetDot("running", `运行中… ${done}/${rep.nodes.length || "?"} 节点`);
        if (r.status !== "running") {
          clearInterval(pollTimer); pollTimer = null;
          dockSetDot(rep.ok ? "pass" : "fail",
            `运行${rep.ok ? "完成: 全部通过 ✓" : "失败 ✗"} (开始于 ${rep.started})`);
          setStatus(rep.ok ? "运行完成: 全部通过 ✓" : "运行失败 ✗", rep.ok ? "ok" : "err");
          resolve(rep);
        }
      } catch (e) {
        clearInterval(pollTimer); pollTimer = null;
        dockSetDot("fail", "轮询失败");
        resolve(null);
      }
    }, 500);
  });
}

/* ---------------- 右侧面板 Tabs ---------------- */
function initTabs() {
  $$("#ins-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("#ins-tabs .tab").forEach((b) => b.classList.toggle("active", b === btn));
      $("#tab-props").classList.toggle("hidden", btn.dataset.tab !== "props");
      $("#tab-ai").classList.toggle("hidden", btn.dataset.tab !== "ai");
      if (btn.dataset.tab === "ai") initAiPanel();
    });
  });
}

/* ---------------- AI 助手 ---------------- */
let aiMessages = [];   // {role, content}
let aiReady = false;

async function initAiPanel() {
  if (aiReady) return;
  aiReady = true;
  try {
    const m = await jfetch("/api/agent/models");
    $("#ai-model").innerHTML = (m.models || []).map(
      (x) => `<option ${x === m.model ? "selected" : ""}>${esc(x)}</option>`).join("");
  } catch { /* 模型列表拉取失败不阻塞 */ }
  $("#ai-send").addEventListener("click", aiSend);
  $("#ai-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) aiSend();
  });
}

function aiBubble(role, text) {
  const div = document.createElement("div");
  div.className = "ai-msg ai-" + (role === "user" ? "user" : "bot");
  div.textContent = text;
  const hist = $("#ai-history");
  hist.appendChild(div);
  hist.scrollTop = hist.scrollHeight;
  return div;
}

async function aiSend() {
  const input = $("#ai-input");
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = "";
  aiBubble("user", prompt);
  aiMessages.push({ role: "user", content: prompt });
  const thinking = aiBubble("bot", "思考中…");
  $("#ai-send").disabled = true;
  try {
    const r = await jpost("/api/agent", { prompt, model: $("#ai-model").value,
                                          history: aiMessages.slice(0, -1) });
    if (r.canvas && r.canvas.nodes?.length) {
      const titles = r.canvas.nodes.map((n) => {
        const s = spec(n.type);
        return `${n.id} ${s ? s.title : n.type}`;
      }).join(" → ");
      thinking.textContent = `已生成画布「${r.canvas.name || "未命名"}」\n流程: ${titles}`;
    } else {
      thinking.textContent = r.reply || "(空回复)";
    }
    aiMessages.push({ role: "assistant", content: r.reply || "" });
    if (r.canvas && r.canvas.nodes?.length) {
      const apply = document.createElement("button");
      apply.className = "ai-apply";
      apply.textContent = `✔ 应用到画布 (${r.canvas.nodes.length} 节点 / ${r.canvas.edges.length} 连线)`
        + (r.canvas.name ? ` : ${r.canvas.name}` : "");
      apply.addEventListener("click", async () => {
        if (!confirm(`用 AI 生成的画布替换当前画布「${canvas.name}」的内容?`)) return;
        const keepName = canvas.name;
        canvas = { ...r.canvas, name: keepName, stop_on_fail: true };
        await saveCanvas();
        renderAll(); fitView(); renderInspector();
        setStatus(`已应用 AI 生成的画布 (${canvas.nodes.length} 节点)`, "ok");
        apply.disabled = true; apply.textContent = "已应用 ✓";
      });
      thinking.after(apply);
    }
  } catch (e) {
    thinking.textContent = "出错: " + e.message;
    thinking.className = "ai-msg ai-bot ai-err";
  } finally { $("#ai-send").disabled = false; }
}

/* ---------------- 图片库 ---------------- */
async function openGallery() {
  $("#gallery-overlay").classList.remove("hidden");
  await refreshGallery();
}
async function refreshGallery() {
  try {
    const r = await jfetch("/api/img");
    $("#gallery-dir").textContent = r.dir;
    const grid = $("#gallery-grid");
    if (!r.files.length) {
      grid.innerHTML = `<div style="color:var(--dim);padding:20px">还没有抓帧图片 —— 运行带「抓帧存图」的画布后这里会显示</div>`;
      return;
    }
    grid.innerHTML = r.files.map((f) => `
      <div class="gal-item" data-name="${esc(f.name)}">
        <img loading="lazy" src="/api/img/thumb?name=${encodeURIComponent(f.name)}">
        <div class="gal-name" title="${esc(f.name)}">${esc(f.name)}</div>
      </div>`).join("");
    $$(".gal-item", grid).forEach((el) => {
      el.addEventListener("click", () => {
        $("#gallery-big").src = "/api/img/thumb?name=" + encodeURIComponent(el.dataset.name);
        $("#gallery-caption").textContent = el.dataset.name;
        $("#gallery-viewer").classList.remove("hidden");
      });
    });
  } catch (e) {
    $("#gallery-grid").innerHTML = `<div style="color:var(--err);padding:20px">${esc(e.message)}</div>`;
  }
}
function initGallery() {
  $("#btn-gallery").addEventListener("click", openGallery);
  $("#gallery-refresh").addEventListener("click", refreshGallery);
  $("#gallery-overlay").addEventListener("click", (e) => {
    if (e.target.id === "gallery-overlay") $("#gallery-overlay").classList.add("hidden");
  });
  $("#gallery-viewer").addEventListener("click", () => $("#gallery-viewer").classList.add("hidden"));
}

/* ---------------- 初始化 ---------------- */
async function loadPorts() {
  try { COM_PORTS = (await jfetch("/api/ports")).ports; } catch { COM_PORTS = []; }
}
async function init() {
  REG = (await jfetch("/api/nodes")).nodes;
  await loadPorts();
  renderPalette();

  initCanvasEvents();
  initClipboard();
  initTabs();
  initGallery();

  $("#canvas-list").addEventListener("change", () => loadCanvas($("#canvas-list").value));
  $("#btn-new").addEventListener("click", async () => {
    const name = prompt("新画布名称 (即 case 名):");
    if (!name) return;
    canvas = { name, stop_on_fail: true,
               nodes: [{ id: "n1", type: "relay.on", x: 0, y: 0, params: { channel: 0 } }],
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
  $("#btn-help").addEventListener("click", () => $("#help-overlay").classList.remove("hidden"));
  $("#dock-toggle").addEventListener("click", () => $("#rundock").classList.toggle("collapsed"));
  $("#dock-head").addEventListener("dblclick", () => $("#rundock").classList.toggle("collapsed"));
  $("#dock-clear").addEventListener("click", dockClear);

  await refreshCanvasList();
  const names = $$("#canvas-list option").map((o) => o.textContent);
  const preferred = names.includes("demo_上电读版本出图") ? "demo_上电读版本出图" : names[0];
  $("#canvas-list").value = preferred;
  await loadCanvas(preferred);
}
init().catch((e) => { setStatus("初始化失败: " + e.message, "err"); console.error(e); });
