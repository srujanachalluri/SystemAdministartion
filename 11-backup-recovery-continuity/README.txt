================================================================
README.txt
Project 11 - DR for the AI Estate
Grace Fellowship RAG assistant
================================================================

This README is written so a grader can reproduce the restore test
from scratch. Every command below is meant to be copy-pasted into
a GitHub Codespace terminal, in order.

Nothing here needs an AWS account, a cloud bill, or anything
installed on a personal machine. Postgres and the S3-compatible
object storage both run as Docker containers inside the Codespace.


----------------------------------------------------------------
WHAT IS IN THIS FOLDER
----------------------------------------------------------------

  dr-asset-register.yaml   the asset register - every asset
                           classified, with the reasoning
  DR-PLAN.txt              the DR plan: classification, lock mode
                           choices, the runbook, the numbers, the
                           weakest link, and the known gaps
  agent-log.txt            required - what was delegated to an AI
                           assistant, and where it was wrong
  report.docx              step-by-step writeup with the commands
                           and the captured output

  code/env.sh              all settings in one place
  code/setup_estate.sh     builds the estate we are protecting
  code/backup_ai_estate.sh the 3-2-1 backup
  code/restore_test.sh     the measured restore test
  code/prove_immutability.sh  attacks our own backups on purpose
  code/rpo_rto.py          computes estate RPO and RTO

  output/                  the committed evidence:
    restore-test.log         the restore test transcript
    immutability-test.log    the object lock test transcript
    rpo-rto-output.txt       the computed RPO/RTO
    backup-<stamp>.log       what the backup run did
    reproducible-receipt-<stamp>.txt
                             proof we skipped the derived assets
                             on purpose, and how to rebuild them


----------------------------------------------------------------
STEP 0 - OPEN A CODESPACE
----------------------------------------------------------------

On the GitHub repo page: Code -> Codespaces -> Create codespace
on main. Wait for the terminal, then:

  cd 11-backup-recovery-continuity


----------------------------------------------------------------
STEP 1 - INSTALL THE PREREQUISITES  (about 3 minutes, once)
----------------------------------------------------------------

A Codespace already has git, python3, curl, tar, sha256sum and
Docker. Five things to add:

  # 1. Postgres command line tools: psql, pg_dump, pg_restore
  sudo apt-get update && sudo apt-get install -y postgresql-client

  # 2. PyYAML, so rpo_rto.py can read the asset register
  pip install pyyaml

  # 3. mc, the MinIO client. It speaks the S3 API.
  mkdir -p ~/gf-bin
  curl -sSL -o ~/gf-bin/mc \
    https://dl.min.io/client/mc/release/linux-amd64/mc
  chmod +x ~/gf-bin/mc

  # 4. Postgres with pgvector already built in
  docker run -d --name gf-pg \
    -e POSTGRES_PASSWORD=gfpass \
    -e POSTGRES_DB=gf_ragdb \
    -p 5432:5432 \
    pgvector/pgvector:pg16

  # 5. MinIO. This is what gives us REAL S3 Object Lock locally.
  docker run -d --name gf-minio \
    -e MINIO_ROOT_USER=gfadmin \
    -e MINIO_ROOT_PASSWORD=gfadmin12345 \
    -p 9000:9000 -p 9001:9001 \
    -v gf-minio-data:/data \
    minio/minio server /data --console-address ":9001"

Check both containers are up and healthy:

  docker ps
  pg_isready -h 127.0.0.1
  curl -s http://127.0.0.1:9000/minio/health/live && echo " minio ok"

If you close the terminal and come back later, the containers stop.
Start them again with:

  docker start gf-pg gf-minio


----------------------------------------------------------------
STEP 2 - LOAD THE SETTINGS
----------------------------------------------------------------

