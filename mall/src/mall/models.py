from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    id: str
    name: str
    summary: str
    description: str
    price_cents: int = Field(ge=0)
    currency: str = "CNY"
    category: str
    stock: int = Field(ge=0)
    badge: str | None = None
    accent: str


class Message(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    status: Literal["complete", "interrupted"]
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    preview: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[Message]


class MessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    status: Literal["complete", "interrupted"] = "complete"

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content cannot be blank")
        return value