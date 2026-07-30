#!/usr/bin/env bash
# restore_test.sh - the part that turns a backup into a backup.
#
# This restores the offsite, object-locked copy into a SCRATCH target, checks that
# what came back is what went in, MEASURES how long the index rebuild takes, and
# then throws the scratch target away.
#
# Production is never touched. Every write goes either into a temporary directory
# from mktemp, or into a throwaway database called dr_scratch. The cleanup runs from
# a trap, so it happens even if a check fails partway through.
#
# WHAT I CHANGED FROM THE CHAPTER'S REFERENCE SCRIPT, AND WHY:
#   * It pulls from MinIO with mc instead of "aws s3". Same S3 API, no cloud bill.
#   * It restores the dump with --section=pre-data --section=data, so the HNSW index
#     is NOT restored, and then rebuilds it separately and times it. If you let
#     pg_restore rebuild the index for you, the rebuild time is hidden inside the
#     restore time and you cannot report it. Splitting them is the whole point.
#   * It also verifies the weights manifest and test-clones the prompt bundle.
#     "The archive exists" and "the archive is usable" are two different claims.
#
# Run:  source code/env.sh && ./code/restore_test.sh "$(cat output/LATEST_STAMP)"
set -euo pipefail
cd "$(dirname "$0")/.."
source code/env.sh >/dev/null

STAMP="${1:?usage: ./code/restore_test.sh <STAMP>    (try: ./code/restore_test.sh \"\$(cat output/LATEST_STAMP)\")}"
SCRATCH="$(mktemp -d)"
FAILURES=0

cleanup() {
  rm -rf "$SCRATCH"
  psql -q -d postgres -c "DROP DATABASE IF EXISTS $GF_SCRATCH_DB;" >/dev/null 2>&1 || true
}
trap cleanup EXIT

