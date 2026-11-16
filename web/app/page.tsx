import type { CSSProperties } from "react";

import AgentChat from "@/components/agent-chat";


type Product = {
  id: string;
  name: string;
  summary: string;
  description: string;
  price_cents: number;
  currency: string;
  category: string;
  stock: number;
  badge: string | null;
  accent: string;
};

async function loadProducts(): Promise<Product[] | null> {
  const apiUrl = process.env.MALL_API_URL ?? "http://127.0.0.1:3001";

  try {
    const response = await fetch(`${apiUrl}/api/products`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      throw new Error(`Mall API returned ${response.status}`);
    }
    return (await response.json()) as Product[];
  } catch {
    return null;
  }
}

const priceFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  minimumFractionDigits: 0,
});

export default async function Home() {
  const products = await loadProducts();

  return (
    <main>
      <nav className="site-nav" aria-label="主导航">
        <a className="wordmark" href="#top" aria-label="返回首页">
          <span className="wordmark-mark">牛</span>
          <span>牛逼商城</span>
        </a>
        <div className="nav-links">
          <a href="#products">本期好物</a>
          <a href="/chat">问问助手</a>
        </div>
      </nav>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">NIUB SELECT · ISSUE 01</p>
          <h1>
            给日常一点
            <br />
            <em>不着急</em>的好东西
          </h1>
          <p className="hero-description">
            从一杯茶到一件器物，我们挑选经得起反复使用、
            也会在时间里变得更顺眼的小物。
          </p>
          <div className="hero-actions">
            <a className="primary-button" href="#products">
              逛逛本期好物
            </a>
            <a className="text-link" href="/chat">
              让购物助手帮我选 <span aria-hidden="true">↘</span>
            </a>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="sun" />
          <div className="vase">
            <div className="branch branch-one" />
            <div className="branch branch-two" />
            <div className="leaf leaf-one" />
            <div className="leaf leaf-two" />
            <div className="leaf leaf-three" />
          </div>
          <p>good things take time</p>
        </div>
      </section>

      <section className="product-section" id="products">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CURATED FOR YOU</p>
            <h2>本期好物</h2>
          </div>
          <p>少而精的六件选择，适合自用，也适合认真送人。</p>
        </div>

        {products ? (
          <div className="product-grid">
            {products.map((product, index) => (
              <article
                className="product-card"
                key={product.id}
                style={
                  {
                    "--card-accent": product.accent,
                  } as CSSProperties
                }
              >
                <div className="product-visual">
                  <span className="product-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="product-category">{product.category}</span>
                  <span className="product-orbit" />
                </div>
                <div className="product-info">
                  <div className="product-title-row">
                    <h3>{product.name}</h3>
                    <span>{priceFormatter.format(product.price_cents / 100)}</span>
                  </div>
                  <p>{product.summary}</p>
                  <div className="product-meta">
                    <span>库存 {product.stock}</span>
                    {product.badge && <span className="badge">{product.badge}</span>}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="service-notice">
            <strong>商品暂时没有加载出来</strong>
            <p>请确认商城 HTTP 服务已在 3001 端口启动，然后刷新页面。</p>
          </div>
        )}
      </section>

      <section className="assistant-section" id="assistant">
        <div className="assistant-copy">
          <p className="eyebrow">A LITTLE HELP</p>
          <h2>不知道怎么选？</h2>
          <p>
            告诉购物助手你的预算、使用场景或想送的人。
            它会给出简单直接的挑选建议。
          </p>
          <ul>
            <li>适合办公室的轻量茶具</li>
            <li>三百元以内送朋友的礼物</li>
            <li>让房间安静下来的香氛</li>
          </ul>
        </div>
        <AgentChat />
      </section>

      <footer>
        <span>牛逼商城 · 慢慢挑，认真用</span>
        <span>Agent Service / Mall / Next.js</span>
      </footer>
    </main>
  );
}
