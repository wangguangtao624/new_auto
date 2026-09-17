# -*- coding: utf-8 -*-
"""拖拽式自动化工具 — 本地服务 (纯标准库, 无需额外依赖)

    python app/server.py            # 默认 http://127.0.0.1:8765
    python app/server.py --port 9000

REST API:
    GET    /api/nodes                节点注册表 (分组/schema)
    GET    /api/config               config.json 内容
    GET/PUT /api/project             项目配置 (默认 ini / Release·Debug 固件)
    GET/PUT /api/presets             I²C 常用寄存器预设库
    GET    /api/ports                本机串口列表
    GET    /api/canvases             画布列表
    GET    /api/canvases/<name>      读取画布 JSON
    PUT    /api/canvases/<name>      保存画布 JSON
    DELETE /api/canvases/<name>      删除画布
    POST   /api/run/<name>           执行画布 (异步) -> {run_id}
    POST   /api/run_until/<name>     执行到指定节点为止 (含其上游依赖链)
    GET    /api/runs/<id>            轮询运行报告 (兼容旧前端)
    GET    /api/stream/<id>          SSE 实时事件流 (日志/进度)
    GET    /api/history              运行历史列表
    GET    /api/history/<id>         某次运行的完整报告 + 事件
    GET    /api/history/<id>/md      导出为 Markdown
    POST   /api/gencode/<name>       画布生成 Python 用例 (cases/<name>.py)
    GET    /api/session              常驻会话状态
    POST   /api/session              打开/关闭/重开会话
"""
import argparse
import json
import logging
import queue
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(ROOT))

from app.engine.registry import get_registry, get_node, DEBUG, NODES   # noqa: E402
from app.engine.executor import run_canvas, CanvasError         # noqa: E402
from app.engine.session import Session                          # noqa: E402
from app.engine import codegen                                  # noqa: E402
from app.engine import agent                                    # noqa: E402
from modules.log_setup import setup_logging                     # noqa: E402
from modules.image import ImageTools                            # noqa: E402
from modules import case_store                                  # noqa: E402

CANVAS_DIR = APP_DIR / "canvases"
CASES_DIR = APP_DIR / "cases"
WEB_DIR = APP_DIR / "web"
RUN_DIR = ROOT / "logs" / "runs"

logger = logging.getLogger("new_auto.server")

# 同一时间只允许一个硬件运行; RUNS 保存每次运行的实时报告与事件
_RUN_LOCK = threading.Lock()
_RUNS = {}       # run_id -> {"status","report","events","subs"}
_RUN_TTL = 3600  # 运行记录保留时长(秒)

# 常驻硬件会话: 单步调试/「运行到此节点」共用同一个 Session, 不再每次新建
_SESSION = None
_SESSION_LOCK = threading.Lock()
SESSION_IDLE_TIMEOUT = 900   # 闲置 15 分钟自动释放句柄


# ---------------------------------------------------------------- 常驻会话

def get_session(create=True, ini=None):
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None and create:
            _SESSION = Session()
            logger.info("打开常驻会话")
        s = _SESSION
    if s is not None:
        s.touch()
        if ini:
            s.current_ini = str(ROOT / "configs" / "init_file" / Path(ini).name)
    return s


def close_session():
    global _SESSION
    with _SESSION_LOCK:
        s, _SESSION = _SESSION, None
    if s is not None:
        try:
            s.close()
        except Exception:
            logger.exception("释放会话异常(忽略)")
        logger.info("已释放常驻会话")


def session_info():
    s = _SESSION
    if s is None:
        return {"open": False, "timeout": SESSION_IDLE_TIMEOUT}
    return {
        "open": True,
        "idle": round(s.idle_seconds()),
        "timeout": SESSION_IDLE_TIMEOUT,
        "ini": Path(s.current_ini).name if s.current_ini else None,
        "powered": s._powered_channel is not None,
        "device_open": bool(s._device_open),
        "video": bool(s._video_on),
    }


def _session_reaper():
    while True:
        time.sleep(60)
        try:
            s = _SESSION
            if s is not None and s.idle_seconds() > SESSION_IDLE_TIMEOUT:
                logger.info("会话闲置超时, 自动释放")
                close_session()
        except Exception:
            pass
        # 顺带清理过期运行记录
        try:
            now = time.time()
            for rid, rec in list(_RUNS.items()):
                if now - rec.get("_born", now) > _RUN_TTL and rid != _RUNS.get("_active"):
                    _RUNS.pop(rid, None)
        except Exception:
            pass


