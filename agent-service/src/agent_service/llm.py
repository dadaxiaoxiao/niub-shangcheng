from collections.abc import AsyncIterator, Sequence
from typing import Any

from openai import AsyncOpenAI

from agent_service.config import LlmConfig


async def stream_chat(
    messages: Sequence[dict[str, str]],
    config: LlmConfig,
) -> AsyncIterator[str]:
    """Stream text deltas from an OpenAI-compatible chat completions endpoint."""
    client = AsyncOpenAI(
        api_key=config.api_key.get_secret_value(),
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=1,
    )

    request_options: dict[str, Any] = {
        "model": config.model,
        "messages": list(messages),
        "stream": True,
    }
    if config.temperature is not None:
        request_options["temperature"] = config.temperature
    if config.max_tokens is not None:
        request_options["max_tokens"] = config.max_tokens

    try:
        stream = await client.chat.completions.create(**request_options)
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if isinstance(content, str) and content:
                yield content
    finally:
        await client.close()


async def complete_chat(
    messages: Sequence[dict[str, str]],
    config: LlmConfig,
) -> str:
    chunks: list[str] = []
    async for chunk in stream_chat(messages, config):
        chunks.append(chunk)
    return "".join(chunks)
