-- Read-only SQLite JSON1 examples. Replace :run_id with a bound run identifier.
-- SQLite stores decimal amounts as JSON strings. Engine aggregates use Decimal;
-- SQL casts below are exploratory reporting, not authoritative penny reconciliation.

-- Finding counts by segment
SELECT json_extract(value, '$.segment') AS segment,
       json_extract(value, '$.status') AS finding,
       count(*) AS records
FROM runs, json_each(runs.payload, '$.results')
WHERE runs.id = :run_id
GROUP BY segment, finding;

-- Highest impact cases with saved operational status
SELECT json_extract(j.value, '$.policy_id') AS policy_id,
       json_extract(j.value, '$.difference') AS difference_aud,
       coalesce(c.status, 'Open') AS case_status,
       c.owner, c.notes
FROM runs r, json_each(r.payload, '$.results') j
LEFT JOIN cases c ON c.run_id = r.id
 AND c.source_row = json_extract(j.value, '$.source_row')
WHERE r.id = :run_id AND json_extract(j.value, '$.status') = 'discrepancy'
ORDER BY abs(CAST(json_extract(j.value, '$.difference') AS REAL)) DESC;

-- Audit trail
SELECT created, source_row, action, payload FROM audit
WHERE run_id = :run_id ORDER BY id;
