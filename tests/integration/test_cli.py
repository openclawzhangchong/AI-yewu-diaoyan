"""CLI 集成测试 — entry.cli 经 click.testing.CliRunner 端到端（LLM 全部打桩，离线）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import entry.cli as cli_module
from tests.conftest import FakeLLMClient, REPO_ROOT


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def patched_cli(monkeypatch):
    """CLI 集成通用打桩：模板指向 repo、日志不落盘、LLM 桩、报告生成器桩。"""
    from tests.conftest import _RepoTemplateManager

    monkeypatch.setattr(cli_module, "TemplateManager", _RepoTemplateManager)
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **k: None)

    fake_llm = FakeLLMClient()
    monkeypatch.setattr(cli_module, "create_llm_client", lambda cfg: fake_llm)

    fake_reporter = _make_fake_report_generator()
    monkeypatch.setattr(cli_module, "ReportGenerator", lambda **kwargs: fake_reporter)
    return {"llm": fake_llm, "reporter": fake_reporter}


def _make_fake_report_generator():
    """duck-type 桩，复刻 conftest 的 fake_report_generator（不写脏 CWD）。"""

    def _as_full(report):
        from domain.analysis import AnalysisResult, FullAnalysisReport

        if isinstance(report, FullAnalysisReport):
            return report
        return FullAnalysisReport(departments=[report])

    class _Fake:
        def __init__(self):
            self.outputs: list = []

        def generate_markdown(self, report):
            full = _as_full(report)
            text = f"# 报告\n部门: {[d.department for d in full.departments]}"
            self.outputs.append(text)
            return text

        def generate_excel(self, report, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            import openpyxl

            wb = openpyxl.Workbook()
            wb.active.title = "执行摘要"
            wb.save(str(filepath))
            self.outputs.append(str(filepath))
            return str(filepath)

        def generate_json(self, report, filepath):
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            full = _as_full(report)
            payload = {
                "departments": [
                    {
                        "department": d.department,
                        "pain_points": d.pain_points,
                        "opportunities": [
                            {"process": o.process, "priority": o.priority}
                            for o in d.opportunities
                        ],
                        "confidence": d.confidence,
                    }
                    for d in full.departments
                ],
            }
            Path(filepath).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.outputs.append(str(filepath))
            return str(filepath)

    return _Fake()


# ---------------------------------------------------------------------------
# departments
# ---------------------------------------------------------------------------


class TestDepartmentsCommand:
    def test_lists_five_departments(self, runner, patched_cli):
        result = runner.invoke(cli_module.main, ["departments"])
        assert result.exit_code == 0, result.output
        for dept in ("运营部", "客服部", "设计部", "仓储部", "财务部"):
            assert dept in result.output
        # 每个部门模板标题出现
        for title in ("运营部业务调研模板", "客服部业务调研模板"):
            assert title in result.output


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


class TestAnalyzeCommand:
    def test_analyze_json_end_to_end(self, runner, patched_cli, md_fixture_path, tmp_path):
        out_dir = tmp_path / "cli_out"
        result = runner.invoke(
            cli_module.main,
            [
                "analyze",
                "--input", str(md_fixture_path),
                "--output-dir", str(out_dir),
                "--output-format", "json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "分析完成" in result.output

        json_files = list(out_dir.glob("report_*.json"))
        assert len(json_files) == 1, result.output
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert data["departments"][0]["department"] == "survey_kefu"  # 输入文件 stem
        assert len(data["departments"][0]["opportunities"]) == 3
        assert data["departments"][0]["pain_points"]
        # LLM 桩确实被调用（离线）
        assert len(patched_cli["llm"].calls) == 1

    def test_analyze_markdown_default(self, runner, patched_cli, json_fixture_path, tmp_path):
        out_dir = tmp_path / "md_out"
        result = runner.invoke(
            cli_module.main,
            ["analyze", "--input", str(json_fixture_path), "--output-dir", str(out_dir)],
        )
        assert result.exit_code == 0, result.output
        md_files = list(out_dir.glob("report_*.md"))
        assert len(md_files) == 1
        assert "survey_cangchu" in md_files[0].read_text(encoding="utf-8")  # 输入文件 stem

    def test_analyze_excel(self, runner, patched_cli, txt_fixture_path, tmp_path):
        out_dir = tmp_path / "xlsx_out"
        result = runner.invoke(
            cli_module.main,
            [
                "analyze",
                "--input", str(txt_fixture_path),
                "--output-dir", str(out_dir),
                "--output-format", "excel",
            ],
        )
        assert result.exit_code == 0, result.output
        xlsx_files = list(out_dir.glob("report_*.xlsx"))
        assert len(xlsx_files) == 1

    def test_analyze_missing_input_file(self, runner, patched_cli, tmp_path):
        result = runner.invoke(
            cli_module.main,
            ["analyze", "--input", str(tmp_path / "nope.md")],
        )
        assert result.exit_code == 1

    def test_analyze_no_answers_exits_1(self, runner, patched_cli, tmp_path):
        f = tmp_path / "empty_survey.md"
        f.write_text("# 只有标题，没有答案\n", encoding="utf-8")
        result = runner.invoke(
            cli_module.main,
            ["analyze", "--input", str(f), "--output-dir", str(tmp_path / "o")],
        )
        assert result.exit_code == 1
        assert "未找到有效的调研数据" in result.output


# ---------------------------------------------------------------------------
# quick-start（非交互路径：stdin 提供输入）
# ---------------------------------------------------------------------------


class TestQuickStartCommand:
    def test_quick_start_guided_flow(self, runner, patched_cli, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # 示例文件写到 tmp 而非仓库
        # 输入序列：API Key 留空 + 模型选择 1(Qwen)
        result = runner.invoke(cli_module.main, ["quick-start"], input="\n1\n")
        assert result.exit_code == 0, result.output
        # 示例文件已创建（CWD = tmp_path）
        example = tmp_path / "调研总结.md"
        assert example.is_file()
        assert "python main.py analyze --input" in result.output


# ---------------------------------------------------------------------------
# help / 透传
# ---------------------------------------------------------------------------


class TestCliBasics:
    def test_help_lists_commands(self, runner, patched_cli):
        result = runner.invoke(cli_module.main, ["--help"])
        assert result.exit_code == 0
        for cmd in ("analyze", "collect", "departments", "quick-start"):
            assert cmd in result.output
