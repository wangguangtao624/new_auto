# -*- coding: utf-8 -*-
"""AI 助手: 对接 SenseNova OpenAI 兼容接口, 按用户描述生成画布 JSON

用法 (server 侧):
    from app.engine.agent import agent_chat, agent_generate
    reply = agent_chat(messages, model)                  # 普通对话
    canvas, reply = agent_generate("先上电再读版本...", model, history)

API key 读取顺序: 环境变量 SENSENOVA_API_KEY -> config.agent.api_key_file
(key 文件不入 git, 避免 key 泄漏)
"""
import json
import os
import re
import urllib.request
from pathlib import Path

from .registry import get_registry, NODES
from .session import ROOT

logger_name = "new_auto.agent"


def agent_cfg() -> dict:
    with open(ROOT / "config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("agent", {})


def load_api_key() -> str:
    key = os.environ.get("SENSENOVA_API_KEY", "")
    if key:
        return key.strip()
    cfg = agent_cfg()
    key_file = ROOT / cfg.get("api_key_file", "app/agent_key.local")
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return ""


def agent_status() -> dict:
    """返回 AI 可用性元数据，绝不返回 API Key 本身。"""
    cfg = agent_cfg()
    env_key = bool(os.environ.get("SENSENOVA_API_KEY", "").strip())
    key_file = ROOT / cfg.get("api_key_file", "app/agent_key.local")
    file_key = key_file.exists() and bool(key_file.read_text(encoding="utf-8").strip())
    return {
        "configured": env_key or file_key,
        "key_source": "environment" if env_key else ("local_file" if file_key else None),
        "key_file": str(key_file.relative_to(ROOT)),
        "base_url": cfg.get("base_url", ""),
    }


def chat_completion(messages: list, model: str = None, temperature: float = 0.3,
                    timeout: int = 180) -> str:
    """调用 OpenAI 兼容 chat/completions, 返回助手文本 (429 限流自动重试)"""
    import time
    cfg = agent_cfg()
    url = cfg.get("base_url", "https://token.sensenova.cn/v1/chat/completions")
    model = model or cfg.get("model", "deepseek-v4-flash")
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "未配置 API key: 请把 key 写入 app/agent_key.local (或设置环境变量 SENSENOVA_API_KEY)")
    body = json.dumps({"model": model, "messages": messages,
                       "stream": False, "temperature": temperature}).encode("utf-8")
    last_err = None
    for attempt in range(4):
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < 3:   # 限流: 退避重试
                wait = 6 * (attempt + 1)
                import logging
                logging.getLogger(logger_name).warning("SenseNova 限流(429), %ds 后重试", wait)
                time.sleep(wait)
                continue
            raise RuntimeError(f"SenseNova 接口错误 HTTP {e.code}: {e.read()[:200]}") from e
    raise RuntimeError(f"SenseNova 限流重试后仍失败: {last_err}")


# ---------------------------------------------------------------- 画布生成

def _condensed_schema() -> str:
    """把节点注册表压缩成给大模型看的精简 schema"""
    out = []
    for n in get_registry():
        if n.get("hidden"):
            continue
        params = []
        for p in n["params"]:
            item = {"name": p["name"], "type": p["type"],
                    "default": p.get("default")}
            if p.get("options"):
                opts = [o["v"] if isinstance(o, dict) else o for o in p["options"]]
                item["options"] = opts[:12]
            params.append(item)
        out.append({"type": n["type"], "title": n["title"], "desc": n["desc"],
                    "params": params, "inputs": list(n["inputs"]),
                    "outputs": list(n["outputs"])})
    return json.dumps(out, ensure_ascii=False)


