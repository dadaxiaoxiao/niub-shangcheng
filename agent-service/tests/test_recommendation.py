import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from agent_service.mall_client import (
    AdCandidate,
    BrowsingEvent,
    Cart,
    CartItem,
    MallError,
    Occasion,
    Order,
    OrderItem,
    Product,
    RecommendationCandidate,
    UserProfile,
)
from agent_service.recommendation import RecommendArgs, RecommendationPipeline


def _iso(days_ago: int) -> str:
    value = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


PRODUCTS = [
    Product(
        id="jasmine-tea",
        name="云岫茉莉",
        summary="清甜花香。",
        description="春季绿茶与茉莉窨制。",
        price_cents=8800,
        category="茶饮",
        stock=36,
    ),
    Product(
        id="white-tea",
        name="云岫白牡丹",
        summary="清润毫香。",
        description="福鼎白茶原料。",
        price_cents=9800,
        category="茶饮",
        stock=20,
    ),
    Product(
        id="travel-tea-set",
        name="旅途茶器组",
        summary="盖碗与品杯。",
        description="白瓷盖碗与品杯。",
        price_cents=21900,
        category="器物",
        stock=10,
    ),
    Product(
        id="bamboo-tray",
        name="竹影茶盘",
        summary="简洁的日常茶席。",
        description="整竹切削。",
        price_cents=23900,
        category="器物",
        stock=12,
    ),
    Product(
        id="ceramic-cup",
        name="手作月白杯",
        summary="温润釉色。",
        description="手工拉坯陶瓷杯。",
        price_cents=12900,
        category="器物",
        stock=18,
    ),
    Product(
        id="linen-tote",
        name="日常亚麻袋",
        summary="轻便耐用。",
        description="高密度亚麻帆布托特包。",
        price_cents=15900,
        category="日常",
        stock=22,
    ),
    Product(
        id="scented-sachet",
        name="浓香桂花囊",
        summary="甜润浓郁的桂花香。",
        description="干桂花与香茅填充，香气偏浓。",
        price_cents=5900,
        category="香氛",
        stock=30,
    ),
    Product(
        id="forest-candle",
        name="雨后森林香氛",
        summary="雪松与苔藓。",
        description="大豆蜡香氛蜡烛。",
        price_cents=16900,
        category="香氛",
        stock=9,
    ),
    Product(
        id="winter-gift-box",
        name="冬日茶礼盒",
        summary="白茶、茶器与暖香。",
        description="白牡丹、盖碗与杯垫。",
        price_cents=29900,
        category="礼盒",
        stock=8,
    ),
    Product(
        id="weekend-gift",
        name="周末慢享礼盒",
        summary="茶、香气与片刻安静。",
        description="茉莉茶、手作杯与香氛蜡烛。",
        price_cents=39900,
        category="礼盒",
        stock=6,
    ),
]

PROFILE = UserProfile(
    user_id="u-demo",
    display_name="林小满",
    member_level="金卡",
    tags=["茶饮爱好者", "器物控"],
    preferred_categories=["茶饮", "器物"],
    price_band_cents=(6000, 26000),
    avoid=["浓香", "甜腻"],
    occasions=[
        Occasion(name="朋友生日", date="2026-12-02", budget_cents=30000)
    ],
)

BROWSING = [
    BrowsingEvent(
        event="view",
        product_id="bamboo-tray",
        count=3,
        dwell_seconds=140,
        last_seen_at=_iso(1),
    ),
    BrowsingEvent(
        event="view",
        product_id="ceramic-cup",
        count=2,
        dwell_seconds=80,
        last_seen_at=_iso(3),
    ),
    BrowsingEvent(
        event="view",
        product_id="linen-tote",
        count=2,
        dwell_seconds=45,
        last_seen_at=_iso(6),
    ),
    BrowsingEvent(
        event="view",
        product_id="scented-sachet",
        count=1,
        dwell_seconds=20,
        last_seen_at=_iso(4),
    ),
    BrowsingEvent(
        event="view",
        product_id="forest-candle",
        count=1,
        dwell_seconds=12,
        last_seen_at=_iso(5),
    ),
]

ORDERS = [
    Order(
        id="order-returned",
        status="returned",
        created_at=_iso(40),
        total_cents=15900,
        items=[
            OrderItem(
                product_id="linen-tote",
                name="日常亚麻袋",
                quantity=1,
                price_cents=15900,
            )
        ],
    ),
    Order(
        id="order-tea",
        status="completed",
        created_at=_iso(64),
        total_cents=8800,
        items=[
            OrderItem(
                product_id="jasmine-tea",
                name="云岫茉莉",
                quantity=1,
                price_cents=8800,
            )
        ],
    ),
    Order(
        id="order-candle",
        status="completed",
        created_at=_iso(100),
        total_cents=16900,
        items=[
            OrderItem(
                product_id="forest-candle",
                name="雨后森林香氛",
                quantity=1,
                price_cents=16900,
            )
        ],
    ),
    Order(
        id="order-gift",
        status="completed",
        created_at=_iso(340),
        total_cents=39900,
        items=[
            OrderItem(
                product_id="weekend-gift",
                name="周末慢享礼盒",
                quantity=1,
                price_cents=39900,
            )
        ],
    ),
]

CART = Cart(
    user_id="u-demo",
    items=[
        CartItem(
            product_id="bamboo-tray",
            name="竹影茶盘",
            quantity=1,
            price_cents=23900,
            added_at=_iso(1),
        ),
        CartItem(
            product_id="ceramic-cup",
            name="手作月白杯",
            quantity=1,
            price_cents=12900,
            added_at=_iso(2),
        ),
    ],
    updated_at=_iso(1),
)


def recommendation(product_id: str, score: float) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=product_id,
        score=score,
        reason=f"{product_id} 推荐理由",
        signals=[],
    )


def ad(product_id: str, relevance: float) -> AdCandidate:
    return AdCandidate(
        product_id=product_id,
        campaign_id=f"campaign-{product_id}",
        campaign_name="测试推广",
        relevance=relevance,
        bid_cents=100,
        ad_copy="测试广告文案",
    )


