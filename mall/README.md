# Mall

商城领域逻辑与 HTTP API。当前商品目录使用内存数据，后续可在这里替换成数据库。

```powershell
uv run uvicorn mall.main:app --reload --port 3001
```

- `GET /health`
- `GET /api/products`
- `GET /api/products/{product_id}`

