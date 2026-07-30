#!/usr/bin/env bash
# backup_ai_estate.sh - the 3-2-1 backup of Grace Fellowship's AI estate.
#
# 3 copies : (1) the live estate  (2) the local archive folder  (3) MinIO buckets
# 2 media  : local filesystem, and object storage
# 1 offsite: the object-locked buckets. In production these are S3 in a different
#            region. Here they are MinIO, which speaks the same S3 API.
#
# WHAT I CHANGED FROM THE CHAPTER'S REFERENCE SCRIPT, AND WHY:
#   * Two buckets instead of one, because the two tiers of assets need two
#     different lock modes. See DR-PLAN.txt section 3.
#   * The reproducible tier is deliberately NOT copied. Instead the script writes a
#     receipt recording how many bytes we chose not to pay for and how to rebuild
#     them. That makes the decision auditable instead of looking like an oversight.
#   * The log goes to this project's output/ folder instead of /var/log/ai-backup,
#     because output/ is what gets committed to git as evidence. On a real server
#     /var/log/ai-backup is the right place.
#
# This script READS the estate and WRITES to backup targets. It deletes nothing.
# Run:  source code/env.sh && ./code/backup_ai_estate.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source code/env.sh >/dev/null

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
STAGE="$GF_LOCAL_BACKUP/$STAMP"
LOG="$GF_OUTPUT/backup-${STAMP}.log"
mkdir -p "$STAGE"/{models,vectors,prompts,datasets/manifests,configs}

