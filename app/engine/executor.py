# -*- coding: utf-8 -*-
"""拓扑执行引擎: 把画布 JSON 按连线依赖顺序执行, 数据沿连线传递

画布 JSON 格式:
{
  "name": "case_上电读版本",
  "stop_on_fail": true,
  "nodes": [
    {"id": "n1", "type": "relay.on", "x": 60, "y": 60, "params": {"channel": 0}},
    ...
  ],
  "edges": [
    {"from": "n3", "fromPort": "value", "to": "n4", "toParam": "value"},
    ...
  ]
}
"""
import logging
import time

from .registry import NODES, get_node
from .session import Session

logger = logging.getLogger("new_auto.engine")


class CanvasError(Exception):
    pass


def topo_sort(nodes, edges):
    """Kahn 拓扑排序; 返回 (顺序列表, 环/缺失依赖错误)"""
    ids = {n["id"] for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for e in edges:
        src, dst = e["from"], e["to"]
        if src not in ids or dst not in ids:
            raise CanvasError(f"连线引用了不存在的节点: {e}")
        adj[src].append(dst)
        indeg[dst] += 1
    queue = [i for i in ids if indeg[i] == 0]
    order = []
    while queue:
        # 同层按画布 y 坐标稳定排序, 视觉上从上到下执行
        queue.sort(key=lambda i: (by_id[i].get("y", 0), by_id[i].get("x", 0)))
        cur = queue.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(ids):
        raise CanvasError("画布中存在环或悬空依赖, 无法执行")
    return order, by_id, adj


def run_canvas(canvas: dict, config_path=None, stop_on_fail=None, on_event=None):
    """执行一个画布

    :param on_event: 实时事件回调 fn(dict); 事件形如
        {"event":"start","id":...} / {"event":"finish","entry":{...}} / {"event":"done"}
    :return: 运行报告 dict
    """
    nodes = canvas.get("nodes", [])
    edges = canvas.get("edges", [])
    if not nodes:
        raise CanvasError("画布为空")
    if stop_on_fail is None:
        stop_on_fail = canvas.get("stop_on_fail", True)

    order, by_id, adj = topo_sort(nodes, edges)

    # 上游输出 -> (节点, 参数) 的连线索引 (执行流连线 "__" 前缀只定序, 不传数据)
    incoming = {}
    for e in edges:
        if str(e.get("toParam", "")).startswith("__"):
            continue
        incoming.setdefault(e["to"], {})[e["toParam"]] = (e["from"], e["fromPort"])

    ctx = Session(config_path)
    report = {"ok": True, "name": canvas.get("name", "unnamed"),
              "nodes": [], "log": [],
              "started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "stop_on_fail": stop_on_fail}
    outputs_by_node = {}
    aborted = False

    def emit(ev):
        if on_event:
            try:
                on_event(ev)
            except Exception:
                pass

    emit({"event": "start_total", "total": len(order)})
    try:
        for nid in order:
            node = by_id[nid]
            ntype = node.get("type")
            entry = {
                "id": nid, "type": ntype,
                "title": NODES[ntype]["title"] if ntype in NODES else ntype,
                "status": "skipped", "outputs": {}, "error": None, "ms": 0,
            }
            report["nodes"].append(entry)
            if aborted:
                emit({"event": "finish", "entry": entry})
                continue

            spec = get_node(ntype)
            # 收集上游数据
            inputs = {}
            for param, (src, port) in incoming.get(nid, {}).items():
                inputs[param] = outputs_by_node.get(src, {}).get(port)

            emit({"event": "start", "id": nid, "title": entry["title"]})
            t0 = time.time()
            try:
                outs = spec["run"](ctx, node.get("params", {}), inputs) or {}
                entry["status"] = "passed"
                entry["outputs"] = outs
                outputs_by_node[nid] = outs
            except Exception as e:
                entry["status"] = "failed"
                entry["error"] = str(e)
                logger.exception("节点 %s(%s) 执行失败", nid, ntype)
                if stop_on_fail:
                    aborted = True
            entry["ms"] = int((time.time() - t0) * 1000)
            emit({"event": "finish", "entry": entry})
    finally:
        try:
            ctx.close()
        except Exception:
            logger.exception("会话收尾异常(忽略)")

    if aborted or any(n["status"] == "failed" for n in report["nodes"]):
        report["ok"] = False
    report["finished"] = time.strftime("%H:%M:%S")
    emit({"event": "done", "ok": report["ok"]})
    return report
