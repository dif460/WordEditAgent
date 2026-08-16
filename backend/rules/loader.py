"""规则加载与归一化。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rules.chinese_units import size_to_pt

RULES_DIR = Path(__file__).resolve().parent


def load_rule_template(name: str) -> dict[str, Any]:
    """加载 rules/*.json 模板。"""
    path = RULES_DIR / f"{name}.json"
    if not path.exists():
        path = RULES_DIR / "default.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_template(text: str) -> str:
    """根据需求文本关键词推断规则模板。"""
    kw_map = {
        "thesis": ["论文", "学位", "毕业论文", "摘要", "参考文献"],
        "contract": ["合同", "甲方", "乙方", "协议"],
        "sop": ["sop", "流程", "标准作业", "操作规范", "作业指导"],
    }
    t = text.lower()
    for name, kws in kw_map.items():
        if any(k.lower() in t for k in kws):
            return name
    return "default"


def normalize_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """把中文单位归一化为 pt，补齐默认结构。"""
    rules = dict(rules)

    for h in rules.get("headings", []):
        h["size"] = size_to_pt(h.get("size"))
        if "bold" not in h:
            h["bold"] = True

    body = rules.get("body")
    if isinstance(body, dict):
        body["size"] = size_to_pt(body.get("size"))

    tables = rules.get("tables")
    if isinstance(tables, dict):
        tables["size"] = size_to_pt(tables.get("size"))

    special = rules.get("special")
    if isinstance(special, dict):
        for sub in special.values():
            if isinstance(sub, dict) and sub.get("size") is not None:
                sub["size"] = size_to_pt(sub.get("size"))

    return rules


def merge_rules(template: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """以 LLM 解析结果为主，模板补齐缺失字段。"""
    merged = json.loads(json.dumps(template))  # deep copy
    for key, val in parsed.items():
        if val is None:
            continue
        if key == "special" and isinstance(val, dict) and isinstance(merged.get("special"), dict):
            # special 是 {子类型: {字段...}}，按子类型深合并
            for sub_name, sub_val in val.items():
                if isinstance(sub_val, dict) and isinstance(merged["special"].get(sub_name), dict):
                    merged["special"][sub_name] = {**merged["special"][sub_name], **sub_val}
                else:
                    merged["special"][sub_name] = sub_val
        elif isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **val}
        elif isinstance(val, list) and isinstance(merged.get(key), list):
            # headings 按 level 合并
            if key == "headings":
                by_level = {h["level"]: h for h in merged.get("headings", [])}
                for h in val:
                    if isinstance(h, dict) and "level" in h:
                        by_level[h["level"]] = {**by_level.get(h["level"], {}), **h}
                merged[key] = [by_level[l] for l in sorted(by_level)]
            else:
                merged[key] = val
        else:
            merged[key] = val
    return merged
