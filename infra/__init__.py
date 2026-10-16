# infra/ - 基础设施层（异常、日志、缓存、事件总线、配置、LLM 客户端）

from infra.exceptions import (
    AppError,
    ConfigError,
    TemplateError,
    CollectionError,
    AnalysisError,
    LLMError,
    ReportError,
    PackError,
)
from infra.logger import setup_logging, get_logger
from infra.cache import CacheManager
from infra.event_bus import (
    EventBus,
    TEMPLATE_LOADED,
    DATA_COLLECTED,
    ANALYSIS_DONE,
    REPORT_GENERATED,
    PACK_DONE,
    ALL_EVENTS,
)
from infra.config import ConfigManager
from infra.llm_client import LLMClient, create_llm_client

__all__ = [
    # 异常
    "AppError",
    "ConfigError",
    "TemplateError",
    "CollectionError",
    "AnalysisError",
    "LLMError",
    "ReportError",
    "PackError",
    # 日志
    "setup_logging",
    "get_logger",
    # 缓存
    "CacheManager",
    # 事件总线
    "EventBus",
    "TEMPLATE_LOADED",
    "DATA_COLLECTED",
    "ANALYSIS_DONE",
    "REPORT_GENERATED",
    "PACK_DONE",
    "ALL_EVENTS",
    # 配置
    "ConfigManager",
    # LLM 客户端
    "LLMClient",
    "create_llm_client",
]
