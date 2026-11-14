import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agent_service.config import ConfigError, config_store
from agent_service.llm import complete_chat, stream_chat


load_dotenv()
logger = logging.getLogger(__name__)

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


def build_model_messages(
    messages: list[ChatMessage],
    system_prompt: str,
) -> list[dict[str, str]]:
    model_messages: list[dict[str, str]] = []
    if system_prompt.strip():
        model_messages.append({"role": "system", "content": system_prompt})
    model_messages.extend(
        {"role": message.role, "content": message.content} for message in messages
    )
    return model_messages


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

    return {
        "status": "ok",
        "service": "agent-service",
        "config_status": "ready",
        "model": config.llm.model,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    config = load_config()
    messages = build_model_messages(
        [ChatMessage(role="user", content=request.message)],
        config.llm.system_prompt,
    )

    try:
        reply = await complete_chat(messages, config.llm)
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
    messages = build_model_messages(payload.messages, config.llm.system_prompt)
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
            async for text in stream_chat(messages, config.llm):
                if await request.is_disconnected():
                    return
                received_text = True
                yield emit(
                    "response.delta",
                    {
                        "type": "delta",
                        "messageId": message_id,
                        "delta": text,
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
