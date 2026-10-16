"""共享 fixtures — 供 tests/ 下所有测试使用。

所有 fixture 均离线、确定性，不产生网络请求：
- fake_llm_client 实现与 LLMClient 相同的 async chat() 接口
- TemplateManager 指向 repo root 下真实 templates/ 目录（绝对路径，任意 cwd 可跑）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from domain.analysis import AnalysisResult, FullAnalysisReport, OpportunityPoint  # noqa: E402
from domain.config import (  # noqa: E402
    AnalysisConfig,
    Config,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)
from domain.template import BusinessTemplate, Question, QuestionType  # noqa: E402
from infra.cache import CacheManager  # noqa: E402
from infra.event_bus import EventBus  # noqa: E402
from core.template_manager import TemplateManager  # noqa: E402
from infra.llm_client import LLMClient  # noqa: E402


# ---------------------------------------------------------------------------
# LLM 桩
# ---------------------------------------------------------------------------

# 确定性 canned 响应：3 个机会点（优先级 5/3/1），2 个痛点
SAMPLE_LLM_RESPONSE = json.dumps(
    {
        "pain_points": ["手工录入错误率高", "报表汇总依赖人工"],
        "opportunities": [
            {
                "department": "客服部",
                "process": "工单分派",
                "current_process": "人工阅读工单后手动分派",
                "ai_suggestion": "LLM 自动分类并分派工单",
                "expected_efficiency_gain": "提效 40%",
                "difficulty": "中",
                "priority": 5,
                "expected_roi": "2.5",
                "timeline": "4周",
            },
            {
                "department": "客服部",
                "process": "报表汇总",
                "current_process": "每日人工拉数汇总",
                "ai_suggestion": "自动生成智能日报",
                "expected_efficiency_gain": "提效 30%",
                "difficulty": "低",
                "priority": 3,
                "expected_roi": "1.8",
                "timeline": "2周",
            },
            {
                "department": "客服部",
                "process": "话术质检",
                "current_process": "抽检人工听录音",
                "ai_suggestion": "全量自动质检",
                "expected_efficiency_gain": "提效 50%",
                "difficulty": "高",
                "priority": 1,
            },
        ],
        "summary": "客服部存在多个可自动化环节",
        "confidence": 0.85,
    },
    ensure_ascii=False,
)


class FakeLLMClient:
    """与 LLMClient 接口一致的确定性桩客户端（离线、无网络）。

    - chat() 为 async，签名与 LLMClient.chat 相同
    - 默认返回 SAMPLE_LLM_RESPONSE，可通过 canned 覆盖
    - delay 参数用于并发测试（asyncio.sleep）
    - calls 记录每次调用的 (messages, temperature, max_tokens)
    - peak_concurrency 记录 chat 最大并发数
    - fail_with 非空时所有调用抛该异常（用于错误路径测试）
    """

    def __init__(
        self,
        canned: str = SAMPLE_LLM_RESPONSE,
        fail_with: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.canned = canned
        self.fail_with = fail_with
        self.delay = delay
        self.calls: list[tuple[list[dict], float, int]] = []
        self._active = 0
        self.peak_concurrency = 0

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        import asyncio

        self.calls.append((messages, temperature, max_tokens))
        self._active += 1
        self.peak_concurrency = max(self.peak_concurrency, self._active)
        try:
            if self.fail_with is not None:
                raise self.fail_with
            if self.delay:
                await asyncio.sleep(self.delay)
            return self.canned
        finally:
            self._active -= 1


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()


# 兼容类型注解：AIAnalysisEngine.__init__ 标注 llm_client: LLMClient，
# 但实际调用只依赖 duck-typed async chat()，FakeLLMClient 可直接注入。


# ---------------------------------------------------------------------------
# 基础域对象 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> Config:
    return Config(
        model=ModelConfig(
            provider="openai",
            api_key="test-key",
            base_url="http://localhost:0",
            model_name="test-model",
        ),
        analysis=AnalysisConfig(max_concurrent=3, timeout_seconds=60),
        logging=LoggingConfig(level="DEBUG", file="./logs/test.log", max_bytes=1024, backup_count=1),
        output=OutputConfig(directory="./output_test", default_format="json"),
    )


@pytest.fixture
def sample_template() -> BusinessTemplate:
    return BusinessTemplate(
        title="测试模板",
        description="用于单元测试的调研模板",
        department_hint="测试部",
        questions=[
            Question(
                id="Q1",
                text="请描述业务流程",
                question_type=QuestionType.BUSINESS_PROCESS,
                required=True,
                description="分环节描述",
            ),
            Question(
                id="Q2",
                text="数据产生频次",
                question_type=QuestionType.BUSINESS_PROCESS,
                required=True,
                options=["每天", "每周", "每月"],
            ),
            Question(
                id="Q3",
                text="最大痛点",
                question_type=QuestionType.PAIN_POINT,
                required=False,
            ),
        ],
    )


@pytest.fixture
def sample_answers(sample_template: BusinessTemplate) -> dict[str, str]:
    """能通过 sample_template.validate() 的答案：必填齐全，选项合法。"""
    return {
        "Q1": "接需求→排期→开发→测试→上线，各环节人工交接",
        "Q2": "每天",
        "Q3": "手工统计耗时长，口径不一致",
    }


@pytest.fixture
def sample_opportunity() -> OpportunityPoint:
    return OpportunityPoint(
        department="客服部",
        process="工单分派",
        current_process="人工阅读工单后手动分派",
        ai_suggestion="LLM 自动分类并分派工单",
        expected_efficiency_gain="提效 40%",
        difficulty="中",
        priority=5,
        expected_roi="2.5",
        timeline="4周",
    )


@pytest.fixture
def sample_analysis_result(sample_opportunity: OpportunityPoint) -> AnalysisResult:
    """3 个机会点（优先级 5/3/1），与 SAMPLE_LLM_RESPONSE 的 canned 结果一致。"""
    return AnalysisResult(
        department="客服部",
        process="工单处理",
        pain_points=["手工录入错误率高", "报表汇总依赖人工"],
        opportunities=[
            sample_opportunity,
            OpportunityPoint(
                department="客服部",
                process="报表汇总",
                current_process="每日人工拉数汇总",
                ai_suggestion="自动生成智能日报",
                expected_efficiency_gain="提效 30%",
                difficulty="低",
                priority=3,
                expected_roi="1.8",
                timeline="2周",
            ),
            OpportunityPoint(
                department="客服部",
                process="话术质检",
                current_process="抽检人工听录音",
                ai_suggestion="全量自动质检",
                expected_efficiency_gain="提效 50%",
                difficulty="高",
                priority=1,
            ),
        ],
        summary="客服部存在多个可自动化环节",
        confidence=0.85,
        raw_insights=["工单量日均 500+"],
    )


@pytest.fixture
def sample_full_report(
    sample_analysis_result: AnalysisResult,
    sample_opportunity: OpportunityPoint,
) -> FullAnalysisReport:
    """2 个部门，共 5 个机会点（优先级 5/3/1 + 4/2）。

    total = 5，high_priority(>=3) = 3（5、3、4）。
    """
    result2 = AnalysisResult(
        department="财务部",
        process="报表",
        pain_points=["月末手工对账"],
        opportunities=[
            OpportunityPoint(
                department="财务部",
                process="报表汇总",
                current_process="月末人工汇总",
                ai_suggestion="自动生成管理报表",
                expected_efficiency_gain="提效 60%",
                difficulty="低",
                priority=4,
            ),
            OpportunityPoint(
                department="财务部",
                process="发票录入",
                current_process="手工录票",
                ai_suggestion="OCR 自动识别发票",
                expected_efficiency_gain="提效 50%",
                difficulty="中",
                priority=2,
            ),
        ],
        summary="财务月末结账存在自动化空间",
        confidence=0.75,
    )
    return FullAnalysisReport(
        departments=[sample_analysis_result, result2],
        total_opportunities=5,
        high_priority_opportunities=3,
        overall_summary="本次对 2 个部门进行了 AI 提效分析分析，共识别出 5 个提效机会点。",
        generated_at="2026-10-16 00:00:00",
    )


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


# ---------------------------------------------------------------------------
# 模板 / 采集 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_templates_dir() -> Path:
    return REPO_ROOT / "templates"


@pytest.fixture
def template_manager(repo_templates_dir: Path) -> TemplateManager:
    """加载 repo 下 5 个真实部门模板的 TemplateManager（绝对路径）。"""
    tm = TemplateManager(template_dir=str(repo_templates_dir))
    loaded = tm.load_all()
    assert len(loaded) == 5, f"应加载 5 个部门模板，实际: {len(loaded)}"
    return tm


class _RepoTemplateManager(TemplateManager):
    """CLI 内构造 TemplateManager() 时使用：强制指向 repo 的 templates/。"""

    def __init__(self, *args, **kwargs):  # 忽略 CLI 传参，统一指向 repo
        super().__init__(template_dir=str(REPO_ROOT / "templates"))


@pytest.fixture
def patch_repo_template_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 entry.cli 中的 TemplateManager 替换为指向 repo templates/ 的版本。"""
    import entry.cli as cli_module

    monkeypatch.setattr(cli_module, "TemplateManager", _RepoTemplateManager)


