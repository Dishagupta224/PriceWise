"""Database bootstrap and deterministic seed data."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, Base, engine
from app.models import CompetitorPrice, Product

COMPETITOR_NAME_SETS = [
    ("MarketSquare", "ValueKart", "UrbanCart"),
    ("QuickBasket", "PrimePick", "DealDock"),
    ("RetailHub", "SmartBuy", "MegaMart"),
    ("ShopOrbit", "PriceNest", "DailyCart"),
    ("TrendLane", "SaverStreet", "EasyBazaar"),
]

COMPETITOR_OFFSETS = [
    (Decimal("-0.11"), Decimal("-0.06"), Decimal("0.09")),
    (Decimal("-0.08"), Decimal("0.07"), Decimal("0.12")),
    (Decimal("-0.05"), Decimal("0.10"), Decimal("0.15")),
    (Decimal("-0.09"), Decimal("0.06"), Decimal("0.13")),
    (Decimal("-0.07"), Decimal("0.08"), Decimal("0.11")),
]

PRODUCT_CATALOG = [
    {
        "name": "Astra X5 5G Smartphone",
        "category": "Electronics",
        "description": "6.7-inch AMOLED smartphone with 120 Hz refresh rate, dual-SIM support, and a 64 MP camera.",
        "cost_price": 18200,
        "markup_percent": 31,
        "stock_quantity": 120,
        "min_margin_percent": 18,
    },
    {
        "name": "Vertex Note Pro Laptop",
        "category": "Electronics",
        "description": "14-inch productivity laptop with 16 GB RAM, fast SSD storage, and all-day battery life.",
        "cost_price": 41200,
        "markup_percent": 29,
        "stock_quantity": 44,
        "min_margin_percent": 20,
    },
    {
        "name": "PulseBeat ANC Headphones",
        "category": "Electronics",
        "description": "Wireless over-ear headphones with adaptive noise cancellation and 40-hour playback.",
        "cost_price": 4800,
        "markup_percent": 35,
        "stock_quantity": 210,
        "min_margin_percent": 22,
    },
    {
        "name": "StreamCam 4K Webcam",
        "category": "Electronics",
        "description": "Ultra HD webcam with dual microphones for streaming, meetings, and content creation.",
        "cost_price": 2600,
        "markup_percent": 33,
        "stock_quantity": 150,
        "min_margin_percent": 17,
    },
    {
        "name": 'EchoPod Mini Bluetooth Speaker',
        "category": "Electronics",
        "description": "Portable speaker with punchy bass, splash resistance, and 12-hour battery backup.",
        "cost_price": 1350,
        "markup_percent": 37,
        "stock_quantity": 280,
        "min_margin_percent": 19,
    },
    {
        "name": "Nimbus Air Tablet 11",
        "category": "Electronics",
        "description": "11-inch entertainment tablet with stereo speakers and stylus-ready display.",
        "cost_price": 14600,
        "markup_percent": 28,
        "stock_quantity": 68,
        "min_margin_percent": 21,
    },
    {
        "name": "VoltFit Smartwatch Gen 3",
        "category": "Electronics",
        "description": "Fitness-focused smartwatch with GPS, SpO2 monitoring, and quick-reply notifications.",
        "cost_price": 3100,
        "markup_percent": 34,
        "stock_quantity": 190,
        "min_margin_percent": 16,
    },
    {
        "name": "FrameView 27 Monitor",
        "category": "Electronics",
        "description": "27-inch QHD monitor with slim bezels, IPS panel, and ergonomic stand.",
        "cost_price": 11200,
        "markup_percent": 27,
        "stock_quantity": 72,
        "min_margin_percent": 18,
    },
    {
        "name": "HyperCharge 20000 Power Bank",
        "category": "Electronics",
        "description": "High-capacity power bank with 22.5 W fast charging and USB-C input/output.",
        "cost_price": 980,
        "markup_percent": 39,
        "stock_quantity": 330,
        "min_margin_percent": 15,
    },
    {
        "name": "SkyLink Wi-Fi 6 Router",
        "category": "Electronics",
        "description": "Dual-band Wi-Fi 6 router built for dense homes and stable video streaming.",
        "cost_price": 4200,
        "markup_percent": 32,
        "stock_quantity": 95,
        "min_margin_percent": 20,
    },
    {
        "name": "Harbor Cotton Oxford Shirt",
        "category": "Clothing",
        "description": "Breathable full-sleeve Oxford shirt tailored for office and weekend wear.",
        "cost_price": 620,
        "markup_percent": 36,
        "stock_quantity": 260,
        "min_margin_percent": 18,
    },
    {
        "name": "TerraFlex Running Shoes",
        "category": "Clothing",
        "description": "Cushioned training shoes with durable outsole and lightweight knit upper.",
        "cost_price": 2100,
        "markup_percent": 31,
        "stock_quantity": 185,
        "min_margin_percent": 20,
    },
    {
        "name": "Northline Quilted Jacket",
        "category": "Clothing",
        "description": "Mid-weight quilted jacket with zip pockets and water-resistant shell.",
        "cost_price": 2450,
        "markup_percent": 34,
        "stock_quantity": 90,
        "min_margin_percent": 22,
    },
    {
        "name": "UrbanEase Chino Trousers",
        "category": "Clothing",
        "description": "Stretch cotton chinos with tapered fit for everyday formal-casual styling.",
        "cost_price": 980,
        "markup_percent": 29,
        "stock_quantity": 220,
        "min_margin_percent": 17,
    },
    {
        "name": "CloudSoft Graphic Hoodie",
        "category": "Clothing",
        "description": "Fleece-lined hoodie with bold chest print and relaxed unisex fit.",
        "cost_price": 1250,
        "markup_percent": 38,
        "stock_quantity": 145,
        "min_margin_percent": 19,
    },
    {
        "name": "StrideLite Performance Socks Pack",
        "category": "Clothing",
        "description": "Pack of five cushioned sports socks with sweat-wicking weave.",
        "cost_price": 240,
        "markup_percent": 35,
        "stock_quantity": 410,
        "min_margin_percent": 15,
    },
    {
        "name": "Elara Linen Summer Dress",
        "category": "Clothing",
        "description": "Lightweight linen-blend dress with flattering waistline and airy silhouette.",
        "cost_price": 1450,
        "markup_percent": 30,
        "stock_quantity": 130,
        "min_margin_percent": 21,
    },
    {
        "name": "TrailMark Cargo Shorts",
        "category": "Clothing",
        "description": "Utility cargo shorts with secure side pockets and quick-dry fabric.",
        "cost_price": 760,
        "markup_percent": 33,
        "stock_quantity": 175,
        "min_margin_percent": 16,
    },
    {
        "name": "AuraFit Sports Bra",
        "category": "Clothing",
        "description": "Medium-impact sports bra with breathable mesh panels and removable cups.",
        "cost_price": 540,
        "markup_percent": 37,
        "stock_quantity": 205,
        "min_margin_percent": 18,
    },
    {
        "name": "ClassicWeave Silk Tie",
        "category": "Clothing",
        "description": "Pure silk tie with subtle texture for boardroom and wedding occasions.",
        "cost_price": 320,
        "markup_percent": 40,
        "stock_quantity": 310,
        "min_margin_percent": 15,
    },
    {
        "name": "ChefMate Mixer Grinder",
        "category": "Home & Kitchen",
        "description": "750 W mixer grinder with three stainless steel jars for everyday kitchen prep.",
        "cost_price": 2650,
        "markup_percent": 28,
        "stock_quantity": 105,
        "min_margin_percent": 18,
    },
    {
        "name": "BrewNest Electric Kettle",
        "category": "Home & Kitchen",
        "description": "1.8 litre electric kettle with auto shut-off and concealed heating element.",
        "cost_price": 890,
        "markup_percent": 34,
        "stock_quantity": 240,
        "min_margin_percent": 16,
    },
    {
        "name": "PureSteam Iron Pro",
        "category": "Home & Kitchen",
        "description": "Steam iron with ceramic soleplate and anti-drip control for crisp ironing.",
        "cost_price": 1350,
        "markup_percent": 31,
        "stock_quantity": 175,
        "min_margin_percent": 17,
    },
    {
        "name": "FreshBox Glass Storage Set",
        "category": "Home & Kitchen",
        "description": "Set of airtight borosilicate storage containers for fridge and microwave use.",
        "cost_price": 640,
        "markup_percent": 39,
        "stock_quantity": 290,
        "min_margin_percent": 19,
    },
    {
        "name": "OakRoot Cast Iron Skillet",
        "category": "Home & Kitchen",
        "description": "Pre-seasoned cast iron skillet for searing, roasting, and stovetop cooking.",
        "cost_price": 1120,
        "markup_percent": 35,
        "stock_quantity": 125,
        "min_margin_percent": 20,
    },
    {
        "name": "AquaFlow Shower Filter",
        "category": "Home & Kitchen",
        "description": "Multi-layer shower filter designed to reduce chlorine and improve water feel.",
        "cost_price": 520,
        "markup_percent": 32,
        "stock_quantity": 180,
        "min_margin_percent": 15,
    },
    {
        "name": "ThermaLock Stainless Flask",
        "category": "Home & Kitchen",
        "description": "Vacuum insulated 1 litre flask that keeps drinks hot or cold for hours.",
        "cost_price": 410,
        "markup_percent": 36,
        "stock_quantity": 260,
        "min_margin_percent": 18,
    },
    {
        "name": "CloudRest Memory Foam Pillow",
        "category": "Home & Kitchen",
        "description": "Contoured memory foam pillow with breathable bamboo-blend cover.",
        "cost_price": 980,
        "markup_percent": 30,
        "stock_quantity": 140,
        "min_margin_percent": 21,
    },
    {
        "name": "SweepSmart Robot Vacuum",
        "category": "Home & Kitchen",
        "description": "App-connected robot vacuum with scheduled cleaning and edge detection sensors.",
        "cost_price": 14800,
        "markup_percent": 27,
        "stock_quantity": 38,
        "min_margin_percent": 22,
    },
    {
        "name": "DinnerCraft 24-Piece Cutlery Set",
        "category": "Home & Kitchen",
        "description": "Mirror-finish stainless steel cutlery set built for daily family dining.",
        "cost_price": 780,
        "markup_percent": 33,
        "stock_quantity": 215,
        "min_margin_percent": 16,
    },
    {
        "name": "Atomic Habits",
        "category": "Books",
        "description": "A practical guide to building good habits, breaking bad ones, and improving systems.",
        "cost_price": 220,
        "markup_percent": 29,
        "stock_quantity": 310,
        "min_margin_percent": 15,
    },
    {
        "name": "Deep Work",
        "category": "Books",
        "description": "A productivity book focused on distraction-free concentration and meaningful output.",
        "cost_price": 240,
        "markup_percent": 31,
        "stock_quantity": 260,
        "min_margin_percent": 17,
    },
    {
        "name": "The Psychology of Money",
        "category": "Books",
        "description": "Personal finance lessons about behavior, decision-making, and long-term wealth.",
        "cost_price": 260,
        "markup_percent": 34,
        "stock_quantity": 285,
        "min_margin_percent": 18,
    },
    {
        "name": "The Pragmatic Programmer",
        "category": "Books",
        "description": "Classic software engineering guidance on craftsmanship, learning, and building resilient systems.",
        "cost_price": 540,
        "markup_percent": 27,
        "stock_quantity": 95,
        "min_margin_percent": 22,
    },
    {
        "name": "Sapiens",
        "category": "Books",
        "description": "A sweeping narrative of human history, culture, and societal development.",
        "cost_price": 320,
        "markup_percent": 30,
        "stock_quantity": 175,
        "min_margin_percent": 16,
    },
    {
        "name": "Ikigai",
        "category": "Books",
        "description": "A reflective read on purpose, longevity, and intentional living.",
        "cost_price": 210,
        "markup_percent": 36,
        "stock_quantity": 340,
        "min_margin_percent": 15,
    },
    {
        "name": "Educated",
        "category": "Books",
        "description": "Memoir about resilience, family, and the transformative impact of education.",
        "cost_price": 280,
        "markup_percent": 28,
        "stock_quantity": 160,
        "min_margin_percent": 19,
    },
    {
        "name": "The Silent Patient",
        "category": "Books",
        "description": "Psychological thriller centered on a shocking act of violence and hidden truths.",
        "cost_price": 230,
        "markup_percent": 35,
        "stock_quantity": 190,
        "min_margin_percent": 18,
    },
    {
        "name": "Can't Hurt Me",
        "category": "Books",
        "description": "Memoir and mindset book on discipline, accountability, and mental toughness.",
        "cost_price": 350,
        "markup_percent": 33,
        "stock_quantity": 145,
        "min_margin_percent": 20,
    },
    {
        "name": "Rich Dad Poor Dad",
        "category": "Books",
        "description": "A popular introduction to financial literacy and asset-focused thinking.",
        "cost_price": 200,
        "markup_percent": 40,
        "stock_quantity": 360,
        "min_margin_percent": 15,
    },
    {
        "name": "FlexCore Yoga Mat",
        "category": "Sports & Fitness",
        "description": "6 mm anti-slip yoga mat with alignment guides and easy-carry strap.",
        "cost_price": 520,
        "markup_percent": 35,
        "stock_quantity": 250,
        "min_margin_percent": 18,
    },
    {
        "name": "PowerPulse Adjustable Dumbbells",
        "category": "Sports & Fitness",
        "description": "Quick-lock adjustable dumbbells designed for compact home workouts.",
        "cost_price": 8800,
        "markup_percent": 28,
        "stock_quantity": 42,
        "min_margin_percent": 21,
    },
    {
        "name": "SprintX Cricket Bat",
        "category": "Sports & Fitness",
        "description": "English willow-style cricket bat balanced for club-level stroke play.",
        "cost_price": 2450,
        "markup_percent": 32,
        "stock_quantity": 88,
        "min_margin_percent": 17,
    },
    {
        "name": "TrailGo Hydration Backpack",
        "category": "Sports & Fitness",
        "description": "Light trekking hydration pack with multiple storage compartments and rain cover.",
        "cost_price": 1700,
        "markup_percent": 30,
        "stock_quantity": 76,
        "min_margin_percent": 20,
    },
    {
        "name": "AeroSpin Skipping Rope",
        "category": "Sports & Fitness",
        "description": "Speed rope with ball bearings and adjustable length for cardio sessions.",
        "cost_price": 260,
        "markup_percent": 38,
        "stock_quantity": 410,
        "min_margin_percent": 15,
    },
    {
        "name": "GlidePro Inline Skates",
        "category": "Sports & Fitness",
        "description": "Recreational inline skates with secure ankle support and smooth ABEC bearings.",
        "cost_price": 3200,
        "markup_percent": 29,
        "stock_quantity": 54,
        "min_margin_percent": 19,
    },
    {
        "name": "IronGrip Gym Gloves",
        "category": "Sports & Fitness",
        "description": "Half-finger training gloves with padded palm and wrist support.",
        "cost_price": 340,
        "markup_percent": 37,
        "stock_quantity": 300,
        "min_margin_percent": 16,
    },
    {
        "name": "EnduraFit Resistance Band Set",
        "category": "Sports & Fitness",
        "description": "Five-band resistance training kit with handles, anchors, and travel pouch.",
        "cost_price": 690,
        "markup_percent": 34,
        "stock_quantity": 165,
        "min_margin_percent": 18,
    },
    {
        "name": "StormGuard Cycling Helmet",
        "category": "Sports & Fitness",
        "description": "Ventilated cycling helmet with adjustable dial-fit system and removable visor.",
        "cost_price": 1180,
        "markup_percent": 31,
        "stock_quantity": 112,
        "min_margin_percent": 22,
    },
    {
        "name": "StrideTrack Fitness Tracker",
        "category": "Sports & Fitness",
        "description": "Slim activity tracker with sleep insights, step tracking, and heart-rate alerts.",
        "cost_price": 1450,
        "markup_percent": 27,
        "stock_quantity": 132,
        "min_margin_percent": 20,
    },
]


def to_money(value: Decimal | int | float) -> Decimal:
    """Normalize values to two-decimal currency format."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_product_payload(raw_product: dict[str, object]) -> dict[str, object]:
    """Convert catalog definitions into product rows."""
    cost_price = to_money(raw_product["cost_price"])
    markup_multiplier = Decimal("1") + (Decimal(str(raw_product["markup_percent"])) / Decimal("100"))
    return {
        "name": raw_product["name"],
        "category": raw_product["category"],
        "description": raw_product["description"],
        "cost_price": cost_price,
        "our_price": to_money(cost_price * markup_multiplier),
        "stock_quantity": raw_product["stock_quantity"],
        "min_margin_percent": float(raw_product["min_margin_percent"]),
        "is_active": True,
    }


