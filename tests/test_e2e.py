"""端到端测试：完整 Agent 流程（需要 DeepSeek 网络，且可选 Word COM）。"""
from __future__ import annotations

import os

import pytest

from agent.graph import run_agent
from engine.reader import read_document
from scripts.generate_sample import generate_sample


@pytest.mark.e2e
def test_full_flow(tmp_path):
    sample = str(tmp_path / "sample.docx")
    generate_sample(sample)

    result = run_agent(
        file_path=sample,
        requirements="标题黑体三号居中，正文宋体小四，1.5倍行距，首行缩进2字符，两端对齐",
        task_id="e2e_test",
    )

    assert result.get("output_path")
    assert os.path.exists(result["output_path"])

    report = result.get("report", {})
    rule_check = report.get("verification", {}).get("rule_check", {})
    assert rule_check.get("checked", 0) > 0

    model = read_document(result["output_path"])
    assert len(model.paragraphs) >= 4

    # 标题应改为黑体
    heading = next(p for p in model.paragraphs if p.outline_level == 1)
    assert heading.runs[0].east_asia == "黑体"