@pytest.fixture
def patch_cli_setup_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁用 CLI 的 setup_logging，避免测试期间向仓库 logs/ 写文件。"""
    import entry.cli as cli_module

    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **k: None)


@pytest.fixture
def patch_cli_report_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """让 CLI 内 ReportGenerator 使用 repo 的 templates/ 绝对路径（jinja 模板）。

    CLI 默认 templates_dir="templates"（相对 CWD）；测试 cwd 不确定，
    这里统一指向 repo 根下 templates/，使 generate_markdown 可离线运行。"""
    import entry.cli as cli_module

    real_cls = cli_module.ReportGenerator

    def factory(event_bus=None):
        return real_cls(templates_dir=str(REPO_ROOT / "templates"), event_bus=event_bus)

    monkeypatch.setattr(cli_module, "ReportGenerator", factory)


@pytest.fixture
def yunying_template(template_manager: TemplateManager) -> BusinessTemplate:
    tpl = template_manager.get_template("运营部业务调研模板")
    assert tpl is not None
    return tpl


@pytest.fixture
def yunying_answers() -> dict[str, str]:
    """能通过 运营部模板 validate() 的完整答案（必填 + 合法选项）。"""
    return {
        "Q1": "活动策划→内容排期→发布分发→数据回收→周复盘，各环节人工衔接",
        "Q2": "运营 6 人，数据回收单环节每天约 2 小时",
        "Q3": "数据口径不一致，活动复盘慢，内容生产依赖人工",
        "Q4": "每天",
        "Q5": "智能数据报表",
    }


# ---------------------------------------------------------------------------
# 报告生成 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def report_generator(template_manager: "TemplateManager") -> "object":
    """真实 ReportGenerator，jinja 模板目录指向 repo 的 templates/（绝对路径）。"""
    from core.report_generator import ReportGenerator

    return ReportGenerator(templates_dir=str(REPO_ROOT / "templates"))


# ---------------------------------------------------------------------------
# 样例文件 fixtures（tests/fixtures/）
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def md_fixture_path() -> Path:
    return FIXTURES_DIR / "survey_kefu.md"


@pytest.fixture
def txt_fixture_path() -> Path:
    return FIXTURES_DIR / "survey_caiwu.txt"


@pytest.fixture
def json_fixture_path() -> Path:
    return FIXTURES_DIR / "survey_cangchu.json"


# ---------------------------------------------------------------------------
# 缓存 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache_manager(tmp_path: Path) -> CacheManager:
    return CacheManager(db_path=str(tmp_path / "cache.db"))


# ---------------------------------------------------------------------------
# 数据采集 fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def data_collector(event_bus: EventBus):
    from core.data_collector import DataCollector

    return DataCollector(event_bus=event_bus)


# ---------------------------------------------------------------------------
# 隔离环境变量（防止宿主机 LLM_API_KEY 等渗入测试）
# ---------------------------------------------------------------------------

_ENV_KEYS = [
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL_NAME",
    "MAX_CONCURRENT",
    "TIMEOUT_SECONDS",
    "LOG_LEVEL",
    "LOG_FILE",
    "OUTPUT_DIR",
    "OUTPUT_FORMAT",
]


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch):
    """每个测试前删除项目相关环境变量，保证离线 + 确定性。"""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


# ---------------------------------------------------------------------------
# 事件辅助
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_events() -> Callable:
    """返回一个闭包：订阅指定事件并把 payload 收集进 list（同步 handler，publish 内立即执行）。"""

    def _capture(event_bus: EventBus, event_type: str) -> list:
        seen: list = []
        event_bus.subscribe(event_type, lambda data: seen.append(data))
        return seen

    return _capture
