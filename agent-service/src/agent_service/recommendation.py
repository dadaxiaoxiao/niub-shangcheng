from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agent_service.mall_client import (
    AdCandidate,
    BrowsingEvent,
    Cart,
    MallClient,
    MallError,
    Order,
    Product,
    RecommendationCandidate,
    UserProfile,
)


AD_RELEVANCE_FLOOR = 0.5
CONSUMABLE_CYCLES_DAYS = {"茶饮": 60, "香氛": 180}
DURABLE_CATEGORIES = {"器物", "日常"}


@dataclass
class RecommendArgs:
    focus: str = ""
    category: str = ""
    max_price_cents: int | None = None
    exclude_product_ids: list[str] = field(default_factory=list)


def _days_since(value: str, now: datetime) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((now - parsed).total_seconds() // 86400))


def _purchase_facts(orders: list[Order]) -> tuple[set[str], dict[str, int]]:
    """Return returned ids and days since the latest completed purchase."""
    returned: set[str] = set()
    completed: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    for order in orders:
        if order.status == "returned":
            returned.update(item.product_id for item in order.items)
            continue
        if order.status != "completed":
            continue

        days = _days_since(order.created_at, now)
        for item in order.items:
            previous = completed.get(item.product_id)
            if previous is None or days < previous:
                completed[item.product_id] = days

    return returned, completed


class RecommendationPipeline:
    """Builds a personalized, validated candidate pool for the model."""

    def __init__(self, mall: MallClient, user_id: str) -> None:
        self._mall = mall
        self._user_id = user_id

    async def run(self, args: RecommendArgs) -> dict[str, Any]:
        products, profile, browsing, orders, cart = await asyncio.gather(
            self._mall.list_products(),
            self._mall.get_profile(self._user_id),
            self._mall.get_browsing_history(self._user_id),
            self._mall.get_orders(self._user_id),
            self._mall.get_cart(self._user_id),
            return_exceptions=True,
        )
        warnings: list[str] = []

        if isinstance(products, Exception):
            raise MallError("商品服务暂时不可用，无法生成推荐。") from products

        profile = self._optional(profile, "用户画像服务", warnings)
        browsing = self._optional(browsing, "行为记录服务", warnings, [])
        orders = self._optional(orders, "订单服务", warnings, [])
        cart = self._optional(cart, "购物车服务", warnings)

        products_by_id = {product.id: product for product in products}
        returned, completed = _purchase_facts(orders)
        cart_ids = {item.product_id for item in (cart.items if cart else [])}
        avoid = profile.avoid if profile else []

        recommendations: list[RecommendationCandidate] = []
        try:
            recommendations = await self._mall.get_recommendations(
                self._user_id,
                focus=args.focus,
                category=args.category,
                max_price_cents=args.max_price_cents,
                limit=10,
            )
        except MallError:
            warnings.append("推荐服务暂时不可用，已改为目录检索兜底。")

        ad_candidates: list[AdCandidate] = []
        try:
            ad_candidates = await self._mall.get_ad_candidates(
                self._user_id,
                context_product_ids=tuple(
                    candidate.product_id for candidate in recommendations
                ),
                limit=3,
            )
        except MallError:
            warnings.append("广告服务暂时不可用，已跳过推广候选。")

        excluded = set(args.exclude_product_ids)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        filtered = 0

        for recommendation in recommendations:
            product = products_by_id.get(recommendation.product_id)
            if product is None:
                warnings.append(
                    f"推荐候选 {recommendation.product_id} 不在商品目录中，已忽略。"
                )
                continue
            if product.id in excluded or product.id in seen:
                continue
            if self._drop_reason(
                product,
                args,
                excluded,
                avoid,
                cart_ids,
                returned,
                completed,
            ):
                filtered += 1
                continue

            seen.add(product.id)
            payload = self._candidate_payload(
                product,
                score=recommendation.score,
                source="recommendation",
                reason=recommendation.reason,
            )
            self._annotate_purchase(payload, product, completed)
            candidates.append(payload)

        ad_slots_used = 0
        skipped_ads = 0
        for ad in sorted(
            ad_candidates,
            key=lambda item: item.relevance,
            reverse=True,
        ):
            if ad.relevance < AD_RELEVANCE_FLOOR:
                skipped_ads += 1
                continue

            product = products_by_id.get(ad.product_id)
            if product is None:
                warnings.append(
                    f"广告候选 {ad.product_id} 不在商品目录中，已忽略。"
                )
                continue
            if product.id in excluded or product.id in seen:
                continue
            if self._drop_reason(
                product,
                args,
                excluded,
                avoid,
                cart_ids,
                returned,
                completed,
            ):
                skipped_ads += 1
                continue

            seen.add(product.id)
            payload = self._candidate_payload(
                product,
                score=ad.relevance,
                source="ad",
                reason=f"广告主推广：{ad.campaign_name}。{ad.ad_copy}",
                sponsored=True,
            )
            self._annotate_purchase(payload, product, completed)
            candidates.append(payload)
            ad_slots_used = 1
            break

        if filtered:
            warnings.append(
                f"已按购物车、退货记录、偏好和预算过滤 {filtered} 个候选。"
            )
        if skipped_ads:
            warnings.append(
                "部分广告候选相关度不足或与偏好/购物车冲突，已跳过。"
            )

        hint: str | None = None
        if len(candidates) < 3:
            hint = "候选不足 3 个，可调用 search_products 从目录补充。"

        return {
            "profile": self._profile_summary(profile),
            "signals": self._signals(
                browsing,
                orders,
                cart,
                products_by_id,
                completed,
            ),
            "candidates": candidates,
            "target_count": 3,
            "ad_slots_used": ad_slots_used,
            "warnings": warnings,
            "hint": hint,
        }

    @staticmethod
    def _optional(
        value: Any,
        label: str,
        warnings: list[str],
        default: Any = None,
    ) -> Any:
        if isinstance(value, Exception):
            warnings.append(f"{label}暂时不可用，本次已降级。")
            return default
        return value

    @staticmethod
    def _matches_avoid(product: Product, avoid: list[str]) -> bool:
        if not avoid:
            return False
        haystack = " ".join(
            [
                product.name,
                product.summary,
                product.description,
                product.category,
            ]
        )
        return any(word and word in haystack for word in avoid)

    def _drop_reason(
        self,
        product: Product,
        args: RecommendArgs,
        excluded: set[str],
        avoid: list[str],
        cart_ids: set[str],
        returned: set[str],
        completed: dict[str, int],
    ) -> str | None:
        if product.id in excluded:
            return "excluded"
        if product.id in cart_ids:
            return "in_cart"
        if product.id in returned:
            return "returned"
        if self._matches_avoid(product, avoid):
            return "avoid"
        if product.category in DURABLE_CATEGORIES and product.id in completed:
            return "owned"
        if (
            args.max_price_cents is not None
            and product.price_cents > args.max_price_cents
        ):
            return "over_budget"
        if (
            args.category
            and product.category.casefold() != args.category.casefold()
        ):
            return "category"
        if product.stock <= 0:
            return "out_of_stock"
        return None

    @staticmethod
    def _candidate_payload(
        product: Product,
        *,
        score: float,
        source: str,
        reason: str,
        sponsored: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": product.id,
            "name": product.name,
            "summary": product.summary,
            "price_yuan": round(product.price_cents / 100, 2),
            "currency": product.currency,
            "category": product.category,
            "stock": product.stock,
            "badge": product.badge,
            "score": round(score, 2),
            "source": source,
            "reason": reason,
            "sponsored": sponsored,
        }

    @staticmethod
    def _annotate_purchase(
        payload: dict[str, Any],
        product: Product,
        completed: dict[str, int],
    ) -> None:
        days = completed.get(product.id)
        if days is None:
            return

        cycle = CONSUMABLE_CYCLES_DAYS.get(product.category)
        if cycle is not None and days >= cycle * 0.8:
            payload["repurchase_due"] = True
        elif product.category == "礼盒":
            payload["previously_purchased"] = True

    @staticmethod
    def _profile_summary(profile: UserProfile | None) -> dict[str, Any]:
        if profile is None:
            return {
                "cold_start": True,
                "member_level": None,
                "tags": [],
                "preferred_categories": [],
                "price_band_yuan": None,
                "avoid": [],
                "occasions": [],
            }

        low, high = profile.price_band_cents
        return {
            "cold_start": False,
            "member_level": profile.member_level,
            "tags": profile.tags,
            "preferred_categories": profile.preferred_categories,
            "price_band_yuan": [round(low / 100), round(high / 100)],
            "avoid": profile.avoid,
            "occasions": [
                {
                    "name": occasion.name,
                    "date": occasion.date,
                    "budget_yuan": (
                        round(occasion.budget_cents / 100)
                        if occasion.budget_cents is not None
                        else None
                    ),
                }
                for occasion in profile.occasions
            ],
        }

    @staticmethod
    def _signals(
        browsing: list[BrowsingEvent],
        orders: list[Order],
        cart: Cart | None,
        products_by_id: dict[str, Product],
        completed: dict[str, int],
    ) -> dict[str, Any]:
        recent_views: list[dict[str, Any]] = []
        recent_searches: list[str] = []

        for event in browsing[:10]:
            if event.event == "view" and event.product_id:
                product = products_by_id.get(event.product_id)
                recent_views.append(
                    {
                        "name": (
                            product.name if product else event.product_id
                        ),
                        "count": event.count,
                        "dwell_seconds": event.dwell_seconds,
                    }
                )
            elif event.event == "search" and event.query:
                recent_searches.append(event.query)

        cart_items: list[dict[str, Any]] = []
        if cart:
            for item in cart.items[:10]:
                product = products_by_id.get(item.product_id)
                cart_items.append(
                    {
                        "name": product.name if product else item.name,
                        "quantity": item.quantity,
                    }
                )

        recent_orders: list[dict[str, Any]] = []
        for order in orders[:5]:
            recent_orders.append(
                {
                    "names": [item.name for item in order.items],
                    "status": order.status,
                    "purchased_on": order.created_at[:10],
                }
            )

        repurchase_due: list[str] = []
        for product_id, days in completed.items():
            product = products_by_id.get(product_id)
            if product is None:
                continue
            cycle = CONSUMABLE_CYCLES_DAYS.get(product.category)
            if cycle and days >= cycle * 0.8:
                repurchase_due.append(product.name)

        return {
            "recent_views": recent_views,
            "recent_searches": recent_searches,
            "cart": cart_items,
            "recent_orders": recent_orders,
            "repurchase_due": repurchase_due,
        }