threading.Thread(target=_session_reaper, daemon=True).start()


# ---------------------------------------------------------------- 运行

def _new_run(name):
    run_id = uuid.uuid4().hex[:8]
    rec = {"status": "running", "current": None, "events": [], "_born": time.time(),
           "report": {"ok": True, "name": name, "nodes": [], "log": [],
                      "started": time.strftime("%Y-%m-%d %H:%M:%S")}}
    rec["subs"] = []
    _RUNS[run_id] = rec
    return run_id, rec


def _publish(rec, ev):
    rec["events"].append(ev)
    for q in list(rec["subs"]):
        try:
            q.put(ev)
        except Exception:
            pass


def _run_thread(run_id, canvas, stop_on_fail, use_session=False, until=None):
    rec = _RUNS[run_id]

    def on_event(ev):
        _publish(rec, ev)
        kind = ev.get("event")
        if kind == "start":
            rec["current"] = ev["id"]
            rec["report"]["log"].append(
                {"t": time.strftime("%H:%M:%S"), "cls": "run",
                 "text": f"▶ [{ev['id']}] {ev['title']} 执行中…"})
        elif kind == "finish":
            entry = ev["entry"]
            if entry["status"] == "passed":
                outs = {k: v for k, v in entry["outputs"].items() if k != "ok"}
                tail = ("  " + "  ".join(f"{k}={v}" for k, v in outs.items())) if outs else ""
                rec["report"]["log"].append(
                    {"t": time.strftime("%H:%M:%S"), "cls": "pass",
                     "text": f"✓ [{entry['id']}] {entry['title']} 通过 ({entry['ms']}ms){tail}"})
            elif entry["status"] == "failed":
                rec["report"]["log"].append(
                    {"t": time.strftime("%H:%M:%S"), "cls": "fail",
                     "text": f"✗ [{entry['id']}] {entry['title']} 失败: {entry['error']}"})
            rec["report"]["nodes"] = [
                n for n in rec["report"]["nodes"] if n["id"] != entry["id"]] + [entry]
        elif kind == "done":
            rec["report"]["log"].append(
                {"t": time.strftime("%H:%M:%S"), "cls": "run",
                 "text": "== 运行结束: " + ("全部通过 ✓" if ev["ok"] else "存在失败 ✗") + " =="})

    try:
        sess = get_session() if use_session else None
        report = run_canvas(canvas, stop_on_fail=stop_on_fail, on_event=on_event,
                            session=sess, close_session=not use_session, until=until,
                            case_name=canvas.get("name"))
        report["log"] = rec["report"].get("log", [])
        report["events"] = rec["events"]
        rec["report"].update(report)
        rec["status"] = "done"
        _save_history(run_id, rec)
    except Exception as e:
        logger.exception("运行异常")
        rec["status"] = "error"
        rec["report"]["log"].append(
            {"t": time.strftime("%H:%M:%S"), "cls": "fail", "text": f"运行异常: {e}"})
        rec["report"]["ok"] = False
        try:
            _save_history(run_id, rec)
        except Exception:
            pass
    finally:
        _publish(rec, {"event": "eof"})
        _RUN_LOCK.release()


def _save_history(run_id, rec):
    """运行历史按 case 落盘: logs/cases/<case>/runs/"""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = rec["report"].get("name", "run")
    run_dir = case_store.case_run_dir(name)
    run_dir.mkdir(parents=True, exist_ok=True)
    safe = case_store.safe_name(name)
    f = run_dir / f"{stamp}_{safe}_{run_id}.json"
    rec["file"] = str(f)
    f.write_text(json.dumps({"id": run_id, "report": rec["report"],
                             "events": rec["events"]}, ensure_ascii=False),
                 encoding="utf-8")


def _history_list(name=None):
    return case_store.list_runs(name)


def _find_run(run_id):
    return case_store.find_run(run_id)


