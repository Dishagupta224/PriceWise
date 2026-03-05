from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_products_returns_paginated_results(client, seed_dashboard_data):
    response = await client.get("/api/products")

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "pagination" in payload
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 20
    assert payload["pagination"]["total_items"] == 25
    assert len(payload["items"]) == 20


@pytest.mark.asyncio
async def test_product_filters_work_correctly(client, seed_dashboard_data):
    category_response = await client.get("/api/products", params={"category": "Electronics"})
    assert category_response.status_code == 200
    category_payload = category_response.json()
    assert category_payload["items"]
    assert all(item["category"] == "Electronics" for item in category_payload["items"])

    low_stock_response = await client.get("/api/products", params={"stock_status": "low"})
    assert low_stock_response.status_code == 200
    low_stock_payload = low_stock_response.json()
    assert low_stock_payload["items"]
    assert all(0 < int(item["stock_quantity"]) <= 15 for item in low_stock_payload["items"])


@pytest.mark.asyncio
async def test_get_product_by_id_valid_and_invalid(client, seed_dashboard_data):
    valid = await client.get("/api/products/1")
    assert valid.status_code == 200
    valid_payload = valid.json()
    assert valid_payload["id"] == 1
    assert valid_payload["name"] == "Product 1"

    invalid = await client.get("/api/products/999999")
    assert invalid.status_code == 404
    assert invalid.json()["detail"] == "Product not found."