line() { printf -- '----------------------------------------------------------------\n'; }
ok()   { printf 'PASS  %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; FAILURES=$((FAILURES+1)); }

echo "================================================================"
echo " RESTORE TEST - Grace Fellowship AI estate"
echo "================================================================"
echo " backup stamp   : $STAMP"
echo " started (UTC)  : $(date -u +%FT%TZ)"
echo " scratch folder : $SCRATCH"
echo " scratch db     : $GF_SCRATCH_DB   (the live db $GF_DB is never written to)"
echo " restoring from : $AWS_ENDPOINT_URL, the object-locked buckets"

# --------------------------------------------------------------------------
line; echo "STEP 1 - eval datasets: restore from the COMPLIANCE bucket, verify checksums"
"$MC" cp -q -r "$MC_ALIAS/$GF_BUCKET_WORM/datasets/" "$SCRATCH/datasets/" >/dev/null
rm -rf "$SCRATCH/datasets/manifests"
"$MC" cp -q "$MC_ALIAS/$GF_BUCKET_WORM/datasets/manifests/datasets-${STAMP}.sha256" \
            "$SCRATCH/datasets/expected.sha256" >/dev/null
echo "the manifest that was captured at backup time:"
sed 's/^/    /' "$SCRATCH/datasets/expected.sha256"
echo "verifying the restored files against it:"
if ( cd "$SCRATCH/datasets" && sha256sum -c expected.sha256 ); then
  ok "datasets: checksums match the manifest captured at backup time"
else
  bad "datasets: CHECKSUM MISMATCH - the archive is corrupt or incomplete"
fi

# --------------------------------------------------------------------------
line; echo "STEP 2 - fine-tuned weights: restore from the COMPLIANCE bucket, verify checksums"
"$MC" cp -q -r "$MC_ALIAS/$GF_BUCKET_WORM/models/finetuned/" "$SCRATCH/finetuned/" >/dev/null
"$MC" cp -q "$MC_ALIAS/$GF_BUCKET_WORM/models/manifests/weights-${STAMP}.sha256" \
            "$SCRATCH/finetuned/expected.sha256" >/dev/null
if ( cd "$SCRATCH/finetuned" && sha256sum -c expected.sha256 ); then
  ok "weights: bit-for-bit identical to what was archived"
else
  bad "weights: CHECKSUM MISMATCH"
fi
echo "restored weights file size: $(du -h "$SCRATCH/finetuned/gf-rag-v3.safetensors" | cut -f1)"

# --------------------------------------------------------------------------
line; echo "STEP 3 - prompt library: does the git bundle actually clone?"
"$MC" cp -q "$MC_ALIAS/$GF_BUCKET_GOV/prompts/prompts-${STAMP}.bundle" "$SCRATCH/prompts.bundle" >/dev/null
if git clone -q "$SCRATCH/prompts.bundle" "$SCRATCH/prompts-restored" 2>/dev/null; then
  ok "prompt library: cloned, $(git -C "$SCRATCH/prompts-restored" rev-list --count HEAD) commit(s), files: $(ls "$SCRATCH/prompts-restored" | tr '\n' ' ')"
else
  bad "prompt library: the bundle would not clone"
fi

# --------------------------------------------------------------------------
line; echo "STEP 4 - vector store: restore the SOURCE into a throwaway database"
"$MC" cp -q "$MC_ALIAS/$GF_BUCKET_GOV/vectors/vectors-${STAMP}.dump" "$SCRATCH/vectors.dump" >/dev/null
psql -q -d postgres -c "DROP DATABASE IF EXISTS $GF_SCRATCH_DB;"
psql -q -d postgres -c "CREATE DATABASE $GF_SCRATCH_DB;"
psql -q -d "$GF_SCRATCH_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# pre-data gives us the table, data gives us the rows, and neither gives us the
# HNSW index. That is on purpose - see the header comment.
pg_restore --no-owner --dbname="$GF_SCRATCH_DB" \
           --section=pre-data --section=data "$SCRATCH/vectors.dump" 2>&1 \
  | grep -v "already exists" || true

ROWS=$(psql -tA -d "$GF_SCRATCH_DB" -c "SELECT count(*) FROM documents;" | tr -d ' ')
LIVE_ROWS=$(psql -tA -d "$GF_DB" -c "SELECT count(*) FROM documents;" | tr -d ' ')
echo "rows recovered into $GF_SCRATCH_DB : $ROWS"
echo "rows in the live database          : $LIVE_ROWS"
if [ "$ROWS" = "$LIVE_ROWS" ] && [ "$ROWS" -gt 0 ]; then
  ok "vector source: recovered row count matches the live database ($ROWS rows)"
else
  bad "vector source: row count mismatch (recovered $ROWS, live has $LIVE_ROWS)"
fi

# A row count alone would not prove the vectors survived, only that rows exist.
DIM=$(psql -tA -d "$GF_SCRATCH_DB" -c "SELECT vector_dims(embedding) FROM documents LIMIT 1;" | tr -d ' ')
DISTINCT=$(psql -tA -d "$GF_SCRATCH_DB" -c "SELECT count(DISTINCT embedding) FROM documents;" | tr -d ' ')
echo "embedding dimensions intact        : $DIM"
echo "distinct embeddings recovered      : $DISTINCT  (should equal the row count)"

echo "confirming the derived index did NOT come back from the archive:"
IDX=$(psql -tA -d "$GF_SCRATCH_DB" -c "SELECT count(*) FROM pg_indexes WHERE indexname='documents_embedding_hnsw';" | tr -d ' ')
if [ "$IDX" = "0" ]; then
  ok "0 HNSW indexes restored - we never paid to store derived state"
else
  bad "the HNSW index came back from the archive, so we did pay to store it"
fi

# --------------------------------------------------------------------------
line; echo "STEP 5 - MEASURED index rebuild. This measured time IS the RTO for the derived tier."
echo "rebuilding: CREATE INDEX documents_embedding_hnsw USING hnsw (m=16, ef_construction=64)"
{ /usr/bin/time -p psql -q -d "$GF_SCRATCH_DB" -c \
    "CREATE INDEX documents_embedding_hnsw ON documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);" \
  ; } 2> "$SCRATCH/idx.time"
sed 's/^/    /' "$SCRATCH/idx.time" | grep -E 'real|user|sys'
REAL=$(awk '/^real/ {print $2}' "$SCRATCH/idx.time")
IDX_SIZE=$(psql -tA -d "$GF_SCRATCH_DB" -c "SELECT pg_size_pretty(pg_relation_size('documents_embedding_hnsw'));" | tr -d ' ')
echo
echo "  MEASURED INDEX REBUILD TIME : ${REAL} seconds"
echo "  rebuilt index size          : $IDX_SIZE   (bytes we kept out of the backup)"
echo "  >> Put this number in DR-PLAN.txt section 5 and in dr-asset-register.yaml"
echo "     under vector-db-hnsw-index."

# --------------------------------------------------------------------------
line; echo "STEP 6 - does the restored store actually answer a similarity query?"
HITS=$(psql -tA -d "$GF_SCRATCH_DB" -c \
  "SELECT count(*) FROM (SELECT id FROM documents ORDER BY embedding <=> (SELECT embedding FROM documents WHERE id = 1) LIMIT 8) t;" | tr -d ' ')
if [ "$HITS" = "8" ]; then
  ok "similarity search on the restored and rebuilt index returned 8 neighbours"
else
  bad "similarity search returned $HITS neighbours, expected 8"
fi

# --------------------------------------------------------------------------
line; echo "STEP 7 - base model: reproducible, so we check the PIN and not the bytes"
echo "recovery path: ollama pull llama3.1:8b-instruct-q4_K_M   (pinned by digest, never :latest)"
echo "Not restored here, by design. It is 4.7 GB of re-pullable bytes. How long that"
echo "re-pull takes is a bandwidth measurement, not a backup measurement - but it is"
echo "still real downtime, and it is the weakest link. See DR-PLAN.txt section 5."

# --------------------------------------------------------------------------
line
echo "finished (UTC): $(date -u +%FT%TZ)"
echo "the scratch database and scratch folder are being deleted now by the cleanup trap."
echo
if [ "$FAILURES" -eq 0 ]; then
  echo "RESULT: RESTORE TEST PASSED. 0 checks failed."
  echo "        Recovery is proven, not assumed."
else
  echo "RESULT: RESTORE TEST FAILED. $FAILURES check(s) failed."
  echo "        Fix the cause, write down what the fix was, and run it again."
  exit 1
fi
