"""工具注册：工具定义与统一调用入口。

工具实现位于 engine.controller.DocumentController；这里只负责描述与转发。
"""
from __future__ import annotations

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {"name": "read_document", "description": "读取 docx 为文档模型", "parameters": {}},
    {"name": "get_document_overview", "description": "返回标题层级、段落、样式摘要", "parameters": {}},
    {"name": "get_paragraph_detail", "description": "查看某段完整格式", "parameters": {"paragraph_id": "str"}},
    {
        "name": "set_heading_style",
        "description": "把段落设为标题样式（Heading 1/2/3 或自定义）",
        "parameters": {
            "paragraph_id": "str",
            "level": "int",
            "font": "str?",
            "east_asia": "str?",
            "size": "float?",
            "bold": "bool?",
            "alignment": "str?",
        },
    },
    {
        "name": "set_paragraph_format",
        "description": "设置对齐、缩进、行距、段前段后",
        "parameters": {
            "paragraph_id": "str",
            "alignment": "str?",
            "line_spacing": "float?",
            "first_line_indent": "str?",
            "space_before": "float?",
            "space_after": "float?",
        },
    },
    {
        "name": "set_run_font",
        "description": "设置字体、中文字体、字号、粗斜体、颜色",
        "parameters": {
            "paragraph_id": "str",
            "font": "str?",
            "east_asia": "str?",
            "size": "float?",
            "bold": "bool?",
            "italic": "bool?",
            "color": "str?",
            "run_index": "int?",
        },
    },
    {"name": "apply_style", "description": "应用命名样式", "parameters": {"paragraph_id": "str", "style_name": "str"}},
    {
        "name": "modify_style_definition",
        "description": "全局修改某样式定义",
        "parameters": {"style_name": "str", "font": "str?", "east_asia": "str?", "size": "float?", "bold": "bool?"},
    },
    {
        "name": "set_section_format",
        "description": "设置页边距、纸张、分节",
        "parameters": {"page_size": "str?", "margins": "dict?", "section_index": "int?"},
    },
    {
        "name": "set_header_footer",
        "description": "设置页眉、页脚",
        "parameters": {"header": "str?", "footer": "str?"},
    },
    {"name": "set_table_font", "description": "设置表格字体", "parameters": {"table_id": "str", "font": "str?", "east_asia": "str?", "size": "float?"}},
    {"name": "update_toc", "description": "更新目录（Word COM）", "parameters": {}},
    {"name": "save_document", "description": "保存 docx", "parameters": {"output_path": "str"}},
    {"name": "undo_last", "description": "回滚上一步", "parameters": {}},
]

TOOL_NAME_MAP = {t["name"]: t for t in TOOL_DEFINITIONS}


def call_tool(controller, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """统一工具调用入口，转发给控制器。"""
    return controller.dispatch(name, args)
