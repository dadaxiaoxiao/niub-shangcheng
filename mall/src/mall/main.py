from fastapi import FastAPI, HTTPException

from mall.catalog import catalog
from mall.models import Product


app = FastAPI(
    title="Niub Mall API",
    version="0.1.0",
    description="Product catalog for Niub Shangcheng.",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "mall",
        "products": "/api/products",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mall"}


@app.get("/api/products", response_model=list[Product])
async def list_products() -> list[Product]:
    return catalog.list_products()


@app.get("/api/products/{product_id}", response_model=Product)
async def get_product(product_id: str) -> Product:
    product = catalog.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product
