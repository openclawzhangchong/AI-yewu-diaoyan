"""结构化 JSON 日志 — 基于 python-json-logger"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from python_json_logger import JsonFormatter

# 全局日志器
_logger = logging.getLogger("ai-efficiency")

_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: str = "./logs/app.log",
    max_bytes: int = 10485760,
    backup_count: int = 5,
) -> logging.Logger:
    """配置结构化日志并返回 logger。

    Args:
        level: 日志级别字符串 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径
        max_bytes: 单文件最大大小
        backup_count: 备份数量
    """
    global _initialized

    if _initialized:
        return _logger

    _logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # JSON 格式化
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "module",
            "message": "message",
        },
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)

    # 文件输出（带轮转）
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    _initialized = True
    return _logger


def get_logger() -> logging.Logger:
    """获取已初始化的 logger，若未初始化则返回默认 logger"""
    return _logger
