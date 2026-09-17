/* 前端冒烟测试: jsdom 里加载真实 index.html + app.js, 连真实本地服务
   node scripts/_smoke_ui.cjs   (NODE_PATH 需指向装了 jsdom 的 workspace) */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "..");
const BASE = "http://127.0.0.1:8765";
const html = fs.readFileSync(path.join(ROOT, "app/web/index.html"), "utf8");
const js = fs.readFileSync(path.join(ROOT, "app/web/app.js"), "utf8");
const bridge = `
<script>
window.__state = {
  get canvas() { return typeof canvas === "undefined" ? null : canvas; },
  get PRESETS() { return typeof PRESETS === "undefined" ? [] : PRESETS; },
  get HIST() { return typeof HIST === "undefined" ? [] : HIST; },
  selectNode: (id) => selectNode(id),
  undo: () => undo(), redo: () => redo(),
  addNodeAt: (t2, x, y) => addNodeAt(t2, x, y),
  loadCanvas: async (n) => loadCanvas(n),
};
</script>`;
// 注意: 用函数做替换 —— String.replace 会把替换串里的 $$ 当成转义, 直接传字符串会破坏代码
const inlined = html.replace('<script src="/web/app.js"></script>',
                             () => "<script>" + js + "</script>" + bridge);

const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push("jsdomError: " + (e.stack || e.message)));
vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
vc.on("warn", () => {});