class FakeMall:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.products = PRODUCTS
        self.profile = PROFILE
        self.browsing = BROWSING
        self.orders = ORDERS
        self.cart = CART
        self.recommendations: list[RecommendationCandidate] = [
            recommendation("bamboo-tray", 0.88),
            recommendation("ceramic-cup", 0.85),
            recommendation("jasmine-tea", 0.8),
            recommendation("white-tea", 0.6),
            recommendation("travel-tea-set", 0.55),
            recommendation("weekend-gift", 0.5),
            recommendation("linen-tote", 0.4),
            recommendation("scented-sachet", 0.3),
            recommendation("forest-candle", 0.2),
        ]
        self.ads: list[AdCandidate] = []
        self.products_error: Exception | None = None
        self.profile_error: Exception | None = None
        self.recommendations_error: Exception | None = None
        self.ads_error: Exception | None = None
        self.ad_context: tuple[str, ...] = ()

    async def list_products(self) -> list[Product]:
        self.calls.append("products")
        if self.products_error:
            raise self.products_error
        return self.products

    async def get_profile(self, user_id: str) -> UserProfile | None:
        self.calls.append("profile")
        if self.profile_error:
            raise self.profile_error
        return self.profile

    async def get_browsing_history(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[BrowsingEvent]:
        self.calls.append("browsing")
        return self.browsing

    async def get_orders(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[Order]:
        self.calls.append("orders")
        return self.orders

    async def get_cart(self, user_id: str) -> Cart | None:
        self.calls.append("cart")
        return self.cart

    async def get_recommendations(
        self,
        user_id: str,
        *,
        focus: str = "",
        category: str = "",
        max_price_cents: int | None = None,
        limit: int = 10,
    ) -> list[RecommendationCandidate]:
        self.calls.append("recommendations")
        if self.recommendations_error:
            raise self.recommendations_error
        return self.recommendations

    async def get_ad_candidates(
        self,
        user_id: str,
        *,
        context_product_ids: tuple[str, ...] = (),
        limit: int = 3,
    ) -> list[AdCandidate]:
        self.calls.append("ads")
        self.ad_context = context_product_ids
        if self.ads_error:
            raise self.ads_error
        return self.ads


def run_pipeline(mall: FakeMall, args: RecommendArgs | None = None) -> dict:
    pipeline = RecommendationPipeline(mall, "u-demo")
    return asyncio.run(pipeline.run(args or RecommendArgs()))


class RecommendationPipelineTest(unittest.TestCase):
    def test_filters_cart_returned_avoid_and_owned_items(self):
        result = run_pipeline(FakeMall())
        ids = [candidate["id"] for candidate in result["candidates"]]

        self.assertNotIn("bamboo-tray", ids)
        self.assertNotIn("ceramic-cup", ids)
        self.assertNotIn("linen-tote", ids)
        self.assertNotIn("scented-sachet", ids)
        self.assertEqual(
            ids,
            [
                "jasmine-tea",
                "white-tea",
                "travel-tea-set",
                "weekend-gift",
                "forest-candle",
            ],
        )

        by_id = {
            candidate["id"]: candidate for candidate in result["candidates"]
        }
        self.assertTrue(by_id["jasmine-tea"]["repurchase_due"])
        self.assertTrue(by_id["weekend-gift"]["previously_purchased"])
        self.assertNotIn("repurchase_due", by_id["forest-candle"])

        cart_names = [
            item["name"] for item in result["signals"]["cart"]
        ]
        self.assertIn("竹影茶盘", cart_names)
        self.assertIn("手作月白杯", cart_names)
        self.assertIsNone(result["hint"])

    def test_ad_slot_uses_one_relevant_unseen_candidate(self):
        mall = FakeMall()
        mall.recommendations = [
            recommendation("jasmine-tea", 0.8),
            recommendation("white-tea", 0.6),
            recommendation("travel-tea-set", 0.55),
        ]
        mall.ads = [
            ad("winter-gift-box", 0.72),
            ad("forest-candle", 0.65),
            ad("ceramic-cup", 0.66),
            ad("scented-sachet", 0.28),
        ]

        result = run_pipeline(mall)
        ids = [candidate["id"] for candidate in result["candidates"]]
        sponsored = [
            candidate
            for candidate in result["candidates"]
            if candidate["sponsored"]
        ]

        self.assertEqual(result["ad_slots_used"], 1)
        self.assertEqual(len(sponsored), 1)
        self.assertEqual(sponsored[0]["id"], "winter-gift-box")
        self.assertEqual(sponsored[0]["source"], "ad")
        self.assertIn("推广", sponsored[0]["reason"])
        self.assertNotIn("forest-candle", ids)
        self.assertNotIn("ceramic-cup", ids)
        self.assertNotIn("scented-sachet", ids)
        self.assertLess(
            mall.calls.index("recommendations"),
            mall.calls.index("ads"),
        )
        self.assertEqual(
            mall.ad_context,
            ("jasmine-tea", "white-tea", "travel-tea-set"),
        )

    def test_service_failures_degrade_with_warnings(self):
        mall = FakeMall()
        mall.profile_error = MallError("profile down")
        mall.recommendations_error = MallError("recs down")
        mall.ads_error = MallError("ads down")
        mall.recommendations = []

        result = run_pipeline(mall)

        self.assertEqual(result["candidates"], [])
        self.assertTrue(result["profile"]["cold_start"])
        self.assertIn("hint", result)
        self.assertTrue(result["hint"])
        joined = " ".join(result["warnings"])
        self.assertIn("用户画像服务", joined)
        self.assertIn("推荐服务", joined)
        self.assertIn("广告服务", joined)

    def test_missing_profile_is_cold_start_without_warning(self):
        mall = FakeMall()
        mall.profile = None
        mall.recommendations = []
        mall.ads = []

        result = run_pipeline(mall)

        self.assertTrue(result["profile"]["cold_start"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["candidates"], [])

    def test_catalog_failure_raises_mall_error(self):
        mall = FakeMall()
        mall.products_error = MallError("catalog down")

        with self.assertRaises(MallError):
            run_pipeline(mall)

    def test_unknown_candidate_is_ignored_and_warned(self):
        mall = FakeMall()
        mall.recommendations = [
            recommendation("ghost-product", 0.9),
            recommendation("jasmine-tea", 0.5),
        ]

        result = run_pipeline(mall)

        self.assertEqual(
            [candidate["id"] for candidate in result["candidates"]],
            ["jasmine-tea"],
        )
        self.assertIn(
            "ghost-product",
            " ".join(result["warnings"]),
        )

    def test_explicit_budget_and_category_are_hard_filters(self):
        mall = FakeMall()
        mall.recommendations = [
            recommendation("jasmine-tea", 0.8),
            recommendation("white-tea", 0.7),
            recommendation("travel-tea-set", 0.6),
            recommendation("winter-gift-box", 0.5),
        ]

        result = run_pipeline(
            mall,
            RecommendArgs(category="茶饮", max_price_cents=10000),
        )

        self.assertEqual(
            [candidate["id"] for candidate in result["candidates"]],
            ["jasmine-tea", "white-tea"],
        )

    def test_out_of_stock_and_duplicate_recommendations_are_filtered(self):
        mall = FakeMall()
        mall.products = [
            product.model_copy(update={"stock": 0})
            if product.id == "white-tea"
            else product
            for product in PRODUCTS
        ]
        mall.recommendations = [
            recommendation("jasmine-tea", 0.8),
            recommendation("jasmine-tea", 0.7),
            recommendation("white-tea", 0.6),
        ]

        result = run_pipeline(mall)

        self.assertEqual(
            [candidate["id"] for candidate in result["candidates"]],
            ["jasmine-tea"],
        )


if __name__ == "__main__":
    unittest.main()