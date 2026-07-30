#!/usr/bin/env bash
# setup_estate.sh - build the thing we are going to protect.
#
# Before you can practice disaster recovery you need something to lose. This script
# builds a small copy of Grace Fellowship's AI estate:
#
#   models/finetuned/   a stand-in fine-tuned model file (25 MB)
#   models/base/PIN.txt the digest of the open base model (we do NOT store its bytes)
#   prompts/            a real git repo holding the prompt library
#   datasets/           hand-labelled evaluation question/answer pairs
#   configs/            serving settings, and a .env TEMPLATE with no real secrets
#   Postgres            a documents table with 512 rows of embeddings + an HNSW index
#
# It also creates the two backup targets: a local archive folder, and two
# object-locked buckets in MinIO.
#
# This script only creates things. It never deletes anything outside $GF_ESTATE.
# Run:  source code/env.sh && ./code/setup_estate.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source code/env.sh >/dev/null

say() { printf '\n=== %s ===\n' "$*"; }

# ---------------------------------------------------------------------------
say "1/5  Files that make up the estate"
mkdir -p "$GF_ESTATE"/{models/finetuned,models/base,prompts,datasets,configs}

# The fine-tuned weights. 25 MB of stand-in bytes for what would really be a
# multi-gigabyte model file.
if [ ! -f "$GF_ESTATE/models/finetuned/gf-rag-v3.safetensors" ]; then
  dd if=/dev/urandom of="$GF_ESTATE/models/finetuned/gf-rag-v3.safetensors" \
     bs=1M count=25 status=none
fi

cat > "$GF_ESTATE/models/finetuned/adapter_config.json" <<'JSON'
{
  "base_model": "llama-3.1-8b-instruct",
  "base_model_digest": "sha256:9f2c7ab41d5e6b08c3f1aa77de204c9b6e5183ffb0aa4c2d3e9017bb5c6d8e41",
  "method": "qlora",
  "rank": 16,
  "trained_epochs": 3,
  "training_hours": 11.5,
  "trained_on": "gf-corpus-2026-05 (three months of volunteer curation)",
  "note": "Re-running this costs 11.5 GPU-hours AND the labelled corpus, which has since been edited. Not reproducible."
}
JSON

# The base model. We deliberately do NOT keep a copy of the 4.7 GB of weights.
# We keep the digest, because that is what a recovery actually needs.
cat > "$GF_ESTATE/models/base/PIN.txt" <<'TXT'
# base-model-checkpoint - REPRODUCIBLE. Do not back up the bytes.
# Recovery means re-pulling this exact digest. Never pull ":latest" - a tag that
# moves is not a recovery point.
source:  oci://registry.ollama.ai/library/llama3.1:8b-instruct-q4_K_M
digest:  sha256:9f2c7ab41d5e6b08c3f1aa77de204c9b6e5183ffb0aa4c2d3e9017bb5c6d8e41
size_gb: 4.7
recovery_command: ollama pull llama3.1:8b-instruct-q4_K_M
TXT

# ---------------------------------------------------------------------------
say "2/5  Prompt library (a real git repo, so we can bundle it offsite)"
if [ ! -d "$GF_ESTATE/prompts/.git" ]; then
  git -C "$GF_ESTATE/prompts" init -q -b main
  cat > "$GF_ESTATE/prompts/system.md" <<'MD'
You are the Grace Fellowship assistant. Answer only from the retrieved church
documents. If the documents do not answer the question, say so and point the person
to the church office. Never invent service times, staff names, or church positions.
MD
  cat > "$GF_ESTATE/prompts/retrieval.md" <<'MD'
Retrieve the top 8 chunks, rerank down to 4, and cite the document title in every
answer. Refuse doctrinal questions that are not covered by the positions corpus.
MD
  git -C "$GF_ESTATE/prompts" add -A
  git -C "$GF_ESTATE/prompts" \
      -c user.email=it@gracefellowship.example -c user.name="GF IT" \
      commit -qm "prompt library v1 (tuned over 40-plus revisions)"
fi
echo "commits in prompt library: $(git -C "$GF_ESTATE/prompts" rev-list --count HEAD)"

# ---------------------------------------------------------------------------
say "3/5  Evaluation datasets and configs"
cat > "$GF_ESTATE/datasets/eval_qa.jsonl" <<'JSONL'
{"q":"When is Sunday worship?","a":"9:00 AM and 11:00 AM.","label":"factual"}
{"q":"How do I sign up for the food pantry?","a":"Contact the church office; forms are at the welcome desk.","label":"process"}
{"q":"What is the church position on infant baptism?","a":"See the positions corpus, document POS-014.","label":"doctrinal"}
{"q":"Who leads youth ministry?","a":"Refer to the staff directory. Do not guess.","label":"refusal"}
JSONL
cat > "$GF_ESTATE/datasets/regression_qa.jsonl" <<'JSONL'
{"q":"Is there parking?","a":"Yes, the north lot and street parking.","label":"factual"}
{"q":"Can you give me a member's phone number?","a":"No. Privacy refusal.","label":"refusal"}
JSONL
cat > "$GF_ESTATE/configs/serving.yaml" <<'YAML'
model: gf-rag-v3
base_digest: sha256:9f2c7ab41d5e6b08c3f1aa77de204c9b6e5183ffb0aa4c2d3e9017bb5c6d8e41
retriever:
  top_k: 8
  rerank_to: 4
  min_score: 0.62
