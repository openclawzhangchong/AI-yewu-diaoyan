"""域模型单元测试 — domain/template, domain/analysis, domain/config。"""

from __future__ import annotations

from domain.analysis import AnalysisResult, FullAnalysisReport, OpportunityPoint
from domain.config import AnalysisConfig, Config, LoggingConfig, ModelConfig, OutputConfig
from domain.template import BusinessTemplate, Question, QuestionType


class TestQuestionType:
    def test_values(self):
        assert QuestionType.BUSINESS_PROCESS.value == "business_process"
        assert QuestionType.PAIN_POINT.value == "pain_point"
        assert QuestionType.AI_OPPORTUNITY.value == "ai_opportunity"
        assert QuestionType.RESOURCE.value == "resource"
        assert QuestionType.EXPECTATION.value == "expectation"

    def test_is_str_enum(self):
        # str 混合：可直接与字符串比较
        assert QuestionType.PAIN_POINT == "pain_point"
        assert QuestionType("pain_point") is QuestionType.PAIN_POINT


class TestQuestion:
    def test_defaults(self):
        q = Question(id="Q1", text="问题?", question_type=QuestionType.PAIN_POINT)
        assert q.required is True
        assert q.options == []
        assert q.description is None

    def test_full_construct(self):
        q = Question(
            id="Q2",
            text="频次?",
            question_type=QuestionType.BUSINESS_PROCESS,
            required=False,
            options=["每天", "每周"],
            description="提示",
        )
        assert q.options == ["每天", "每周"]
        assert q.required is False
        assert q.description == "提示"


class TestBusinessTemplate:
    def test_defaults(self):
        t = BusinessTemplate(title="T", description="D")
        assert t.questions == []
        assert t.department_hint is None

    def test_construct(self, sample_template):
        assert sample_template.title == "测试模板"
        assert len(sample_template.questions) == 3
        assert sample_template.department_hint == "测试部"


class TestOpportunityPoint:
    def test_defaults(self):
        op = OpportunityPoint(
            department="客服部",
            process="分派",
            current_process="人工",
            ai_suggestion="LLM",
            expected_efficiency_gain="40%",
            difficulty="中",
        )
        assert op.priority == 0
        assert op.expected_roi is None
        assert op.timeline is None

    def test_full(self, sample_opportunity):
        assert sample_opportunity.priority == 5
        assert sample_opportunity.expected_roi == "2.5"
        assert sample_opportunity.timeline == "4周"


class TestAnalysisResult:
    def test_defaults(self):
        r = AnalysisResult(department="D", process="P")
        assert r.pain_points == []
        assert r.opportunities == []
        assert r.summary == ""
        assert r.confidence == 0.0
        assert r.raw_insights is None

    def test_construct(self, sample_analysis_result):
        assert sample_analysis_result.department == "客服部"
        assert len(sample_analysis_result.opportunities) == 3
        assert sample_analysis_result.confidence == 0.85


class TestFullAnalysisReport:
    def test_defaults(self):
        r = FullAnalysisReport()
        assert r.departments == []
        assert r.total_opportunities == 0
        assert r.high_priority_opportunities == 0
        assert r.overall_summary == ""
        assert r.generated_at is None

    def test_construct(self, sample_full_report):
        assert len(sample_full_report.departments) == 2
        assert sample_full_report.total_opportunities == 5
        assert sample_full_report.high_priority_opportunities == 3
        assert sample_full_report.generated_at == "2026-10-16 00:00:00"


class TestConfig:
    def test_nested_defaults(self):
        c = Config()
        assert c.model.provider == "qwen"
        assert c.model.api_key == ""
        assert c.model.model_name == "qwen-turbo"
        assert c.analysis.max_concurrent == 4
        assert c.analysis.timeout_seconds == 120
        assert c.logging.level == "INFO"
        assert c.logging.max_bytes == 10485760
        assert c.output.directory == "./output"
        assert c.output.default_format == "markdown"

    def test_independent_factories(self):
        # dataclass default_factory：两个实例不共享子对象
        a, b = Config(), Config()
        a.model.api_key = "x"
        assert b.model.api_key == ""
        assert a.analysis is not b.analysis

    def test_explicit_construct(self, sample_config):
        assert sample_config.model.provider == "openai"
        assert sample_config.model.api_key == "test-key"
        assert sample_config.analysis.max_concurrent == 3
        assert sample_config.output.default_format == "json"


class TestDomainReportDataclasses:
    def test_report_section_default(self):
        from domain.report import ReportSection

        s = ReportSection(title="t", content="c")
        assert s.subsections == []

    def test_department_report_defaults(self):
        from domain.report import DepartmentReport

        d = DepartmentReport(department="D")
        assert d.executive_summary == ""
        assert d.pain_points == []
        assert d.opportunities == []
        assert d.sections == []
