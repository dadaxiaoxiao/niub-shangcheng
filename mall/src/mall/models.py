from pydantic import BaseModel, Field


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