vector_store:
  dsn_env: GF_DSN
  table: documents
  index: documents_embedding_hnsw
YAML
# A TEMPLATE, not a secrets file. Real credentials never go into a backup archive.
cat > "$GF_ESTATE/configs/.env.template" <<'ENVT'
# Template only. The real values live in the password manager, never in a backup.
GF_DSN=postgresql://USER:PASSWORD@HOST:5432/gf_ragdb
ENVT
echo "datasets and configs written"

# ---------------------------------------------------------------------------
say "4/5  Vector store: Postgres + pgvector"
command -v psql >/dev/null || { echo "psql not found. See README.txt step 1."; exit 1; }
pg_isready -q || { echo "Postgres is not answering on $PGHOST:$PGPORT. Is the gf-pg container running?"; exit 1; }

psql -q -d "$GF_DB" -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS documents;
CREATE TABLE documents (
  id        serial PRIMARY KEY,
  title     text NOT NULL,
  chunk     text NOT NULL,
  embedding vector($GF_VECTOR_DIM) NOT NULL
);

-- Note on how this generates the vectors. The obvious way to write this is with a
-- nested subquery per row, but Postgres treats an uncorrelated subquery as a
-- one-time plan: it runs random() once and every row gets the IDENTICAL vector.
-- I hit exactly that and only noticed because the pg_dump came out at 19 KB
-- instead of 580 KB. Cross joining the two series and grouping forces random() to
-- run once per (row, dimension), which is what we want. The distinct-vector count
-- printed below is the check that it worked.
INSERT INTO documents (title, chunk, embedding)
SELECT
  'GF-DOC-' || lpad(i::text, 4, '0'),
  'Grace Fellowship curated chunk #' || i || ' - ministries, events, positions.',
  ('[' || string_agg(round(random()::numeric, 5)::text, ',' ORDER BY d) || ']')::vector
FROM generate_series(1, $GF_DOC_ROWS) AS i,
     generate_series(1, $GF_VECTOR_DIM) AS d
GROUP BY i;

-- The HNSW index. This is DERIVED data - it can be rebuilt from the embeddings
-- above, which is why the asset register marks it reproducible and why we do not
-- back it up. restore_test.sh rebuilds it and times the rebuild.
CREATE INDEX documents_embedding_hnsw ON documents
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
SQL

echo "rows in documents  : $(psql -tA -d "$GF_DB" -c 'SELECT count(*) FROM documents;')"
echo "distinct vectors   : $(psql -tA -d "$GF_DB" -c 'SELECT count(DISTINCT embedding) FROM documents;')  <- must match the row count"
echo "table size         : $(psql -tA -d "$GF_DB" -c "SELECT pg_size_pretty(pg_relation_size('documents'));")"
echo "hnsw index size    : $(psql -tA -d "$GF_DB" -c "SELECT pg_size_pretty(pg_relation_size('documents_embedding_hnsw'));")  <- bytes we will NOT back up"

# ---------------------------------------------------------------------------
say "5/5  Backup targets: local archive folder, and two object-locked buckets"
mkdir -p "$GF_LOCAL_BACKUP"
echo "local archive folder: $GF_LOCAL_BACKUP"

curl -sf "$AWS_ENDPOINT_URL/minio/health/live" >/dev/null || { echo "MinIO is not answering. Is the gf-minio container running?"; exit 1; }
"$MC" alias set "$MC_ALIAS" "$AWS_ENDPOINT_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null

# --with-lock turns on versioning AND S3 Object Lock at creation time. This is a
# one-way door: Object Lock cannot be added to a bucket afterwards. That is the
# decision point, and it is why there are two buckets instead of one.
"$MC" mb --with-lock "$MC_ALIAS/$GF_BUCKET_WORM" 2>/dev/null || echo "($GF_BUCKET_WORM already exists)"
"$MC" mb --with-lock "$MC_ALIAS/$GF_BUCKET_GOV"  2>/dev/null || echo "($GF_BUCKET_GOV already exists)"

# A DEFAULT retention on the bucket means every object uploaded into it inherits the
# lock automatically. Nobody has to remember to set it per file, which is the kind of
# step that gets forgotten at 2 a.m.
"$MC" retention set --default COMPLIANCE "${GF_RETENTION_DAYS}d" "$MC_ALIAS/$GF_BUCKET_WORM"
"$MC" retention set --default GOVERNANCE "${GF_RETENTION_DAYS}d" "$MC_ALIAS/$GF_BUCKET_GOV"

echo
echo "The estate is up. Next:  ./code/backup_ai_estate.sh"
