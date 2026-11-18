from fastapi import APIRouter, HTTPException, Query

from mall import personalization
from mall.models import (
    AdResponse,
    BrowsingEvent,
    Cart,
    Order,
    RecommendationResponse,
    UserProfile,
)


router = APIRouter(tags=["personalization"])


def _ensure_user(user_id: str) -> None:
    if personalization.get_profile(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")


@router.get("/api/users/{user_id}/profile", response_model=UserProfile)
def get_profile(user_id: str) -> dict:
    profile = personalization.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return profile


@router.get(
    "/api/users/{user_id}/browsing-history",
    response_model=list[BrowsingEvent],
)
def list_browsing_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict]:
    _ensure_user(user_id)
    return personalization.list_browsing_history(user_id, limit)


@router.get("/api/users/{user_id}/orders", response_model=list[Order])
def list_orders(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    _ensure_user(user_id)
    return personalization.list_orders(user_id, limit)


@router.get("/api/users/{user_id}/cart", response_model=Cart)
def get_cart(user_id: str) -> dict:
    cart = personalization.get_cart(user_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return cart


@router.get(
    "/api/recommendations/{user_id}",
    response_model=RecommendationResponse,
)
def get_recommendations(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=20),
    focus: str = Query(default="", max_length=200),
    category: str = Query(default="", max_length=40),
    max_price_cents: int | None = Query(default=None, ge=0),
) -> dict:
    _ensure_user(user_id)
    candidates = personalization.recommend(
        user_id,
        focus=focus,
        category=category,
        max_price_cents=max_price_cents,
        limit=limit,
    )
    return {
        "user_id": user_id,
        "strategy": "hybrid",
        "candidates": candidates,
    }


@router.get("/api/ads/candidates", response_model=AdResponse)
def get_ad_candidates(
    user_id: str = Query(min_length=1, max_length=64),
    context_product_ids: str = Query(default="", max_length=500),
    limit: int = Query(default=3, ge=1, le=10),
) -> dict:
    _ensure_user(user_id)
    context = tuple(
        item.strip()
        for item in context_product_ids.split(",")
        if item.strip()
    )
    return {
        "candidates": personalization.list_ad_candidates(
            user_id,
            context_product_ids=context,
            limit=limit,
        )
    }