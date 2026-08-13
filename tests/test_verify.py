from engine.document_model import DocumentModel, ParagraphFormatModel, ParagraphModel, RunModel
from verify.rule_check import check_rules


def _para(pid, text, level, font, size, alignment=None, line_spacing=None, indent=None, bold=None):
    runs = [RunModel(text=text, font=font, east_asia=font, size=size, bold=bold)]
    fmt = ParagraphFormatModel(
        alignment=alignment, line_spacing=line_spacing, first_line_indent=indent
    )
    return ParagraphModel(id=pid, text=text, outline_level=level, runs=runs, format=fmt)


def test_rule_check_pass():
    model = DocumentModel(
        paragraphs=[
            _para("p_0001", "第一章 绪论", 1, "黑体", 16, alignment="center", bold=True),
            _para("p_0002", "正文内容。", None, "宋体", 12, alignment="justify", line_spacing=1.5, indent="2字符"),
        ]
    )
    rules = {
        "headings": [{"level": 1, "font": "黑体", "size": 16, "bold": True, "alignment": "center"}],
        "body": {"font": "宋体", "size": 12, "line_spacing": 1.5, "first_line_indent": "2字符", "alignment": "justify"},
    }
    report = check_rules(model, rules)
    assert report["ok"] is True, report["issues"]


def test_rule_check_fail():
    model = DocumentModel(
        paragraphs=[
            _para("p_0001", "正文内容。", None, "楷体", 14, alignment="left", line_spacing=1.0, indent="0字符"),
        ]
    )
    rules = {"body": {"font": "宋体", "size": 12, "line_spacing": 1.5, "alignment": "justify"}}
    report = check_rules(model, rules)
    assert report["ok"] is False
    fields = {i["field"] for i in report["issues"]}
    assert "font" in fields
    assert "size" in fields
