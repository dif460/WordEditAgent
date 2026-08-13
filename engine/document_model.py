"""文档模型（Pydantic）。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class RunModel(BaseModel):
    text: str = ""
    font: Optional[str] = None  # 西文字体
    east_asia: Optional[str] = None  # 中文字体 (w:eastAsia)
    size: Optional[float] = None  # pt
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    color: Optional[str] = None


class ParagraphFormatModel(BaseModel):
    alignment: Optional[str] = None  # left/center/right/justify
    line_spacing: Optional[float] = None  # 1.5 表示 1.5 倍行距
    line_spacing_rule: Optional[str] = None
    first_line_indent: Optional[str] = None  # 首行缩进，如 "2字符" 或 "0.74cm"
    space_before: Optional[float] = None  # pt
    space_after: Optional[float] = None  # pt


class ParagraphModel(BaseModel):
    id: str
    text: str = ""
    style: Optional[str] = None
    outline_level: Optional[int] = None
    runs: list[RunModel] = Field(default_factory=list)
    format: ParagraphFormatModel = Field(default_factory=ParagraphFormatModel)


class SectionModel(BaseModel):
    margins: dict[str, float] = Field(default_factory=dict)  # cm
    page_size: str = "A4"
    header: str = ""
    footer: str = ""


class TableModel(BaseModel):
    id: str
    rows: int = 0
    cols: int = 0
    text: str = ""


class StyleModel(BaseModel):
    font: Optional[str] = None
    east_asia: Optional[str] = None
    size: Optional[float] = None
    bold: Optional[bool] = None


class DocumentModel(BaseModel):
    sections: list[SectionModel] = Field(default_factory=list)
    paragraphs: list[ParagraphModel] = Field(default_factory=list)
    tables: list[TableModel] = Field(default_factory=list)
    styles: dict[str, StyleModel] = Field(default_factory=dict)

    def overview(self) -> dict[str, Any]:
        """结构摘要：标题层级、段落数、样式分布。"""
        headings = [p for p in self.paragraphs if p.outline_level or (p.style or "").startswith("Heading")]
        style_counts: dict[str, int] = {}
        for p in self.paragraphs:
            key = p.style or "Normal"
            style_counts[key] = style_counts.get(key, 0) + 1
        return {
            "paragraph_count": len(self.paragraphs),
            "table_count": len(self.tables),
            "heading_count": len(headings),
            "headings": [
                {
                    "id": p.id,
                    "level": p.outline_level or _style_level(p.style),
                    "text": p.text[:60],
                    "style": p.style,
                }
                for p in headings
            ],
            "style_counts": style_counts,
        }


def _style_level(style: Optional[str]) -> Optional[int]:
    if not style:
        return None
    for lvl in (1, 2, 3, 4, 5, 6):
        if style == f"Heading {lvl}":
            return lvl
    return None
