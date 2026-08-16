"""段落类型分类器：识别论文中各类段落（标题/题目/图片/公式/表格/参考文献/致谢/附录/图表标题等）。

独立于 agent 与 verify，避免循环依赖；由 nodes（规划）与 rule_check（校验）共用。
"""
from __future__ import annotations

import re
from typing import Optional

from engine.document_model import DocumentModel

# 标题识别正则（按优先级）
HEADING_PATTERNS: list[tuple[int, re.Pattern]] = [
    (1, re.compile(r"^第[一二三四五六七八九十百千0-9]+章")),
    (2, re.compile(r"^第[一二三四五六七八九十百千0-9]+节")),
    (3, re.compile(r"^\d+\.\d+\.\d+")),
    (2, re.compile(r"^\d+\.\d+")),
    (1, re.compile(r"^\d+\s+\S")),  # “1  前言”：序号后空格、无标点
    (2, re.compile(r"^[一二三四五六七八九十]+、")),
    (3, re.compile(r"^（[一二三四五六七八九十]+）")),
    (2, re.compile(r"^\d+[、.．]\s*")),
]

# 特殊段落识别正则
RE_REFERENCES_HEADING = re.compile(r"^参考文献\s*$")
RE_ACK_HEADING = re.compile(r"^致\s*谢\s*$")
RE_APPENDIX_HEADING = re.compile(r"^附\s*录\s*[:：]?\s*$")
RE_ABSTRACT = re.compile(r"^摘\s*要")
RE_KEYWORDS = re.compile(r"^关\s*键\s*词")
RE_ABSTRACT_EN = re.compile(r"^Abstract[:：]?", re.IGNORECASE)
RE_KEYWORDS_EN = re.compile(r"^Key\s*words[:：]?", re.IGNORECASE)
RE_REF_ENTRY = re.compile(r"^\[\d+\]")
RE_FIGURE = re.compile(r"^图\s*\d+")
RE_TABLE = re.compile(r"^表\s*\d+")

# 新增：封面/声明/小标题/日期等识别
RE_COVER_KEYWORD = re.compile(r"本科毕业论文|毕业设计|学士学位|四川农业大学|开题报告")
RE_DECLARATION = re.compile(r"原创|独创|声明|版权|授权")
RE_SUB_HEADING = re.compile(r"^[（(][\d一二三四五六七八九十]+[）)]")
RE_DATE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
RE_ENGLISH_TITLE = re.compile(r"^[A-Z][a-zA-Z\s\-:]+$")  # 全英文行（用于识别英文标题）
RE_ENGLISH_AUTHOR = re.compile(r"^[A-Z][a-z]+[\s\-][A-Z]")  # 英文作者名


def match_heading_pattern(text: str) -> Optional[int]:
    if len(text) > 50:
        return None
    for lvl, pat in HEADING_PATTERNS:
        if pat.match(text):
            return lvl
    return None


def classify_paragraphs(model: DocumentModel) -> dict[str, tuple[str, Optional[int]]]:
    """识别每段类型。返回 pid -> (kind, level)。

    kind 取值：empty / heading / body / title / image / formula /
    abstract_body / keywords / references_heading / references_entry /
    acknowledgement_heading / appendix_heading / figure_caption / table_caption /
    cover / declaration / sub_heading / english_abstract / english_keywords /
    english_title / english_author / date_text。

    优先使用 Word 自身的 outline_level / Heading 样式，其次用文本正则匹配。
    """
    result: dict[str, tuple[str, Optional[int]]] = {}
    in_references = False
    in_cover = True  # 前 N 段视为封面区域
    first_nonempty_seen = False
    cover_para_count = 0

    for p in model.paragraphs:
        text = p.text.strip()

        if not text:
            # 空段落但含图片/公式：仍按图片/公式处理
            kind = "empty"
            if p.has_image:
                kind = "image"
            elif p.has_formula:
                kind = "formula"
            result[p.id] = (kind, None)
            continue

        is_first_nonempty = not first_nonempty_seen
        kind: str = "body"
        level: Optional[int] = None

        # 封面区域检测（前 10 个非空段落中含封面关键词）
        if in_cover and cover_para_count < 10:
            cover_para_count += 1
            if RE_COVER_KEYWORD.search(text) or RE_DECLARATION.search(text):
                if RE_DECLARATION.search(text):
                    kind = "declaration"
                else:
                    kind = "cover"
                result[p.id] = (kind, None)
                first_nonempty_seen = True
                continue
            elif cover_para_count >= 10:
                in_cover = False

        # 先检测图片/公式（段落含嵌入式对象，不论文本内容）
        if p.has_image:
            kind = "image"
        elif p.has_formula:
            kind = "formula"
        # 新增：日期文本
        elif RE_DATE.search(text):
            kind = "date_text"
        # 新增：声明标题
        elif RE_DECLARATION.search(text) and len(text) <= 30:
            kind = "declaration"
        elif RE_REFERENCES_HEADING.match(text):
            kind, in_references = "references_heading", True
        elif RE_ACK_HEADING.match(text):
            kind, in_references = "acknowledgement_heading", False
        elif RE_APPENDIX_HEADING.match(text):
            kind, in_references = "appendix_heading", False
        # 新增：英文标题/摘要/关键词
        elif RE_ABSTRACT_EN.match(text):
            kind = "english_abstract"
        elif RE_KEYWORDS_EN.match(text):
            kind = "english_keywords"
        elif RE_ENGLISH_TITLE.match(text) and len(text) > 5 and len(text) <= 80:
            kind = "english_title"
        elif RE_ENGLISH_AUTHOR.match(text) and len(text) <= 40:
            kind = "english_author"
        elif RE_ABSTRACT.match(text):
            kind = "abstract_body"
        elif RE_KEYWORDS.match(text):
            kind = "keywords"
        elif RE_REF_ENTRY.match(text) and in_references:
            kind = "references_entry"
        elif RE_FIGURE.match(text):
            kind = "figure_caption"
        elif RE_TABLE.match(text):
            kind = "table_caption"
        # 新增：小标题（1）（2）等
        elif RE_SUB_HEADING.match(text):
            kind = "sub_heading"
        else:
            # 优先使用 Word 自身的 outline_level / Heading 样式
            if p.outline_level is not None:
                kind, level = "heading", p.outline_level
            elif (p.style or "").startswith("Heading"):
                lvl = _parse_heading_style_level(p.style)
                if lvl is not None:
                    kind, level = "heading", lvl
            if kind == "body":
                # 文本正则匹配兜底
                lvl = match_heading_pattern(text)
                if lvl is not None:
                    kind, level = "heading", lvl
                elif is_first_nonempty and len(text) <= 50:
                    kind = "title"

        result[p.id] = (kind, level)
        first_nonempty_seen = True

    return result


def _parse_heading_style_level(style: Optional[str]) -> Optional[int]:
    """从 'Heading 1' / 'Heading 2' 等样式名提取层级。"""
    if not style:
        return None
    m = re.match(r"^Heading\s+(\d+)$", style)
    return int(m.group(1)) if m else None
