from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from agent_service.mall_client import MallClient, MallError, Product
from agent_service.recommendation import RecommendArgs, RecommendationPipeline


TOOL_LABELS = {
    "search_products": "正在检索商品目录",
    "get_product": "正在查看商品详情",
    "recommend_products": "正在结合你的偏好与浏览记录挑选商品",
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "在牛逼商城的商品目录中按关键词、品类、价格和库存筛选商品。"
                "推荐任何商品前必须先调用此工具；返回结果是真实商品及其价格与库存。"
                "关键词按字面匹配商品名称、描述和品类，多个词需要同时出现；"
                "可用品类：茶饮、器物、日常、香氛、礼盒。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "关键词，按字面匹配商品名称、描述或品类。"
                            "优先用具体名词，例如 茶、杯、香氛、茶盘、礼盒、亚麻；"
                            "「礼物」「送礼」这类泛词可能匹配不到商品。多个词用空格分隔，需同时出现。"
                        ),
                    },
                    "category": {
                        "type": "string",
                        "description": "品类精确匹配，例如 茶饮、器物、日常、香氛、礼盒。",
                    },
                    "max_price_cents": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "最高价格，单位分。例如 300 元传 30000。",
                    },
                    "in_stock_only": {
                        "type": "boolean",
                        "description": "是否只返回有库存的商品，默认 true。",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "最多返回几个商品，默认 5。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "按商品 ID 获取单个商品的完整信息，包括详细描述。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "商品 ID，例如 jasmine-tea。",
                    }
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_products",
            "description": (
                "基于当前用户的画像、浏览/搜索记录、历史订单和购物车，"
                "先向商品推荐系统获取候选，再向广告系统获取最多 1 个推广候选，"
                "并完成库存、价格、负反馈和购物车校验。"
                "用户请求个性化推荐、送礼建议或不知道买什么时，必须先调用此工具。"
                "工具返回候选池和用户信号，由你综合判断后选出 3 个商品。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": (
                            "用户本轮关注点或场景的简短摘要，"
                            "例如 送朋友生日礼物、办公室自用。"
                        ),
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "用户明确要求的品类，"
                            "例如 茶饮、器物、日常、香氛、礼盒。"
                        ),
                    },
                    "max_price_cents": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "用户明确给出的最高价格，单位分。例如 300 元传 30000。",
                    },
                    "exclude_product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 20,
                        "description": "本次对话中已经推荐过、需要排除的商品 ID。",
                    },
                },
                "required": [],
            },
        },
    },
]


class SearchProductsArgs(BaseModel):
    query: str = ""
    category: str = ""
    max_price_cents: int | None = Field(default=None, ge=0)
    in_stock_only: bool = True
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class GetProductArgs(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class RecommendProductsArgs(BaseModel):
    focus: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=40)
    max_price_cents: int | None = Field(default=None, ge=0)
    exclude_product_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("focus", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("exclude_product_ids")
    @classmethod
    def clean_product_ids(cls, value: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                item.strip() for item in value if item.strip()
            )
        )


def product_payload(
    product: Product,
    *,
    include_description: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": product.id,
        "name": product.name,
        "summary": product.summary,
        "price_cents": product.price_cents,
        "price_yuan": round(product.price_cents / 100, 2),
        "currency": product.currency,
        "category": product.category,
        "stock": product.stock,
        "badge": product.badge,
    }
    if include_description:
        payload["description"] = product.description
    return payload


def filter_products(
    products: list[Product],
    args: SearchProductsArgs,
) -> list[Product]:
    tokens = [token for token in args.query.casefold().split() if token]
    category = args.category.casefold()
    matched: list[Product] = []

    for product in products:
        if (
            args.max_price_cents is not None
            and product.price_cents > args.max_price_cents
        ):
            continue
        if args.in_stock_only and product.stock <= 0:
            continue
        if category and product.category.casefold() != category:
            continue
        if tokens:
            haystack = " ".join(
                [
                    product.name,
                    product.summary,
                    product.description,
                    product.category,
                ]
            ).casefold()
            if not all(token in haystack for token in tokens):
                continue
        matched.append(product)

    return matched[: args.limit]


class ToolRunner:
    """Executes model-requested tools against the mall catalog."""

    def __init__(self, mall: MallClient, user_id: str = "u-demo") -> None:
        self._mall = mall
        self._pipeline = RecommendationPipeline(mall, user_id)

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return TOOL_DEFINITIONS

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if name == "search_products":
            return await self._search(arguments)
        if name == "get_product":
            return await self._get_product(arguments)
        if name == "recommend_products":
            return await self._recommend(arguments)
        return {"error": f"未知工具：{name}"}

    async def _recommend(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = RecommendProductsArgs.model_validate(arguments)
        except ValidationError:
            return {"error": "推荐参数不合法，请调整约束后重试。"}

        try:
            return await self._pipeline.run(
                RecommendArgs(
                    focus=args.focus,
                    category=args.category,
                    max_price_cents=args.max_price_cents,
                    exclude_product_ids=args.exclude_product_ids,
                )
            )
        except MallError as exc:
            return {"error": str(exc)}

    async def _search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = SearchProductsArgs.model_validate(arguments)
        except ValidationError:
            return {"error": "查询参数不合法，请调整筛选条件后重试。"}

        try:
            products = await self._mall.list_products()
        except MallError as exc:
            return {"error": str(exc)}

        matched = filter_products(products, args)
        result: dict[str, Any] = {
            "count": len(matched),
            "products": [product_payload(product) for product in matched],
        }
        if not matched:
            result["hint"] = (
                "没有匹配结果。可以去掉过窄的关键词，"
                "或改用具体品类：茶饮、器物、日常、香氛、礼盒。"
            )
        return result

    async def _get_product(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = GetProductArgs.model_validate(arguments)
        except ValidationError:
            return {"error": "商品 ID 不合法。"}

        try:
            products = await self._mall.list_products()
        except MallError as exc:
            return {"error": str(exc)}

        product = next(
            (item for item in products if item.id == args.product_id),
            None,
        )
        if product is None:
            return {"error": "没有找到该商品。"}
        return {"product": product_payload(product, include_description=True)}