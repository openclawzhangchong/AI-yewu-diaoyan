"""LLM 客户端 — 策略模式，支持 OpenAI / Qwen / Zhipu，带重试"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import List, Optional

from openai import AsyncOpenAI

from domain.config import ModelConfig
from infra.exceptions import LLMError


class LLMClient:
    """LLM 客户端，支持多模型提供商。

    策略模式：根据 provider 分发到对应的 ProviderHandler。
    内置指数退避重试。
    """

    # 默认重试参数
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # 秒
    DEFAULT_BACKOFF_FACTOR = 2.0

    def __init__(
        self,
        config: ModelConfig,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        timeout: int = 120,
    ):
        self._provider = config.provider
        self._handler = self._select_handler(config)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._backoff_factor = backoff_factor
        self._timeout = timeout

    def _select_handler(self, config: ModelConfig):
        """根据 provider 选择对应的处理策略"""
        if not config.api_key:
            raise LLMError(
                "缺少 LLM api_key，请通过环境变量（如 LLM_API_KEY / QWEN_API_KEY）或 config.yaml 配置",
                code="LLM_API_KEY_MISSING",
            )
        handlers = {
            "openai": OpenAIHandler,
            "qwen": QwenHandler,
            "zhipu": ZhipuHandler,
        }
        handler_cls = handlers.get(config.provider)
        if handler_cls is None:
            raise LLMError(f"未知的模型提供商: {config.provider}")
        return handler_cls(config)

    async def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送对话请求并返回回复文本。

        Args:
            messages: 消息列表，如 [{"role": "user", "content": "..."}]
            temperature: 采样温度
            max_tokens: 最大输出 token 数
        """
        return await self._do_with_retry(self._handler.chat, messages, temperature, max_tokens)

    async def _do_with_retry(self, fn, *args, **kwargs) -> str:
        """带指数退避的重试包装器"""
        last_error = None

        for attempt in range(self._max_retries):
            try:
                return await fn(*args, **kwargs)
            except LLMError:
                raise  # 业务错误不重试
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (self._backoff_factor ** attempt)
                    jitter = delay * 0.5 * (1 + random.random())
                    await asyncio.sleep(jitter)

        raise LLMError(f"LLM 请求失败（{self._max_retries} 次重试后）: {last_error}")


class OpenAIHandler:
    """OpenAI 兼容 API 处理器"""

    def __init__(self, config: ModelConfig):
        self._client = AsyncOpenAI(
            api_key=config.api_key or "",
            base_url=config.base_url or "https://api.openai.com/v1",
        )
        self._model = config.model_name

    async def chat(self, messages: List[dict], temperature: float, max_tokens: int) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


class QwenHandler:
    """通义千问（Qwen）处理器"""

    def __init__(self, config: ModelConfig):
        self._client = AsyncOpenAI(
            api_key=config.api_key or "",
            base_url=config.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self._model = config.model_name

    async def chat(self, messages: List[dict], temperature: float, max_tokens: int) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


class ZhipuHandler:
    """智谱 AI（Zhipu）处理器"""

    def __init__(self, config: ModelConfig):
        self._client = AsyncOpenAI(
            api_key=config.api_key or "",
            base_url=config.base_url or "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        )
        self._model = config.model_name

    async def chat(self, messages: List[dict], temperature: float, max_tokens: int) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


def create_llm_client(config: ModelConfig) -> LLMClient:
    """工厂函数：根据配置创建 LLM 客户端"""
    return LLMClient(config)