def _report_md(rep, events):
    """把一次运行导出成 Markdown"""
    L = []
    L.append(f"# 运行报告 · {rep.get('name', 'unnamed')}")
    L.append("")
    L.append(f"- 开始: {rep.get('started')}   结束: {rep.get('finished')}")
    L.append(f"- 结果: {'全部通过 ✓' if rep.get('ok') else '存在失败 ✗'}")
    L.append(f"- 节点数: {len(rep.get('nodes', []))}")
    L.append("")
    L.append("## 节点结果")
    L.append("")
    L.append("| # | 节点 | 类型 | 结果 | 耗时(ms) | 说明 |")
    L.append("|---|---|---|---|---|---|")
    for i, n in enumerate(rep.get("nodes", []), 1):
        res = {"passed": "✓ 通过", "failed": "✗ 失败",
               "skipped": "– 跳过"}.get(n.get("status"), n.get("status"))
        L.append(f"| {i} | {n.get('title')} | `{n.get('type')}` | {res} | "
                 f"{n.get('ms')} | {str(n.get('error') or '')[:120]} |")
    L.append("")
    L.append("## 运行日志")
    L.append("")
    L.append("```")
    for ev in events or []:
        if ev.get("event") != "log":
            continue
        ts = time.strftime("%H:%M:%S", time.localtime(ev.get("ts", time.time()) / 1000))
        tag = {"error": "✗", "warn": "!"}.get(ev.get("level"), "·")
        head = f"[{ts}] {tag} {ev.get('text') or ev.get('kind')}"
        L.append(head)
        for k, v in (ev.get("fields") or {}).items():
            L.append(f"    {k:<8}{v}")
    L.append("```")
    return "\n".join(L)


# ---------------------------------------------------------------- 配置 / 预设

def _project_cfg():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg.get("project", {})


def _project_save(project):
    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["project"] = {**cfg.get("project", {}), **project}
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg["project"]


def _presets_path():
    return ROOT / _project_cfg().get("reg_presets", "configs/reg_presets.json")


def _presets_load():
    p = _presets_path()
    if not p.exists():
        return {"presets": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"presets": []}


def _demo_canvas():
    """首次启动自动生成一个可运行的示例画布 (含执行流连线)"""
    return {
        "name": "demo_上电读版本出图",
        "stop_on_fail": True,
        "nodes": [
            {"id": "n1", "type": "relay.on", "x": 60, "y": 40,
             "params": {"channel": 0}},
            {"id": "n2", "type": "device.configure", "x": 60, "y": 170, "params": {}},
            {"id": "n3", "type": "i2c.rw", "x": 60, "y": 300,
             "params": {"op": "read", "slave": "0x40", "addr": "0x00d8",
                         "value": "0x0001", "verify": True, "mode": "A2D4"}},
            {"id": "n4", "type": "flow.assert_value", "x": 400, "y": 300,
             "params": {"mask": "0x00FF0000", "shift": 16, "op": ">=", "expected": "0x4"}},
            {"id": "n5", "type": "device.open_video", "x": 60, "y": 440, "params": {}},
            {"id": "n6", "type": "device.grab_save", "x": 400, "y": 440,
             "params": {"name": "demo"}},
            {"id": "n7", "type": "device.fps", "x": 740, "y": 440, "params": {}},
            {"id": "n8", "type": "relay.off", "x": 400, "y": 570,
             "params": {"channel": 0}},
        ],
        "edges": [
            {"from": "n1", "fromPort": "__out", "to": "n2", "toParam": "__in", "kind": "flow"},
            {"from": "n2", "fromPort": "__out", "to": "n3", "toParam": "__in", "kind": "flow"},
            {"from": "n3", "fromPort": "__out", "to": "n4", "toParam": "__in", "kind": "flow"},
            {"from": "n4", "fromPort": "__out", "to": "n5", "toParam": "__in", "kind": "flow"},
            {"from": "n5", "fromPort": "__out", "to": "n6", "toParam": "__in", "kind": "flow"},
            {"from": "n6", "fromPort": "__out", "to": "n7", "toParam": "__in", "kind": "flow"},
            {"from": "n7", "fromPort": "__out", "to": "n8", "toParam": "__in", "kind": "flow"},
            {"from": "n3", "fromPort": "value", "to": "n4", "toParam": "value", "kind": "data"},
        ],
    }


