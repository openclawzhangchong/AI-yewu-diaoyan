"""配置管理 — 命令行 > 环境变量 > config.yaml > 默认值"""

from __future__ import annotations

import os
from typing import Optional

import yaml

from domain.config import Config as DomainConfig


class ConfigManager:
    """配置管理器，按优先级链加载配置。

    优先级：
        1. 命令行参数（通过 set_from_args 设置）
        2. 环境变量
        3. config.yaml
        4. 内置默认值
    """

    # 环境变量映射
    _ENV_MAP = {
        "provider": "LLM_PROVIDER",
        "api_key": "LLM_API_KEY",
        "base_url": "LLM_BASE_URL",
        "model_name": "LLM_MODEL_NAME",
        "max_concurrent": "MAX_CONCURRENT",
        "timeout_seconds": "TIMEOUT_SECONDS",
        "log_level": "LOG_LEVEL",
        "log_file": "LOG_FILE",
        "output_dir": "OUTPUT_DIR",
        "output_format": "OUTPUT_FORMAT",
    }

    def __init__(self, config_path: str = "config.yaml") -> None:
        self._config = DomainConfig()
        self._config_path = config_path
        self._pending_args: dict = {}

    def load(self) -> DomainConfig:
        """按优先级链加载配置，返回最终 Config 对象"""
        # 1. 内置默认值（已在 __init__ 创建）
        # 2. config.yaml
        self._load_from_yaml()
        # 3. 环境变量
        self._load_from_env()
        # 4. 命令行参数（由 set_from_args 处理，优先级最高，重新应用）
        if self._pending_args:
            self._apply_args()

        return self._config

    def _load_from_yaml(self) -> None:
        """从 config.yaml 加载配置"""
        path = self._config_path
        if not os.path.isfile(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return

        # model 配置
        if "model" in data:
            m = data["model"]
            if isinstance(m, dict):
                if "provider" in m:
                    self._config.model.provider = m["provider"]
                if "api_key" in m:
                    self._config.model.api_key = m["api_key"]
                if "base_url" in m:
                    self._config.model.base_url = m["base_url"]
                if "model_name" in m:
                    self._config.model.model_name = m["model_name"]

        # analysis 配置
        if "analysis" in data:
            a = data["analysis"]
            if isinstance(a, dict):
                if "max_concurrent" in a:
                    self._config.analysis.max_concurrent = int(a["max_concurrent"])
                if "timeout_seconds" in a:
                    self._config.analysis.timeout_seconds = int(a["timeout_seconds"])

        # logging 配置
        if "logging" in data:
            l = data["logging"]
            if isinstance(l, dict):
                if "level" in l:
                    self._config.logging.level = l["level"]
                if "file" in l:
                    self._config.logging.file = l["file"]
                if "max_bytes" in l:
                    self._config.logging.max_bytes = int(l["max_bytes"])
                if "backup_count" in l:
                    self._config.logging.backup_count = int(l["backup_count"])

        # output 配置
        if "output" in data:
            o = data["output"]
            if isinstance(o, dict):
                if "directory" in o:
                    self._config.output.directory = o["directory"]
                if "default_format" in o:
                    self._config.output.default_format = o["default_format"]

    def _load_from_env(self) -> None:
        """从环境变量覆盖配置"""
        # 环境变量优先级高于 yaml 但低于命令行参数
        if "LLM_PROVIDER" in os.environ:
            self._config.model.provider = os.environ["LLM_PROVIDER"]
        if "LLM_API_KEY" in os.environ:
            self._config.model.api_key = os.environ["LLM_API_KEY"]
        if "LLM_BASE_URL" in os.environ:
            self._config.model.base_url = os.environ["LLM_BASE_URL"]
        if "LLM_MODEL_NAME" in os.environ:
            self._config.model.model_name = os.environ["LLM_MODEL_NAME"]
        if "MAX_CONCURRENT" in os.environ:
            self._config.analysis.max_concurrent = int(os.environ["MAX_CONCURRENT"])
        if "TIMEOUT_SECONDS" in os.environ:
            self._config.analysis.timeout_seconds = int(os.environ["TIMEOUT_SECONDS"])
        if "LOG_LEVEL" in os.environ:
            self._config.logging.level = os.environ["LOG_LEVEL"]
        if "LOG_FILE" in os.environ:
            self._config.logging.file = os.environ["LOG_FILE"]
        if "OUTPUT_DIR" in os.environ:
            self._config.output.directory = os.environ["OUTPUT_DIR"]
        if "OUTPUT_FORMAT" in os.environ:
            self._config.output.default_format = os.environ["OUTPUT_FORMAT"]

    def set_from_args(self, args: dict) -> None:
        """从命令行参数设置（最高优先级）

        支持参数：
            --provider, --api-key, --base-url, --model-name
            --max-concurrent, --timeout
            --log-level, --log-file
            --output-dir, --output-format

        立即应用到当前配置，并缓存到 ``self._pending_args``：
        若之后再次调用 :meth:`load`，命令行参数会在 yaml/环境变量
        加载后重新应用，保证 "命令行 > 环境变量 > yaml" 的优先级。
        """
        self._pending_args = dict(args)
        self._apply_args()

    def _apply_args(self) -> None:
        """应用缓存的命令行参数到当前配置。"""
        args = self._pending_args
        if "provider" in args and args["provider"]:
            self._config.model.provider = args["provider"]
        if "api_key" in args and args["api_key"]:
            self._config.model.api_key = args["api_key"]
        if "base_url" in args and args["base_url"]:
            self._config.model.base_url = args["base_url"]
        if "model_name" in args and args["model_name"]:
            self._config.model.model_name = args["model_name"]
        if "max_concurrent" in args:
            self._config.analysis.max_concurrent = args["max_concurrent"]
        if "timeout" in args:
            self._config.analysis.timeout_seconds = args["timeout"]
        if "log_level" in args and args["log_level"]:
            self._config.logging.level = args["log_level"]
        if "log_file" in args and args["log_file"]:
            self._config.logging.file = args["log_file"]
        if "output_dir" in args and args["output_dir"]:
            self._config.output.directory = args["output_dir"]
        if "output_format" in args and args["output_format"]:
            self._config.output.default_format = args["output_format"]

    def get_config(self) -> DomainConfig:
        """获取当前配置"""
        return self._config

    @property
    def model_provider(self) -> str:
        return self._config.model.provider

    @property
    def api_key(self) -> str:
        return self._config.model.api_key

    @property
    def model_name(self) -> str:
        return self._config.model.model_name
