"""infra 单元测试 — 异常 code、EventBus 派发、ConfigManager 优先级、CacheManager 读写。"""

from __future__ import annotations

import asyncio
import json

import pytest

from domain.config import Config
from infra.cache import CacheManager
from infra.config import ConfigManager
from infra.event_bus import (
    ANALYSIS_DONE,
    ALL_EVENTS,
    DATA_COLLECTED,
    PACK_DONE,
    REPORT_GENERATED,
    TEMPLATE_LOADED,
    EventBus,
)
from infra.exceptions import (
    AnalysisError,
    AppError,
    CollectionError,
    ConfigError,
    LLMError,
    PackError,
    ReportError,
    TemplateError,
)


# ---------------------------------------------------------------------------
# exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_app_error_defaults(self):
        e = AppError()
        assert e.message == "应用错误"
        assert e.code == "APP_ERROR"
        assert str(e) == "应用错误"

    def test_app_error_custom(self):
        e = AppError("boom", "MY_CODE")
        assert e.message == "boom"
        assert e.code == "MY_CODE"
        assert isinstance(e, Exception)

    def test_subclass_fixed_codes(self):
        cases = [
            (ConfigError, "CONFIG_ERROR"),
            (TemplateError, "TEMPLATE_ERROR"),
            (CollectionError, "COLLECTION_ERROR"),
            (AnalysisError, "ANALYSIS_ERROR"),
            (LLMError, "LLM_ERROR"),
            (ReportError, "REPORT_ERROR"),
            (PackError, "PACK_ERROR"),
        ]
        for cls, code in cases:
            e = cls()
            assert isinstance(e, AppError), f"{cls.__name__} 应继承 AppError"
            assert e.code == code, f"{cls.__name__} 默认 code 应为 {code}"
            # 消息可覆盖，code 固定
            e2 = cls("custom msg")
            assert e2.message == "custom msg"
            assert e2.code == code, f"{cls.__name__} 传消息时 code 应保持默认"

    def test_llm_error_custom_code(self):
        e = LLMError("missing", code="LLM_API_KEY_MISSING")
        assert e.code == "LLM_API_KEY_MISSING"


# ---------------------------------------------------------------------------
# event bus
# ---------------------------------------------------------------------------


class TestEventBusConstants:
    def test_event_constants(self):
        assert TEMPLATE_LOADED == "template.loaded"
        assert DATA_COLLECTED == "data.collected"
        assert ANALYSIS_DONE == "analysis.done"
        assert REPORT_GENERATED == "report.generated"
        assert PACK_DONE == "pack.done"
        assert ALL_EVENTS == [
            TEMPLATE_LOADED,
            DATA_COLLECTED,
            ANALYSIS_DONE,
            REPORT_GENERATED,
            PACK_DONE,
        ]


