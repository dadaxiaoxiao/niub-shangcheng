from mall.models import Product


PRODUCTS = (
    Product(
        id="jasmine-tea",
        name="云岫茉莉",
        summary="清甜花香，适合工作间隙的一杯热茶。",
        description="精选春季绿茶与茉莉窨制，香气轻盈，回甘干净。每罐 80 克。",
        price_cents=8800,
        category="茶饮",
        stock=36,
        badge="本周精选",
        accent="#b6c89f",
    ),
    Product(
        id="ceramic-cup",
        name="手作月白杯",
        summary="温润釉色与恰到好处的握持感。",
        description="手工拉坯陶瓷杯，容量 260 毫升。釉面存在自然细微差异，每一只都独一无二。",
        price_cents=12900,
        category="器物",
        stock=18,
        accent="#c9c5b6",
    ),
    Product(
        id="linen-tote",
        name="日常亚麻袋",
        summary="轻便耐用，通勤与周末都合适。",
        description="高密度亚麻帆布托特包，内置小口袋，可容纳 14 英寸笔记本电脑。",
        price_cents=15900,
        category="日常",
        stock=22,
        badge="补货到店",
        accent="#d6b99a",
    ),
    Product(
        id="forest-candle",
        name="雨后森林香氛",
        summary="雪松、苔藓与一点点湿木气息。",
        description="大豆蜡香氛蜡烛，净含量 180 克，建议单次燃烧 1 至 2 小时。",
        price_cents=16900,
        category="香氛",
        stock=9,
        accent="#9dae94",
    ),
    Product(
        id="bamboo-tray",
        name="竹影茶盘",
        summary="简洁的日常茶席，也可以作为首饰托盘。",
        description="整竹切削与手工打磨，表面使用植物木蜡油处理。尺寸 32 × 20 厘米。",
        price_cents=23900,
        category="器物",
        stock=12,
        accent="#b99e75",
    ),
    Product(
        id="weekend-gift",
        name="周末慢享礼盒",
        summary="把茶、香气和片刻安静打包送人。",
        description="包含茉莉茶一罐、手作杯一只与香氛蜡烛一份，附可重复使用包装盒。",
        price_cents=39900,
        category="礼盒",
        stock=6,
        badge="限量",
        accent="#c88f7a",
    ),
)


class Catalog:
    def list_products(self) -> list[Product]:
        return list(PRODUCTS)

    def get_product(self, product_id: str) -> Product | None:
        return next(
            (product for product in PRODUCTS if product.id == product_id),
            None,
        )


catalog = Catalog()

