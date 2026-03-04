-- Deterministic pricing-agent test fixtures.
-- Product 9001 is tuned for a likely PRICE_DROP.
-- Product 9002 is tuned for a likely PRICE_INCREASE.

BEGIN;

DELETE FROM agent_decisions WHERE product_id IN (9001, 9002);
DELETE FROM price_history WHERE product_id IN (9001, 9002);
DELETE FROM competitor_prices WHERE product_id IN (9001, 9002);
DELETE FROM order_events WHERE product_id IN (9001, 9002);

INSERT INTO products (
    id,
    name,
    category,
    description,
    our_price,
    cost_price,
    stock_quantity,
    min_margin_percent,
    is_active
)
VALUES
    (
        9001,
        'Codex Test Drop Product',
        'Electronics',
        'Purpose-built fixture for testing a likely PRICE_DROP path.',
        1100.00,
        600.00,
        120,
        5.0,
        TRUE
    ),
    (
        9002,
        'Codex Test Increase Product',
        'Electronics',
        'Purpose-built fixture for testing a likely PRICE_INCREASE path.',
        1000.00,
        500.00,
        1,
        5.0,
        TRUE
    )
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    our_price = EXCLUDED.our_price,
    cost_price = EXCLUDED.cost_price,
    stock_quantity = EXCLUDED.stock_quantity,
    min_margin_percent = EXCLUDED.min_margin_percent,
    is_active = EXCLUDED.is_active;

INSERT INTO competitor_prices (product_id, competitor_name, price, captured_at)
VALUES
    (9001, 'FlipMart', 980.00, NOW() - INTERVAL '20 minutes'),
    (9001, 'FlipMart', 820.00, NOW() - INTERVAL '30 seconds'),
    (9001, 'QuickBazaar', 845.00, NOW() - INTERVAL '45 seconds'),
    (9001, 'DealDirect', 860.00, NOW() - INTERVAL '60 seconds'),
    (9002, 'FlipMart', 1080.00, NOW() - INTERVAL '20 minutes'),
    (9002, 'FlipMart', 1120.00, NOW() - INTERVAL '30 seconds'),
    (9002, 'QuickBazaar', 1135.00, NOW() - INTERVAL '45 seconds'),
    (9002, 'DealDirect', 1145.00, NOW() - INTERVAL '60 seconds');

INSERT INTO order_events (event_id, product_id, quantity, customer_region, created_at)
VALUES
    ('9002-prev-1', 9002, 1, 'Mumbai', NOW() - INTERVAL '10 days'),
    ('9002-cur-1', 9002, 3, 'Mumbai', NOW() - INTERVAL '6 days'),
    ('9002-cur-2', 9002, 3, 'Delhi', NOW() - INTERVAL '5 days'),
    ('9002-cur-3', 9002, 3, 'Bengaluru', NOW() - INTERVAL '4 days'),
    ('9002-cur-4', 9002, 3, 'Hyderabad', NOW() - INTERVAL '3 days'),
    ('9002-cur-5', 9002, 3, 'Pune', NOW() - INTERVAL '2 days'),
    ('9002-cur-6', 9002, 3, 'Chennai', NOW() - INTERVAL '1 day');

COMMIT;
