/* new_auto 拖拽式流程画布 (原生 JS + SVG, 无构建依赖)
 * v1.0.4: 无限画布(平移/缩放/居中) + 连线状态机(点击连接/拖线吸附/兼容高亮)
 *         + 四大模块分组 + 跨画布复制粘贴 */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let REG = [];              // 节点注册表
let canvas = null;         // 当前画布 {name, stop_on_fail, nodes, edges, view}
let selected = null;       // 选中节点 id
let selEdge = null;        // 选中的连线 (选中后 Delete 才删, 防误删)
let COM_PORTS = [];        // 本机串口列表
let PRESETS = [];          // I²C 常用寄存器预设
let dirty = false;         // 有未保存修改
let autoSaveTimer = null;

/* 撤销栈: 存整张画布的快照(字符串), 简单可靠 */
const HIST = [], FUTURE = [];
let _prevSnap = null;

function snapshot() {
  return JSON.stringify({ nodes: canvas.nodes, edges: canvas.edges });
}
function beginEdit() { if (canvas) _prevSnap = snapshot(); }
function commitEdit() {
  if (!canvas || _prevSnap === null) return;
  const now = snapshot();
  if (now !== _prevSnap) {
    HIST.push(_prevSnap);
    if (HIST.length > 100) HIST.shift();
    FUTURE.length = 0;
    markDirty(true);
    scheduleAutoSave();
  }
  _prevSnap = null;
}
function markDirty(v) {
  dirty = v;
  $("#dirty-dot")?.classList.toggle("hidden", !v);
}
function restore(snap) {
  const s = JSON.parse(snap);
  canvas.nodes = s.nodes; canvas.edges = s.edges;
  if (!nodeById(selected)) selected = null;
  selEdge = null;
  renderAll(); renderInspector();
  markDirty(true); scheduleAutoSave();
}
function undo() {
  if (!HIST.length) { setStatus("没有可撤销的操作"); return; }
  FUTURE.push(snapshot());
  restore(HIST.pop());
  setStatus("已撤销");
}
function redo() {
  if (!FUTURE.length) { setStatus("没有可重做的操作"); return; }
  HIST.push(snapshot());
  restore(FUTURE.pop());
  setStatus("已重做");
}
function scheduleAutoSave() {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(async () => {
    try { await saveCanvas(true); } catch { /* 自动保存失败不打断编辑 */ }
  }, 1500);
}

/* 无限画布视图: 世界坐标 -> 屏幕 = pan + world*z */
const view = { x: 0, y: 0, z: 1 };
const ZOOM_MIN = 0.3, ZOOM_MAX = 2.5;

/* 连线状态机: null | {kind, dir:'out'|'in', node, port, moved, armed} */
let conn = null;
let clipboard = null;

const GROUP_ORDER = ["常用节点", "高级节点"];
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
  const rows = Math.min(Array.isArray(node.params?.ops) ? node.params.ops.length : 0, 8);
  return 56 + n * 17 + rows * 13 + (s.debug?.length ? 8 : 0);
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

  // 数据端口已移除 (蓝色连线取消): 断言写在节点内部
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
      // 旧画布残留的数据连线: 画得很淡, 表示已废弃但仍保留
      p.setAttribute("stroke", "#4a89dc"); p.setAttribute("stroke-width", 1.5);
      p.setAttribute("stroke-dasharray", "4 4"); p.setAttribute("opacity", "0.35");
    }
    p.setAttribute("fill", "none"); p.classList.add("edge");
    if (edge) {
      if (edge === selEdge) p.classList.add("sel-edge");
      // 单击选中, Delete 才删 —— 不再点一下就没了
      p.addEventListener("click", (e) => {
        e.stopPropagation();
        selEdge = selEdge === edge ? null : edge;
        selected = null;
        $$(".node").forEach((n) => n.classList.remove("sel"));
        drawWires();
        setStatus(selEdge ? "已选中连线, 按 Delete 删除 (Esc 取消选中)" : "");
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
  if (kind === "data") {
    setStatus("数据连线已移除 —— 断言写在节点内部 (如 I²C 行的『期待值』)", "err");
    return;
  }
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
  beginEdit();
  drawWires();
  commitEdit();
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
  beginEdit();
  const mv = (ev) => {
    node.x = ox + (ev.clientX - sx) / view.z;
    node.y = oy + (ev.clientY - sy) / view.z;
    el.style.left = node.x + "px"; el.style.top = node.y + "px";
    drawWires();
  };
  const up = () => {
    document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
    commitEdit();
  };
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
/* 通用右键菜单: items = [{key,label,group?,disabled?,onClick()}] */
function popupMenu(items, x, y) {
  hideMenu();
  const menu = document.createElement("div");
  menu.id = "ctx-menu";
  let html = "", lastGroup = null;
  for (const it of items) {
    if (it.group && it.group !== lastGroup) {
      html += `<div class="ctx-group">${esc(it.group)}</div>`; lastGroup = it.group;
    }
    html += `<div class="ctx-item${it.disabled ? " disabled" : ""}" data-act="${esc(it.key)}">`
      + `${esc(it.label)}</div>`;
  }
  menu.innerHTML = html;
  menu.addEventListener("click", (e) => {
    const key = e.target.dataset?.act;
    if (!key) return;
    const it = items.find((i) => i.key === key);
    if (it && !it.disabled) it.onClick();
    hideMenu();
  });
  document.body.appendChild(menu);
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, innerWidth - r.width - 8) + "px";
  menu.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
}

function showMenu(screenX, screenY, worldX, worldY) {
  const items = [];
  visibleRegistry().forEach((n) => items.push({
    key: n.type, label: n.title, group: n.group,
    onClick: () => addNodeAt(n.type, Math.round(worldX), Math.round(worldY)),
  }));
  popupMenu(items, screenX, screenY);
}
function initCanvasEvents() {
  const wrap = $("#canvas-wrap");

  // 平移: 空白左键拖动 / 任意位置中键拖动
  wrap.addEventListener("mousedown", (e) => {
    const onBg = e.target.id === "canvas-wrap" || e.target.id === "world"
      || e.target.id === "wires" || e.target.tagName === "svg" || e.target.tagName === "defs";
    if (!(e.button === 1 || (e.button === 0 && onBg))) return;
    if (e.button === 0) { selectNode(null); if (selEdge) { selEdge = null; drawWires(); } }
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

  // Esc: 取消连线 / 取消选中
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (conn) cancelConn();
    if (selEdge) { selEdge = null; drawWires(); setStatus(""); }
  });
}

function addNodeAt(type, x, y) {
  const s = spec(type);
  const params = {};
  beginEdit();
  s.params.forEach((p) => {
    if (p.default !== null && p.default !== undefined)
      params[p.name] = JSON.parse(JSON.stringify(p.default));   // 列表参数要深拷贝
  });
  const node = { id: uid(), type, x, y, params };
  canvas.nodes.push(node);
  renderAll(); selectNode(node.id);
  commitEdit();
  setStatus(`已添加节点: ${s.title} (${node.id})`);
}

/* ---------------- 右键菜单 (画布空白处) ---------------- */

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
    } else if (e.key === "Delete" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      if (selEdge) {
        beginEdit();
        canvas.edges = canvas.edges.filter((e2) => e2 !== selEdge);
        selEdge = null; drawWires(); commitEdit();
        setStatus("已删除连线 (Ctrl+Z 可撤销)");
      } else if (selected) {
        beginEdit();
        canvas.nodes = canvas.nodes.filter((n) => n.id !== selected);
        canvas.edges = canvas.edges.filter((e2) => e2.from !== selected && e2.to !== selected);
        selected = null; renderAll(); renderInspector(); commitEdit();
        setStatus("已删除节点 (Ctrl+Z 可撤销)");
      }
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
      e.preventDefault(); undo();
    } else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y"
               || (e.shiftKey && e.key.toLowerCase() === "z"))) {
      e.preventDefault(); redo();
    }
  });
}

