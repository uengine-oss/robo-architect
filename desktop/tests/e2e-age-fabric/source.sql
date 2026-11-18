-- A small source database for the age-fabric E2E: a shop with no declared foreign keys
-- (the relationships are what relinfer has to find), one view, and a read-only login.
-- orders.coupon_id is never filled: relinfer cannot measure it and leaves it for a reviewer.
CREATE SCHEMA shop;
CREATE TABLE shop.regions (code text PRIMARY KEY, name text NOT NULL);
CREATE TABLE shop.customers (id integer PRIMARY KEY, name text NOT NULL, region_code text, email text);
CREATE TABLE shop.products (id integer PRIMARY KEY, sku text NOT NULL UNIQUE, name text NOT NULL, price numeric(10,2));
CREATE TABLE shop.coupons (coupon_id integer PRIMARY KEY, label text NOT NULL);
CREATE TABLE shop.orders (id integer PRIMARY KEY, customer_id integer NOT NULL, ordered_at date NOT NULL, status text NOT NULL,
                          coupon_id integer);
CREATE TABLE shop.order_items (order_id integer NOT NULL, line_no integer NOT NULL, product_id integer NOT NULL,
                               qty integer NOT NULL, PRIMARY KEY (order_id, line_no));
INSERT INTO shop.regions VALUES ('KR-11','Seoul'),('KR-26','Busan'),('KR-27','Daegu'),('KR-28','Incheon'),('KR-29','Gwangju');
INSERT INTO shop.customers SELECT i, 'customer ' || i, (ARRAY['KR-11','KR-26','KR-27','KR-28','KR-29'])[1 + i % 5],
                                  'c' || i || '@example.test' FROM generate_series(1, 60) i;
INSERT INTO shop.coupons SELECT i, 'coupon ' || i FROM generate_series(1, 8) i;
INSERT INTO shop.products SELECT i, 'SKU-' || lpad(i::text, 4, '0'), 'product ' || i, (i * 7 % 90) + 9.5 FROM generate_series(1, 40) i;
INSERT INTO shop.orders SELECT i, 1 + (i * 13 % 60), date '2026-01-01' + (i % 300),
                               (ARRAY['new','paid','shipped','closed'])[1 + i % 4] FROM generate_series(1, 240) i;
INSERT INTO shop.order_items SELECT o, l, 1 + ((o * 7 + l * 11) % 40), 1 + (o + l) % 5
                               FROM generate_series(1, 240) o, generate_series(1, 3) l;
CREATE VIEW shop.big_orders AS
  SELECT o.id, o.customer_id, sum(i.qty) AS qty FROM shop.orders o JOIN shop.order_items i ON i.order_id = o.id
   GROUP BY o.id, o.customer_id HAVING sum(i.qty) > 8;
-- the fabric reads with a login that may only read
CREATE ROLE shop_ro LOGIN PASSWORD :'ro_password';
GRANT USAGE ON SCHEMA shop TO shop_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA shop TO shop_ro;
