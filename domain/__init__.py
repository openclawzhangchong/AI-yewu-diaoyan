"""domain — 业务调研提效分析系统领域模型"""

from domain.analysis import (
    AnalysisResult,
    FullAnalysisReport,
    OpportunityPoint,
)
from domain.config import (
    AnalysisConfig,
    Config,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)
from domain.report import (
    DepartmentReport,
    ReportSection,
)
from domain.template import (
    BusinessTemplate,
    Question,
    QuestionType,
)

__all__ = [
    # template
    "QuestionType",
    "Question",
    "BusinessTemplate",
    # analysis
    "AnalysisResult",
    "OpportunityPoint",
    "FullAnalysisReport",
    # report
    "ReportSection",
    "DepartmentReport",
    # config
    "Config",
    "ModelConfig",
    "AnalysisConfig",
    "LoggingConfig",
    "OutputConfig",
]
