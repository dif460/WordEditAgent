from rules.chinese_units import first_line_indent_chars, size_to_pt
from rules.loader import load_rule_template, merge_rules, normalize_rules


def test_size_to_pt_chinese():
    assert size_to_pt("三号") == 16
    assert size_to_pt("小四") == 12
    assert size_to_pt("五号") == 10.5
    assert size_to_pt("小三") == 15


def test_size_to_pt_number():
    assert size_to_pt(12) == 12
    assert size_to_pt("12pt") == 12


def test_first_line_indent_chars():
    assert first_line_indent_chars("2字符") == "200"
    assert first_line_indent_chars("2字") == "200"


def test_load_rule_template():
    t = load_rule_template("thesis")
    assert t["name"] == "thesis"
    assert t["body"]["size"] == 12


def test_normalize_rules():
    rules = {"headings": [{"level": 1, "font": "黑体", "size": "三号"}], "body": {"font": "宋体", "size": "小四"}}
    n = normalize_rules(rules)
    assert n["headings"][0]["size"] == 16
    assert n["body"]["size"] == 12


def test_merge_rules():
    template = load_rule_template("default")
    parsed = {"body": {"font": "仿宋"}}
    merged = merge_rules(template, parsed)
    assert merged["body"]["font"] == "仿宋"
    assert merged["body"]["size"] == 12  # 保留模板默认
