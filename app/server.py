# -*- coding: utf-8 -*-
"""拖拽式自动化工具 — 本地服务 (纯标准库, 无需额外依赖)

    python app/server.py            # 默认 http://127.0.0.1:8765
    python app/server.py --port 9000

REST API:
    GET    /api/nodes                节点注册表 (分组/schema)
    GET    /api/config               config.json 内容
    GET    /api/canvases             画布列表
    GET    /api/canvases/<name>      读取画布 JSON
    PUT    /api/canvases/<name>      保存画布 JSON
    DELETE /api/canvases/<name>      删除画布
    POST   /api/run/<name>           执行画布 (同步), 返回逐节点报告
    POST   /api/gencode/<name>       画布生成 Python 用例 (cases/<name>.py)
"""
import argparse
import json
import logging
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

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

CANVAS_DIR = APP_DIR / "canvases"
CASES_DIR = APP_DIR / "cases"
WEB_DIR = APP_DIR / "web"

logger = logging.getLogger("new_auto.server")

# 同一时间只允许一个硬件运行; RUNS 保存每次运行的实时报告供前端轮询
_RUN_LOCK = threading.Lock()
_RUNS = {}   # run_id -> {"status": running|done|error, "report": {...}}


def _run_thread(run_id, canvas, stop_on_fail):
    rec = _RUNS[run_id]

    def on_event(ev):
        kind = ev.get("event")
        if kind == "start":
            rec["report"]["log"].append(
                {"t": time.strftime("%H:%M:%S"), "cls": "run",
                 "text": f"▶ [{ev['id']}] {ev['title']} 执行中…"})
            rec["current"] = ev["id"]
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
        report = run_canvas(canvas, stop_on_fail=stop_on_fail, on_event=on_event)
        # 保留 on_event 阶段积累的实时日志 (run_canvas 内部 log 为空)
        report["log"] = rec["report"].get("log", [])
        rec["report"].update(report)
        rec["status"] = "done"
    except Exception as e:
        logger.exception("运行异常")
        rec["status"] = "error"
        rec["report"]["log"].append(
            {"t": time.strftime("%H:%M:%S"), "cls": "fail", "text": f"运行异常: {e}"})
    finally:
        _RUN_LOCK.release()


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
            # 执行流 (决定执行顺序, 粗线箭头)
            {"from": "n1", "fromPort": "__out", "to": "n2", "toParam": "__in", "kind": "flow"},
            {"from": "n2", "fromPort": "__out", "to": "n3", "toParam": "__in", "kind": "flow"},
            {"from": "n3", "fromPort": "__out", "to": "n4", "toParam": "__in", "kind": "flow"},
            {"from": "n4", "fromPort": "__out", "to": "n5", "toParam": "__in", "kind": "flow"},
            {"from": "n5", "fromPort": "__out", "to": "n6", "toParam": "__in", "kind": "flow"},
            {"from": "n6", "fromPort": "__out", "to": "n7", "toParam": "__in", "kind": "flow"},
            {"from": "n7", "fromPort": "__out", "to": "n8", "toParam": "__in", "kind": "flow"},
            # 数据流 (传值, 细线)
            {"from": "n3", "fromPort": "value", "to": "n4", "toParam": "value", "kind": "data"},
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
        if path == "/api/img":
            """列出抓帧目录中的图片文件 (新->旧)"""
            img_dir = ROOT / agent.agent_cfg().get("img_dir", "logs/img")
            files = []
            if img_dir.is_dir():
                for p in sorted(img_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    if p.is_file() and p.suffix.lower() in (".uyvy", ".yuyv", ".yvyu", ".vyuy",
                                                            ".bin", ".raw", ".raw16", ".png"):
                        files.append({"name": p.name, "size": p.stat().st_size,
                                      "mtime": int(p.stat().st_mtime)})
            return self._json({"dir": str(img_dir), "files": files[:200]})
        if path.startswith("/api/img/thumb"):
            """帧文件转 PNG 预览 (带磁盘缓存)"""
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(self.path).query)
            name = Path((qs.get("name") or [""])[0]).name
            img_dir = ROOT / agent.agent_cfg().get("img_dir", "logs/img")
            f = img_dir / name
            if not f.exists():
                return self._json({"error": f"图片不存在: {name}"}, 404)
            try:
                tools = ImageTools(str(img_dir))
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
        if path == "/api/run_node":
            """单节点调试: 新建独立会话, 只执行这一个节点"""
            body = self._read_json()
            ntype = body.get("type")
            if ntype not in NODES:
                return self._json({"error": f"未知节点类型 {ntype}"}, 400)
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            try:
                ctx = Session()
                try:
                    outs = get_node(ntype)["run"](ctx, body.get("params", {}), {}) or {}
                    return self._json({"ok": True, "outputs": outs})
                finally:
                    ctx.close()
            except Exception as e:
                logger.exception("单节点调试失败")
                return self._json({"ok": False, "error": str(e)})
            finally:
                _RUN_LOCK.release()
        if path == "/api/debug":
            """节点调试动作 (如扫描串口/测试通道), 独立会话执行"""
            body = self._read_json()
            key = f"{body.get('type')}:{body.get('action')}"
            if key not in DEBUG:
                return self._json({"error": f"未知调试动作 {key}"}, 400)
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            try:
                ctx = Session()
                try:
                    result = DEBUG[key](ctx, body.get("params", {})) or {}
                    return self._json(result)
                finally:
                    ctx.close()
            except Exception as e:
                logger.exception("调试动作失败")
                return self._json({"ok": False, "error": str(e)})
            finally:
                _RUN_LOCK.release()
        if path.startswith("/api/run/"):
            """异步启动运行: 返回 run_id, 前端轮询 /api/runs/<id> 获取实时报告"""
            name = path[len("/api/run/"):]
            f = CANVAS_DIR / f"{name}.json"
            if not f.exists():
                return self._json({"error": f"画布不存在: {name}"}, 404)
            canvas = json.loads(f.read_text(encoding="utf-8"))
            body = self._read_json()
            stop = body.get("stop_on_fail")
            if not _RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "已有一次运行在进行中, 请稍候"}, 409)
            run_id = uuid.uuid4().hex[:8]
            _RUNS[run_id] = {"status": "running",
                             "report": {"ok": True, "name": name, "nodes": [], "log": [],
                                        "started": time.strftime("%H:%M:%S")},
                             "current": None}
            threading.Thread(target=_run_thread, args=(run_id, canvas, stop),
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    setup_logging(ROOT / "logs")
    ensure_demo()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"\n  拖拽式自动化工具已启动:  http://{args.host}:{args.port}\n"
          f"  画布目录: {CANVAS_DIR}\n"
          f"  用例目录: {CASES_DIR}\n"
          f"  Ctrl+C 退出\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
