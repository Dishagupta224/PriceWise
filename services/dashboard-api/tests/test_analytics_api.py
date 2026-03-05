from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_summary_endpoint_returns_expected_structure(client, seed_dashboard_data):
    response = await client.get("/api/analytics/summary")

    assert response.status_code == 200
    payload = response.json()
    expected_fields = {
        "total_active_products",
        "total_decisions_today",
        "avg_margin_percent",
        "total_revenue_impact",
        "products_needing_attention",
        "low_stock_products",
        "overpriced_products",
    }
    assert expected_fields <= set(payload.keys())
    assert isinstance(payload["total_active_products"], int)
    assert isinstance(payload["total_decisions_today"], int)
