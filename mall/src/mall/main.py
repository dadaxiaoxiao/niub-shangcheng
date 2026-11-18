import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from mall import db
from mall.catalog import catalog
from mall.conversations_api import router as conversations_router
from mall.models import Product
from mall.personalization_api import router as personalization_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.ensure_ready()
    yield


app = FastAPI(
    title="Niub Mall API",
    version="0.2.0",
    description="Product catalog and conversation history for Niub Shangcheng.",
    lifespan=lifespan,
)

app.include_router(conversations_router)
app.include_router(personalization_router)


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database operation failed")
    return JSONResponse(
        status_code=503,
        content={"detail": "数据库暂时不可用，请稍后重试。"},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "mall",
        "products": "/api/products",
        "conversations": "/api/conversations",
        "users": "/api/users/{user_id}/profile",
        "recommendations": "/api/recommendations/{user_id}",
        "ads": "/api/ads/candidates",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, object]:
    ready, error = db.status()
    return {
        "status": "ok",
        "service": "mall",
        "database": "ready" if ready else "unavailable",
        "database_error": error,
    }


@app.get("/api/products", response_model=list[Product])
async def list_products() -> list[Product]:
    return catalog.list_products()


@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: str) -> Product:
    product = catalog.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product