def build_system_prompt() -> str:
    ini_files = sorted(p.name for p in (ROOT / "configs" / "init_file").glob("*.ini"))
    return (
        "你是「相机模组自动化测试画布」的生成助手。用户用自然语言描述测试意图,"
        "你输出画布 JSON。\n"
        "严格只输出一个 JSON 对象, 不要 markdown 代码块, 不要任何解释文字。格式:\n"
        '{"name":"用例名","nodes":[{"id":"n1","type":"节点类型","x":80,"y":0,"params":{}}],'
        '"edges":[{"from":"n1","fromPort":"__out","to":"n2","toParam":"__in","kind":"flow"}]}\n'
        "规则:\n"
        '1. 执行顺序用 kind="flow" 的执行流连线, fromPort 固定 "__out", toParam 固定 "__in",'
        "按用户描述的步骤先后依次相连\n"
        '2. 需要把上游输出传给下游参数时用 kind="data" 数据连线,'
        "fromPort=上游输出端口名, toParam=下游输入参数名\n"
        "3. 坐标: 按执行顺序 x=100, y 每步 +150; x/y 必须是数字\n"
        "4. params 的键名和取值只能用下方 schema 列出的参数, 不要发明参数; "
        "布尔参数用 true/false\n"
        "5. 优先使用合并节点: 继电器用 relay.ctrl(动作在 params.action 选 on/off/cycle), "
        "I2C 多条读写+断言用 i2c.batch(写在 params.ops, 每行一条), "
        "出图+抓帧+FPS 用 device.stream(勾选项 capture/read_fps/read_dn)\n"
        "6. 不要添加用户没提的步骤; i2c.batch 的 ops 里每行一条指令\n\n"
        "节点 schema:\n" + _condensed_schema() +
        "\n\n可用 ini 文件: " + ", ".join(ini_files) +
        "\n常用固件寄存器 (slave 0x40): 0x00d8 固件版本(A2D4, 主版本=(值&0xFF0000)>>16), "
        "0x00c0/0x00c4 启动信息(A2D4), 0x00cc 帧计数器(A2D4, 递增), "
        "0x0918/0x091c AWB/AE 开关(A2D2), 0x093c/0x0940 功能安全(A2D2)"
    )


def extract_json(text: str) -> dict:
    """从模型回复中提取画布 JSON (容忍 ```json 围栏与前后杂文本)"""
    text = re.sub(r"```(?:json)?|```", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型回复中没有找到 JSON 画布")
    data = json.loads(text[start:end + 1])
    return normalize_canvas(data)


def normalize_canvas(data: dict) -> dict:
    """校验/修正模型输出的画布: 类型过滤、参数收敛、坐标兜底、边引用检查"""
    valid = {n["type"] for n in get_registry()}
    nodes, seen = [], set()
    dropped = []
    for n in data.get("nodes", []):
        ntype = n.get("type")
        if ntype not in NODES or n["id"] in seen:
            dropped.append(ntype)
            continue
        seen.add(n["id"])
        spec = NODES[ntype]
        allowed = {p["name"]: p for p in spec["params"]}
        params = {}
        for k, v in (n.get("params") or {}).items():
            if k in allowed:
                params[k] = v
        # 补默认值
        for p in spec["params"]:
            if p["name"] not in params and p.get("default") is not None:
                params[p["name"]] = p["default"]
        nodes.append({"id": str(n.get("id") or f"n{len(nodes)+1}"),
                      "type": ntype,
                      "x": float(n.get("x", 100)) if isinstance(n.get("x"), (int, float)) else 100,
                      "y": float(n.get("y", len(nodes) * 150)) if isinstance(n.get("y"), (int, float)) else len(nodes) * 150,
                      "params": params})
    edges = []
    ids = {n["id"] for n in nodes}
    for e in data.get("edges", []):
        if e.get("from") in ids and e.get("to") in ids and e.get("from") != e.get("to"):
            edges.append({"from": e["from"], "fromPort": e.get("fromPort", "__out"),
                          "to": e["to"], "toParam": e.get("toParam", "__in"),
                          "kind": e.get("kind", "data")})
    if dropped:
        data.setdefault("_notes", []).append(f"已忽略不支持的节点类型: {dropped}")
    data["nodes"], data["edges"] = nodes, edges
    if not nodes:
        raise ValueError("模型没有生成任何有效节点")
    return data


def agent_generate(user_prompt: str, model: str = None, history: list = None):
    """对话生成画布: 返回 (canvas, 助手回复文本)"""
    messages = [{"role": "system", "content": build_system_prompt()}]
    for m in (history or [])[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:4000]})
    messages.append({"role": "user",
                     "content": str(user_prompt)[:4000] + "\n\n请生成画布 JSON。"})
    reply = chat_completion(messages, model=model)
    canvas = extract_json(reply)
    canvas["name"] = canvas.get("name") or "ai_case"
    return canvas, reply