const evSources = [];
const dom = new JSDOM(inlined, {
  runScripts: "dangerously",
  url: BASE + "/",
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    window.fetch = (p, opts) => fetch(p.startsWith("http") ? p : BASE + p, opts);
    class ES {
      constructor(url) { this.url = url; this.readyState = 0; evSources.push(this); }
      close() { this._closed = true; }
    }
    window.EventSource = ES;
    window.alert = () => {};
    window.confirm = () => true;
    window.prompt = (q, dv) => dv;
    if (!window.URL.createObjectURL) window.URL.createObjectURL = () => "blob:x";
  },
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  await sleep(4000);                       // 等初始化完成
  const w = dom.window, doc = w.document;
  const results = [];
  const t = (name, cond, extra = "") =>
    results.push(`${cond ? "✓" : "✗"} ${name}${extra ? "  " + extra : ""}`);

  // 1 面板节点数
  const items = doc.querySelectorAll(".pal-item").length;
  t("面板渲染", items >= 8, `(${items} 项)`);
  const groups = [...doc.querySelectorAll(".pal-group-name")].map((e) => e.textContent);
  t("分组为常用/高级", groups.includes("常用节点") && groups.includes("高级节点"),
    JSON.stringify(groups));

  // 2 画布加载
  const nodes = doc.querySelectorAll(".node").length;
  t("画布节点渲染", nodes > 0, `(${nodes} 个)`);

  // 3 蓝色数据端口已移除
  t("已无蓝色数据端口", doc.querySelectorAll(".port").length === 0);
  t("执行流端口存在", doc.querySelectorAll(".flow-out").length === nodes);

  // 4 选中 i2c.seq 节点 -> 属性面板渲染出表格
  const S = w.__state;
  // ⚠ 测试会点"添加一行"并触发 1.5s 自动保存 —— 先把画布快照下来, 收尾时还原
  const BEFORE = S.canvas ? JSON.parse(JSON.stringify(S.canvas)) : null;
  const opsOf = (id) => (S.canvas.nodes.find((n) => n.id === id) || {}).params.ops.length;
  // 行内字段是 <label class="fx"><span>字段名</span><input></label>, 按字段名找输入框
  // (⚠ 在编辑器根上找 —— ⚙ 展开的 .ops-adv 是行的兄弟节点, 不在 .ops-row 里面)
  const hasField = (root, txt) =>
    !!root && [...root.querySelectorAll(".fx > span")].some((s) => s.textContent.trim() === txt);
  const i2cNode = (S.canvas ? S.canvas.nodes : []).find((n) => n.type === "i2c.seq");
  if (!i2cNode) { results.push("✗ 画布里没有 i2c.seq 节点"); }
  else {
    S.selectNode(i2cNode.id);
    await sleep(300);
    const host = doc.querySelector("#ins-body .ops-editor.i2c");
    const rows = host.querySelectorAll(".ops-row").length;
    t("I²C 表格渲染", rows === i2cNode.params.ops.length,
      `(期望 ${i2cNode.params.ops.length} 行, 实际 ${rows})`);
    const readRow = host.querySelector(".ops-row");
    t("读行有『期待值』输入框", hasField(readRow, "期待"), "(留空=不断言)");
    t("每行有位宽模式下拉", host.querySelectorAll(".ops-row .mode-sel").length === rows);
    // 每条指令自带类型: 类型下拉数 == 行数
    t("每条指令有独立类型下拉",
      host.querySelectorAll(".ops-row select.op-sel").length === rows);
    // 类型下拉切换 -> 参数区随之变化 (读 -> 写会出现『写入』)
    const firstSel = host.querySelector(".ops-row select.op-sel");
    firstSel.value = "write";
    firstSel.dispatchEvent(new w.Event("change", { bubbles: true }));
    await sleep(80);
    t("改类型后字段随之变化", hasField(doc.querySelector("#ins-body .ops-editor.i2c"), "写入"));
    // 断言参数(遮罩/右移)藏在 ⚙ 里
    const gear = doc.querySelector("#ins-body .ops-editor.i2c .ops-row button.mini");
    gear.click(); await sleep(80);
    t("⚙ 展开遮罩/右移", hasField(doc.querySelector("#ins-body .ops-editor.i2c"), "遮罩"));
    doc.querySelector("#ins-body .ops-editor.i2c .ops-row button.mini").click();
    await sleep(80);
    // 添加一行
    const before = opsOf(i2cNode.id);
    doc.querySelector("#ins-body [data-addop]").click();
    await sleep(50);
    const after = opsOf(i2cNode.id);
    t("表格添加一行", after === before + 1, `(${before} → ${after})`);
    t("每行都有拖拽抓手", doc.querySelectorAll("#ins-body .ops-editor.i2c .ops-row .grip").length === after);
    // 撤销
    S.undo(); await sleep(50);
    const undone = opsOf(i2cNode.id);
    t("Ctrl+Z 撤销生效", undone === before, `(${after} → ${undone})`);
  }

  // 5 device.check 操作列表
  const dcNode = (S.canvas ? S.canvas.nodes : []).find((n) => n.type === "device.check");
  if (dcNode) {
    S.selectNode(dcNode.id);
    await sleep(300);
    const oplHost = () => doc.querySelector("#ins-body .ops-editor.opl");
    const rows = oplHost().querySelectorAll(".ops-row").length;
    t("Device 操作列表渲染", rows === dcNode.params.ops.length,
      `(期望 ${dcNode.params.ops.length}, 实际 ${rows})`);
    // 带参数的操作: 参数放在独立的 row-params 行里, 字段名紧贴输入框
    const withParams = [...oplHost().querySelectorAll(".ops-row")]
      .find((r) => r.querySelector(".row-params"));
    t("操作参数收在 row-params 行内", !!withParams,
      withParams ? `(${withParams.querySelectorAll(".fx").length} 个字段)` : "");
    const before = dcNode.params.ops.length;
    doc.querySelector("#ins-body [data-adoplist], #ins-body [data-addoplist]")?.click();
    await sleep(60);
    const after = opsOf(dcNode.id);
    t("操作列表添加一项", after === before + 1, `(${before} → ${after})`);
    // renderInspector 会重建 .ops-editor, 必须重新取节点
    t("操作列表每项可拖拽", oplHost().querySelectorAll(".ops-row .grip").length === after,
      `(${oplHost().querySelectorAll(".ops-row .grip").length}/${after})`);
  }

  // 6 撤销/重做按钮存在
  t("顶栏有撤销/重做", !!doc.querySelector("#btn-undo") && !!doc.querySelector("#btn-redo"));
  t("顶栏有运行到此", !!doc.querySelector("#btn-rununtil"));
  t("顶栏有项目配置/历史", !!doc.querySelector("#btn-project") && !!doc.querySelector("#btn-history"));
  t("会话状态标签存在", !!doc.querySelector("#sess-chip"));

  // 7 日志坞工具栏
  t("日志坞有筛选/搜索/导出", !!doc.querySelector('#dock-head [data-filter="fail"]')
    && !!doc.querySelector("#dock-search") && !!doc.querySelector("#dock-export"));

  // 7.5 旧画布(含蓝色数据连线)仍能加载渲染
  if ((S.canvas ? S.canvas.nodes : []).some((n) => (S.canvas.edges || []).some((e) => (e.kind || "data") === "data"))) {
    t("旧画布数据连线保留渲染", doc.querySelectorAll("#wires path.edge").length > 0);
  }
  // 会话控制按钮
  t("会话重开/释放按钮存在", !!doc.querySelector("#ins-sess-reopen") && !!doc.querySelector("#ins-sess-close"));

  // 8 预设已加载
  t("常用寄存器预设已加载", (S.PRESETS || []).length > 0, `(${ (S.PRESETS || []).length } 条)`);

  // 9 面板自由伸缩 (改 CSS 变量 + 记住尺寸)
  {
    const root = doc.documentElement;
    const getVar = (n) => root.style.getPropertyValue(n);
    const dragBy = (el, from, to) => {
      el.dispatchEvent(new w.MouseEvent("mousedown",
        { bubbles: true, button: 0, clientY: from, clientX: from }));
      doc.dispatchEvent(new w.MouseEvent("mousemove", { bubbles: true, clientY: to, clientX: to }));
      doc.dispatchEvent(new w.MouseEvent("mouseup", { bubbles: true }));
    };
    t("坞/属性台有拖拽条", !!doc.querySelector("#dock-resizer") && !!doc.querySelector("#ins-resizer"));

    const h0 = parseInt(getVar("--dock-h"), 10) || 0;
    dragBy(doc.querySelector("#dock-resizer"), 520, 400);      // 往上拖 -> 变高
    const h1 = parseInt(getVar("--dock-h"), 10) || 0;
    t("运行台可拖拽调高", h1 > h0, `(--dock-h ${h0} → ${h1})`);

    const w0 = parseInt(getVar("--ins-w"), 10) || 0;
    dragBy(doc.querySelector("#ins-resizer"), 900, 760);       // 往左拖 -> 变宽
    const w1 = parseInt(getVar("--ins-w"), 10) || 0;
    t("属性台可拖拽调宽", w1 > w0, `(--ins-w ${w0} → ${w1})`);

    doc.querySelector("#dock-resizer").dispatchEvent(new w.MouseEvent("dblclick", { bubbles: true }));
    doc.querySelector("#ins-resizer").dispatchEvent(new w.MouseEvent("dblclick", { bubbles: true }));
    t("双击复位到默认尺寸",
      parseInt(getVar("--dock-h"), 10) === 210 && parseInt(getVar("--ins-w"), 10) === 336,
      `(${getVar("--dock-h")} / ${getVar("--ins-w")})`);
    t("尺寸写入 localStorage",
      !!w.localStorage.getItem("newauto.dockH") && !!w.localStorage.getItem("newauto.insW"));
  }

  // 10 本 case 独立空间: 三栏 + 一键清空
  {
    const tabs = [...doc.querySelectorAll("#dock-tabs .dtab")].map((b) => b.dataset.dtab);
    t("运行台分三栏(日志/图片/历史)", tabs.join(",") === "log,img,hist", tabs.join(","));
    t("显示当前 case 名", (doc.querySelector("#dock-case").textContent || "").startsWith("case: "),
      doc.querySelector("#dock-case").textContent.trim());

    doc.querySelector('#dock-tabs .dtab[data-dtab="img"]').click();
    await sleep(700);
    const imgHost = doc.querySelector("#dock-img");
    t("图片栏 = 本 case 图片空间",
      !imgHost.classList.contains("hidden") && doc.querySelector("#dock-body").classList.contains("hidden")
        && /dk-empty|dk-imgs/.test(imgHost.innerHTML),
      imgHost.innerHTML.includes("dk-imgs") ? "(有图片)" : "(空态)");

    doc.querySelector('#dock-tabs .dtab[data-dtab="hist"]').click();
    await sleep(700);
    const histHost = doc.querySelector("#dock-hist");
    t("历史栏 = 本 case 运行记录",
      !histHost.classList.contains("hidden") && /dk-empty|hist-row/.test(histHost.innerHTML),
      histHost.innerHTML.includes("hist-row") ? "(有记录)" : "(空态)");

    doc.querySelector('#dock-tabs .dtab[data-dtab="log"]').click();
    await sleep(250);
    t("切回日志栏", !doc.querySelector("#dock-body").classList.contains("hidden")
      && doc.querySelector("#dock-logtools").style.display !== "none");

    doc.querySelector("#dock-clear").click();
    await sleep(150);
    const menu = doc.querySelector("#ctx-menu");
    const items = menu ? [...menu.querySelectorAll(".ctx-item")].map((e) => e.textContent) : [];
    t("『清空本 case』给出分项菜单",
      items.length === 4 && items.some((s) => s.includes("全部清空"))
        && items.some((s) => s.includes("运行日志")) && items.some((s) => s.includes("清空界面日志")),
      `(${items.length} 项)`);
    menu?.remove();
  }

  // 11 本 case 产物接口可用 (只读探测)
  {
    const name = S.canvas.name;
    const r = await fetch(BASE + "/api/cases/" + encodeURIComponent(name) + "/assets");
    const a = await r.json();
    t("case 产物接口 /api/cases/<case>/assets",
      r.ok && a.case === name && a.counts && typeof a.counts.images === "number",
      JSON.stringify(a.counts || {}));
  }

  // 12 收尾: 等自动保存落盘, 再把画布还原成测试前的样子 (绝不污染真实用例)
  if (BEFORE) {
    await sleep(2000);                       // 让挂起的 autosave 先跑完
    const rr = await fetch(BASE + "/api/canvases/" + encodeURIComponent(BEFORE.name), {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(BEFORE),
    });
    const back = await (await fetch(BASE + "/api/canvases/" + encodeURIComponent(BEFORE.name))).json();
    const same = JSON.stringify(back.nodes) === JSON.stringify(BEFORE.nodes)
      && JSON.stringify(back.edges || []) === JSON.stringify(BEFORE.edges || []);
    t("测试收尾: 画布已还原", rr.ok && same);
  }

  console.log("\n===== 前端冒烟测试 =====");
  results.forEach((r) => console.log("  " + r));
  console.log("\n运行期间错误:", errors.length ? "\n  " + errors.join("\n  ") : "无");
  const failed = results.filter((r) => r.startsWith("✗")).length;
  console.log(`\n结果: ${results.length - failed}/${results.length} 通过`);
  dom.window.close();
  process.exit(failed || errors.length ? 1 : 0);
})();
