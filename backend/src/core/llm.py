"""LLM 调用封装：支持 vLLM / DeepSeek / Minimax / OpenAI

所有 provider 统一使用 OpenAI 兼容接口（vLLM、DeepSeek、Minimax
都支持 OpenAI 格式的 /v1/chat/completions），简化维护。

支持通过 contextvars 注入用户级 LLM 配置，实现前端自定义模型切换。
"""

import asyncio
from contextvars import ContextVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 当前请求/任务的用户自定义 LLM 配置
_current_llm_config: ContextVar[dict | None] = ContextVar("current_llm_config", default=None)


def set_current_llm_config(config: dict | None) -> None:
    """设置当前异步上下文的 LLM 配置，HTTP 中间件或后台任务调用前设置"""
    _current_llm_config.set(config)


def get_current_llm_config() -> dict | None:
    """获取当前异步上下文的 LLM 配置，_build_llm 内部使用"""
    return _current_llm_config.get()

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


def _resolve_llm_params() -> dict:
    """解析 LLM 参数，优先使用 context var 中的用户配置，否则使用全局配置"""
    ctx_config = get_current_llm_config()

    if ctx_config and ctx_config.get("api_key"):
        provider = ctx_config.get("provider", "openai")
        model = ctx_config["model"]
        api_key = ctx_config["api_key"]
        base_url = ctx_config.get("base_url", "")
        max_tokens = ctx_config.get("max_tokens", 8192)
        logger.info(f"使用用户自定义 LLM 配置: provider={provider}, model={model}, base_url={base_url}, max_tokens={max_tokens}")
        return {"provider": provider, "model": model, "api_key": api_key, "base_url": base_url, "max_tokens": max_tokens}

    # 全局配置回退
    provider = settings.llm_provider.lower()
    model = settings.llm_model
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url
    max_tokens = settings.llm_max_tokens if hasattr(settings, 'llm_max_tokens') else 8192

    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["vllm"])
    if base_url == "http://localhost:8000/v1" and provider != "vllm":
        base_url = defaults["base_url"]
    if api_key == "EMPTY" and provider != "vllm":
        api_key = defaults.get("api_key", "")
    if "model" in defaults and model == "Qwen/Qwen2.5-72B-Instruct":
        model = defaults["model"]

    logger.info(f"使用全局默认 LLM 配置: provider={provider}, model={model}, base_url={base_url}, max_tokens={max_tokens}")
    return {"provider": provider, "model": model, "api_key": api_key, "base_url": base_url, "max_tokens": max_tokens}


def get_llm() -> BaseChatModel:
    """根据配置获取 LLM 实例，优先使用用户自定义配置"""
    params = _resolve_llm_params()
    logger.info(f"初始化 LLM: provider={params['provider']}, model={params['model']}, base_url={params['base_url']}, max_tokens={params['max_tokens']}")

    return ChatOpenAI(
        model=params["model"],
        openai_api_key=params["api_key"],
        base_url=params["base_url"],
        temperature=0.7,
        max_tokens=params["max_tokens"],
    )


def _is_sensitive_error(exc: Exception) -> bool:
    """判断是否为敏感内容过滤错误"""
    msg = str(exc).lower()
    return any(kw in msg for kw in _SENSITIVE_ERRORS)


def _build_llm(max_tokens: int = 8192, temperature: float = 0.7) -> BaseChatModel:
    """构建 LLM 实例，优先使用用户自定义配置"""
    params = _resolve_llm_params()
    return ChatOpenAI(
        model=params["model"],
        openai_api_key=params["api_key"],
        base_url=params["base_url"],
        temperature=temperature,
        max_tokens=params["max_tokens"],
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