Do this once in every new terminal, before anything else:

  chmod +x code/*.sh
  source code/env.sh

It prints where everything lives so you can see the settings took.


----------------------------------------------------------------
STEP 3 - BUILD THE ESTATE WE ARE PROTECTING
----------------------------------------------------------------

  ./code/setup_estate.sh

This creates the fine-tuned weights file, the base model digest
pin, the git prompt library, the eval datasets, the configs, the
Postgres documents table with 512 embeddings and an HNSW index,
the local archive folder, and the two object-locked buckets.

Check the output for these three lines:

  rows in documents  : 512
  distinct vectors   : 512     <- these two MUST match
  hnsw index size    : ...     <- the bytes we will not back up

If distinct vectors does not equal 512, stop. It means every row
got the same vector and every later test is meaningless. That
exact bug happened while building this - see agent-log.txt 2.1.


----------------------------------------------------------------
STEP 4 - RUN THE BACKUP
----------------------------------------------------------------

  ./code/backup_ai_estate.sh 2>&1 | tee output/backup-run.log

Three copies, two media, one offsite. The irreplaceable assets go
to the object-locked buckets. The reproducible ones are skipped on
purpose and a receipt records what was skipped and how to rebuild
it.

The backup stamp is saved to output/LATEST_STAMP so you do not
have to copy it by hand.


----------------------------------------------------------------
STEP 5 - THE RESTORE TEST  (this is the graded core)
----------------------------------------------------------------

  ./code/restore_test.sh "$(cat output/LATEST_STAMP)" \
    2>&1 | tee output/restore-test.log

Restores from the object-locked buckets into a temporary folder and
a throwaway database called dr_scratch. Production is never
written to. Both scratch targets are deleted afterwards by a
cleanup trap, so this is safe to run more than once.

What to look for:

  PASS  datasets: checksums match ...
  PASS  weights: bit-for-bit identical ...
  PASS  prompt library: cloned ...
  PASS  vector source: recovered row count matches ... (512 rows)
  PASS  0 HNSW indexes restored ...
  MEASURED INDEX REBUILD TIME : <seconds>
  PASS  similarity search ... returned 8 neighbours
  RESULT: RESTORE TEST PASSED. 0 checks failed.

Take the MEASURED INDEX REBUILD TIME number and put it in two
places:

  - DR-PLAN.txt section 5, on the "measured" line
  - dr-asset-register.yaml, under vector-db-hnsw-index

Also fill in last_restore_test in the register with today's date.


----------------------------------------------------------------
STEP 6 - PROVE THE OBJECT LOCK IS REAL
----------------------------------------------------------------

  ./code/prove_immutability.sh 2>&1 | tee output/immutability-test.log

This attacks a throwaway canary object the way ransomware would,
and checks that the right calls fail. It confirms that a specific
version cannot be deleted from the COMPLIANCE bucket even with a
bypass and root credentials, that an overwrite makes a new version
and leaves the good one readable, and that the GOVERNANCE bucket
does allow a deliberate privileged delete.

It also demonstrates the thing that is easy to get wrong: a plain
delete on a versioned bucket only writes a delete marker, and
removing the marker brings the object back.


----------------------------------------------------------------
STEP 7 - COMPUTE THE RPO AND RTO
----------------------------------------------------------------

  python3 code/rpo_rto.py dr-asset-register.yaml \
    | tee output/rpo-rto-output.txt

These are computed from the register, not guessed. The output
prints both the chapter's formula and the true critical path
figure, and names the weakest link.


----------------------------------------------------------------
STEP 8 - COMMIT THE EVIDENCE
----------------------------------------------------------------

  git add -A
  git commit -m "Project 11: DR for the AI estate - measured restore test"
  git push


----------------------------------------------------------------
IF SOMETHING GOES WRONG
----------------------------------------------------------------

"psql: could not connect"
  The container is not running. Try: docker start gf-pg
  then: pg_isready -h 127.0.0.1
  If it still fails: docker logs gf-pg

"mc: command not found" or "$MC: No such file"
  Step 1 item 3 did not finish, or you did not source code/env.sh
  in this terminal. Run: source code/env.sh

"Unable to initialize new alias" / connection refused on 9000
  MinIO is not running. Try: docker start gf-minio
  then: curl -s http://127.0.0.1:9000/minio/health/live

"Bucket already exists" during setup
  Harmless. The script says so and carries on.

restore_test.sh says a stamp's objects are missing
  You probably passed an older stamp. Use:
    ./code/restore_test.sh "$(cat output/LATEST_STAMP)"

Starting completely over
  docker rm -f gf-pg gf-minio
  docker volume rm gf-minio-data
  rm -rf ~/gf-ai ~/gf-backup-local
  Then repeat from step 1 items 4 and 5.

  Worth noticing: the only reason that wipes COMPLIANCE-locked
  objects is that it deletes the whole storage volume out from
  under the server. Through the S3 API those objects genuinely
  cannot be deleted for 30 days. In production you do not have
  access to the storage vendor's disks, which is exactly why
  COMPLIANCE mode is a real control and not a checkbox.
