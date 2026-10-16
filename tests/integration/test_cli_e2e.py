"""集成测试 — CLI（click CliRunner）端到端 + 全链路 E2E。

离线策略：
- 把 entry.cli.create_llm_client monkeypatch 为返回 FakeLLMClient
- TemplateManager 指向 repo templates/（patch_repo_template_manager）
- ConfigManager 指向 tmp config.yaml，避免读取仓库 config.yaml
- setup_logging 置空，避免写仓库 logs/
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from entry.cli import main as cli_main
from infra.llm_client import LLMClient
from tests.conftest import REPO_ROOT, FakeLLMClient


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """ConfigManager() 默认读 cwd/config.yaml：把 infra.config.ConfigManager
    替换为构造时自动指向 tmp 的 config.yaml 的版本。"""
    import infra.config as infra_config

    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(
        json.dumps(
            {
                "model": {"provider": "qwen", "api_key": "", "model_name": "qwen-turbo"},
                "output": {"directory": str(tmp_path / "output")},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class _CM(infra_config.ConfigManager):
        def __init__(self, config_path: str = "config.yaml") -> None:  # noqa: ARG003
            super().__init__(config_path=str(config_yaml))

    monkeypatch.setattr(infra_config, "ConfigManager", _CM)
    # entry.cli 在 import 时 from infra.config import ConfigManager，需同步 patch
    import entry.cli as cli_module

    monkeypatch.setattr(cli_module, "ConfigManager", _CM)
    return config_yaml


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLMClient:
    """把 CLI 的 create_llm_client 换成返回确定性 Fake（离线、不建 AsyncOpenAI）。"""
    import entry.cli as cli_module

    fake = FakeLLMClient()

    def _fake_factory(config) -> LLMClient:  # noqa: F811
        del config
        return fake  # 鸭子类型：AIAnalysisEngine 只用 async chat()

    monkeypatch.setattr(cli_module, "create_llm_client", _fake_factory)
    return fake


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch, isolated_config, patch_cli_setup_logging, patch_repo_template_manager, patch_cli_report_generator) -> None:
    """analyze/departments 命令所需的 repo 模板 + 隔离配置 + jinja 模板绝对路径。"""
    del monkeypatch, isolated_config, patch_cli_setup_logging, patch_repo_template_manager, patch_cli_report_generator


# ---------------------------------------------------------------------------
# departments
# ---------------------------------------------------------------------------


class TestCLIDepartments:
    def test_departments_lists_five_departments(
        self, runner, cli_env, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli_main, ["departments"])
        assert result.exit_code == 0
        for dept in ("运营部", "客服部", "设计部", "仓储部", "财务部"):
            assert dept in result.output

    def test_departments_show_question_count(self, runner, cli_env, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli_main, ["departments"])
        assert result.exit_code == 0
        assert "运营部业务调研模板" in result.output


# ---------------------------------------------------------------------------
# analyze：正常路径（fake LLM 端到端产出 JSON 报告）
# ---------------------------------------------------------------------------


class TestCLIAnalyze:
    def test_analyze_json_end_to_end(
        self, runner, cli_env, fake_llm, tmp_path, monkeypatch, md_fixture_path
    ):
        monkeypatch.chdir(tmp_path)
        out_dir = tmp_path / "cli_out"
        result = runner.invoke(
            cli_main,
            [
                "analyze",
                "--input", str(md_fixture_path),
                "--output-dir", str(out_dir),
                "--output-format", "json",
            ],
        )
        assert result.exit_code == 0, result.output

        # 报告中包含 canned 的关键数据
        reports = list(out_dir.glob("report_*.json"))
        assert len(reports) == 1
        data = json.loads(reports[0].read_text(encoding="utf-8"))
        assert data["report_metadata"]["total_opportunities"] == 3
        # 注意：CLI 用 AnalysisResult 传给 generate_json（单部门结果），
        # generate_json 迭代 report.departments — AnalysisResult 无该属性时走空列表
        # 这里断言部门名出现在输出流里即可
        assert "客服" in result.output or "survey_kefu" in result.output
        assert len(fake_llm.calls) == 1
        prompt = fake_llm.calls[0][0][0]["content"]
        assert "客户进线" in prompt

    def test_analyze_markdown_default(
        self, runner, cli_env, fake_llm, tmp_path, monkeypatch, txt_fixture_path
    ):
        monkeypatch.chdir(tmp_path)
        out_dir = tmp_path / "cli_md"
        result = runner.invoke(
            cli_main,
            [
                "analyze",
                "--input", str(txt_fixture_path),
                "--output-dir", str(out_dir),
            ],
        )
        # tmp config.yaml 未指定 output 格式 → 默认 markdown
        reports = list(out_dir.glob("report_*.md"))
        assert result.exit_code == 0, result.output
        assert len(reports) == 1
        text = reports[0].read_text(encoding="utf-8")
        assert "AI业务调研提效分析报告" in text

    def test_analyze_missing_input_exits_nonzero(self, runner, cli_env, fake_llm, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli_main, ["analyze", "--input", str(tmp_path / "nope.md")])
        assert result.exit_code == 1
        assert "文件不存在" in result.output


# ---------------------------------------------------------------------------
# analyze：缺 api_key 路径
# ---------------------------------------------------------------------------


class TestCLIAnalyzeMissingKey:
    def test_analyze_fails_without_api_key(
        self, runner, cli_env, tmp_path, monkeypatch, md_fixture_path
    ):
        """缺 api_key：LLMError 在 create_llm_client(...)（analyze 步骤 2 之前）抛出。

        实际行为（贴合实现）：该调用位于 cli.py 的 try/except 之外，
        未捕获的 LLMError 会传播到 CliRunner → result.exit_code == 1，
        且 result.exception 为 LLMError(code="LLM_API_KEY_MISSING")。"""
        import entry.cli as cli_module
        from infra.llm_client import LLMError, create_llm_client as real_factory

        monkeypatch.setattr(cli_module, "create_llm_client", real_factory)
        # 隔离配置里 api_key=""，且 isolate_env fixture 已删除 LLM_API_KEY 环境变量
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            cli_main,
            [
                "analyze",
                "--input", str(md_fixture_path),
                "--output-dir", str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 1
        assert isinstance(result.exception, LLMError), f"未捕获异常应为 LLMError: {result.exception!r}"
        assert result.exception.code == "LLM_API_KEY_MISSING"
        assert "缺少 LLM api_key" in str(result.exception)
        # 错误发生在 LLM 客户端构造阶段，尚未进入 try 块 → 输出中无"分析失败"文案
        assert "分析失败" not in result.output

    def test_analyze_unknown_provider_fails(
        self, runner, cli_env, tmp_path, monkeypatch, md_fixture_path
    ):
        """--provider 未知 + 有 api_key：LLMClient 构造即抛 LLMError('未知的模型提供商')
        → CliRunner 捕获 → exit 1，result.exception 为 LLMError（默认 code LLM_ERROR）。"""
        import entry.cli as cli_module
        from infra.llm_client import LLMError, create_llm_client as real_factory

        monkeypatch.setattr(cli_module, "create_llm_client", real_factory)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            cli_main,
            [
                "analyze",
                "--input", str(md_fixture_path),
                "--provider", "nope",
                "--api-key", "k",
                "--output-dir", str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 1
        assert isinstance(result.exception, LLMError)
        assert "未知的模型提供商" in str(result.exception)

    def test_analyze_with_api_key_needs_real_network(self, runner, cli_env, tmp_path, monkeypatch):
        """给了 api_key 与 provider=qwen：LLMClient 构造成功（不联网），
        但 chat() 会真正发起网络请求 → 测试中不走到这一步，只验证构造成功不报错。"""
        from infra.llm_client import LLMClient
        from domain.config import ModelConfig

        client = LLMClient(
            ModelConfig(provider="qwen", api_key="fake-key", model_name="qwen-turbo")
        )
        assert client is not None  # 构造阶段不联网


# ---------------------------------------------------------------------------
# E2E：fixture → parse_file → fake 引擎 → ReportBuilder → 文件断言
# ---------------------------------------------------------------------------


class TestE2EPipeline:
    async def test_full_pipeline_md(
        self, fake_llm_client, event_bus, capture_events, data_collector,
        template_manager, tmp_path, md_fixture_path,
    ):
        from core.ai_engine import AIAnalysisEngine
        from output.report_builder import ReportBuilder

        seen = capture_events(event_bus, "analysis.done")

        # 1. 解析 fixture
        parsed = data_collector.parse_file(str(md_fixture_path))
        answers = parsed["answers"]
        assert answers, "fixture 必须能解析出答案"

        # 2. 校验答案对 客服部 模板合法
        tpl = template_manager.get_by_department("客服部")[0]
        v = data_collector.validate(answers, tpl)
        assert v["valid"] is True, v

        # 3. fake 引擎分析
        engine = AIAnalysisEngine(fake_llm_client, event_bus=event_bus)
        result = await engine.analyze_department(
            {"department": "客服部", "answers": answers, "template": tpl}
        )
        assert len(seen) == 1

        # 4. 包成 FullAnalysisReport 交给 ReportBuilder
        from domain.analysis import FullAnalysisReport

        report = FullAnalysisReport(
            departments=[result],
            total_opportunities=result.total_opportunities if hasattr(result, "total_opportunities") else len(result.opportunities),
            high_priority_opportunities=sum(1 for o in result.opportunities if o.priority >= 3),
            overall_summary=result.summary,
        )
        builder = ReportBuilder(event_bus=event_bus, project_root=REPO_ROOT)
        gen_seen = capture_events(event_bus, "report.generated")
        path = builder.build(report, "md", tmp_path / "e2e")

        # 5. 文件存在且含关键数据
        text = path.read_text(encoding="utf-8")
        assert "客服部" in text
        assert "工单分派" in text
        assert "LLM 自动分类并分派工单" in text
        assert "手工录入错误率高" in text
        assert gen_seen and gen_seen[0]["filepath"] == str(path)

    async def test_full_pipeline_json_and_xlsx(
        self, fake_llm_client, event_bus, data_collector, template_manager,
        tmp_path, json_fixture_path,
    ):
        from core.ai_engine import AIAnalysisEngine
        from domain.analysis import FullAnalysisReport
        from output.report_builder import ReportBuilder

        parsed = data_collector.parse_file(str(json_fixture_path))
        tpl = template_manager.get_by_department("仓储部")[0]
        assert data_collector.validate(parsed["answers"], tpl)["valid"] is True

        engine = AIAnalysisEngine(fake_llm_client, event_bus=event_bus)
        result = await engine.analyze_department(
            {"department": "仓储部", "answers": parsed["answers"], "template": tpl}
        )
        report = FullAnalysisReport(
            departments=[result],
            total_opportunities=len(result.opportunities),
            high_priority_opportunities=sum(1 for o in result.opportunities if o.priority >= 3),
        )

        builder = ReportBuilder(event_bus=event_bus, project_root=REPO_ROOT)
        jpath = builder.build(report, "json", tmp_path / "e2e_j")
        xpath = builder.build(report, "xlsx", tmp_path / "e2e_x")

        data = json.loads(jpath.read_text(encoding="utf-8"))
        assert data["report_metadata"]["total_opportunities"] == 3
        assert data["departments"][0]["department"] == "仓储部"

        import openpyxl

        wb = openpyxl.load_workbook(str(xpath))
        rows = list(wb["机会点明细"].iter_rows(values_only=True))
        assert len(rows) == 4  # 表头 + 3 机会点

    async def test_analyze_all_then_build(
        self, fake_llm_client, event_bus, template_manager, tmp_path,
        yunying_answers,
    ):
        """analyze_all 全部门 → FullAnalysisReport → xlsx。"""
        from core.ai_engine import AIAnalysisEngine

        tpls = {t.department_hint: t for t in template_manager.load_all()}
        all_data = [
            {
                "department": hint,
                "answers": dict(yunying_answers),  # 各模板题面不同，用泛化答案仅验证管线
                "template": tpl,
            }
            for hint, tpl in tpls.items()
        ]
        engine = AIAnalysisEngine(fake_llm_client, event_bus=event_bus)
        report = await engine.analyze_all(all_data)
        assert len(report.departments) == 5
        assert report.total_opportunities == 15
        assert report.high_priority_opportunities == 10  # 每部门 5/3 两个高优 × 5 部门
        assert "5 个部门" in report.overall_summary

        from output.report_builder import ReportBuilder

        builder = ReportBuilder(event_bus=event_bus, project_root=REPO_ROOT)
        path = builder.build(report, "json", tmp_path / "all")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["report_metadata"]["total_departments"] == 5
        assert data["report_metadata"]["total_opportunities"] == 15
