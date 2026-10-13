-- FixMate SQLite query reference.
-- Run with: sqlite3 fixmate.db ".read DBMS_QUERIES.sql"
-- Foreign-key enforcement is per connection; this enables it for this session.
PRAGMA foreign_keys = ON;

-- 1. Inspect tables and table/index definitions.
SELECT name, type, sql
FROM sqlite_master
WHERE type IN ('table', 'index')
  AND name NOT LIKE 'sqlite_%'
ORDER BY type, name;

-- 2. Inspect the declared columns, keys, and constraints for each table.
PRAGMA table_info('users');
PRAGMA table_info('provider_profiles');
PRAGMA table_info('provider_services');
PRAGMA table_info('service_requests');
PRAGMA table_info('bookings');
PRAGMA table_info('reviews');
PRAGMA foreign_key_list('provider_profiles');
PRAGMA foreign_key_list('provider_services');
PRAGMA foreign_key_list('service_requests');
PRAGMA foreign_key_list('bookings');
PRAGMA foreign_key_list('reviews');
PRAGMA index_list('bookings');
PRAGMA index_list('reviews');

-- 3. Verify one booking per repair request and one review per booking.
SELECT request_id, COUNT(*) AS booking_count, GROUP_CONCAT(id) AS booking_ids
FROM bookings
GROUP BY request_id
HAVING COUNT(*) > 1;

SELECT booking_id, COUNT(*) AS review_count, GROUP_CONCAT(id) AS review_ids
FROM reviews
GROUP BY booking_id
HAVING COUNT(*) > 1;

-- 4. List bookings with the matching consumer, provider, and repair request.
SELECT b.id AS booking_id,
       b.status AS booking_status,
       b.amount,
       b.created_at,
       consumer.name AS consumer_name,
       provider_user.name AS provider_name,
       sr.id AS request_id,
       sr.category,
       sr.description,
       sr.service_area,
       sr.preferred_date,
       sr.status AS request_status
FROM bookings AS b
JOIN users AS consumer ON consumer.id = b.consumer_id
JOIN provider_profiles AS pp ON pp.id = b.provider_id
JOIN users AS provider_user ON provider_user.id = pp.user_id
JOIN service_requests AS sr ON sr.id = b.request_id
ORDER BY b.created_at DESC, b.id DESC;

-- 5. Show booking totals and average booking amount by provider.
SELECT pp.id AS provider_id,
       u.name AS provider_name,
       COUNT(b.id) AS booking_count,
       AVG(b.amount) AS average_booking_amount
FROM provider_profiles AS pp
JOIN users AS u ON u.id = pp.user_id
LEFT JOIN bookings AS b ON b.provider_id = pp.id
GROUP BY pp.id, u.name
ORDER BY booking_count DESC, provider_name;

-- 6. Calculate provider ratings from reviews; no average is stored.
SELECT pp.id AS provider_id,
       u.name AS provider_name,
       AVG(r.rating) AS average_rating,
       COUNT(r.id) AS review_count
FROM provider_profiles AS pp
JOIN users AS u ON u.id = pp.user_id
LEFT JOIN reviews AS r ON r.provider_id = pp.id
GROUP BY pp.id, u.name
ORDER BY average_rating DESC, review_count DESC, provider_name;

-- 7. Providers with at least two reviews and an average rating of 4 or more.
SELECT pp.id AS provider_id,
       u.name AS provider_name,
       AVG(r.rating) AS average_rating,
       COUNT(r.id) AS review_count
FROM provider_profiles AS pp
JOIN users AS u ON u.id = pp.user_id
JOIN reviews AS r ON r.provider_id = pp.id
GROUP BY pp.id, u.name
HAVING COUNT(r.id) >= 2
   AND AVG(r.rating) >= 4
ORDER BY average_rating DESC;

-- 8. Repair requests without a booking (subquery).
SELECT sr.id, sr.consumer_id, sr.category, sr.description,
       sr.service_area, sr.preferred_date, sr.status
FROM service_requests AS sr
WHERE NOT EXISTS (
    SELECT 1
    FROM bookings AS b
    WHERE b.request_id = sr.id
)
ORDER BY sr.created_at DESC, sr.id DESC;

-- 9. Completed bookings that are eligible for a consumer review.
SELECT b.id AS booking_id,
       b.consumer_id,
       b.provider_id,
       sr.category,
       sr.description,
       b.status
FROM bookings AS b
JOIN service_requests AS sr ON sr.id = b.request_id
WHERE b.status = 'COMPLETED'
  AND NOT EXISTS (
      SELECT 1
      FROM reviews AS r
      WHERE r.booking_id = b.id
  )
ORDER BY b.id;

-- 10. Check for cross-table owner/provider mismatches and broken references.
SELECT b.id AS booking_id
FROM bookings AS b
JOIN service_requests AS sr ON sr.id = b.request_id
WHERE b.consumer_id <> sr.consumer_id;

SELECT r.id AS review_id
FROM reviews AS r
JOIN bookings AS b ON b.id = r.booking_id
WHERE r.consumer_id <> b.consumer_id
   OR r.provider_id <> b.provider_id
   OR b.status <> 'COMPLETED';

PRAGMA foreign_key_check;

-- 11. Example parameterized, transaction-safe repair-status synchronization.
-- Bind :request_id and :consumer_id. The update only marks an OPEN request
-- booked when a matching booking exists; inspect changes() before continuing.
BEGIN IMMEDIATE;
UPDATE service_requests
SET status = 'BOOKED'
WHERE id = :request_id
  AND consumer_id = :consumer_id
  AND status = 'OPEN'
  AND EXISTS (
      SELECT 1
      FROM bookings AS b
      WHERE b.request_id = service_requests.id
        AND b.consumer_id = service_requests.consumer_id
  );
SELECT changes() AS request_rows_marked_booked;
COMMIT;

-- Database constraints relied on by the application:
-- users.email is UNIQUE;
-- provider_profiles.user_id is UNIQUE;
-- provider_services(provider_id, category) is UNIQUE;
-- bookings.request_id has UNIQUE index idx_bookings_request_id_unique;
-- reviews.booking_id is UNIQUE;
-- reviews.rating has CHECK(rating BETWEEN 1 AND 5).