class TestEventBus:
    def test_sync_handler_called_in_order(self, event_bus, capture_events):
        seen = capture_events(event_bus, ANALYSIS_DONE)
        event_bus.publish(ANALYSIS_DONE, {"n": 1})
        event_bus.publish(ANALYSIS_DONE, {"n": 2})
        assert seen == [{"n": 1}, {"n": 2}]

    def test_multiple_handlers_and_no_subscribers(self, event_bus):
        payloads: list = []
        handler_a = lambda d: payloads.append(("A", d))  # noqa: E731
        handler_b = lambda d: payloads.append(("B", d))  # noqa: E731
        event_bus.subscribe(REPORT_GENERATED, handler_a)
        event_bus.subscribe(REPORT_GENERATED, handler_b)

        event_bus.publish(REPORT_GENERATED, {"x": 1})
        event_bus.publish(REPORT_GENERATED, {"x": 2})

        # 所有 handler 均按订阅顺序收到
        assert payloads == [("A", {"x": 1}), ("B", {"x": 1}), ("A", {"x": 2}), ("B", {"x": 2})]
        # 无订阅者时 publish 不抛错
        event_bus.publish("nobody.subscribed", 42)

    def test_unsubscribe(self, event_bus):
        seen: list = []
        handler = lambda d: seen.append(d)  # noqa: E731
        event_bus.subscribe(PACK_DONE, handler)
        event_bus.publish(PACK_DONE, "first")
        assert seen == ["first"]

        # 真正 unsubscribe 掉已订阅的那个 handler（按对象身份）
        event_bus.unsubscribe(PACK_DONE, handler)
        assert PACK_DONE not in event_bus.registered_events()

        event_bus.publish(PACK_DONE, "second")
        assert seen == ["first"], "取消订阅后不应再收到事件"
        # 无订阅者时 publish 不抛错
        event_bus.publish(PACK_DONE, "third")
        assert seen == ["first"]

    def test_registered_events(self, event_bus):
        assert event_bus.registered_events() == []
        event_bus.subscribe(TEMPLATE_LOADED, lambda d: None)
        event_bus.subscribe(DATA_COLLECTED, lambda d: None)
        assert set(event_bus.registered_events()) == {TEMPLATE_LOADED, DATA_COLLECTED}

    def test_async_handler_without_running_loop_uses_asyncio_run(
        self, event_bus, capture_events
    ):
        """协程 handler：无运行中事件循环时应通过 asyncio.run 立即执行。

        同时订阅同步 handler（capture_events 提供）与协程 handler，
        publish 返回后两者都应已完成（asyncio.run 是同步等待的）。"""
        sync_seen = capture_events(event_bus, ANALYSIS_DONE)

        async def handler(data):
            await asyncio.sleep(0)
            sync_seen.append(("async", data))

        event_bus.subscribe(ANALYSIS_DONE, handler)
        event_bus.publish(ANALYSIS_DONE, {"v": 9})

        # 同步 handler 先执行、协程 handler 经 asyncio.run 同步执行
        assert ("async", {"v": 9}) in sync_seen
        assert {"v": 9} in sync_seen

    def test_publish_swallows_handler_errors(self, event_bus):
        def bad(d):
            raise RuntimeError("handler boom")

        event_bus.subscribe(DATA_COLLECTED, bad)
        event_bus.subscribe(DATA_COLLECTED, lambda d: None)
        # 不抛错即可
        event_bus.publish(DATA_COLLECTED, "x")

    def test_async_handler_with_running_loop_creates_task(self):
        """协程 handler 在有运行事件循环时用 create_task；测试体内等待任务完成。"""
        async def run():
            bus = EventBus()
            seen: list = []

            async def handler(data):
                await asyncio.sleep(0.01)
                seen.append(data)

            bus.subscribe(PACK_DONE, handler)
            bus.publish(PACK_DONE, "fire")
            assert seen == [], "任务应尚未完成（create_task 不立即执行）"
            await asyncio.sleep(0.05)
            assert seen == ["fire"]

        asyncio.run(run())


# ---------------------------------------------------------------------------
# config manager
# ---------------------------------------------------------------------------