def _demo_canvas_v2():
    """收敛后的示例画布: 电源开关 → 打开设备 → 读固件版本(断言 v4) → 出图检查 → 关闭"""
    return {
        "name": "示例_上电读版本出图",
        "stop_on_fail": True,
        "nodes": [
            {"id": "n1", "type": "power.ctrl", "x": 60, "y": 40,
             "params": {"action": "on", "channel": 0, "port": "",
                        "off_seconds": 15, "wait_after_on": 8}},
            {"id": "n2", "type": "device.open", "x": 60, "y": 170,
             "params": {"ini": "", "auto_power": True}},
            {"id": "n3", "type": "i2c.seq", "x": 60, "y": 300,
             "params": {"slave": "0x40", "mode": "A2D4",
                        "ops": [{"op": "read", "addr": "0x00d8", "mode": "A2D4",
                                 "value": "", "expect": "0x04", "mask": "0x00FF0000",
                                 "shift": 16, "slave": ""},
                                {"op": "read", "addr": "0x00c0", "mode": "A2D4",
                                 "value": "", "expect": "", "mask": "0xFFFFFFFF",
                                 "shift": 0, "slave": ""}]}},
            {"id": "n4", "type": "device.check", "x": 60, "y": 470,
             "params": {"ini": "",
                        "ops": [{"op": "open_video"},
                                {"op": "capture", "name": "demo"},
                                {"op": "fps", "min": "25"},
                                {"op": "dn", "min": "20", "max": "120"}]}},
            {"id": "n5", "type": "device.close", "x": 60, "y": 640,
             "params": {"power_off": False}},
            {"id": "n6", "type": "power.ctrl", "x": 60, "y": 760,
             "params": {"action": "off", "channel": 0, "port": "",
                        "off_seconds": 15, "wait_after_on": 8}},
        ],
        "edges": [
            {"from": "n1", "fromPort": "__out", "to": "n2", "toParam": "__in", "kind": "flow"},
            {"from": "n2", "fromPort": "__out", "to": "n3", "toParam": "__in", "kind": "flow"},
            {"from": "n3", "fromPort": "__out", "to": "n4", "toParam": "__in", "kind": "flow"},
            {"from": "n4", "fromPort": "__out", "to": "n5", "toParam": "__in", "kind": "flow"},
            {"from": "n5", "fromPort": "__out", "to": "n6", "toParam": "__in", "kind": "flow"},
        ],
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ 基础

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def log_message(self, fmt, *args):  # 静默默认访问日志
        pass

    # ------------------------------------------------------------ SSE

    def _stream(self, run_id):
        rec = _RUNS.get(run_id)
        if not rec:
            return self._json({"error": f"运行不存在: {run_id}"}, 404)
        self.protocol_version = "HTTP/1.0"   # 流式输出不需要 Content-Length
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        q = queue.Queue()
        rec["subs"].append(q)
        idx = 0
        try:
            # 单一数据源: 只按游标扫 rec["events"], 队列仅作为有新事件的唤醒信号
            while True:
                evs = rec["events"]
                while idx < len(evs):
                    ev = evs[idx]; idx += 1
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    if ev.get("event") == "eof":
                        return
                try:
                    q.get(timeout=0.4)   # 有新事件会立即唤醒, 否则最多等 0.4s
                    continue
                except queue.Empty:
                    self.wfile.write(b": ping\n\n"); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        finally:
            try:
                rec["subs"].remove(q)
            except ValueError:
                pass

    # ------------------------------------------------------------ 路由

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/" or path == "/index.html":
            return self._static(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if path.startswith("/web/"):
            return self._static(WEB_DIR / path[len("/web/"):])
        if path == "/api/nodes":
            return self._json({"nodes": get_registry()})
        if path == "/api/ports":
            import serial.tools.list_ports
            ports = [{"port": p.device, "desc": p.description}
                     for p in serial.tools.list_ports.comports()]
            return self._json({"ports": ports})
        if path == "/api/config":
            return self._json(json.loads((ROOT / "config.json").read_text(encoding="utf-8")))
        if path == "/api/project":
            cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            return self._json({"project": _project_cfg(),
                               "inis": sorted(p.name for p in (ROOT / "configs" / "init_file").glob("*.ini")),
                               "bins": sorted(p.name for p in (ROOT / "fw").glob("*.bin")),
                               "relay_port": cfg["relay"]["port"]})
        if path == "/api/presets":
            return self._json(_presets_load())
        if path == "/api/session":
            return self._json({"session": session_info()})
        if path == "/api/history":
            qs = parse_qs(urlparse(self.path).query)
            case = (qs.get("case") or [None])[0]
            return self._json({"history": _history_list(case), "case": case})
        if path.startswith("/api/history/") and path.endswith("/md"):
            rid = path[len("/api/history/"):-len("/md")]
            it = _find_run(rid)
            if it:
                d = json.loads(Path(it["file"]).read_text(encoding="utf-8"))
                md = _report_md(d["report"], d.get("events"))
                return self._send(200, md.encode("utf-8"),
                                  "text/markdown; charset=utf-8")
            return self._json({"error": "记录不存在"}, 404)
        if path.startswith("/api/history/"):
            rid = path[len("/api/history/"):]
            it = _find_run(rid)
            if it:
                return self._json(json.loads(Path(it["file"]).read_text(encoding="utf-8")))
            return self._json({"error": "记录不存在"}, 404)
        if path.startswith("/api/cases/") and path.endswith("/assets"):
            """本 case 的独立空间: 运行日志 + 图片"""
            name = path[len("/api/cases/"):-len("/assets")]
            return self._json(case_store.case_assets(name))
        if path == "/api/img":
            """抓帧图片列表: 传 case 则只列该 case 的图片空间"""
            qs = parse_qs(urlparse(self.path).query)
            case = (qs.get("case") or [None])[0]
            if case:
                files = case_store.list_images(case)
                return self._json({"dir": str(case_store.case_img_dir(case)),
                                   "case": case_store.safe_name(case),
                                   "files": files[:200]})
            img_dir = ROOT / agent.agent_cfg().get("img_dir", "logs/img")
            files = []
            if img_dir.is_dir():
                for p in sorted(img_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    if p.is_file() and p.suffix.lower() in case_store.IMG_SUFFIXES:
                        files.append({"name": p.name, "size": p.stat().st_size,
                                      "mtime": int(p.stat().st_mtime)})
            return self._json({"dir": str(img_dir), "files": files[:200]})
        if path.startswith("/api/img/thumb"):
            """帧文件转 PNG 预览 (带磁盘缓存); case 参数优先在该 case 目录找"""
            qs = parse_qs(urlparse(self.path).query)
            name = Path((qs.get("name") or [""])[0]).name
            case = (qs.get("case") or [None])[0]
            if case:
                f = case_store.find_image(case, name)
            else:
                img_dir = ROOT / agent.agent_cfg().get("img_dir", "logs/img")
                f = img_dir / name
            if not f.exists():
                return self._json({"error": f"图片不存在: {name}"}, 404)
            try:
                tools = ImageTools(str(f.parent))
                png = tools.convert_to_png(f)
                return self._send(200, png.read_bytes(), "image/png")
            except Exception as e:
                return self._json({"error": f"转换失败: {e}"}, 500)
        if path == "/api/agent/models":
            return self._json({"models": agent.agent_cfg().get("models", []),
                               "model": agent.agent_cfg().get("model")})
        if path == "/api/canvases":
            CANVAS_DIR.mkdir(exist_ok=True)
            names = sorted(p.stem for p in CANVAS_DIR.glob("*.json"))
            return self._json({"canvases": names})
        if path.startswith("/api/canvases/"):
            name = path[len("/api/canvases/"):]
            f = CANVAS_DIR / f"{name}.json"
            if not f.exists():
                return self._json({"error": f"画布不存在: {name}"}, 404)
            return self._json(json.loads(f.read_text(encoding="utf-8")))
        if path.startswith("/api/stream/"):
            return self._stream(path[len("/api/stream/"):])
        if path.startswith("/api/runs/"):
            run_id = path[len("/api/runs/"):]
            rec = _RUNS.get(run_id)
            if not rec:
                return self._json({"error": f"运行不存在: {run_id}"}, 404)
            return self._json({"status": rec["status"], "report": rec["report"],
                               "current": rec.get("current")})
        return self._json({"error": f"未知路径 {path}"}, 404)

    def do_PUT(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/canvases/"):
            name = path[len("/api/canvases/"):]
            CANVAS_DIR.mkdir(exist_ok=True)
            data = self._read_json()
            data["name"] = name
            f = CANVAS_DIR / f"{name}.json"
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json({"ok": True, "file": str(f)})
        if path == "/api/project":
            data = self._read_json()
            return self._json({"ok": True, "project": _project_save(data.get("project", data))})
        if path == "/api/presets":
            data = self._read_json()
            p = _presets_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json({"ok": True, "count": len(data.get("presets", []))})
        return self._json({"error": "未知路径"}, 404)

    def do_DELETE(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/canvases/"):
            name = path[len("/api/canvases/"):]
            f = CANVAS_DIR / f"{name}.json"
            if f.exists():
                f.unlink()
                return self._json({"ok": True})
            return self._json({"error": "画布不存在"}, 404)
        if path.startswith("/api/history/"):
            rid = path[len("/api/history/"):]
            it = _find_run(rid)
            if it:
                Path(it["file"]).unlink(missing_ok=True)
                return self._json({"ok": True})
            return self._json({"error": "记录不存在"}, 404)
        return self._json({"error": "未知路径"}, 404)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/agent":
            """AI 助手: 对话 + 生成画布。body: {prompt, model, history:[{role,content}]}"""
            body = self._read_json()
            prompt = str(body.get("prompt") or "").strip()
            if not prompt:
                return self._json({"error": "prompt 为空"}, 400)
            model = body.get("model") or agent.agent_cfg().get("model")
            try:
                canvas, reply = agent.agent_generate(prompt, model=model,
                                                     history=body.get("history"))
                return self._json({"reply": reply, "canvas": canvas, "model": model})
            except Exception as e:
                logger.exception("Agent 调用失败")
                return self._json({"error": f"Agent 调用失败: {e}"}, 500)
        if path == "/api/session":
            """常驻会话控制: {action: open|close|reopen, ini?}"""
            body = self._read_json()
            action = (body.get("action") or "status").lower()
            if action == "close":
                if _RUN_LOCK.locked():
                    return self._json({"error": "有运行在进行中, 不能释放会话"}, 409)
                close_session()
                return self._json({"ok": True, "session": session_info()})
            if action == "reopen":
                close_session()
            get_session(ini=body.get("ini"))
            return self._json({"ok": True, "session": session_info()})
        if path == "/api/run_node":
            """单节点调试: 复用常驻会话 (设备保持上电/已配置状态)"""
            body = self._read_json()
            ntype = body.get("type")
            if ntype not in NODES:
                return self._json({"error": f"未知节点类型 {ntype}"}, 400)
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            try:
                ctx = get_session()
                if body.get("reopen"):
                    close_session()
                    ctx = get_session(ini=body.get("ini"))
                # 单步调试的产物也归到当前画布(case)空间
                if body.get("case"):
                    try:
                        ctx.set_case(body["case"])
                    except Exception:
                        logger.warning("单节点调试绑定 case 失败: %r", body["case"])
                try:
                    outs = get_node(ntype)["run"](ctx, body.get("params", {}), {}) or {}
                    return self._json({"ok": True, "outputs": outs,
                                       "session": session_info()})
                finally:
                    ctx.set_emitter(None)
            except Exception as e:
                logger.exception("单节点调试失败")
                return self._json({"ok": False, "error": str(e)})
            finally:
                _RUN_LOCK.release()
        if path == "/api/debug":
            """节点调试动作 (如扫描串口/测试通道), 复用常驻会话"""
            body = self._read_json()
            key = f"{body.get('type')}:{body.get('action')}"
            if key not in DEBUG:
                return self._json({"error": f"未知调试动作 {key}"}, 400)
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            try:
                ctx = get_session()
                result = DEBUG[key](ctx, body.get("params", {})) or {}
                return self._json(result)
            except Exception as e:
                logger.exception("调试动作失败")
                return self._json({"ok": False, "error": str(e)})
            finally:
                _RUN_LOCK.release()
        if path.startswith("/api/cases/") and path.endswith("/clear"):
            """清空本 case 的产物: {what: "logs"|"images"|"all"}"""
            name = path[len("/api/cases/"):-len("/clear")]
            body = self._read_json()
            what = (body.get("what") or "all").lower()
            if what not in ("logs", "images", "all"):
                return self._json({"error": f"what 只能是 logs/images/all, 收到 {what}"}, 400)
            res = case_store.clear_case(name, what)
            logger.info("清空 case %s 产物 (%s): %s", name, what, res)
            return self._json({"ok": True, "case": case_store.safe_name(name),
                               "what": what, "deleted": res,
                               "assets": case_store.case_assets(name)})
        if path.startswith("/api/run_until/"):
            """运行到指定节点为止 (含上游依赖链), 会话结束后保留"""
            name = path[len("/api/run_until/"):]
            f = CANVAS_DIR / f"{name}.json"
            if not f.exists():
                return self._json({"error": f"画布不存在: {name}"}, 404)
            canvas = json.loads(f.read_text(encoding="utf-8"))
            body = self._read_json()
            until = body.get("node_id")
            if not until:
                return self._json({"error": "缺少 node_id"}, 400)
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            run_id, rec = _new_run(name)
            threading.Thread(target=_run_thread,
                             args=(run_id, canvas, True, True, until),
                             daemon=True).start()
            return self._json({"run_id": run_id})
        if path.startswith("/api/run/"):
            """异步启动运行: 返回 run_id, 前端用 /api/stream/<id> 订阅实时事件"""
            name = path[len("/api/run/"):]
            f = CANVAS_DIR / f"{name}.json"
            if not f.exists():
                return self._json({"error": f"画布不存在: {name}"}, 404)
            canvas = json.loads(f.read_text(encoding="utf-8"))
            body = self._read_json()
            stop = body.get("stop_on_fail")
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            run_id, rec = _new_run(name)
            threading.Thread(target=_run_thread,
                             args=(run_id, canvas, stop, bool(body.get("use_session"))),
                             daemon=True).start()
            return self._json({"run_id": run_id})
        if path.startswith("/api/gencode/"):
            name = path[len("/api/gencode/"):]
            f = CANVAS_DIR / f"{name}.json"
            if not f.exists():
                return self._json({"error": f"画布不存在: {name}"}, 404)
            canvas = json.loads(f.read_text(encoding="utf-8"))
            try:
                out = codegen.generate(canvas)
                return self._json({"ok": True, "file": str(out)})
            except Exception as e:
                return self._json({"error": f"代码生成失败: {e}"}, 500)
        return self._json({"error": "未知路径"}, 404)

    # ------------------------------------------------------------ 静态

    def _static(self, fpath: Path, ctype=None):
        if not fpath.exists() or not fpath.is_file():
            return self._json({"error": f"文件不存在: {fpath.name}"}, 404)
        if ctype is None:
            table = {".html": "text/html; charset=utf-8",
                     ".js": "text/javascript; charset=utf-8",
                     ".css": "text/css; charset=utf-8",
                     ".svg": "image/svg+xml"}
            ctype = table.get(fpath.suffix, "application/octet-stream")
        self._send(200, fpath.read_bytes(), ctype)


def ensure_demo():
    CANVAS_DIR.mkdir(exist_ok=True)
    CASES_DIR.mkdir(exist_ok=True)
    demo = CANVAS_DIR / "demo_上电读版本出图.json"
    if not demo.exists():
        demo.write_text(json.dumps(_demo_canvas(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        logger.info("已生成示例画布: %s", demo.name)
    v2 = CANVAS_DIR / "示例_上电读版本出图.json"
    if not v2.exists():
        v2.write_text(json.dumps(_demo_canvas_v2(), ensure_ascii=False, indent=2),
                      encoding="utf-8")
        logger.info("已生成收敛版示例画布: %s", v2.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    setup_logging(ROOT / "logs")
    ensure_demo()
    moved = case_store.migrate_legacy()
    if moved:
        logger.info("已把 %d 条旧版运行历史迁移到 logs/cases/<case>/runs/", moved)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"\n  拖拽式自动化工具已启动:  http://{args.host}:{args.port}\n"
          f"  画布目录: {CANVAS_DIR}\n"
          f"  用例目录: {CASES_DIR}\n"
          f"  用例产物(日志+图片): {case_store.CASES_ROOT}/<case>/\n"
          f"  Ctrl+C 退出\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
