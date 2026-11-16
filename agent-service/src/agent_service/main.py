import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from agents import MaxTurnsExceeded
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agent_service.config import AppConfig, ConfigError, config_store
from agent_service.llm import (
    TextDelta,
    ToolCall,
    ToolResult,
    complete_chat,
    stream_chat,
)
from agent_service.mall_client import MallClient
from agent_service.prompts import PromptStore
from agent_service.tools import TOOL_LABELS, ToolRunner


load_dotenv()
logger = logging.getLogger(__name__)
prompt_store = PromptStore()

app = FastAPI(
    title="Niub Agent Service",
    version="0.2.0",
    description="Streaming chat service for an OpenAI-compatible model.",
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content cannot be blank")
        return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value


class StreamChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


class ChatResponse(BaseModel):
    reply: str
    agent: str = "Niub Assistant"


def load_config():
    try:
        return config_store.get()
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def load_instructions(config: AppConfig) -> str:
    try:
        return prompt_store.get(config.llm.prompt_file)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def sse_event(sequence: int, name: str, data: dict[str, object]) -> str:
    timestamp_ms = int(time.time() * 1000)
    payload = {
        "sequence": sequence,
        "timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.gmtime(timestamp_ms / 1000),
        )
        + f".{timestamp_ms % 1000:03d}Z",
        "timestampMs": timestamp_ms,
        **data,
    }
    return (
        f"id: {sequence}\n"
        f"event: {name}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


@app.get("/health")
async def health() -> dict[str, object]:
    try:
        config = config_store.get()
    except ConfigError:
        return {
            "status": "ok",
            "service": "agent-service",
            "config_status": "missing_or_invalid",
        }

    prompt_status = "ready"
    try:
        prompt_store.get(config.llm.prompt_file)
    except ConfigError:
        prompt_status = "missing_or_invalid"

    return {
        "status": "ok",
        "service": "agent-service",
        "config_status": "ready",
        "model": config.llm.model,
        "mall": config.mall.base_url,
        "prompt": prompt_status,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    config = load_config()
    instructions = load_instructions(config)
    messages = [{"role": "user", "content": request.message}]
    tool_runner = ToolRunner(MallClient(config.mall))

    try:
        reply = await complete_chat(
            messages,
            config.llm,
            tool_runner,
            instructions,
        )
    except MaxTurnsExceeded as exc:
        raise HTTPException(
            status_code=502,
            detail="工具调用轮次过多，请简化问题后重试。",
        ) from exc
    except Exception as exc:
        logger.exception("Model request failed")
        raise HTTPException(status_code=502, detail="Model request failed.") from exc

    if not reply:
        raise HTTPException(status_code=502, detail="Model returned no text.")
    return ChatResponse(reply=reply)


@app.post("/api/chat/stream")
async def chat_stream(
    payload: StreamChatRequest,
    request: Request,
) -> StreamingResponse:
    if not any(message.role == "user" for message in payload.messages):
        raise HTTPException(status_code=400, detail="At least one user message is required.")

    config = load_config()
    instructions = load_instructions(config)
    messages = [
        {"role": message.role, "content": message.content}
        for message in payload.messages
    ]
    tool_runner = ToolRunner(MallClient(config.mall))
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    async def generate() -> AsyncIterator[str]:
        sequence = 0
        started_at = time.perf_counter()
        received_text = False

        def emit(name: str, data: dict[str, object]) -> str:
            nonlocal sequence
            sequence += 1
            return sse_event(sequence, name, data)

        yield emit(
            "stream.open",
            {
                "type": "start",
                "sessionId": session_id,
                "messageId": message_id,
                "model": config.llm.model,
            },
        )
        yield emit(
            "response.status",
            {
                "type": "status",
                "phase": "connecting",
                "statusText": f"正在连接模型 {config.llm.model}",
            },
        )

        try:
            async for event in stream_chat(
                messages,
                config.llm,
                tool_runner,
                instructions,
            ):
                if await request.is_disconnected():
                    return

                if isinstance(event, TextDelta):
                    received_text = True
                    yield emit(
                        "response.delta",
                        {
                            "type": "delta",
                            "messageId": message_id,
                            "delta": event.text,
                        },
                    )
                elif isinstance(event, ToolCall):
                    yield emit(
                        "response.status",
                        {
                            "type": "status",
                            "phase": "tools",
                            "statusText": TOOL_LABELS.get(
                                event.name,
                                "正在查询商品",
                            ),
                        },
                    )
                    yield emit(
                        "tool.start",
                        {
                            "type": "tool_start",
                            "name": event.name,
                            "arguments": event.arguments,
                        },
                    )
                elif isinstance(event, ToolResult):
                    yield emit(
                        "tool.result",
                        {
                            "type": "tool_result",
                            "name": event.name,
                            "result": event.result,
                        },
                    )

            if not received_text:
                yield emit(
                    "response.error",
                    {
                        "type": "error",
                        "message": "模型没有返回文本内容。",
                    },
                )
                return

            yield emit(
                "response.completed",
                {
                    "type": "done",
                    "sessionId": session_id,
                    "messageId": message_id,
                    "model": config.llm.model,
                    "elapsedMs": round(
                        (time.perf_counter() - started_at) * 1000,
                    ),
                },
            )
        except asyncio.CancelledError:
            raise
        except MaxTurnsExceeded:
            if not await request.is_disconnected():
                yield emit(
                    "response.error",
                    {
                        "type": "error",
                        "message": "工具调用轮次过多，请简化问题后重试。",
                    },
                )
        except Exception:
            logger.exception("Streaming model request failed")
            if not await request.is_disconnected():
                yield emit(
                    "response.error",
                    {
                        "type": "error",
                        "message": "模型调用失败，请检查配置文件中的接口地址、密钥和模型名称。",
                    },
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )