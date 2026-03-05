from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_get_decisions_with_pagination(client, seed_dashboard_data):
    response = await client.get("/api/decisions", params={"page": 1, "page_size": 10})

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "pagination" in payload
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 10
    assert payload["pagination"]["total_items"] >= 25
    assert len(payload["items"]) == 10


@pytest.mark.asyncio
async def test_decision_filter_combinations(client, seed_dashboard_data):
    now = datetime.now(UTC)
    date_from = (now - timedelta(hours=3)).isoformat()
    date_to = now.isoformat()

    response = await client.get(
        "/api/decisions",
        params={
            "decision_type": "PRICE_DROP",
            "product_id": 1,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    for item in payload["items"]:
        assert item["decision_type"] == "PRICE_DROP"
        assert item["product_id"] == 1
