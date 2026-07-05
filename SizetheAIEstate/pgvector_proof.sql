-- pgvector_proof.sql — predict-then-measure the on-disk cost of a vector store.
-- Loads 50,000 representative halfvec(1536) rows (1% of the planned 5,000,000)
-- and reports the REAL on-disk size to compare against the hand prediction.
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS doc_chunks;
CREATE TABLE doc_chunks (
    id          bigserial PRIMARY KEY,
    doc_id      text          NOT NULL,
    chunk_text  text          NOT NULL,
    sensitivity text          NOT NULL DEFAULT 'internal',
    embedding   halfvec(1536) NOT NULL
);

-- 50,000 rows, each a distinct random 1536-dim halfvec (correlated subquery
-- via "WHERE g IS NOT NULL" forces a fresh vector per row).
INSERT INTO doc_chunks (doc_id, chunk_text, embedding)
SELECT 'doc_'||g,
       'chunk '||g,
       (SELECT array_agg(random()::real)
          FROM generate_series(1,1536) i
         WHERE g IS NOT NULL)::vector::halfvec(1536)
FROM generate_series(1,50000) g;

SET maintenance_work_mem = '512MB';   -- let the HNSW graph build in RAM
CREATE INDEX ON doc_chunks USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 32, ef_construction = 128);

-- ---- MEASURE ----
SELECT count(*) AS rows_loaded FROM doc_chunks;
SELECT
  pg_size_pretty(pg_total_relation_size('doc_chunks')) AS total_size,
  pg_size_pretty(pg_relation_size('doc_chunks'))       AS heap_only,
  pg_size_pretty(pg_table_size('doc_chunks'))          AS heap_plus_toast,
  pg_size_pretty(pg_indexes_size('doc_chunks'))        AS all_indexes,
  pg_total_relation_size('doc_chunks')                 AS total_bytes;