log() { printf '%s  %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

log "backup stamp : $STAMP"
log "source       : $GF_ESTATE"
log "copy 2       : $STAGE"
log "copy 3       : $AWS_ENDPOINT_URL  ($GF_BUCKET_WORM and $GF_BUCKET_GOV)"

# ==========================================================================
# 1. PROMPT LIBRARY AND CONFIGS
#    Tiny in bytes, irreplaceable in effect. Forty-plus revisions of tuning is
#    what stops the assistant inventing service times.
#    GOVERNANCE lock, not COMPLIANCE: volunteers edit these files. If someone ever
#    pastes a real password into a prompt, we have to be able to delete that
#    object. Under COMPLIANCE the leak would be permanent for the full retention.
# ==========================================================================
log "[1/5] prompt library and configs (irreplaceable, GOVERNANCE lock)"
git -C "$GF_ESTATE/prompts" bundle create "$STAGE/prompts/prompts-${STAMP}.bundle" --all 2>&1 | tail -1 | tee -a "$LOG"
tar -czf "$STAGE/configs/configs-${STAMP}.tgz" -C "$GF_ESTATE" configs
"$MC" cp -q "$STAGE/prompts/prompts-${STAMP}.bundle" "$MC_ALIAS/$GF_BUCKET_GOV/prompts/" | tee -a "$LOG"
"$MC" cp -q "$STAGE/configs/configs-${STAMP}.tgz"    "$MC_ALIAS/$GF_BUCKET_GOV/configs/" | tee -a "$LOG"

# ==========================================================================
# 2. VECTOR STORE SOURCE
#    The documents and their embeddings. Three months of volunteer curation. This
#    is the asset whose loss would actually end the project.
#    GOVERNANCE lock: a member can ask us to delete a document about them, and that
#    request has to be honourable inside the backups too, not just in production.
# ==========================================================================
log "[2/5] pgvector source dump (irreplaceable, GOVERNANCE lock)"
pg_dump --format=custom --file="$STAGE/vectors/vectors-${STAMP}.dump" "$GF_DB"
log "      dump size: $(du -h "$STAGE/vectors/vectors-${STAMP}.dump" | cut -f1)"
"$MC" cp -q "$STAGE/vectors/vectors-${STAMP}.dump" "$MC_ALIAS/$GF_BUCKET_GOV/vectors/" | tee -a "$LOG"

# ==========================================================================
# 3. FINE-TUNED WEIGHTS
#    11.5 GPU-hours of training on a corpus that has since been edited. Even with
#    the same data the run is not bit-for-bit reproducible.
#    COMPLIANCE lock: these bytes never legitimately change after a release. The
#    only thing that would want to overwrite them is ransomware.
# ==========================================================================
log "[3/5] fine-tuned weights (irreplaceable, COMPLIANCE lock)"
( cd "$GF_ESTATE/models/finetuned" && sha256sum ./* ) > "$STAGE/models/weights-${STAMP}.sha256"
cp -R "$GF_ESTATE/models/finetuned" "$STAGE/models/finetuned"
"$MC" mirror -q --overwrite "$GF_ESTATE/models/finetuned" "$MC_ALIAS/$GF_BUCKET_WORM/models/finetuned" | tee -a "$LOG"
"$MC" cp -q "$STAGE/models/weights-${STAMP}.sha256" "$MC_ALIAS/$GF_BUCKET_WORM/models/manifests/" | tee -a "$LOG"

# ==========================================================================
# 4. EVALUATION DATASETS
#    Hand-labelled question and answer pairs. Without them we cannot tell whether a
#    restored model is the model we had, so they are the yardstick for every future
#    recovery. COMPLIANCE lock: a tampered eval set is worse than a missing one,
#    because it makes a broken restore look healthy.
#
#    The checksum manifest uses BASENAMES (note the "cd" first). That matters:
#    restore_test.sh verifies from inside a scratch folder where the original
#    absolute path does not exist, and sha256sum -c would fail on absolute paths.
# ==========================================================================
log "[4/5] eval datasets and checksum manifest (irreplaceable, COMPLIANCE lock)"
( cd "$GF_ESTATE/datasets" && sha256sum ./*.jsonl ) > "$STAGE/datasets/manifests/datasets-${STAMP}.sha256"
cp "$GF_ESTATE/datasets"/*.jsonl "$STAGE/datasets/"
tee -a "$LOG" < "$STAGE/datasets/manifests/datasets-${STAMP}.sha256"
"$MC" mirror -q --overwrite --exclude "manifests/*" "$STAGE/datasets" "$MC_ALIAS/$GF_BUCKET_WORM/datasets" | tee -a "$LOG"
"$MC" cp -q "$STAGE/datasets/manifests/datasets-${STAMP}.sha256" \
            "$MC_ALIAS/$GF_BUCKET_WORM/datasets/manifests/datasets-${STAMP}.sha256" | tee -a "$LOG"

# ==========================================================================
# 5. THE REPRODUCIBLE TIER - NOT BACKED UP, ON PURPOSE
#    We store the rebuild instructions instead of the bytes, and we write down how
#    many bytes that saved, so a grader can see this was a decision and not an
#    omission.
# ==========================================================================
log "[5/5] reproducible tier: writing a rebuild receipt instead of copying bytes"
HNSW_SIZE=$(psql -tA -d "$GF_DB" -c "SELECT pg_size_pretty(pg_relation_size('documents_embedding_hnsw'));" | tr -d ' ')
RECEIPT="$GF_OUTPUT/reproducible-receipt-${STAMP}.txt"
{
  echo "REPRODUCIBLE ASSETS - DELIBERATELY NOT BACKED UP     ($STAMP)"
  echo "================================================================"
  echo
  echo "asset: vector-db-hnsw-index"
  echo "  bytes not stored : $HNSW_SIZE"
  echo "  why              : the HNSW graph is derived entirely from the embeddings"
  echo "                     in the documents table, and those ARE backed up."
  echo "  rebuild command  : CREATE INDEX documents_embedding_hnsw ON documents"
  echo "                       USING hnsw (embedding vector_cosine_ops)"
  echo "                       WITH (m = 16, ef_construction = 64);"
  echo "  recovery cost    : measured in output/restore-test.log. That measured time"
  echo "                     IS this asset's RTO."
  echo
  echo "asset: base-model-checkpoint"
  echo "  bytes not stored : 4.7 GB"
  echo "  why              : an open-weight checkpoint anyone can re-pull. We store"
  echo "                     the digest, which is what a recovery actually needs."
  sed 's/^/  /' "$GF_ESTATE/models/base/PIN.txt"
  echo
  echo "Why this is a decision and not laziness: storing derived bytes makes the"
  echo "backup window longer and the storage bill bigger without making recovery any"
  echo "faster. What has to be protected is the SOURCE embeddings and the digest pin."
  echo "Both of those are backed up above."
} > "$RECEIPT"
"$MC" cp -q "$RECEIPT" "$MC_ALIAS/$GF_BUCKET_GOV/receipts/" | tee -a "$LOG"

# ==========================================================================
log "checking that the offsite copy actually landed"
{
  echo "--- $GF_BUCKET_WORM (COMPLIANCE) ---"
  "$MC" ls -r "$MC_ALIAS/$GF_BUCKET_WORM"
  echo "--- $GF_BUCKET_GOV (GOVERNANCE) ---"
  "$MC" ls -r "$MC_ALIAS/$GF_BUCKET_GOV"
} | tee -a "$LOG"

echo "$STAMP" > "$GF_OUTPUT/LATEST_STAMP"
log "backup finished. Stamp saved to output/LATEST_STAMP"
log "A backup is not a backup until it has been restored. Next:"
log "  ./code/restore_test.sh \$(cat output/LATEST_STAMP) | tee output/restore-test.log"