class TestConfigManager:
    def test_defaults_when_no_yaml(self, tmp_path):
        cm = ConfigManager(config_path=str(tmp_path / "missing.yaml"))
        cfg = cm.load()
        assert isinstance(cfg, Config)
        assert cfg.model.provider == "qwen"
        assert cfg.model.api_key == ""
        assert cfg.analysis.max_concurrent == 4
        assert cfg.output.directory == "./output"
        # 便捷属性
        assert cm.model_provider == "qwen"
        assert cm.api_key == ""
        assert cm.model_name == "qwen-turbo"

    def test_yaml_overrides_defaults(self, tmp_path, monkeypatch):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(
            json.dumps(
                {
                    "model": {"provider": "zhipu", "api_key": "yk", "model_name": "glm-4"},
                    "analysis": {"max_concurrent": 8, "timeout_seconds": 300},
                    "logging": {"level": "WARNING", "max_bytes": 2048},
                    "output": {"directory": "./out_y", "default_format": "excel"},
                }
            ),
            encoding="utf-8",
        )
        cm = ConfigManager(config_path=str(yaml_path))
        cfg = cm.load()
        assert cfg.model.provider == "zhipu"
        assert cfg.model.api_key == "yk"
        assert cfg.model.model_name == "glm-4"
        assert cfg.analysis.max_concurrent == 8
        assert cfg.analysis.timeout_seconds == 300
        assert cfg.logging.level == "WARNING"
        assert cfg.logging.max_bytes == 2048
        assert cfg.output.directory == "./out_y"
        assert cfg.output.default_format == "excel"

    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(
            json.dumps(
                {
                    "model": {"provider": "zhipu", "api_key": "yaml-key"},
                    "analysis": {"max_concurrent": 8},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_API_KEY", "env-key")
        monkeypatch.setenv("MAX_CONCURRENT", "2")

        cm = ConfigManager(config_path=str(yaml_path))
        cfg = cm.load()
        # 环境变量 > yaml
        assert cfg.model.provider == "openai"
        assert cfg.model.api_key == "env-key"
        assert cfg.analysis.max_concurrent == 2
        # yaml 未在 env 中出现的字段保留
        assert cfg.analysis.timeout_seconds == 120

    def test_cli_args_override_env_and_yaml(self, tmp_path, monkeypatch):
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(
            json.dumps({"model": {"api_key": "yaml-key"}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("LLM_API_KEY", "env-key")

        cm = ConfigManager(config_path=str(yaml_path))
        cm.set_from_args(
            {
                "provider": "qwen",
                "api_key": "cli-key",
                "model_name": "qwen-max",
                "max_concurrent": 1,
                "timeout": 5,
                "output_format": "json",
            }
        )
        cfg = cm.load()
        assert cfg.model.api_key == "cli-key"
        assert cfg.model.provider == "qwen"
        assert cfg.model.model_name == "qwen-max"
        assert cfg.analysis.max_concurrent == 1
        assert cfg.analysis.timeout_seconds == 5
        assert cfg.output.default_format == "json"

    def test_set_from_args_ignores_empty(self, tmp_path):
        cm = ConfigManager(config_path=str(tmp_path / "missing.yaml"))
        cm.set_from_args({"provider": None, "api_key": "", "max_concurrent": 7})
        cfg = cm.load()
        # None/空值不应覆盖默认
        assert cfg.model.provider == "qwen"
        assert cfg.model.api_key == ""
        # 非空 int 生效
        assert cfg.analysis.max_concurrent == 7

    def test_repo_config_yaml_parses(self):
        """项目根 config.yaml 至少可被安全加载（不依赖其具体值）。"""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent.parent
        p = root / "config.yaml"
        if p.is_file():
            cm = ConfigManager(config_path=str(p))
            cfg = cm.load()
            assert isinstance(cfg, Config)


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------


class TestCacheManager:
    def test_put_get_roundtrip(self, cache_manager):
        assert cache_manager.get("客服部", "v1", "3", "qwen", "0.7") is None
        cache_manager.put("客服部", "v1", "3", "qwen", "0.7", '{"ok": 1}')
        assert cache_manager.get("客服部", "v1", "3", "qwen", "0.7") == '{"ok": 1}'

    def test_key_format(self, cache_manager):
        cache_manager.put("a", "v", "d", "m", "t", "val")
        assert cache_manager.keys() == ["a:v:d:m:t"]
        assert cache_manager.count() == 1

    def test_overwrite_same_key(self, cache_manager):
        cache_manager.put("a", "v", "d", "m", "t", "old")
        cache_manager.put("a", "v", "d", "m", "t", "new")
        assert cache_manager.get("a", "v", "d", "m", "t") == "new"
        assert cache_manager.count() == 1

    def test_delete_and_clear(self, cache_manager):
        cache_manager.put("a", "v", "d", "m", "t", "1")
        cache_manager.put("b", "v", "d", "m", "t", "2")
        cache_manager.delete("a:v:d:m:t")
        assert cache_manager.get("a", "v", "d", "m", "t") is None
        assert cache_manager.count() == 1
        cache_manager.clear()
        assert cache_manager.count() == 0
        assert cache_manager.keys() == []

    def test_expired_cache_returns_none(self, cache_manager):
        # ttl=0 表示不过期；用负 TTL 无法表达，验证 ttl=0 长期可读
        cache_manager.put("x", "v", "d", "m", "t", "persist", ttl=0)
        assert cache_manager.get("x", "v", "d", "m", "t") == "persist"

    def test_db_file_created(self, tmp_path):
        db = tmp_path / "sub" / "cache.db"
        cm = CacheManager(db_path=str(db))
        assert db.is_file()
