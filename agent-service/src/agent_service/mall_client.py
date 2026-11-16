import asyncio
import json
import urllib.error
import urllib.request

from pydantic import BaseModel, ValidationError

from agent_service.config import MallConfig


class MallError(RuntimeError):
    """The mall catalog is unreachable or returned unexpected data."""


class Product(BaseModel):
    id: str
    name: str
    summary: str
    description: str = ""
    price_cents: int
    currency: str = "CNY"
    category: str
    stock: int
    badge: str | None = None


class MallClient:
    """Read-only client for the mall mock product catalog."""

    def __init__(self, config: MallConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._timeout = config.timeout_seconds
        self._products: list[Product] | None = None

    async def list_products(self) -> list[Product]:
        """Fetch the catalog once per chat request."""
        if self._products is None:
            self._products = await asyncio.to_thread(self._fetch_products)
        return self._products

    def _fetch_products(self) -> list[Product]:
        url = f"{self._base_url}/api/products"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise MallError("商品服务暂时不可用。") from exc

        if not isinstance(payload, list):
            raise MallError("商品服务返回了意外的数据。")

        try:
            return [Product.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise MallError("商品服务返回了意外的数据。") from exc