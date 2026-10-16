"""应用配置定义 — Config"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelConfig:
    """模型配置"""

    provider: str = "qwen"  # 模型提供商: openai / qwen / zhipu
    api_key: str = ""  # API密钥
    base_url: str = ""  # 基础URL
    model_name: str = "qwen-turbo"  # 模型名称


@dataclass
class AnalysisConfig:
    """分析配置"""

    max_concurrent: int = 4  # 最大并发数
    timeout_seconds: int = 120  # 超时秒数


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"  # 日志级别
    file: str = "./logs/app.log"  # 日志文件路径
    max_bytes: int = 10485760  # 日志文件大小上限 (10MB)
    backup_count: int = 5  # 备份数量


@dataclass
class OutputConfig:
    """输出配置"""

    directory: str = "./output"  # 输出目录
    default_format: str = "markdown"  # 默认输出格式


@dataclass
class Config:
    """应用配置"""

    model: ModelConfig = field(default_factory=ModelConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

