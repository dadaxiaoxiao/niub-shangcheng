import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from agent_service.config import MallConfig


class MallError(RuntimeError):
    """The mall is unreachable or returned unexpected data."""


class MallNotFoundError(MallError):
    """The requested mall resource does not exist (HTTP 404)."""


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


class Occasion(BaseModel):
    name: str
    date: str
    budget_cents: int | None = None


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
    count: int
    dwell_seconds: int = 0
    last_seen_at: str


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price_cents: int


class Order(BaseModel):
    id: str
    status: Literal["completed", "returned", "cancelled"]
    created_at: str
    total_cents: int
    items: list[OrderItem] = Field(default_factory=list)


class CartItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price_cents: int
    added_at: str


class Cart(BaseModel):
    user_id: str
    items: list[CartItem] = Field(default_factory=list)
    updated_at: str


class RecommendationCandidate(BaseModel):
    product_id: str
    score: float
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
    relevance: float
    bid_cents: int
    ad_copy: str


class AdResponse(BaseModel):
    candidates: list[AdCandidate] = Field(default_factory=list)


class MallClient:
    """Read-only client for the mall catalog and personalization mocks."""

    def __init__(self, config: MallConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._timeout = config.timeout_seconds
        self._products: list[Product] | None = None
        self._profile: UserProfile | None = None
        self._profile_loaded = False
        self._browsing: list[BrowsingEvent] | None = None
        self._orders: list[Order] | None = None
        self._cart: Cart | None = None
        self._cart_loaded = False

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        service_label: str,
    ) -> Any:
        return await asyncio.to_thread(
            self._fetch_json,
            path,
            params or {},
            service_label,
        )

    def _fetch_json(
        self,
        path: str,
        params: dict[str, Any],
        service_label: str,
    ) -> Any:
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise MallNotFoundError(
                    f"{service_label}没有找到对应的用户。"
                ) from exc
            raise MallError(f"{service_label}暂时不可用。") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise MallError(f"{service_label}暂时不可用。") from exc

    @staticmethod
    def _validate(
        model: type[BaseModel],
        payload: Any,
        service_label: str,
    ) -> Any:
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise MallError(f"{service_label}返回了意外的数据。") from exc

    async def list_products(self) -> list[Product]:
        """Fetch the catalog once per chat request."""
        if self._products is None:
            payload = await self._get_json(
                "/api/products",
                service_label="商品服务",
            )
            if not isinstance(payload, list):
                raise MallError("商品服务返回了意外的数据。")
            try:
                self._products = [
                    Product.model_validate(item) for item in payload
                ]
            except ValidationError as exc:
                raise MallError("商品服务返回了意外的数据。") from exc
        return self._products

    async def get_profile(self, user_id: str) -> UserProfile | None:
        """Return the user profile, or None when the user has no profile."""
        if not self._profile_loaded:
            try:
                payload = await self._get_json(
                    f"/api/users/{urllib.parse.quote(user_id, safe='')}/profile",
                    service_label="用户画像服务",
                )
                self._profile = self._validate(
                    UserProfile,
                    payload,
                    "用户画像服务",
                )
            except MallNotFoundError:
                self._profile = None
            self._profile_loaded = True
        return self._profile

    async def get_browsing_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[BrowsingEvent]:
        if self._browsing is None:
            try:
                payload = await self._get_json(
                    f"/api/users/{urllib.parse.quote(user_id, safe='')}"
                    "/browsing-history",
                    params={"limit": limit},
                    service_label="行为记录服务",
                )
                if not isinstance(payload, list):
                    raise MallError("行为记录服务返回了意外的数据。")
                try:
                    self._browsing = [
                        BrowsingEvent.model_validate(item) for item in payload
                    ]
                except ValidationError as exc:
                    raise MallError("行为记录服务返回了意外的数据。") from exc
            except MallNotFoundError:
                self._browsing = []
        return self._browsing

    async def get_orders(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[Order]:
        if self._orders is None:
            try:
                payload = await self._get_json(
                    f"/api/users/{urllib.parse.quote(user_id, safe='')}/orders",
                    params={"limit": limit},
                    service_label="订单服务",
                )
                if not isinstance(payload, list):
                    raise MallError("订单服务返回了意外的数据。")
                try:
                    self._orders = [
                        Order.model_validate(item) for item in payload
                    ]
                except ValidationError as exc:
                    raise MallError("订单服务返回了意外的数据。") from exc
            except MallNotFoundError:
                self._orders = []
        return self._orders

    async def get_cart(self, user_id: str) -> Cart | None:
        if not self._cart_loaded:
            try:
                payload = await self._get_json(
                    f"/api/users/{urllib.parse.quote(user_id, safe='')}/cart",
                    service_label="购物车服务",
                )
                self._cart = self._validate(Cart, payload, "购物车服务")
            except MallNotFoundError:
                self._cart = None
            self._cart_loaded = True
        return self._cart

    async def get_recommendations(
        self,
        user_id: str,
        *,
        focus: str = "",
        category: str = "",
        max_price_cents: int | None = None,
        limit: int = 10,
    ) -> list[RecommendationCandidate]:
        params: dict[str, Any] = {"limit": limit}
        if focus:
            params["focus"] = focus
        if category:
            params["category"] = category
        if max_price_cents is not None:
            params["max_price_cents"] = max_price_cents

        try:
            payload = await self._get_json(
                f"/api/recommendations/{urllib.parse.quote(user_id, safe='')}",
                params=params,
                service_label="推荐服务",
            )
            response = self._validate(
                RecommendationResponse,
                payload,
                "推荐服务",
            )
            return response.candidates
        except MallNotFoundError:
            return []

    async def get_ad_candidates(
        self,
        user_id: str,
        *,
        context_product_ids: tuple[str, ...] = (),
        limit: int = 3,
    ) -> list[AdCandidate]:
        params: dict[str, Any] = {"user_id": user_id, "limit": limit}
        if context_product_ids:
            params["context_product_ids"] = ",".join(context_product_ids)

        try:
            payload = await self._get_json(
                "/api/ads/candidates",
                params=params,
                service_label="广告服务",
            )
            response = self._validate(AdResponse, payload, "广告服务")
            return response.candidates
        except MallNotFoundError:
            return []