/* ---------------- 列表参数编辑器 (I²C 表格 / Device 操作列表) ----------------

   两个编辑器共用一套紧凑行: 行内字段是 <label class="fx"><span>地址</span><input></label>,
   面板窄时整体换行、每行仍自带字段名 —— 不会再出现"下拉框独占一整行、字段各自
   撑成上百像素高的空行"。排序只有左侧抓手可拖, 拖动时在被跨过的行上画高亮线。
--------------------------------------------------------------------------- */

const I2C_MODES = ["A1D1", "A1D2", "A1D4", "A2D1", "A2D2", "A2D4", "A4D1", "A4D2", "A4D4"];
// 每条指令自带完整类型; 与 registry 里 i2c.seq 的 op 一一对应
const I2C_OPS = [
  ["read", "读"],
  ["read_verify", "读并校验"],
  ["write", "写"],
  ["write_verify", "写并回读校验"],
];
const DEFAULT_MODE = "A2D4";
let PROJ_DEFAULT_MODE = null;      // 项目配置里的"新行默认位宽模式"

function getOps(node, name) {
  if (!Array.isArray(node.params[name])) node.params[name] = [];
  return node.params[name];
}

/* 行内输入改动: 标脏 + 1.5s 自动落盘 (列表行的编辑不经过 renderInspector 的 change 委托) */
function touchRow() { markDirty(true); scheduleAutoSave(); }

function newI2CRow(op) {
  return { op: op || "read", addr: "0x0000", mode: PROJ_DEFAULT_MODE || DEFAULT_MODE,
           value: "", expect: "", mask: "0xFFFFFFFF", shift: "0", slave: "" };
}

/* 微元素构造 */
function mkel(cls, txt, tip) {
  const d = document.createElement("div");
  d.className = cls;
  if (txt !== undefined && txt !== null) d.textContent = txt;
  if (tip) d.title = tip;
  return d;
}
function gripEl() {
  return mkel("grip", "⠿", "按住上下拖拽调整执行顺序 (只有这里能拖)");
}
function idxEl(i) { return mkel("idx", String(i + 1)); }

/* 带字段名的小输入组: 换行后依然看得懂每格是什么 */
function fx(label, input, cls) {
  const l = document.createElement("label");
  l.className = "fx" + (cls ? " " + cls : "");
  const s = document.createElement("span");
  s.textContent = label;
  l.append(s, input);
  return l;
}

/* 指针拖拽排序: 抓手按下 -> 跟随鼠标 -> 松开落位 (避免 HTML5 DnD 的整行幽灵图)
   注意: 事件只绑一次 —— 否则每次 rerender 都会叠一层 mousedown, 表现为"拖拽不灵/乱跳" */
function makeSortable(host, onMove) {
  host._sortCb = onMove;
  if (host._sortBound) return;
  host._sortBound = true;
  host.addEventListener("mousedown", (e) => {
    const grip = e.target.closest && e.target.closest(".grip");
    if (!grip || !host.contains(grip)) return;
    const row = grip.closest(".ops-row");
    if (!row || row.classList.contains("ops-head")) return;
    e.preventDefault();
    e.stopPropagation();
    const rows = [...host.querySelectorAll(".ops-row:not(.ops-head)")];
    const from = rows.indexOf(row);
    if (from < 0) return;
    let drop = from;
    row.classList.add("dragging");
    document.body.classList.add("sorting");
    const clear = () => rows.forEach((r) => r.classList.remove("drop-before", "drop-after"));
    const onMoveEv = (ev) => {
      const el = document.elementFromPoint(ev.clientX, ev.clientY);
      const over = el && el.closest ? el.closest(".ops-row") : null;
      clear();
      if (!over || !host.contains(over) || over.classList.contains("ops-head")) return;
      const r = over.getBoundingClientRect();
      const after = ev.clientY > r.top + r.height / 2;
      over.classList.add(after ? "drop-after" : "drop-before");
      const i = rows.indexOf(over);
      drop = (after ? i + 1 : i);
      if (drop > from) drop -= 1;      // 自身抽走后索引左移
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMoveEv);
      document.removeEventListener("mouseup", onUp);
      clear();
      row.classList.remove("dragging");
      document.body.classList.remove("sorting");
      if (drop !== from) host._sortCb(from, drop);
    };
    document.addEventListener("mousemove", onMoveEv);
    document.addEventListener("mouseup", onUp);
  });
}

function hexRowInput(row, key, cls, ph, onChange) {
  const inp = document.createElement("input");
  inp.type = "text";
  inp.className = "hex " + cls;
  inp.placeholder = ph || "";
  inp.value = row[key] ?? "";
  inp.addEventListener("change", () => { row[key] = inp.value.trim(); onChange && onChange(); });
  return inp;
}

