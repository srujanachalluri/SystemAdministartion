#!/usr/bin/env bash
# env.sh - all the settings in one place, so no script has a path buried inside it.
# Run this first, every time you open a new terminal:
#
#     source code/env.sh
#
# Nothing secret is in here. MinIO and Postgres both run on localhost inside this
# Codespace with throwaway passwords, so anyone grading this can rebuild the whole
# drill from scratch with no cloud account and no bill.

# ---- where the live AI estate lives (this is "production") -------------------
# Kept OUTSIDE the git repo on purpose. The fake weights file is 25 MB and has no
# business being in version control.
export GF_ESTATE="${GF_ESTATE:-$HOME/gf-ai}"

# ---- copy 2: the local archive ----------------------------------------------
export GF_LOCAL_BACKUP="${GF_LOCAL_BACKUP:-$HOME/gf-backup-local}"

# ---- copy 3: offsite object storage (MinIO standing in for S3) --------------
export GF_BIN="${GF_BIN:-$HOME/gf-bin}"
export MC="${MC:-$GF_BIN/mc}"
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://127.0.0.1:9000}"
export MINIO_ROOT_USER="${MINIO_ROOT_USER:-gfadmin}"
export MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-gfadmin12345}"
export MC_ALIAS="${MC_ALIAS:-gf}"

# Two buckets, because the two tiers of assets need two different lock modes.
# COMPLIANCE = nobody can delete a version before it expires. Not even us.
# GOVERNANCE = a privileged user CAN delete it, on purpose, and it gets logged.
export GF_BUCKET_WORM="${GF_BUCKET_WORM:-gf-ai-worm}"   # COMPLIANCE tier
export GF_BUCKET_GOV="${GF_BUCKET_GOV:-gf-ai-gov}"      # GOVERNANCE tier
export GF_RETENTION_DAYS="${GF_RETENTION_DAYS:-30}"

# ---- Postgres + pgvector (the RAG vector store) -----------------------------
export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"
export PGPASSWORD="${PGPASSWORD:-gfpass}"
export GF_DB="${GF_DB:-gf_ragdb}"
export GF_SCRATCH_DB="${GF_SCRATCH_DB:-dr_scratch}"
export GF_VECTOR_DIM="${GF_VECTOR_DIM:-384}"
export GF_DOC_ROWS="${GF_DOC_ROWS:-512}"

# ---- container names --------------------------------------------------------
export GF_PG_CONTAINER="${GF_PG_CONTAINER:-gf-pg}"
export GF_MINIO_CONTAINER="${GF_MINIO_CONTAINER:-gf-minio}"

# ---- where the evidence I commit to git goes --------------------------------
export GF_PROJECT="${GF_PROJECT:-$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )}"
export GF_OUTPUT="$GF_PROJECT/output"
mkdir -p "$GF_OUTPUT"

echo "Settings loaded:"
echo "  live estate    : $GF_ESTATE"
echo "  copy 2 (local) : $GF_LOCAL_BACKUP"
echo "  copy 3 (S3)    : $AWS_ENDPOINT_URL"
echo "                   $GF_BUCKET_WORM  (COMPLIANCE lock)"
echo "                   $GF_BUCKET_GOV   (GOVERNANCE lock)"
echo "  database       : $GF_DB on $PGHOST:$PGPORT"
echo "  evidence goes  : $GF_OUTPUT"
