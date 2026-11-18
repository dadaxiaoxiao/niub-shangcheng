"""In-memory mock of the personalization services used by the shopping agent.

This module stands in for the real user-profile, recommendation and ad
services. Everything is derived from the fixed demo user and the in-memory
catalog, so it works without MySQL.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from mall.catalog import catalog
from mall.models import Product


DEMO_USER_ID = "u-demo"

# A consumable is considered due for repurchase after 80% of its cycle.
CONSUMABLE_CYCLES_DAYS = {"茶饮": 60, "香氛": 180}
GIFT_WORDS = ("送", "礼", "生日", "朋友", "家人", "同事")
SELF_WORDS = ("自己", "自用", "日常", "办公室")
FOCUS_TERMS = ("茶", "杯", "盘", "香", "礼盒", "包", "蜡烛")

# Campaign-only products stay out of the organic recommendation pool so that
# the ad slot has something distinct to offer.
AD_ONLY_PRODUCT_IDS = {"winter-gift-box"}


def _iso(days_ago: float = 0) -> str:
    value = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _date_in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def get_profile(user_id: str) -> dict[str, Any] | None:
    if user_id != DEMO_USER_ID:
        return None

    return {
        "user_id": DEMO_USER_ID,
        "display_name": "林小满",
        "member_level": "金卡",
        "tags": ["茶饮爱好者", "器物控", "偏好清淡香气", "有送礼需求"],
        "preferred_categories": ["茶饮", "器物"],
        "price_band_cents": (6000, 26000),
        "avoid": ["浓香", "甜腻"],
        "occasions": [
            {
                "name": "朋友生日",
                "date": _date_in(14),
                "budget_cents": 30000,
            }
        ],
    }


def list_browsing_history(
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if user_id != DEMO_USER_ID:
        return []

    events: list[dict[str, Any]] = [
        {
            "event": "search",
            "product_id": None,
            "query": "送朋友的生日礼物",
            "count": 2,
            "dwell_seconds": 0,
            "last_seen_at": _iso(1),
        },
        {
            "event": "view",
            "product_id": "bamboo-tray",
            "query": None,
            "count": 3,
            "dwell_seconds": 140,
            "last_seen_at": _iso(1),
        },
        {
            "event": "search",
            "product_id": None,
            "query": "茶盘",
            "count": 1,
            "dwell_seconds": 0,
            "last_seen_at": _iso(2),
        },
        {
            "event": "view",
            "product_id": "ceramic-cup",
            "query": None,
            "count": 2,
            "dwell_seconds": 80,
            "last_seen_at": _iso(3),
        },
        {
            "event": "view",
            "product_id": "linen-tote",
            "query": None,
            "count": 2,
            "dwell_seconds": 45,
            "last_seen_at": _iso(6),
        },
        {
            "event": "view",
            "product_id": "scented-sachet",
            "query": None,
            "count": 1,
            "dwell_seconds": 20,
            "last_seen_at": _iso(4),
        },
        {
            "event": "view",
            "product_id": "forest-candle",
            "query": None,
            "count": 1,
            "dwell_seconds": 12,
            "last_seen_at": _iso(5),
        },
    ]
    return events[:limit]


def list_orders(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    if user_id != DEMO_USER_ID:
        return []

    orders: list[dict[str, Any]] = [
        {
            "id": "demo-order-1003",
            "status": "returned",
            "created_at": _iso(40),
            "total_cents": 15900,
            "items": [
                {
                    "product_id": "linen-tote",
                    "name": "日常亚麻袋",
                    "quantity": 1,
                    "price_cents": 15900,
                }
            ],
        },
        {
            "id": "demo-order-1001",
            "status": "completed",
            "created_at": _iso(64),
            "total_cents": 8800,
            "items": [
                {
                    "product_id": "jasmine-tea",
                    "name": "云岫茉莉",
                    "quantity": 1,
                    "price_cents": 8800,
                }
            ],
        },
        {
            "id": "demo-order-1002",
            "status": "completed",
            "created_at": _iso(100),
            "total_cents": 16900,
            "items": [
                {
                    "product_id": "forest-candle",
                    "name": "雨后森林香氛",
                    "quantity": 1,
                    "price_cents": 16900,
                }
            ],
        },
        {
            "id": "demo-order-1004",
            "status": "completed",
            "created_at": _iso(340),
            "total_cents": 39900,
            "items": [
                {
                    "product_id": "weekend-gift",
                    "name": "周末慢享礼盒",
                    "quantity": 1,
                    "price_cents": 39900,
                }
            ],
        },
    ]
    return orders[:limit]


def get_cart(user_id: str) -> dict[str, Any] | None:
    if user_id != DEMO_USER_ID:
        return None

    return {
        "user_id": DEMO_USER_ID,
        "items": [
            {
                "product_id": "bamboo-tray",
                "name": "竹影茶盘",
                "quantity": 1,
                "price_cents": 23900,
                "added_at": _iso(1),
            },
            {
                "product_id": "ceramic-cup",
                "name": "手作月白杯",
                "quantity": 1,
                "price_cents": 12900,
                "added_at": _iso(2),
            },
        ],
        "updated_at": _iso(1),
    }


def _days_since(iso_timestamp: str, now: datetime) -> int:
    try:
        parsed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((now - parsed).total_seconds() // 86400))


def _purchase_facts(
    user_id: str,
) -> tuple[set[str], dict[str, int]]:
    """Return returned product ids and days since the latest completed purchase."""
    returned: set[str] = set()
    completed: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    for order in list_orders(user_id, limit=50):
        if order["status"] == "returned":
            returned.update(item["product_id"] for item in order["items"])
            continue
        if order["status"] != "completed":
            continue

        days = _days_since(order["created_at"], now)
        for item in order["items"]:
            previous = completed.get(item["product_id"])
            if previous is None or days < previous:
                completed[item["product_id"]] = days

    return returned, completed


def _product_text(product: Product) -> str:
    return " ".join(
        [
            product.name,
            product.summary,
            product.description,
            product.category,
        ]
    ).casefold()


def recommend(
    user_id: str,
    *,
    focus: str = "",
    category: str = "",
    max_price_cents: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    profile = get_profile(user_id)
    if profile is None:
        return []

    events = list_browsing_history(user_id, limit=50)
    views = {
        event["product_id"]: event
        for event in events
        if event["event"] == "view" and event["product_id"]
    }
    cart = get_cart(user_id)
    cart_ids = {
        item["product_id"] for item in (cart or {}).get("items", [])
    }
    returned, completed = _purchase_facts(user_id)
    focus_text = focus.casefold()
    gift_intent = any(word in focus_text for word in GIFT_WORDS)
    self_intent = any(word in focus_text for word in SELF_WORDS)
    focus_terms = [term for term in FOCUS_TERMS if term in focus_text]
    category_key = category.casefold()

    scored: list[dict[str, Any]] = []
    for product in catalog.list_products():
        if product.id in AD_ONLY_PRODUCT_IDS:
            continue
        if product.stock <= 0:
            continue
        if category_key and product.category.casefold() != category_key:
            continue
        if (
            max_price_cents is not None
            and product.price_cents > max_price_cents
        ):
            continue

        score = 0.15
        signals: list[str] = []
        reasons: list[str] = []

        if product.category in profile["preferred_categories"]:
            score += 0.18
            signals.append("preferred_category")
            reasons.append(f"你常买{product.category}")

        view = views.get(product.id)
        if view:
            score += min(view["count"] * 0.03, 0.09)
            score += min(view["dwell_seconds"] / 1800, 0.06)
            if view["count"] >= 2 or view["dwell_seconds"] >= 60:
                signals.append("recent_view")
                reasons.append(f"你最近看过 {view['count']} 次")

        if product.id in cart_ids:
            score += 0.12
            signals.append("in_cart")
            reasons.append("已在购物车，可作为搭配参考")

        if product.id in returned:
            signals.append("returned")
            reasons.append("上次购买后退货，谨慎推荐")
        else:
            days = completed.get(product.id)
            if days is not None:
                cycle = CONSUMABLE_CYCLES_DAYS.get(product.category)
                if cycle and days >= cycle * 0.8:
                    score += 0.2
                    signals.append("repurchase_due")
                    reasons.append("上次购买已接近复购周期")
                elif cycle:
                    score += 0.02
                    signals.append("recently_purchased")
                    reasons.append("你最近买过")
                elif product.category == "礼盒":
                    score += 0.05
                    signals.append("previously_purchased")
                    reasons.append("你之前买过同款礼盒")
                else:
                    score -= 0.25
                    signals.append("owned")
                    reasons.append("你已买过同类商品")

        if gift_intent and product.category == "礼盒":
            score += 0.12
            signals.append("gift_occasion")
            reasons.append("适合你近期的送礼场合")
        if self_intent and product.category == "礼盒":
            score -= 0.15
            signals.append("self_use")
            reasons.append("你这次偏向自用")

        haystack = _product_text(product)
        if focus_terms and any(term in haystack for term in focus_terms):
            score += 0.05
            signals.append("matches_focus")
            reasons.append("符合你这轮的关键词")
        if any(word in haystack for word in profile["avoid"]):
            score -= 0.4
            signals.append("avoid")
            reasons.append("含你不太喜欢的风格")

        score = round(max(0.0, min(1.0, score)), 2)
        if not reasons:
            reasons.append("本期值得关注")

        scored.append(
            {
                "product_id": product.id,
                "score": score,
                "reason": "；".join(reasons[:2]),
                "signals": signals,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def list_ad_candidates(
    user_id: str,
    *,
    context_product_ids: tuple[str, ...] = (),
    limit: int = 3,
) -> list[dict[str, Any]]:
    if user_id != DEMO_USER_ID:
        return []

    tea_context = bool(
        set(context_product_ids) & {"jasmine-tea", "white-tea", "travel-tea-set"}
    )
    candidates = [
        {
            "product_id": "winter-gift-box",
            "campaign_id": "campaign-winter-2026",
            "campaign_name": "冬日茶礼",
            "relevance": 0.77 if tea_context else 0.72,
            "bid_cents": 180,
            "ad_copy": "冬日限定茶礼，含白牡丹与盖碗，送礼体面。",
        },
        {
            "product_id": "ceramic-cup",
            "campaign_id": "campaign-cup-2026",
            "campaign_name": "手作器物周",
            "relevance": 0.66,
            "bid_cents": 120,
            "ad_copy": "手作月白杯，温润釉色，日常好用。",
        },
        {
            "product_id": "scented-sachet",
            "campaign_id": "campaign-sachet-2026",
            "campaign_name": "桂花季",
            "relevance": 0.28,
            "bid_cents": 80,
            "ad_copy": "浓香桂花囊，衣柜与玄关留香。",
        },
    ]
    candidates.sort(key=lambda item: item["relevance"], reverse=True)
    return candidates[:limit]