function renderI2CTable(host, node, param) {
  const rows = getOps(node, param.name);
  host.innerHTML = "";
  const rerender = () => renderI2CTable(host, node, param);
  const wrapEdit = (fn) => { beginEdit(); fn(); commitEdit(); };
  const needWrite = (op) => op === "write" || op === "write_verify";
  const needRead = (op) => op === "read" || op === "read_verify" || op === "write_verify";

  rows.forEach((row, i) => {
    const op = row.op || "read";
    if (!row.mode) row.mode = PROJ_DEFAULT_MODE || DEFAULT_MODE;   // 逐条模式: 不继承上层
    const el = document.createElement("div");
    el.className = "ops-row";
    el.append(gripEl(), idxEl(i));

    // ① 本条指令的类型 + 位宽 (都在第一行, 紧凑; 每条指令单独指定, 没有全局默认)
    const opSel = document.createElement("select");
    opSel.className = "op-sel";
    opSel.title = "本条指令的类型: 读 / 读并校验 / 写 / 写并回读校验";
    I2C_OPS.forEach(([v, l]) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = l; if (op === v) o.selected = true;
      opSel.appendChild(o);
    });
    opSel.addEventListener("change", () => wrapEdit(() => { row.op = opSel.value; rerender(); }));
    el.append(mkel("lbl", "类型"), opSel);

    const modeSel = document.createElement("select");
    modeSel.className = "mode-sel";
    modeSel.title = "本条指令的位宽: A<地址字节数>D<数据字节数> —— 每条都要单独指定";
    I2C_MODES.forEach((m) => {
      const o = document.createElement("option");
      o.value = m; o.textContent = m;
      if (row.mode === m) o.selected = true;
      modeSel.appendChild(o);
    });
    modeSel.addEventListener("change", () => wrapEdit(() => { row.mode = modeSel.value; }));
    el.append(mkel("lbl", "位宽"), modeSel);

    const btns = mkel("row-btns");
    const gear = document.createElement("button");
    gear.className = "mini"; gear.textContent = "⚙";
    gear.title = "遮罩 / 右移 / 单独指定 slave";
    gear.addEventListener("click", () => { row.advOpen = !row.advOpen; rerender(); });
    const saveP = document.createElement("button");
    saveP.className = "mini"; saveP.textContent = "⤓"; saveP.title = "把这行存为常用寄存器预设";
    saveP.addEventListener("click", () => saveRowAsPreset(row));
    const del = document.createElement("button");
    del.className = "mini danger-x"; del.textContent = "✕"; del.title = "删除这一条";
    del.addEventListener("click", () => wrapEdit(() => { rows.splice(i, 1); rerender(); }));
    btns.append(gear, saveP, del);
    el.appendChild(btns);
    host.appendChild(el);

    // ② 参数第二行: 地址 + 写入/期待 —— 每格字段名紧贴输入框
    const box = mkel("row-params");
    box.appendChild(fx("地址", hexRowInput(row, "addr", "w74", "0x0000", touchRow)));
    if (needWrite(op)) box.appendChild(fx("写入", hexRowInput(row, "value", "w74", "0x0001", touchRow)));
    if (needRead(op)) {
      const ph = op === "read_verify" ? "必填" : (op === "write_verify" ? "留空=比写入值" : "留空=不断言");
      box.appendChild(fx("期待", hexRowInput(row, "expect", "w74", ph, touchRow)));
    }
    el.appendChild(box);

    if (row.advOpen) {
      const adv = document.createElement("div");
      adv.className = "ops-adv";
      adv.append(fx("遮罩", hexRowInput(row, "mask", "w90", "0xFFFFFFFF", touchRow)),
                 fx("右移", hexRowInput(row, "shift", "w50", "0", touchRow)),
                 fx("slave", hexRowInput(row, "slave", "w60", "留空=统一", touchRow)));
      adv.appendChild(mkel("adv-hint", "比较: (回读 & 遮罩) >> 右移 == 期待值"));
      host.appendChild(adv);
    }
  });

  const addBar = document.createElement("div");
  addBar.className = "ops-addbar";
  const addBtn = document.createElement("button");
  addBtn.className = "ops-add"; addBtn.textContent = "＋ 添加一条";
  addBtn.dataset.addop = param.name;
  const presetBtn = document.createElement("button");
  presetBtn.className = "ops-add"; presetBtn.textContent = "常用寄存器 ▾";
  presetBtn.dataset.presetfor = param.name;
  addBar.append(addBtn, presetBtn);
  host.appendChild(addBar);

  makeSortable(host, (from, to) => wrapEdit(() => {
    const [x] = rows.splice(from, 1); rows.splice(to, 0, x); rerender();
  }));
}

function saveRowAsPreset(row) {
  const name = prompt("预设名称:", `自定义_${row.addr || "reg"}`);
  if (!name) return;
  PRESETS = PRESETS.filter((p) => p.name !== name);
  PRESETS.push({ ...row, name, advOpen: undefined });
  api("/api/presets", { method: "PUT", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ presets: PRESETS }) })
    .then(() => setStatus(`已保存预设「${name}」`, "ok"))
    .catch((e) => setStatus("预设保存失败: " + e.message, "err"));
}

function renderOpList(host, node, param, schema) {
  const rows = getOps(node, param.name);
  const labels = {};
  (schema || []).forEach((o) => (labels[o.op] = { label: o.label, params: o.params || [] }));
  host.innerHTML = "";
  const rerender = () => renderOpList(host, node, param, schema);
  const wrapEdit = (fn) => { beginEdit(); fn(); commitEdit(); };

  rows.forEach((row, i) => {
    // 兼容旧数据: op 已下线时回落到第一个可用操作
    if (!labels[row.op] && (schema || []).length) row.op = schema[0].op;
    const meta = labels[row.op] || { label: row.op, params: [] };
    const el = document.createElement("div");
    el.className = "ops-row";
    el.append(gripEl(), idxEl(i));

    const sel = document.createElement("select");
    sel.className = "op-sel wide";
    sel.title = "本项操作";
    (schema || []).forEach((o) => {
      const op = document.createElement("option");
      op.value = o.op; op.textContent = o.label; if (row.op === o.op) op.selected = true;
      sel.appendChild(op);
    });
    sel.addEventListener("change", () => {
      wrapEdit(() => {
        row.op = sel.value;
        (labels[sel.value]?.params || []).forEach((pf) => { row[pf.name] = pf.default; });
        rerender();
      });
    });
    el.appendChild(sel);

    const btns = mkel("row-btns");
    const del = document.createElement("button");
    del.className = "mini danger-x"; del.textContent = "✕"; del.title = "删除这一项";
    del.addEventListener("click", () => wrapEdit(() => { rows.splice(i, 1); rerender(); }));
    btns.appendChild(del);
    el.appendChild(btns);

    // 参数另起一行并缩进: 每格都是「字段名 + 输入框」紧挨着, 行高一致、互不拉开
    const pfList = meta.params || [];
    if (pfList.length) {
      const box = mkel("row-params");
      pfList.forEach((pf) => {
        if (row[pf.name] === undefined || row[pf.name] === null) row[pf.name] = pf.default;
        box.appendChild(fx(pf.label, hexRowInput(row, pf.name, "w74", pf.default ?? "", touchRow)));
      });
      el.appendChild(box);
    }
    host.appendChild(el);
  });

  const addBar = document.createElement("div");
  addBar.className = "ops-addbar";
  const addBtn = document.createElement("button");
  addBtn.className = "ops-add"; addBtn.textContent = "＋ 添加一项";
  addBtn.dataset.addoplist = param.name;
  addBar.appendChild(addBtn);
  host.appendChild(addBar);

  makeSortable(host, (from, to) => wrapEdit(() => {
    const [x] = rows.splice(from, 1); rows.splice(to, 0, x); rerender();
  }));
}

