"""LLM 封装（DeepSeek，OpenAI 兼容接口）。"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_json_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0,
        timeout=120,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