def build_competitor_payloads(product: Product, product_index: int) -> list[dict[str, object]]:
    """Create deterministic competitor prices around our own price."""
    names = COMPETITOR_NAME_SETS[product_index % len(COMPETITOR_NAME_SETS)]
    offsets = COMPETITOR_OFFSETS[product_index % len(COMPETITOR_OFFSETS)]

    competitor_prices: list[dict[str, object]] = []
    for competitor_name, offset in zip(names, offsets, strict=True):
        competitor_prices.append(
            {
                "product_id": product.id,
                "competitor_name": competitor_name,
                "price": to_money(Decimal(product.our_price) * (Decimal("1") + offset)),
            }
        )
    return competitor_prices


async def init_db() -> None:
    """Create database tables."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def seed_products() -> None:
    """Insert products and competitor prices without duplicating existing rows."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Product).options(selectinload(Product.competitor_prices)).order_by(Product.id)
        )
        existing_products = {product.name: product for product in result.scalars().unique().all()}

        catalog_products = [build_product_payload(product) for product in PRODUCT_CATALOG]

        new_products = [
            Product(**product_payload)
            for product_payload in catalog_products
            if product_payload["name"] not in existing_products
        ]
        if new_products:
            session.add_all(new_products)
            await session.flush()

        refreshed_result = await session.execute(
            select(Product).options(selectinload(Product.competitor_prices)).order_by(Product.id)
        )
        products_by_name = {product.name: product for product in refreshed_result.scalars().unique().all()}

        competitor_rows: list[CompetitorPrice] = []
        for index, product_payload in enumerate(catalog_products):
            product = products_by_name[product_payload["name"]]
            existing_competitor_names = {price.competitor_name for price in product.competitor_prices}

            for competitor_payload in build_competitor_payloads(product, index):
                if competitor_payload["competitor_name"] in existing_competitor_names:
                    continue
                competitor_rows.append(CompetitorPrice(**competitor_payload))

        if competitor_rows:
            session.add_all(competitor_rows)

        await session.commit()


async def main() -> None:
    """Initialize schema and seed realistic product data."""
    await init_db()
    await seed_products()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
