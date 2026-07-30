#!/usr/bin/env bash
# prove_immutability.sh - an object lock you have not tested is a claim, not a control.
#
# This script attacks our own backups the way ransomware would, and checks that the
# right things fail. It works on a throwaway CANARY object, not on the real assets.
#
# TWO MISTAKES I MADE WRITING THIS, BOTH KEPT HERE BECAUSE THEY ARE THE LESSON:
#
# 1. My first version ran "mc rm" on the weights and asserted it must fail. It did
#    not fail. It reported success, and I nearly wrote down "object lock is broken."
#    It is not broken. On a versioned bucket, rm without a version id writes a
#    DELETE MARKER. The object vanishes from a normal listing while the locked
#    version sits underneath, untouched and still readable. Object Lock protects
#    VERSIONS, not names. So the real test is to delete a SPECIFIC VERSION - that is
#    what an attacker would have to do to actually destroy the archive.
#
# 2. That same first version attacked the real weights object. It left a 24-byte
#    "ransomware" file as the current version, which broke the next restore test.
#    And because the bucket is COMPLIANCE locked, I could not delete my own mess.
#    That is a very fast way to learn what COMPLIANCE mode means. Hence the canary.
#
# Run:  source code/env.sh && ./code/prove_immutability.sh
set -uo pipefail          # deliberately no -e: refusals are the expected outcome here
cd "$(dirname "$0")/.."
source code/env.sh >/dev/null

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
PASS=0; FAIL=0
line() { printf -- '----------------------------------------------------------------\n'; }
ok()   { printf 'PASS  %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf 'FAIL  %s\n' "$*"; FAIL=$((FAIL+1)); }

# True if the output looks like the server refused us.
refused() { echo "$1" | grep -qiE 'denied|retention|WORM|not allowed|forbidden|locked|Object is'; }

# Version id of the newest real upload of an object (skipping delete markers).
newest_version() {
  "$MC" ls --versions --json "$1" 2>/dev/null | python3 -c '
import sys, json
rows = [json.loads(l) for l in sys.stdin if l.strip()]
rows = [r for r in rows if r.get("versionId") and not r.get("isDeleteMarker")]
print(rows[0]["versionId"] if rows else "")'
}

echo "================================================================"
echo " IMMUTABILITY TEST - attacking our own backups on purpose"
echo "================================================================"
echo " run at (UTC) : $(date -u +%FT%TZ)"
echo " target       : a disposable canary object. Real assets are not touched."

# --------------------------------------------------------------------------
line; echo "A - how the buckets are actually configured on the server"
echo "\$ mc retention info --default $MC_ALIAS/$GF_BUCKET_WORM"
"$MC" retention info --default "$MC_ALIAS/$GF_BUCKET_WORM"
echo "\$ mc retention info --default $MC_ALIAS/$GF_BUCKET_GOV"
"$MC" retention info --default "$MC_ALIAS/$GF_BUCKET_GOV"
echo "\$ mc version info $MC_ALIAS/$GF_BUCKET_WORM"
"$MC" version info "$MC_ALIAS/$GF_BUCKET_WORM"
echo
echo "Object Lock requires versioning, and it can only be switched on when a bucket"
echo "is CREATED. 'mc mb --with-lock' is a one-way door. You cannot add it later to a"
echo "bucket you already have."

# --------------------------------------------------------------------------
line; echo "B - plant a canary in the COMPLIANCE bucket and look at its lock"
CANARY="$MC_ALIAS/$GF_BUCKET_WORM/canary/canary-${STAMP}.txt"
printf 'canary %s - these are the good bytes\n' "$STAMP" > /tmp/gf-canary.txt
GOOD_SUM=$(sha256sum /tmp/gf-canary.txt | awk '{print $1}')
"$MC" cp -q /tmp/gf-canary.txt "$CANARY" >/dev/null
echo "\$ mc stat $CANARY"
"$MC" stat "$CANARY" | grep -iE 'name|size|lock|retain' | sed 's/^/    /'
CVID="$(newest_version "$CANARY")"
echo "    version id of the good copy: $CVID"
if "$MC" stat "$CANARY" | grep -qi 'COMPLIANCE'; then
  ok "the canary inherited COMPLIANCE retention from the bucket default"
  echo "      (nobody had to remember to set it per file, which is the point)"
else
  bad "the canary did not inherit a retention mode - the bucket default is not working"
fi

# --------------------------------------------------------------------------
line; echo "C - ATTACK 1: delete that specific version. This is the attack that matters."
echo "\$ mc rm --version-id $CVID <canary>"
OUT="$("$MC" rm --version-id "$CVID" "$CANARY" 2>&1)"; echo "$OUT" | sed 's/^/    /'
if refused "$OUT"; then
  ok "version-level delete was REFUSED by COMPLIANCE retention"
else
  bad "version-level delete was not refused - check the bucket lock configuration"
fi

# --------------------------------------------------------------------------
line; echo "D - ATTACK 2: the same delete, now with the governance bypass flag."
echo "On a COMPLIANCE object this must still fail. That is the whole difference"
echo "between the two modes."
echo "\$ mc rm --bypass --version-id $CVID <canary>"
OUT="$("$MC" rm --bypass --version-id "$CVID" "$CANARY" 2>&1)"; echo "$OUT" | sed 's/^/    /'
if refused "$OUT"; then
  ok "bypass was REFUSED on COMPLIANCE - even root cannot shorten the retention"
else
  bad "bypass succeeded on a COMPLIANCE object, which should be impossible"
fi

# --------------------------------------------------------------------------
line; echo "E - ATTACK 3: a plain rm with no version id. This SUCCEEDS, and that is fine."
echo "It writes a delete marker. The file looks gone. The locked version is not."
echo "This is the step that fooled me the first time."
"$MC" rm "$CANARY" 2>&1 | sed 's/^/    /'
echo
echo "\$ mc ls $MC_ALIAS/$GF_BUCKET_WORM/canary/     # normal listing: looks deleted"
"$MC" ls "$MC_ALIAS/$GF_BUCKET_WORM/canary/" 2>/dev/null | grep -- "$STAMP" | sed 's/^/    /' \
  || echo "    (nothing listed - the delete marker is hiding it)"
echo
echo "\$ mc ls --versions <canary>                    # version listing: still there"
"$MC" ls --versions "$CANARY" | sed 's/^/    /'
echo
echo "\$ mc cat --version-id $CVID <canary> | sha256sum"
BACK_SUM=$("$MC" cat --version-id "$CVID" "$CANARY" 2>/dev/null | sha256sum | awk '{print $1}')
echo "    archived version sha256 : $BACK_SUM"
echo "    original sha256         : $GOOD_SUM"
if [ "$BACK_SUM" = "$GOOD_SUM" ]; then
  ok "the good bytes are still readable and still verify after that 'successful' delete"
else
  bad "the archived version no longer matches its original checksum"
fi

# Undo the ransomware delete. Delete markers carry no retention, so removing one is
# allowed - and that is exactly how you recover from this attack.
DMVID="$("$MC" ls --versions --json "$CANARY" 2>/dev/null | python3 -c '
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if d.get("isDeleteMarker"):
        print(d["versionId"]); break')"
if [ -n "$DMVID" ]; then
  if "$MC" rm --version-id "$DMVID" "$CANARY" >/dev/null 2>&1; then
    ok "recovered: removed the delete marker and the object is visible again"
  fi
fi

# --------------------------------------------------------------------------
line; echo "F - ATTACK 4: overwrite it with garbage, which is what ransomware really does."
printf 'ENCRYPTED_BY_RANSOMWARE\n' > /tmp/gf-ransom.txt
"$MC" cp -q /tmp/gf-ransom.txt "$CANARY" >/dev/null 2>&1
echo "\$ mc cat <canary>                       # current version: encrypted"
"$MC" cat "$CANARY" | sed 's/^/    /'
echo "\$ mc cat --version-id $CVID <canary>    # archived version: intact"
"$MC" cat --version-id "$CVID" "$CANARY" | sed 's/^/    /'
BACK_SUM=$("$MC" cat --version-id "$CVID" "$CANARY" 2>/dev/null | sha256sum | awk '{print $1}')
if [ "$BACK_SUM" = "$GOOD_SUM" ]; then
  ok "the overwrite made a NEW version; the locked good version survived it"
else
  bad "the locked version did not survive an overwrite"
fi

# --------------------------------------------------------------------------
line; echo "G - the contrast: the GOVERNANCE bucket has a deliberate escape hatch"
GCAN="$MC_ALIAS/$GF_BUCKET_GOV/canary/canary-${STAMP}.txt"
"$MC" cp -q /tmp/gf-canary.txt "$GCAN" >/dev/null
GVID="$(newest_version "$GCAN")"
echo "\$ mc rm --version-id $GVID <gov canary>             # ordinary delete"
OUT="$("$MC" rm --version-id "$GVID" "$GCAN" 2>&1)"; echo "$OUT" | sed 's/^/    /'
if refused "$OUT"; then
  ok "GOVERNANCE also refuses an ordinary version delete - it is a real lock"
else
  bad "the GOVERNANCE object was deleted with no bypass at all"
fi
echo "\$ mc rm --bypass --version-id $GVID <gov canary>    # privileged and deliberate"
OUT="$("$MC" rm --bypass --version-id "$GVID" "$GCAN" 2>&1)"; echo "$OUT" | sed 's/^/    /'
if refused "$OUT"; then
  bad "the GOVERNANCE bypass was refused - we have lost our privacy-deletion hatch"
else
  ok "GOVERNANCE bypass ALLOWED - the same call that was refused in attack 2"
  echo "      This is the capability we keep on purpose: a member asking us to delete"
  echo "      their document, or a password accidentally committed to a prompt file."
fi

rm -f /tmp/gf-canary.txt /tmp/gf-ransom.txt

# --------------------------------------------------------------------------
line
echo "checks passed: $PASS    checks failed: $FAIL"
echo
echo "WHAT THIS PROVES"
echo
echo "COMPLIANCE tier - the fine-tuned weights and the eval datasets:"
echo "  A specific version cannot be deleted. Not with a normal delete, not with a"
echo "  bypass, not with the root credential, not until the 30-day retention runs"
echo "  out. An overwrite becomes a new version and leaves the old one readable."
echo "  Ransomware running with our own credentials cannot destroy the recovery point."
echo
echo "GOVERNANCE tier - the vector dumps, prompts and configs:"
echo "  The same delete is refused for an ordinary caller but allowed for a"
echo "  privileged one who passes --bypass. We keep that hatch deliberately. The"
echo "  trade-off is that a sufficiently privileged attacker could use it too, and"
echo "  that is exactly why the weights are NOT in this tier."
echo
echo "And the thing that is easy to get wrong: a plain delete on a versioned bucket"
echo "only writes a delete marker. Remove the marker and the object is back."
echo "Immutability lives at the version level, not at the filename level."
[ "$FAIL" -eq 0 ] || exit 1
