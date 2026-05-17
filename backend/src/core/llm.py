"""LLM 调用封装：支持 vLLM / DeepSeek / Minimax / OpenAI

所有 provider 统一使用 OpenAI 兼容接口（vLLM、DeepSeek、Minimax
都支持 OpenAI 格式的 /v1/chat/completions），简化维护。
"""

import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 敏感内容相关错误标识
_SENSITIVE_ERRORS = ("new_sensitive", "sensitive", "content_policy", "safety")

# Provider 配置映射：每个 provider 的默认 base_url
PROVIDER_DEFAULTS = {
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "api_key": "EMPTY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",  # 需要用户配置
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "api_key": "",  # 需要用户配置
    },
    "minimax2.7": {
        "base_url": "https://api.minimax.chat/v1",
        "api_key": "",  # 需要用户配置
        "model": "MiniMax-Text-01",
    },
    # "mimo": {
    #     "base_url": "https://api.mimo.ai/v1",
    #     "api_key": "",  # 需要用户配置
    # },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",  # 需要用户配置
    },
}


def get_llm() -> BaseChatModel:
    """根据配置获取 LLM 实例，统一使用 OpenAI 兼容接口"""
    provider = settings.llm_provider.lower()
    model = settings.llm_model
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url

    # 如果用户没有自定义 base_url，使用 provider 默认值
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["vllm"])
    if base_url == "http://localhost:8000/v1" and provider != "vllm":
        base_url = defaults["base_url"]
    if api_key == "EMPTY" and provider != "vllm":
        api_key = defaults.get("api_key", "")
    # 如果 provider 有默认 model 配置，使用它
    if "model" in defaults and model == "Qwen/Qwen2.5-72B-Instruct":
        model = defaults["model"]

    logger.info(f"初始化 LLM: provider={provider}, model={model}, base_url={base_url}")

    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        max_tokens=8192,
    )


def _is_sensitive_error(exc: Exception) -> bool:
    """判断是否为敏感内容过滤错误"""
    msg = str(exc).lower()
    return any(kw in msg for kw in _SENSITIVE_ERRORS)


def _build_llm(max_tokens: int = 8192, temperature: float = 0.7) -> BaseChatModel:
    """构建 LLM 实例"""
    provider = settings.llm_provider.lower()
    model = settings.llm_model
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["vllm"])
    if base_url == "http://localhost:8000/v1" and provider != "vllm":
        base_url = defaults["base_url"]
    if api_key == "EMPTY" and provider != "vllm":
        api_key = defaults.get("api_key", "")
    if "model" in defaults and model == "Qwen/Qwen2.5-72B-Instruct":
        model = defaults["model"]
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192,
    max_retries: int = 3,
    temperature: float = 0.7,
) -> str:
    """调用 LLM 并返回响应文本，遇到敏感内容错误自动重试"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    last_exc = None
    for attempt in range(max_retries):
        temp = temperature + attempt * 0.05
        llm = _build_llm(max_tokens, temperature=min(temp, 1.0))

        try:
            response = await llm.ainvoke(messages)

            # 检测截断
            if hasattr(response, 'response_metadata'):
                finish_reason = response.response_metadata.get('finish_reason', '')
                if finish_reason == 'length':
                    logger.warning("LLM 输出被截断（max_tokens 不足），生成内容可能不完整")

            return response.content
        except Exception as e:
            if _is_sensitive_error(e) and attempt < max_retries - 1:
                logger.warning(f"触发敏感内容过滤，第 {attempt + 1} 次重试: {e}")
                await asyncio.sleep(1)
                last_exc = e
                continue
            raise

    raise last_exc  # type: ignore[misc]


async def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192,
    max_retries: int = 3,
    temperature: float = 0.7,
):
    """调用 LLM 并以流式方式逐块返回响应文本（async generator），遇到敏感内容错误自动重试"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    last_exc = None
    for attempt in range(max_retries):
        temp = temperature + attempt * 0.05
        llm = _build_llm(max_tokens, temperature=min(temp, 1.0))

        try:
            async for chunk in llm.astream(messages):
                if chunk.content:
                    yield chunk.content
            return  # 流式正常结束
        except Exception as e:
            if _is_sensitive_error(e) and attempt < max_retries - 1:
                logger.warning(f"流式生成触发敏感内容过滤，第 {attempt + 1} 次重试: {e}")
                await asyncio.sleep(1)
                last_exc = e
                continue
            raise

    raise last_exc  # type: ignore[misc]