/* 属性面板里列表容器的事件委托 (添加一行 / 预设菜单) */
function initOpsDelegation(body) {
  body.addEventListener("click", (e) => {
    if (e.target.dataset?.addop) {
      const node = nodeById(selected);
      beginEdit();
      getOps(node, e.target.dataset.addop).push(newI2CRow("read"));
      commitEdit(); renderInspector();
    } else if (e.target.dataset?.addoplist) {
      const node = nodeById(selected);
      const sch = (spec(node.type).ops_schema || []);
      beginEdit();
      const rows = getOps(node, e.target.dataset.addoplist);
      const firstNotUsed = sch.find((o) => !rows.some((r) => r.op === o.op)) || sch[0];
      const row = { op: firstNotUsed.op };
      (firstNotUsed.params || []).forEach((pf) => (row[pf.name] = pf.default));
      rows.push(row);
      commitEdit(); renderInspector();
    } else if (e.target.dataset?.presetfor) {
      const items = PRESETS.map((p, i) => ({
        key: "p" + i, label: `${p.name}  ${p.addr || ""} ${p.op === "read" ? "读" : "写"}`,
        onClick: () => {
          const node = nodeById(selected);
          beginEdit();
          const r = { ...p };
          delete r.name; delete r.desc; delete r.advOpen;
          r.mode = r.mode || PROJ_DEFAULT_MODE || DEFAULT_MODE;
          getOps(node, e.target.dataset.presetfor).push(r);
          commitEdit(); renderInspector();
          setStatus(`已插入预设「${p.name}」(可就地修改)`, "ok");
        },
      }));
      const r = e.target.getBoundingClientRect();
      popupMenu(items.length ? items : [{ key: "none", label: "(还没有预设)", disabled: true,
                                          onClick: () => {} }], r.left, r.bottom + 2);
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
      + "<b>连线</b>: 点一下金色端口 → 再点一下目标端口<br>"
      + "(或按住端口拖线, 会自动吸附)<br>"
      + "只有<b>金色执行流</b>; 断言写在节点内部<br>"
      + "(I²C 行的『期待值』/ 操作行的上下限)<br><br>"
      + "空白拖动=平移 · 滚轮=缩放<br>"
      + "Delete=删除选中 · Ctrl+Z=撤销 · 自动保存";
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
    } else if (p.type === "i2ctable") {
      html += `<div class="field wide"><label>${esc(p.label)}</label>` +
        `<div class="ops-editor i2c" data-kind="i2c" data-param="${esc(p.name)}"></div></div>`;
    } else if (p.type === "oplist") {
      html += `<div class="field wide"><label>${esc(p.label)}</label>` +
        `<div class="ops-editor opl" data-kind="opl" data-param="${esc(p.name)}"></div></div>`;
    } else {
      html += `<div class="field"><label>${esc(p.label)}${p.hex ? " (十六进制)" : ""}</label>` +
        `<input type="text" data-param="${esc(p.name)}" value="${esc(v)}"></div>`;
    }
  }
  if (!s.params.length) html += `<div class="field"><label>该节点无参数</label></div>`;

  html += `<div class="ins-debug"><div class="ins-conn" style="margin-top:10px">调试</div>`;
  html += `<button class="dbg-run" id="ins-run-node">▶ 运行此节点</button>`;
  html += `<div class="ins-row"><button class="dbg-btn" id="ins-sess-reopen">↻ 重开会话</button>`
    + `<button class="dbg-btn" id="ins-sess-close">⏻ 释放会话</button></div>`
    + `<div class="ins-hint">单步调试复用常驻会话: 设备保持上电/已配置, 改了参数直接点节点上的 ▶</div>`;
  for (const d of s.debug || [])
    html += `<button class="dbg-btn" data-dbg="${esc(d.name)}">${esc(d.label)}</button>`;
  html += `<div id="dbg-result" class="dbg-result"></div></div>`;
  body.innerHTML = html;

  // 列表型参数: 渲染 I²C 表格 / 操作列表
  $$(".ops-editor", body).forEach((host) => {
    const pd = (s.params || []).find((p) => p.name === host.dataset.param);
    if (host.dataset.kind === "i2c") renderI2CTable(host, node, pd);
    else renderOpList(host, node, pd, s.ops_schema);
  });

  $$("[data-param]", body).forEach((input) => {
    if (input.classList.contains("ops-editor")) return;
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
  $("#ins-sess-reopen", body)?.addEventListener("click", async () => {
    setStatus("正在重开会话…");
    try {
      await jpost("/api/session", { action: "reopen" });
      setStatus("会话已重开 (设备需重新配置)", "ok");
    } catch (e) { setStatus("重开失败: " + e.message, "err"); }
    refreshSession();
  });
  $("#ins-sess-close", body)?.addEventListener("click", async () => {
    try {
      await jpost("/api/session", { action: "close" });
      setStatus("会话已释放, COM 口与设备句柄已交还", "ok");
    } catch (e) { setStatus("释放失败: " + e.message, "err"); }
    refreshSession();
  });
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
    const r = await jpost("/api/run_node",
      { type: node.type, params: node.params, case: canvas ? canvas.name : null });
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
  const fresh = await jfetch("/api/canvases/" + encodeURIComponent(name));
  const adopt = () => {
    canvas = fresh;
    HIST.length = 0; FUTURE.length = 0; selEdge = null; selected = null;
  };
  adopt();
  $("#chk-stopfail").checked = canvas.stop_on_fail !== false;
  renderAll(); renderInspector();
  if (canvas.view && typeof canvas.view.z === "number") {
    Object.assign(view, canvas.view);
    applyView();
  } else {
    fitView();          // 新画布: 内容自动居中
  }
  setDockCase(name);
  if (dockTab === "img") loadDockImages();
  else if (dockTab === "hist") loadDockHist();
  else refreshDockCounts();
  setStatus(`已加载画布: ${name} (空白拖动平移, 滚轮缩放)`, "ok");
  markDirty(false);
}
async function saveCanvas(silent) {
  canvas.stop_on_fail = $("#chk-stopfail").checked;
  canvas.view = { x: Math.round(view.x), y: Math.round(view.y), z: +view.z.toFixed(3) };
  await jput("/api/canvases/" + encodeURIComponent(canvas.name), canvas);
  await refreshCanvasList(canvas.name);
  markDirty(false);
  if (!silent) setStatus(`画布已保存: ${canvas.name}`, "ok");
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

/* ---------------- 运行监控坞 (SSE 实时事件流) ---------------- */
let evtSrc = null, lastRunId = null;
let runEvents = [];            // 本次运行的全部事件
let logFilter = "all", foldPassed = false, logQuery = "";

function dockOpen() { $("#rundock").classList.remove("collapsed"); }
function dockSetDot(cls, info) {
  $("#dock-dot").className = cls;
  $("#dock-info").textContent = info || "";
}
function dockClear() { $("#dock-body").innerHTML = ""; runEvents = []; $("#dock-body").dataset.nodeFilter = ""; }

function evTime(ev) {
  return new Date(ev.ts || Date.now()).toTimeString().slice(0, 8);
}

function logLine(ev) {
  const el = document.createElement("div");
  el.className = "lg-item lv-" + (ev.level || "info") + " res-" + (ev.result || "none");
  const head = document.createElement("div");
  head.className = "lg-head";
  const t = document.createElement("span"); t.className = "lg-t"; t.textContent = evTime(ev);
  const seq = document.createElement("span"); seq.className = "lg-seq";
  seq.textContent = `[${ev.seq ?? "-"}]`;
  const kind = document.createElement("span"); kind.className = "lg-kind";
  kind.textContent = ev.kind || "";
  const txt = document.createElement("span"); txt.className = "lg-txt";
  txt.textContent = ev.text || "";
  head.append(t, seq, kind, txt);
  el.appendChild(head);
  const fields = ev.fields || {};
  if (Object.keys(fields).length) {
    const box = document.createElement("div");
    box.className = "lg-fields";
    for (const [k, v] of Object.entries(fields)) {
      const row = document.createElement("div");
      row.className = "lg-f";
      const kk = document.createElement("span"); kk.className = "lg-fk"; kk.textContent = k;
      const vv = document.createElement("span"); vv.className = "lg-fv"; vv.textContent = v;
      row.append(kk, vv); box.appendChild(row);
    }
    el.appendChild(box);
  }
  return el;
}

function progressLine(ev) {
  let el = $("#dock-body .pg-item");
  if (!el) {
    el = document.createElement("div");
    el.className = "pg-item";
    el.innerHTML = `<span class="pg-label"></span><span class="pg-bar"><i></i></span><span class="pg-pct">0%</span>`;
    $("#dock-body").appendChild(el);
    return updateBar(el, ev);
  }
  return updateBar(el, ev);
}
function updateBar(el, ev) {
  $(".pg-label", el).textContent = ev.phase || "进度";
  $(".pg-bar i", el).style.width = (ev.pct || 0) + "%";
  $(".pg-pct", el).textContent = (ev.pct || 0) + "%";
  return el;
}

function logRow(ev) {
  const body = $("#dock-body");
  const line = document.createElement("div");
  line.className = "dl " + ({ error: "fail", warn: "warn" }[ev.level] || "");
  line.innerHTML = `<span class="t">[${esc(ev.t || timeStr())}]</span>${esc(ev.text || "")}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function matchFilter(ev) {
  if (logFilter === "fail") {
    const bad = ev.result === "fail" || ev.level === "error";
    if (ev.event === "log" && !bad) return false;
  }
  if (logQuery) {
    const hay = JSON.stringify(ev).toLowerCase();
    if (!hay.includes(logQuery.toLowerCase())) return false;
  }
  return true;
}

function rerenderDock() {
  const body = $("#dock-body");
  body.innerHTML = "";
  for (const ev of runEvents) {
    if (ev.event === "log") {
      if (!matchFilter(ev)) continue;
      body.appendChild(logLine(ev));
    } else if (ev.event === "progress") {
      if (logFilter === "fail") continue;
      updateBar(progressLine(ev), ev);
    }
  }
  body.classList.toggle("fold-passed", foldPassed);
  body.scrollTop = body.scrollHeight;
}

const timeStr = () => new Date().toTimeString().slice(0, 8);

function finishRunUI(ok, started) {
  if (evtSrc) { evtSrc.close(); evtSrc = null; }
  dockSetDot(ok ? "pass" : "fail",
    `运行${ok ? "完成: 全部通过 ✓" : "失败 ✗"}${started ? " (开始于 " + started + ")" : ""}`);
  setStatus(ok ? "运行完成: 全部通过 ✓" : "运行失败 ✗", ok ? "ok" : "err");
  $("#btn-run").disabled = false;
  $("#btn-rununtil").disabled = false;
  refreshSession();
  refreshDockCounts();
}

function subscribeStream(runId) {
  if (evtSrc) evtSrc.close();
  evtSrc = new EventSource("/api/stream/" + runId);
  evtSrc.onmessage = (msg) => {
    let ev;
    try { ev = JSON.parse(msg.data); } catch { return; }
    if (ev.event !== "eof") runEvents.push(ev);
    if (ev.event === "log") {
      if (matchFilter(ev)) { $("#dock-body").appendChild(logLine(ev)); $("#dock-body").classList.toggle("fold-passed", foldPassed); $("#dock-body").scrollTop = 1e6; }
    } else if (ev.event === "progress") {
      if (logFilter !== "fail") {
        const el = progressLine(ev);
        $("#dock-body").appendChild(el);
        $("#dock-body").scrollTop = 1e6;
      }
    } else if (ev.event === "start") {
      markNode(ev.id, "running");
      logRow({ t: timeStr(), cls: "run", text: `▶ [${ev.id}] ${ev.title} 执行中…` });
      runEvents.push({ event: "note", t: timeStr(), text: `▶ ${ev.title}` });
      dockSetDot("running", `运行中… ${ev.id}`);
    } else if (ev.event === "finish") {
      const e = ev.entry;
      markNode(e.id, e.status, e.outputs, e.error);
      logRow({ t: timeStr(), cls: e.status === "passed" ? "pass" : "fail",
               text: e.status === "passed"
                 ? `✓ [${e.id}] ${e.title} 通过 (${e.ms}ms)`
                 : `✗ [${e.id}] ${e.title} 失败: ${e.error}` });
      runEvents.push({ event: "note", t: timeStr(),
                       text: `${e.status === "passed" ? "✓" : "✗"} ${e.title} ${e.error || ""}` });
    } else if (ev.event === "done") {
      logRow({ t: timeStr(), cls: "run",
               text: "== 运行结束: " + (ev.ok ? "全部通过 ✓" : "存在失败 ✗") + " ==" });
      finishRunUI(ev.ok, timeStr());
    } else if (ev.event === "eof") {
      if (evtSrc) { evtSrc.close(); evtSrc = null; }
      $("#btn-run").disabled = false;
      $("#btn-rununtil").disabled = false;
      refreshSession();
    }
  };
  evtSrc.onerror = () => { /* 断线由 eof/轮询兜底 */ };
}

async function startRun(name, body) {
  await saveCanvas(true);
  clearStatusBadges();
  setDockCase(name);
  dockOpen(); dockTabShow("log"); dockClear();
  dockSetDot("running", "启动中…");
  $("#btn-run").disabled = true; $("#btn-rununtil").disabled = true;
  try {
    const r = await jpost("/api/run/" + encodeURIComponent(name), body || {});
    lastRunId = r.run_id;
    runEvents = [];
    subscribeStream(r.run_id);
    setStatus("运行中… (下方日志实时刷新)");
  } catch (e) {
    dockSetDot("fail", "启动失败");
    logRow({ t: timeStr(), cls: "fail", text: "启动失败: " + e.message });
    setStatus("运行出错: " + e.message, "err");
    $("#btn-run").disabled = false; $("#btn-rununtil").disabled = false;
  }
}

async function runCanvas() {
  await startRun(canvas.name, { stop_on_fail: $("#chk-stopfail").checked });
}

async function runUntilHere() {
  if (!selected) { setStatus("先选中一个节点, 再点『运行到此』", "err"); return; }
  const id = selected;
  await saveCanvas(true);
  clearStatusBadges();
  setDockCase(canvas.name);
  dockOpen(); dockTabShow("log"); dockClear();
  dockSetDot("running", "准备依赖链…");
  $("#btn-run").disabled = true; $("#btn-rununtil").disabled = true;
  try {
    const r = await jpost("/api/run_until/" + encodeURIComponent(canvas.name), { node_id: id });
    lastRunId = r.run_id;
    runEvents = [];
    subscribeStream(r.run_id);
    setStatus(`运行到 ${id} 为止 (含上游依赖链), 会话结束后保留`);
  } catch (e) {
    dockSetDot("fail", "启动失败");
    logRow({ t: timeStr(), cls: "fail", text: "启动失败: " + e.message });
    $("#btn-run").disabled = false; $("#btn-rununtil").disabled = false;
  }
}

function exportRunMD() {
  if (!runEvents.length) { setStatus("当前没有可导出的运行日志", "err"); return; }
  const lines = [];
  lines.push(`# 运行报告 · ${canvas ? canvas.name : ""}`);
  lines.push("");
  lines.push(`- 导出时间: ${new Date().toLocaleString()}`);
  lines.push("");
  lines.push("```");
  for (const ev of runEvents) {
    if (ev.event === "log") {
      lines.push(`[${evTime(ev)}] [${ev.seq ?? "-"}] ${ev.text || ev.kind}`);
      for (const [k, v] of Object.entries(ev.fields || {})) lines.push(`      ${k}: ${v}`);
    } else if (ev.event === "progress") {
      lines.push(`[${evTime(ev)}] [进度] ${ev.phase} ${ev.pct}% ${ev.detail || ""}`);
    } else if (ev.event === "note") {
      lines.push(`[${ev.t}] ${ev.text}`);
    }
  }
  lines.push("```");
  const md = lines.join("\n");
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `run_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.md`;
  a.click();
  setStatus("运行日志已导出为 Markdown", "ok");
}

/* ---------------- 面板自由伸缩 (坞高 / 属性台宽) ---------------- */
function initResizers() {
  const root = document.documentElement;
  let dockH = parseInt(localStorage.getItem("newauto.dockH") || "", 10) || 210;
  let insW = parseInt(localStorage.getItem("newauto.insW") || "", 10) || 336;
  const applyDock = () => root.style.setProperty("--dock-h", Math.max(64, dockH) + "px");
  const applyIns = () => root.style.setProperty("--ins-w", Math.max(232, insW) + "px");
  applyDock(); applyIns();

  const bind = (el, o) => {
    if (!el) return;
    let lastDown = 0;
    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      // 双击 = 复位。用"两次按下间隔 <400ms"判定, 不依赖 detail
      // (下面 preventDefault 会拦住浏览器合成 dblclick; 且自动化点击的 detail 不可靠)
      const now = performance.now();
      const dbl = e.detail >= 2 || (now - lastDown < 400);
      lastDown = now;
      e.preventDefault(); e.stopPropagation();
      if (dbl) { o.reset(); o.save(); setStatus("尺寸已复位"); return; }
      const s = o.axis === "y" ? e.clientY : e.clientX;
      const base = o.get();
      document.body.classList.add(o.cls);
      const mv = (ev) => {
        const cur = o.axis === "y" ? ev.clientY : ev.clientX;
        o.set(base + (s - cur));            // 往上 / 往左拖 = 变大
      };
      const up = () => {
        document.removeEventListener("mousemove", mv);
        document.removeEventListener("mouseup", up);
        document.body.classList.remove(o.cls);
        o.save();
      };
      document.addEventListener("mousemove", mv);
      document.addEventListener("mouseup", up);
    });
    el.addEventListener("dblclick", (e) => {
      e.stopPropagation(); o.reset(); o.save(); setStatus("尺寸已复位");
    });
  };

  bind($("#dock-resizer"), {
    axis: "y", cls: "row-resizing",
    get: () => dockH,
    set: (v) => { dockH = Math.min(Math.max(64, v), Math.max(120, innerHeight - 190)); applyDock(); },
    reset: () => { dockH = 210; applyDock(); },
    save: () => localStorage.setItem("newauto.dockH", String(dockH)),
  });
  bind($("#ins-resizer"), {
    axis: "x", cls: "col-resizing",
    get: () => insW,
    set: (v) => { insW = Math.min(Math.max(232, v), Math.max(280, innerWidth - 420)); applyIns(); },
    reset: () => { insW = 336; applyIns(); },
    save: () => localStorage.setItem("newauto.insW", String(insW)),
  });
}

/* ---------------- 本 case 的独立空间 (日志 / 图片 / 历史) ----------------
   一个画布 = 一个 case。产物流在 logs/cases/<case>/ 下, 与其它 case 完全隔离,
   「清空」只删本 case 自己的 runs/ 与 img/。 */
let dockCase = null, dockTab = "log";

function setDockCase(name) {
  dockCase = name || null;
  const el = $("#dock-case");
  if (el) { el.textContent = "case: " + (dockCase || "-"); el.title = dockCase || ""; }
}

function dockTabShow(tab) {
  dockTab = tab;
  $$("#dock-tabs .dtab").forEach((b) => b.classList.toggle("on", b.dataset.dtab === tab));
  $("#dock-body").classList.toggle("hidden", tab !== "log");
  $("#dock-img").classList.toggle("hidden", tab !== "img");
  $("#dock-hist").classList.toggle("hidden", tab !== "hist");
  const lt = $("#dock-logtools");
  if (lt) lt.style.display = tab === "log" ? "" : "none";
  if (tab === "img") loadDockImages();
  else if (tab === "hist") loadDockHist();
  else rerenderDock();
}

const caseUrl = (suffix) => "/api/cases/" + encodeURIComponent(dockCase) + suffix;

async function fetchCaseAssets() {
  if (!dockCase) return null;
  try { return await jfetch(caseUrl("/assets")); } catch { return null; }
}
function setCaseCounts(a) {
  if (!a || !a.counts) return;
  $("#dtab-img-n").textContent = a.counts.images;
  $("#dtab-hist-n").textContent = a.counts.runs;
}
async function refreshDockCounts() { setCaseCounts(await fetchCaseAssets()); }

function humanSize(n) {
  n = n || 0;
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  return (n / 1048576).toFixed(1) + " MB";
}

async function loadDockImages() {
  const host = $("#dock-img");
  if (!dockCase) { host.innerHTML = `<div class="dk-empty">先选一个画布 —— 画布名就是 case。</div>`; return; }
  host.innerHTML = `<div class="dk-empty">读取中…</div>`;
  const a = await fetchCaseAssets();
  if (!a) { host.innerHTML = `<div class="dk-empty">读取失败</div>`; return; }
  setCaseCounts(a);
  const imgs = a.images || [];
  if (!imgs.length) {
    host.innerHTML = `<div class="dk-empty">本 case 还没有抓帧图片。<br>`
      + `跑一次带「抓帧存图 / 出图检查」的流程, 图片会落在这里:<br>`
      + `<code>${esc(a.img_dir)}</code></div>`;
    return;
  }
  host.innerHTML = `<div class="dk-tools"><span class="dim">${imgs.length} 张 · ${humanSize(a.counts.img_bytes)} · ${esc(a.img_dir)}</span>`
    + `<span class="dock-spacer"></span>`
    + `<button class="mini" id="dk-img-refresh">刷新</button>`
    + `<button class="mini danger-x" id="dk-img-clear">🗑 清空图片</button></div>`
    + `<div class="dk-imgs">` + imgs.map((f) => `
        <div class="dk-img" data-name="${esc(f.name)}" title="${esc(f.name)} · ${humanSize(f.size)}">
          <img loading="lazy" src="/api/img/thumb?case=${encodeURIComponent(a.case)}&name=${encodeURIComponent(f.name)}">
          <div class="nm">${esc(f.name)}</div>
        </div>`).join("") + `</div>`;
  $("#dk-img-refresh", host).addEventListener("click", loadDockImages);
  $("#dk-img-clear", host).addEventListener("click", () => clearCaseAssets("images"));
  $$(".dk-img", host).forEach((el) => el.addEventListener("click", () => {
    $("#gallery-big").src = `/api/img/thumb?case=${encodeURIComponent(a.case)}&name=${encodeURIComponent(el.dataset.name)}`;
    $("#gallery-caption").textContent = el.dataset.name;
    $("#gallery-viewer").classList.remove("hidden");
  }));
}

async function loadDockHist() {
  const host = $("#dock-hist");
  if (!dockCase) { host.innerHTML = `<div class="dk-empty">先选一个画布 —— 画布名就是 case。</div>`; return; }
  host.innerHTML = `<div class="dk-empty">读取中…</div>`;
  const a = await fetchCaseAssets();
  if (!a) { host.innerHTML = `<div class="dk-empty">读取失败</div>`; return; }
  setCaseCounts(a);
  const runs = a.runs || [];
  if (!runs.length) {
    host.innerHTML = `<div class="dk-empty">本 case 还没有运行记录。<br>`
      + `点顶栏「▶ 运行」或「⤵ 运行到此」, 报告与逐字段事件会存到:<br><code>${esc(a.dir)}\\runs</code></div>`;
    return;
  }
  host.innerHTML = `<div class="dk-tools"><span class="dim">${runs.length} 次运行 · 通过 ${a.counts.passed} / 失败 ${a.counts.failed}</span>`
    + `<span class="dock-spacer"></span>`
    + `<button class="mini" id="dk-hist-refresh">刷新</button>`
    + `<button class="mini" id="dk-hist-all">全部 case 历史</button>`
    + `<button class="mini danger-x" id="dk-hist-clear">🗑 清空日志</button></div>`
    + runs.map((h) => `
      <div class="hist-row">
        <span class="ht">${esc(h.started || "")}</span>
        <span class="hn">${esc(h.name || "")}</span>
        <span class="${h.ok ? "ok-t" : "err-t"}">${h.ok ? "✓ 全部通过" : `✗ ${h.failed} 个失败`}</span>
        <span class="dim">${h.nodes} 节点</span>
        <a class="hist-a" href="/api/history/${esc(h.id)}/md" target="_blank">导出 MD</a>
        <button class="mini" data-load="${esc(h.id)}">查看</button>
        <button class="mini danger-x" data-del="${esc(h.id)}">删除</button>
      </div>`).join("");
  $("#dk-hist-refresh", host).addEventListener("click", loadDockHist);
  $("#dk-hist-all", host).addEventListener("click", openHistory);
  $("#dk-hist-clear", host).addEventListener("click", () => clearCaseAssets("logs"));
  $$("[data-load]", host).forEach((b) => b.addEventListener("click", async () => {
    const d = await jfetch("/api/history/" + b.dataset.load);
    dockOpen(); dockTabShow("log");
    runEvents = d.events || []; rerenderDock();
    setStatus(`已载入历史运行 ${b.dataset.load}`, "ok");
  }));
  $$("[data-del]", host).forEach((b) => b.addEventListener("click", async () => {
    await api("/api/history/" + b.dataset.del, { method: "DELETE" });
    loadDockHist();
  }));
}

/* 一键清空本 case: 日志 / 图片 / 全部 (只删这个 case, 不碰别的) */
const CLEAR_LABEL = { logs: "运行日志", images: "抓帧图片", all: "运行日志 + 抓帧图片" };
function clearCaseMenu(anchor) {
  const r = anchor.getBoundingClientRect();
  popupMenu([
    { key: "all", group: `清空 case「${dockCase || "-"}」`, label: "🗑 全部清空 (日志 + 图片)", onClick: () => clearCaseAssets("all") },
    { key: "logs", label: "🗒 只清空运行日志", onClick: () => clearCaseAssets("logs") },
    { key: "images", label: "🖼 只清空抓帧图片", onClick: () => clearCaseAssets("images") },
    { key: "screen", label: "🧹 只清空界面日志", onClick: () => { runEvents = []; rerenderDock(); setStatus("界面日志已清空"); } },
  ], r.left - 120, r.bottom + 2);
}

async function clearCaseAssets(what) {
  if (!dockCase) { setStatus("先选一个画布 (画布名就是 case)", "err"); return; }
  const label = CLEAR_LABEL[what] || what;
  if (!confirm(`清空 case「${dockCase}」的${label}?\n\n不可撤销, 且只影响这个 case。`)) return;
  try {
    const r = await jpost(caseUrl("/clear"), { what });
    const d = r.deleted || {};
    if (what === "all" || what === "logs") runEvents = [];
    setCaseCounts(r.assets);
    setStatus(`已清空「${dockCase}」的${label}: 日志 ${d.runs || 0} 条 / 图片 ${d.images || 0} 个, 释放 ${humanSize(d.bytes)}`, "ok");
    if (dockTab === "img") loadDockImages();
    else if (dockTab === "hist") loadDockHist();
    else rerenderDock();
  } catch (e) { setStatus("清空失败: " + e.message, "err"); }
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

/* ---------------- 会话状态 / 项目配置 / 历史 ---------------- */
async function refreshSession() {
  try {
    const { session } = await jfetch("/api/session");
    const chip = $("#sess-chip");
    if (!session.open) {
      chip.textContent = "会话: 未开"; chip.className = "sess-chip";
      return;
    }
    const bits = [];
    if (session.ini) bits.push(shortIni(session.ini));
    if (session.powered) bits.push("已上电");
    if (session.device_open) bits.push("已建会话");
    if (session.video) bits.push("视频开");
    chip.textContent = "会话: " + (bits.join(" · ") || "开");
    chip.className = "sess-chip on";
    chip.title = `常驻会话运行中 · 闲置 ${session.idle}s\n`
      + `闲置超过 ${session.timeout}s 自动释放, 释放/重开在属性面板 Debug 区或项目配置里`;
  } catch { /* 忽略 */ }
}
function shortIni(n) { return String(n).replace(/_max96712.*$/, "").slice(0, 44); }

async function loadPresets() {
  try { PRESETS = (await jfetch("/api/presets")).presets || []; }
  catch { PRESETS = []; }
}

let PROJ = null;
async function openProject() {
  try { PROJ = await jfetch("/api/project"); } catch (e) { setStatus("读取项目配置失败", "err"); return; }
  const fill = (sel, val, extra) => {
    sel.innerHTML = (extra || []) .concat(PROJ[sel.dataset.key] || [])
      .map((n) => `<option value="${esc(n)}" ${n === val ? "selected" : ""}>${esc(n)}</option>`).join("");
    if (val && ![...sel.options].some((o) => o.value === val)) {
      const o = document.createElement("option"); o.value = val; o.textContent = val;
      o.selected = true; sel.appendChild(o);
    }
    sel.value = val || "";
  };
  const iniSel = $("#proj-ini"), relSel = $("#proj-fw-release"), dbgSel = $("#proj-fw-debug");
  iniSel.dataset.key = "inis"; relSel.dataset.key = "bins"; dbgSel.dataset.key = "bins";
  const p = PROJ.project || {};
  fill(iniSel, p.default_ini);
  $("#proj-slave").value = p.default_slave || "0x40";
  fill(relSel, (p.firmware || {}).release, [{ v: "", l: "(未绑定)" }].map((o) => o.v));
  relSel.innerHTML = `<option value="">(未绑定)</option>` + (PROJ.bins || [])
    .map((n) => `<option value="${esc(n)}" ${n === (p.firmware || {}).release ? "selected" : ""}>${esc(n)}</option>`).join("");
  dbgSel.innerHTML = `<option value="">(未绑定)</option>` + (PROJ.bins || [])
    .map((n) => `<option value="${esc(n)}" ${n === (p.firmware || {}).debug ? "selected" : ""}>${esc(n)}</option>`).join("");
  renderPresetEditor();
  $("#proj-overlay").classList.remove("hidden");
}

function renderPresetEditor() {
  const list = $("#proj-preset-list");
  list.innerHTML = "";
  PRESETS.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "preset-row";
    row.innerHTML = `<input class="pn" value="${esc(p.name || "")}">`
      + `<select class="pop">${I2C_OPS.map(([v, l]) =>
        `<option value="${v}" ${p.op === v ? "selected" : ""}>${l}</option>`).join("")}</select>`
      + `<input class="pa" value="${esc(p.addr || "0x0000")}" placeholder="地址">`
      + `<input class="pm" value="${esc(p.mode || "A2D4")}" placeholder="模式">`
      + `<input class="pe" value="${esc(p.op === "read" ? (p.expect || "") : (p.value || ""))}" `
      + `placeholder="${p.op === "read" ? "期待值" : "写入值"}">`
      + `<input class="pd" value="${esc(p.desc || "")}" placeholder="说明">`
      + `<button class="mini danger-x">✕</button>`;
    const sync = () => {
      const q = (s) => row.querySelector(s).value.trim();
      PRESETS[i] = { ...PRESETS[i], name: q(".pn"), op: q(".pop"), addr: q(".pa"),
                     mode: q(".pm"), desc: q(".pd"),
                     expect: q(".pop") === "read" ? q(".pe") : (PRESETS[i].expect || ""),
                     value: q(".pop") !== "read" ? q(".pe") : (PRESETS[i].value || "") };
    };
    $$("input,select", row).forEach((el) => el.addEventListener("change", sync));
    $(".danger-x", row).addEventListener("click", () => { PRESETS.splice(i, 1); renderPresetEditor(); });
    list.appendChild(row);
  });
  if (!PRESETS.length) list.innerHTML = `<div class="dim" style="padding:6px">还没有预设</div>`;
}

async function saveProject() {
  try {
    await jput("/api/project", {
      project: {
        default_ini: $("#proj-ini").value,
        default_slave: $("#proj-slave").value.trim() || "0x40",
        firmware: { release: $("#proj-fw-release").value || null,
                    debug: $("#proj-fw-debug").value || null },
      },
    });
    await jput("/api/presets", { presets: PRESETS });
    $("#proj-msg").textContent = "已保存 ✓";
    setStatus("项目配置已保存", "ok");
    setTimeout(() => ($("#proj-msg").textContent = ""), 2500);
  } catch (e) {
    $("#proj-msg").textContent = "保存失败: " + e.message;
  }
}

async function openHistory() {
  $("#hist-overlay").classList.remove("hidden");
  try {
    const { history } = await jfetch("/api/history");
    const box = $("#hist-list");
    if (!history.length) {
      box.innerHTML = `<div class="dim" style="padding:14px">还没有运行记录</div>`;
      return;
    }
    box.innerHTML = history.map((h) => `
      <div class="hist-row">
        <span class="ht">${esc(h.started || "")}</span>
        <span class="hn">${esc(h.name || "")}</span>
        <span class="${h.ok ? "ok-t" : "err-t"}">${h.ok ? "✓ 全部通过" : `✗ ${h.failed} 个失败`}</span>
        <span class="dim">${h.nodes} 节点</span>
        <a class="hist-a" href="/api/history/${esc(h.id)}/md" target="_blank">导出 MD</a>
        <button class="mini" data-load="${esc(h.id)}">查看</button>
        <button class="mini danger-x" data-del="${esc(h.id)}">删除</button>
      </div>`).join("");
    $$("[data-load]", box).forEach((b) => b.addEventListener("click", async () => {
      const d = await jfetch("/api/history/" + b.dataset.load);
      dockClear(); dockOpen(); runEvents = d.events || [];
      $("#hist-overlay").classList.add("hidden");
      rerenderDock();
      setStatus(`已载入历史运行 ${b.dataset.load}`, "ok");
    }));
    $$("[data-del]", box).forEach((b) => b.addEventListener("click", async () => {
      await api("/api/history/" + b.dataset.del, { method: "DELETE" });
      openHistory();
    }));
  } catch (e) { $("#hist-list").innerHTML = `<div class="dim">读取失败: ${esc(e.message)}</div>`; }
}

/* ---------------- 初始化 ---------------- */
async function loadPorts() {
  try { COM_PORTS = (await jfetch("/api/ports")).ports; } catch { COM_PORTS = []; }
}
async function init() {
  REG = (await jfetch("/api/nodes")).nodes;
  await loadPorts();
  await loadPresets();
  renderPalette();

  initCanvasEvents();
  initClipboard();
  initTabs();
  initGallery();
  initResizers();
  initOpsDelegation($("#ins-body"));

  // 顶栏新按钮
  $("#btn-undo").addEventListener("click", undo);
  $("#btn-redo").addEventListener("click", redo);
  $("#btn-rununtil").addEventListener("click", runUntilHere);
  $("#btn-project").addEventListener("click", openProject);
  $("#btn-history").addEventListener("click", openHistory);
  $("#proj-save").addEventListener("click", saveProject);
  $("#proj-preset-add").addEventListener("click", () => {
    PRESETS.push({ name: "新预设", op: "read", addr: "0x0000", mode: "A2D4",
                   value: "", expect: "", mask: "0xFFFFFFFF", shift: "0", desc: "" });
    renderPresetEditor();
  });
  $("#proj-overlay").addEventListener("click", (e) => {
    if (e.target.id === "proj-overlay") $("#proj-overlay").classList.add("hidden");
  });
  $("#hist-overlay").addEventListener("click", (e) => {
    if (e.target.id === "hist-overlay") $("#hist-overlay").classList.add("hidden");
  });

  // 日志坞工具栏
  $$("#dock-head .dock-tab[data-filter]").forEach((b) => b.addEventListener("click", () => {
    logFilter = b.dataset.filter;
    $$("#dock-head .dock-tab[data-filter]").forEach((x) => x.classList.toggle("on", x === b));
    rerenderDock();
  }));
  $("#dock-fold").addEventListener("click", () => {
    foldPassed = !foldPassed;
    $("#dock-fold").classList.toggle("on", foldPassed);
    $("#dock-body").classList.toggle("fold-passed", foldPassed);
  });
  $("#dock-search").addEventListener("input", (e) => {
    logQuery = e.target.value.trim();
    rerenderDock();
  });
  $("#dock-export").addEventListener("click", exportRunMD);

  // 会话状态轮询
  setInterval(refreshSession, 5000);
  refreshSession();
  window.addEventListener("beforeunload", (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  $("#canvas-list").addEventListener("change", () => loadCanvas($("#canvas-list").value));
  $("#btn-new").addEventListener("click", async () => {
    const name = prompt("新画布名称 (即 case 名):");
    if (!name) return;
    canvas = { name, stop_on_fail: true,
               nodes: [{ id: "n1", type: "power.ctrl", x: 0, y: 0,
                         params: { action: "on", channel: 0, port: "",
                                   off_seconds: 15, wait_after_on: 8 } }],
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
  $("#dock-clear").addEventListener("click", (e) => clearCaseMenu(e.currentTarget));
  // 坞内分栏: 运行日志 / 本 case 图片 / 本 case 历史
  $$("#dock-tabs .dtab").forEach((b) => b.addEventListener("click", () => {
    $("#rundock").classList.remove("collapsed");
    dockTabShow(b.dataset.dtab);
  }));

  await refreshCanvasList();
  const names = $$("#canvas-list option").map((o) => o.textContent);
  const preferred = names.includes("示例_上电读版本出图") ? "示例_上电读版本出图"
    : (names.includes("demo_上电读版本出图") ? "demo_上电读版本出图" : names[0]);
  $("#canvas-list").value = preferred;
  await loadCanvas(preferred);
  dockTabShow("log");
}
init().catch((e) => { setStatus("初始化失败: " + e.message, "err"); console.error(e); });
