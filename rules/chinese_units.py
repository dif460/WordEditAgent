"""中文排版单位换算。

常见字号 -> 磅值(pt)：
初号=42, 小初=36, 一号=26, 小一=24, 二号=22, 小二=18,
三号=16, 小三=15, 四号=14, 小四=12, 五号=10.5, 小五=9,
六号=7.5, 小六=6.5, 七号=5.5, 八号=5
"""
from __future__ import annotations

SIZE_TO_PT: dict[str, float] = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5,
}

PT_TO_SIZE: dict[float, str] = {v: k for k, v in SIZE_TO_PT.items()}

# 首行缩进“2字符” -> w:firstLineChars="200"（单位：百分之一字符）
CHAR_TO_FIRST_LINE_CHARS = 100


def size_to_pt(size: object) -> float | None:
    """把字号（中文或数值）统一换算为 pt。

    支持：
    - 数值（如 16 / "16" / "16pt"）直接返回数值
    - 中文字号（如 "三号" / "小三"）
    """
    if size is None:
        return None
    if isinstance(size, (int, float)):
        return float(size)
    s = str(size).strip()
    if s in SIZE_TO_PT:
        return SIZE_TO_PT[s]
    # 去掉单位 pt/磅/号
    cleaned = s.lower().replace("pt", "").replace("磅", "").replace("号", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def pt_to_size(pt: float) -> str:
    """pt -> 中文字号描述（用于报告展示）。"""
    if pt in PT_TO_SIZE:
        return PT_TO_SIZE[pt]
    return f"{pt:g}pt"


def first_line_indent_chars(text: str) -> str | None:
    """解析“2字符”缩进，返回 w:firstLineChars 值字符串（如 "200"）。"""
    import re

    if isinstance(text, (int, float)):
        return str(int(text * CHAR_TO_FIRST_LINE_CHARS))
    m = re.search(r"([\d.]+)\s*(?:字符|字)", str(text))
    if m:
        return str(int(float(m.group(1)) * CHAR_TO_FIRST_LINE_CHARS))
    return None
