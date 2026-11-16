import asyncio
import unittest

from pydantic import ValidationError

from agent_service.mall_client import Product
from agent_service.tools import (
    GetProductArgs,
    SearchProductsArgs,
    ToolRunner,
    filter_products,
    product_payload,
)


PRODUCTS = [
    Product(
        id="jasmine-tea",
        name="云岫茉莉",
        summary="清甜花香，适合工作间隙的一杯热茶。",
        description="精选春季绿茶与茉莉窨制，香气轻盈，回甘干净。每罐 80 克。",
        price_cents=8800,
        category="茶饮",
        stock=36,
        badge="本周精选",
    ),
    Product(
        id="ceramic-cup",
        name="手作月白杯",
        summary="温润釉色与恰到好处的握持感。",
        description="手工拉坯陶瓷杯，容量 260 毫升。",
        price_cents=12900,
        category="器物",
        stock=18,
    ),
    Product(
        id="linen-tote",
        name="日常亚麻袋",
        summary="轻便耐用，通勤与周末都合适。",
        description="高密度亚麻帆布托特包，可容纳 14 英寸笔记本电脑。",
        price_cents=15900,
        category="日常",
        stock=22,
        badge="补货到店",
    ),
    Product(
        id="forest-candle",
        name="雨后森林香氛",
        summary="雪松、苔藓与一点点湿木气息。",
        description="大豆蜡香氛蜡烛，净含量 180 克。",
        price_cents=16900,
        category="香氛",
        stock=9,
    ),
    Product(
        id="bamboo-tray",
        name="竹影茶盘",
        summary="简洁的日常茶席，也可以作为首饰托盘。",
        description="整竹切削与手工打磨，尺寸 32 × 20 厘米。",
        price_cents=23900,
        category="器物",
        stock=12,
    ),
    Product(
        id="weekend-gift",
        name="周末慢享礼盒",
        summary="把茶、香气和片刻安静打包送人。",
        description="包含茉莉茶一罐、手作杯一只与香氛蜡烛一份。",
        price_cents=39900,
        category="礼盒",
        stock=6,
        badge="限量",
    ),
]


class FilterProductsTest(unittest.TestCase):
    def test_filters_by_budget(self):
        result = filter_products(
            PRODUCTS,
            SearchProductsArgs(max_price_cents=15900, limit=10),
        )
        self.assertEqual(
            [product.id for product in result],
            ["jasmine-tea", "ceramic-cup", "linen-tote"],
        )

    def test_query_requires_all_tokens(self):
        self.assertEqual(
            filter_products(PRODUCTS, SearchProductsArgs(query="办公室 茶具")),
            [],
        )

    def test_query_matches_name_summary_and_description(self):
        result = filter_products(
            PRODUCTS,
            SearchProductsArgs(query="茶", limit=10),
        )
        self.assertEqual(
            [product.id for product in result],
            ["jasmine-tea", "bamboo-tray", "weekend-gift"],
        )

    def test_query_and_category_combine(self):
        result = filter_products(
            PRODUCTS,
            SearchProductsArgs(query="日常 茶", category="器物", limit=10),
        )
        self.assertEqual([product.id for product in result], ["bamboo-tray"])

    def test_filters_by_category_and_stock(self):
        result = filter_products(
            PRODUCTS,
            SearchProductsArgs(category="器物", limit=10),
        )
        self.assertEqual(
            [product.id for product in result],
            ["ceramic-cup", "bamboo-tray"],
        )

        out_of_stock = [
            product.model_copy(update={"stock": 0})
            if product.id == "ceramic-cup"
            else product
            for product in PRODUCTS
        ]
        self.assertEqual(
            [
                product.id
                for product in filter_products(
                    out_of_stock,
                    SearchProductsArgs(category="器物", limit=10),
                )
            ],
            ["bamboo-tray"],
        )
        self.assertEqual(
            [
                product.id
                for product in filter_products(
                    out_of_stock,
                    SearchProductsArgs(
                        category="器物",
                        in_stock_only=False,
                        limit=10,
                    ),
                )
            ],
            ["ceramic-cup", "bamboo-tray"],
        )

    def test_respects_limit(self):
        self.assertEqual(
            len(filter_products(PRODUCTS, SearchProductsArgs(limit=2))),
            2,
        )


class ProductPayloadTest(unittest.TestCase):
    def test_payload_includes_yuan_price_without_description(self):
        payload = product_payload(PRODUCTS[0])
        self.assertEqual(payload["price_yuan"], 88.0)
        self.assertEqual(payload["price_cents"], 8800)
        self.assertNotIn("description", payload)

    def test_detail_payload_includes_description(self):
        payload = product_payload(PRODUCTS[0], include_description=True)
        self.assertIn("description", payload)


class ArgumentValidationTest(unittest.TestCase):
    def test_rejects_out_of_range_values(self):
        with self.assertRaises(ValidationError):
            SearchProductsArgs(limit=0)
        with self.assertRaises(ValidationError):
            SearchProductsArgs(limit=11)
        with self.assertRaises(ValidationError):
            SearchProductsArgs(max_price_cents=-1)

    def test_rejects_empty_product_id(self):
        with self.assertRaises(ValidationError):
            GetProductArgs(product_id="")


class FakeMall:
    async def list_products(self):
        return PRODUCTS


class ToolRunnerTest(unittest.TestCase):
    def setUp(self):
        self.runner = ToolRunner(FakeMall())

    def test_search_returns_products(self):
        result = asyncio.run(
            self.runner.execute(
                "search_products",
                {"max_price_cents": 15900, "limit": 10},
            )
        )
        self.assertEqual(result["count"], 3)
        self.assertEqual(
            [product["id"] for product in result["products"]],
            ["jasmine-tea", "ceramic-cup", "linen-tote"],
        )
        self.assertNotIn("hint", result)

    def test_search_empty_result_includes_hint(self):
        result = asyncio.run(
            self.runner.execute("search_products", {"query": "相机"})
        )
        self.assertEqual(result["count"], 0)
        self.assertIn("hint", result)

    def test_get_product_includes_description(self):
        result = asyncio.run(
            self.runner.execute("get_product", {"product_id": "jasmine-tea"})
        )
        self.assertEqual(result["product"]["id"], "jasmine-tea")
        self.assertIn("description", result["product"])

    def test_get_unknown_product_returns_error(self):
        result = asyncio.run(
            self.runner.execute("get_product", {"product_id": "missing"})
        )
        self.assertIn("error", result)

    def test_invalid_arguments_return_error(self):
        result = asyncio.run(
            self.runner.execute("search_products", {"limit": 0})
        )
        self.assertIn("error", result)

    def test_unknown_tool_returns_error(self):
        result = asyncio.run(self.runner.execute("delete_everything", {}))
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()