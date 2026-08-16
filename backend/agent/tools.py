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
        "description": "设置对齐、缩进、行距、悬挂缩进、段前段后",
        "parameters": {
            "paragraph_id": "str",
            "alignment": "str?",
            "line_spacing": "float?",
            "first_line_indent": "str?",
            "hanging_indent": "str?",
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
    {
        "name": "set_page_number",
        "description": "添加页码（底端居中，小五号 Times New Roman）",
        "parameters": {"alignment": "str?", "font": "str?", "size": "float?"},
    },
    {"name": "set_table_font", "description": "设置表格字体", "parameters": {"table_id": "str", "font": "str?", "east_asia": "str?", "size": "float?"}},
    {"name": "set_table_alignment", "description": "设置表格整体对齐方式", "parameters": {"table_id": "str", "alignment": "str?"}},
    {"name": "update_toc", "description": "更新目录（Word COM）", "parameters": {}},
    {"name": "save_document", "description": "保存 docx", "parameters": {"output_path": "str"}},
    {"name": "undo_last", "description": "回滚上一步", "parameters": {}},
    # 新增：三线表转换
    {"name": "convert_table_to_three_line", "description": "表格转为标准三线表（删除左右竖线，上下1磅粗线，中间0.75磅细线）", "parameters": {"table_id": "str"}},
    {"name": "set_table_cell_alignment", "description": "设置表格所有单元格文字对齐方式", "parameters": {"table_id": "str", "alignment": "str?"}},
    # 新增：标点半角清洗
    {"name": "normalize_punctuation", "description": "将段落中中文全角标点替换为英文半角", "parameters": {"paragraph_id": "str"}},
    # 新增：批量西文字体替换
    {"name": "batch_replace_latin_font", "description": "段落中数字/英文批量替换为 Times New Roman", "parameters": {"paragraph_id": "str"}},
    # 新增：分页与空行
    {"name": "insert_page_break_before", "description": "段落前插入分页符", "parameters": {"paragraph_id": "str"}},
    {"name": "add_blank_after", "description": "段落后插入空行", "parameters": {"paragraph_id": "str"}},
    # 新增：日期清洗
    {"name": "normalize_date", "description": "清洗日期文本多余空格", "parameters": {"paragraph_id": "str"}},
    # 新增：关键词分隔符
    {"name": "normalize_keywords", "description": "关键词分隔符统一为英文半角分号", "parameters": {"paragraph_id": "str"}},
    # 新增：图片标准化
    {"name": "normalize_image", "description": "图片尺寸标准化（不超过最大宽高）", "parameters": {"paragraph_id": "str"}},
    # 新增：公式处理
    {"name": "strip_trailing_punctuation", "description": "移除公式段落末尾多余标点", "parameters": {"paragraph_id": "str"}},
    {"name": "fix_formula_citation", "description": "修正公式引用上浮标注", "parameters": {"paragraph_id": "str"}},
    # 新增：图表编号重排
    {"name": "renumber_figures_tables", "description": "图/表编号全文重排为连续递增", "parameters": {}},
    # 新增：段落前后空行
    {"name": "ensure_blank_around", "description": "段落前后插入空行分隔", "parameters": {"paragraph_id": "str"}},
]

TOOL_NAME_MAP = {t["name"]: t for t in TOOL_DEFINITIONS}


def call_tool(controller, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """统一工具调用入口，转发给控制器。"""
    return controller.dispatch(name, args)
