# Rep 2 — Triage the same feed with AI, then judge the gap

I pasted the same `code/cve_feed.json` into an AI copilot and asked it to rank the
advisories and recommend a patch schedule. Full prompt and raw reply are logged in
`agent-log.txt`.

## What the AI produced

<!-- paste the copilot's actual ranking here if yours differed -->

The copilot's ranking:

1. CVE-2026-10122 — patch immediately (RCE, KEV, internet-facing)
2. CVE-2026-10588 — "critical, escalate to the vendor and patch as soon as a fix ships"
3. CVE-2026-10733 — patch this week
4. CVE-2026-10477 — next window
5. CVE-2026-10610 — defer

It also volunteered a recommended maintenance calendar, a suggested rollback plan,
and a line noting that the reverse proxy "likely fronts a load balancer that will
need to drain connections during the patch."

## Where it differed from `patch_triage.py`

| | patch_triage.py | AI copilot |
|---|---|---|
| 1 | CVE-2026-10122 | CVE-2026-10122 |
| 2 | CVE-2026-10733 | **CVE-2026-10588** |
| 3 | CVE-2026-10477 | CVE-2026-10733 |
| 4 | CVE-2026-10610 | CVE-2026-10477 |
| 5 | CVE-2026-10588 | CVE-2026-10610 |

The two agree on first and mostly on last. The interesting disagreement is
CVE-2026-10588, which the scorer ranks **fifth** and the AI ranks **second**.

**Did it invent a downstream dependency or risk that is not in the data?** Yes,
twice. The load balancer that "will need to drain connections" does not appear
anywhere in `cve_feed.json` — the feed has five fields per advisory and none of
them describe my topology. It is a plausible guess about a reverse-proxy
deployment, and it might even be true of my estate, but the model did not know
that; it pattern-matched. It also asserted the GPU driver flaw was reachable from
the container runtime, which is a claim about my isolation posture that no one
gave it.

**Did it miss the `has_fix: false` case?** This is the one that matters. It did
not miss the field — it read it and then reasoned *past* it, telling me to
"patch as soon as a fix ships" while still sorting the item second. That is a
scheduling instruction that cannot be executed. `patch_triage.py` adds +30 for a
missing fix precisely to keep unpatchable items out of the urgent queue, because
an urgent ticket nobody can close is worse than a tracked one: it burns attention
and it teaches the team that EMERGENCY does not mean EMERGENCY. The right handling
for 10588 is **mitigate** — restrict access to the GPU nodes, add detection for
privilege-escalation attempts, set a recheck date on the vendor advisory — and the
AI's ranking pushes toward the opposite instinct.

## Reflection (three sentences on which ranking I would act on, and why the human owns the schedule)

I would act on the `patch_triage.py` ranking, because it is deterministic and
auditable — I can re-run it in six months, get the identical ordering, and show an
auditor the exact arithmetic that produced each tier, which I cannot do with a
copilot reply that may rank the same feed differently tomorrow. The AI's output was
genuinely useful as *drafting* material — its rollback notes and its connection
draining observation are worth keeping in the change record — but it mixed those
real contributions with two invented facts about my infrastructure, and a ranking I
have to fact-check line by line is not a ranking, it is homework. The human owns
the schedule because the schedule is a risk acceptance: deciding that
CVE-2026-10588 stays unpatched with compensating controls means someone is
accepting the residual risk of a GPU-driver privilege escalation, and that
acceptance needs a name and a date on it — a model cannot be accountable for a
decision it will not remember making.
