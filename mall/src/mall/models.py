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


class Occasion(BaseModel):
    name: str
    date: str
    budget_cents: int | None = Field(default=None, ge=0)


class UserProfile(BaseModel):
    user_id: str
    display_name: str
    member_level: str
    tags: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    price_band_cents: tuple[int, int]
    avoid: list[str] = Field(default_factory=list)
    occasions: list[Occasion] = Field(default_factory=list)


class BrowsingEvent(BaseModel):
    event: Literal["view", "search"]
    product_id: str | None = None
    query: str | None = None
    count: int = Field(ge=1)
    dwell_seconds: int = Field(default=0, ge=0)
    last_seen_at: str


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int = Field(ge=1)
    price_cents: int = Field(ge=0)


class Order(BaseModel):
    id: str
    status: Literal["completed", "returned", "cancelled"]
    created_at: str
    total_cents: int = Field(ge=0)
    items: list[OrderItem] = Field(default_factory=list)


class CartItem(BaseModel):
    product_id: str
    name: str
    quantity: int = Field(ge=1)
    price_cents: int = Field(ge=0)
    added_at: str


class Cart(BaseModel):
    user_id: str
    items: list[CartItem] = Field(default_factory=list)
    updated_at: str


class RecommendationCandidate(BaseModel):
    product_id: str
    score: float = Field(ge=0, le=1)
    reason: str
    signals: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    user_id: str
    strategy: str
    candidates: list[RecommendationCandidate] = Field(default_factory=list)


class AdCandidate(BaseModel):
    product_id: str
    campaign_id: str
    campaign_name: str
    relevance: float = Field(ge=0, le=1)
    bid_cents: int = Field(ge=0)
    ad_copy: str


class AdResponse(BaseModel):
    candidates: list[AdCandidate] = Field(default_factory=list)