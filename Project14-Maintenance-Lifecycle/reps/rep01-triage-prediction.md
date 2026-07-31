# Rep 1 — Triage a CVE feed deterministically

Command run:

```
python3 code/patch_triage.py code/cve_feed.json
```

## Step 1 — My prediction (written BEFORE running the scorer)

I predicted **CVE-2026-10122** would land in EMERGENCY.

Why: it is the only advisory in the feed that is high severity (CVSS 9.8) **and**
on CISA's Known Exploited Vulnerabilities list **and** internet-facing **and**
already has a vendor fix. All four of the scorer's levers push in the same
direction, so nothing else in the feed can beat it.

I also predicted CVE-2026-10733 (CVSS 9.1, KEV, but internal) would land second,
and that CVE-2026-10588 (no vendor fix) would sort near the bottom even though
its CVSS of 8.1 is higher than 7.5 and 4.3.

## Step 2 — Actual output

<!-- paste the real terminal output here -->

```
CVE                CVSS  KEV  TIER
------------------------------------------------------------
CVE-2026-10122      9.8  yes  EMERGENCY (patch in 24h)
CVE-2026-10733      9.1  yes  HIGH (patch this week)
CVE-2026-10477      7.5   no  MEDIUM (next maintenance window)
CVE-2026-10610      4.3   no  LOW (track; defer)
CVE-2026-10588      8.1   no  LOW (track; defer)

Reminder: this ranks. A human owns the maintenance schedule and the risk acceptance.
```

## Step 3 — Prediction vs. reality (the gap)

My EMERGENCY call was right. What I got wrong was the *size* of the gap between
10122 and 10733. I expected them to be close; they are not.

Working the arithmetic by hand:

| CVE | base | CVSS x5 | KEV | internet | no fix | final | tier |
|---|---|---|---|---|---|---|---|
| CVE-2026-10122 | 100 | -49 | -40 | -20 | — | **-9** | EMERGENCY |
| CVE-2026-10733 | 100 | -45 | -40 | — | — | **15** | HIGH |
| CVE-2026-10477 | 100 | -37 | — | -20 | — | **43** | MEDIUM |
| CVE-2026-10610 | 100 | -21 | — | — | — | **79** | LOW |
| CVE-2026-10588 | 100 | -40 | — | — | +30 | **90** | LOW |

The 20-point internet-facing penalty is what separates the two 9-point CVEs.
Only one item crosses the EMERGENCY threshold of 10, and it crosses by 19 points.

## Reflection

**CVE-2026-10733 is CVSS 9.1 and actively exploited (KEV) but not internet-facing,
while CVE-2026-10477 is only CVSS 7.5 but internet-facing. Defend the scorer's
ordering — or argue it is wrong for my hypothetical estate.**

I defend the ordering, and I would ship it as written for my estate.

The scorer puts 10733 (HIGH, score 15) above 10477 (MEDIUM, score 43), which is
correct because *exploitation is a fact and severity is a forecast*. CVSS is a
model of how bad a vulnerability could be under assumed conditions. KEV is an
observation that someone is actually using it right now, today, against real
targets. Weighting the observation (-40) more heavily than a point and a half of
forecast severity is the right instinct. An auth bypass in the model registry
also has an unusually nasty blast radius for an AI estate — the registry is where
weights and aliases live, so an attacker who owns it can swap what my `@champion`
alias resolves to and poison every downstream inference without ever touching the
serving layer. That is a supply-chain compromise wearing an internal-only badge.

The one place I would push back is the assumption baked into "not internet-facing."
That flag is doing 20 points of work, and it only earns those points if my network
segmentation is real. In my estate the registry sits behind the VPN, but the CI
runners that pull from it are reachable from the build system, and the build
system takes webhooks from the internet. So "internal" is one pivot away, not
zero. If I could not prove the segmentation with a current network diagram and a
recent test, I would manually promote 10733 to EMERGENCY rather than change the
scorer — and I would say so in the change record, with my name on it.

CVE-2026-10477 at MEDIUM is fine. It is a denial of service, not a compromise:
the pgvector backend crashes and retrieval degrades, but nothing leaks and nothing
executes. It is internet-facing so it does deserve the -20, and MEDIUM (next
maintenance window) reflects an availability hit I can absorb behind a restart
policy.

The item I want to say the most about is **CVE-2026-10588**, which lands dead last
at LOW with a score of 90 despite a CVSS of 8.1 — higher than 10477's 7.5. That is
not the scorer being dumb. `has_fix: false` adds +30 on purpose, because there is
nothing to patch. Ranking it urgently would produce a ticket that no engineer can
close, which is how backlogs rot and how real EMERGENCY items get lost in noise.
What the tier name hides is that LOW here means "no patch action," not "no action."
This one needs a mitigation track — restrict who can reach the GPU nodes, watch
for privilege-escalation signatures, and set a recheck date for the vendor
advisory — and it needs a human to own that, because the scorer has no column for it.

That is the honest limit of the whole tool. It sorts a queue deterministically and
auditably, which is exactly what I want at 2 a.m. when judgment is worst. It does
not know my topology, it cannot see that "internal" is contingent, and it cannot
tell the difference between "safe to defer" and "impossible to patch." I own those.
