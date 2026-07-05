-- pgvector_setup.sql — a minimal, real RAG vector store on Postgres.
-- Tested in spirit against pgvector 0.8.x (Postgres 16/17), as of 2026.
-- pgvector is the right first choice up to roughly 5-10M vectors; past that,
-- HNSW build time and memory push teams to Qdrant/Milvus (chapter 4.6).

CREATE EXTENSION IF NOT EXISTS vector;

-- One chunk of a document plus its embedding.
-- 1536-dim is the OpenAI text-embedding-3-small / -large default.
-- Use `halfvec` (2 bytes/component) to halve storage at ~no recall cost.
CREATE TABLE doc_chunks (
    id          bigserial PRIMARY KEY,
    doc_id      text        NOT NULL,
    chunk_text  text        NOT NULL,
    sensitivity text        NOT NULL DEFAULT 'internal',  -- governance tag (4.7)
    embedding   halfvec(1536) NOT NULL
);

-- HNSW index: the near-universal ANN graph index.
-- m         = graph connectivity (16-64; recall plateaus past ~32-64)
-- ef_construction = build-time effort (higher = better recall, slower build)
CREATE INDEX ON doc_chunks
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 32, ef_construction = 128);

-- Query-time recall/latency knob (per session).
SET hnsw.ef_search = 100;

-- The "overfiltering" fix: when a WHERE clause prunes most rows, a plain
-- HNSW scan can return too few results. Iterative scan walks the graph
-- until it has enough. Real pgvector 0.8 feature.
SET hnsw.iterative_scan = 'relaxed_order';

-- Top-5 nearest neighbors to a query embedding, governance-filtered.
-- :q is the bind parameter for the query vector.
SELECT id, doc_id, sensitivity, embedding <=> :q AS cosine_distance
FROM   doc_chunks
WHERE  sensitivity <> 'restricted'
ORDER  BY embedding <=> :q
LIMIT  5;

-- Storage check: see what the vectors actually cost on disk.
SELECT pg_size_pretty(pg_total_relation_size('doc_chunks')) AS total_size;
