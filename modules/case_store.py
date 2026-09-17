# -*- coding: utf-8 -*-
"""用例(case)产物存储: 每个 case 拥有独立的日志与图片空间

目录结构::

    logs/cases/<case 名>/
        runs/   每次运行的报告 + 事件 (json, 可导出 Markdown)
        img/    抓帧 / 出图检查落盘的图片
    logs/runs/*.json     旧版历史 (仍可读取, 首次启动自动迁移进 case 目录)

一个 case = 一个画布, 所以「清空本 case」= 删掉这个目录下的 runs/ 与 img/,
不会碰到其它 case 的产物。
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_ROOT = ROOT / "logs" / "cases"
LEGACY_RUN_DIR = ROOT / "logs" / "runs"

# 抓帧/出图落盘的图片后缀 (与 modules/image.py 保持一致)
IMG_SUFFIXES = (".uyvy", ".yuyv", ".yvyu", ".vyuy", ".bin", ".raw", ".raw16", ".png")

_BAD = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_name(name) -> str:
    """把画布名压成安全的目录名 (与画布文件名同规则: 只去掉非法字符)"""
    s = _BAD.sub("_", str(name or "")).strip().strip(".")
    return (s[:60] or "unnamed").strip()


def case_dir(name) -> Path:
    return CASES_ROOT / safe_name(name)


def case_run_dir(name) -> Path:
    return case_dir(name) / "runs"


def case_img_dir(name) -> Path:
    return case_dir(name) / "img"


def ensure_case(name) -> Path:
    """建立 case 目录 (runs/ + img/)"""
    d = case_dir(name)
    case_run_dir(name).mkdir(parents=True, exist_ok=True)
    case_img_dir(name).mkdir(parents=True, exist_ok=True)
    return d


def list_images(name, limit=None):
    """某 case 的图片 (新 -> 旧)"""
    d = case_img_dir(name)
    out = []
    if d.is_dir():
        for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file() and p.suffix.lower() in IMG_SUFFIXES:
                st = p.stat()
                out.append({"name": p.name, "size": st.st_size,
                            "mtime": int(st.st_mtime), "path": str(p),
                            "case": safe_name(name)})
    return out[:limit] if limit else out


def find_image(name, fname) -> Path:
    """在 case 目录里找图片; 找不到再回落到默认目录 (兼容旧产物)"""
    p = case_img_dir(name) / Path(fname).name
    if p.exists():
        return p
    from .image import default_img_dir
    p2 = Path(default_img_dir()) / Path(fname).name
    return p2


def list_runs(name=None, limit=None):
    """运行历史: case 目录优先, 同时兼容旧版 logs/runs。

    :param name: 只列某个 case 的历史; None = 全部
    """
    items = []
    paths = []
    if name:
        paths += list(case_run_dir(name).glob("*.json"))
    else:
        paths += list(CASES_ROOT.glob("*/runs/*.json"))
        for p in CASES_ROOT.glob("*/runs/*/*.json"):     # 兜底: 更深一层
            if p not in paths:
                paths.append(p)
    paths += list(LEGACY_RUN_DIR.glob("*.json"))
    for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            import json
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        rep = d.get("report", {})
        rname = rep.get("name")
        if name and rname != name:
            continue
        items.append({
            "id": d.get("id") or p.stem, "name": rname,
            "started": rep.get("started"), "finished": rep.get("finished"),
            "ok": rep.get("ok"), "nodes": len(rep.get("nodes", [])),
            "failed": sum(1 for n in rep.get("nodes", []) if n.get("status") == "failed"),
            "file": str(p), "mtime": int(p.stat().st_mtime),
            "case": safe_name(rname) if rname else None,
        })
    return items[:limit] if limit else items


def find_run(run_id):
    for it in list_runs():
        if it["id"] == run_id:
            return it
    return None


def case_assets(name):
    """某 case 的全部产物概览 (前端的「本 case 空间」用)"""
    runs = list_runs(name)
    imgs = list_images(name)
    passed = sum(1 for r in runs if r.get("ok"))
    return {
        "case": safe_name(name),
        "dir": str(case_dir(name)),
        "img_dir": str(case_img_dir(name)),
        "runs": runs[:100],
        "images": imgs[:200],
        "counts": {"runs": len(runs), "images": len(imgs),
                   "passed": passed, "failed": len(runs) - passed,
                   "img_bytes": sum(i["size"] for i in imgs)},
    }


def clear_case(name, what="all"):
    """清空本 case 的产物

    :param what: "logs"(运行历史) | "images"(图片) | "all"
    :return: {"runs": 删除条数, "images": 删除文件数, "bytes": 释放字节}
    """
    res = {"runs": 0, "images": 0, "bytes": 0}
    if what in ("logs", "all"):
        for it in list_runs(name):
            try:
                p = Path(it["file"])
                res["bytes"] += p.stat().st_size
                p.unlink()
                res["runs"] += 1
            except Exception:
                pass
    if what in ("images", "all"):
        d = case_img_dir(name)
        if d.is_dir():
            for p in d.iterdir():
                if p.is_file():
                    try:
                        res["bytes"] += p.stat().st_size
                        p.unlink()
                        res["images"] += 1
                    except Exception:
                        pass
        # 顺手清掉图片转 PNG 的缩略缓存 (_thumbs)
        cache = d / "_thumbs"
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
    return res


def migrate_legacy():
    """旧版 logs/runs/*.json -> logs/cases/<case>/runs/ (只搬一次)"""
    moved = 0
    if not LEGACY_RUN_DIR.is_dir():
        return moved
    for p in list(LEGACY_RUN_DIR.glob("*.json")):
        try:
            import json
            d = json.loads(p.read_text(encoding="utf-8"))
            name = d.get("report", {}).get("name")
            if not name:
                continue
            dst_dir = case_run_dir(name)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / p.name
            if dst.exists():
                dst = dst_dir / (p.stem + "_dup" + p.suffix)
            shutil.move(str(p), str(dst))
            moved += 1
        except Exception:
            continue
    return moved
