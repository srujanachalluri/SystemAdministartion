# Rep 3 — Change Record: CR-2026-0714

**One page. Applying the EMERGENCY patch from Rep 1.**

| Field | Value |
|---|---|
| **Change ID** | CR-2026-0714 |
| **Title** | Emergency patch — CVE-2026-10122, unauthenticated RCE in the reverse proxy fronting the inference API |
| **Type** | Emergency / unplanned |
| **Raised by** | Srujana Challuri, Systems Administration |
| **Date raised** | 2026-07-30 |
| **Target window** | 2026-07-30 22:00–23:00 CDT (within the 24h EMERGENCY SLA) |
| **Systems affected** | `proxy-01`, `proxy-02` (reverse proxy tier), ministry-rag-summarizer inference API behind them |
| **Service impact** | ~90 seconds of degraded latency per node during rolling restart; no full outage expected |

## WHO

- **Implementer:** Srujana Challuri
- **Peer reviewer:** _[name of the second engineer who reviewed the diff]_
- **Approver (change authority):** _[name]_
- **Risk acceptance signature (deferred CVEs):** ______________________ / date ______

## WHAT

Upgrade the reverse proxy package on `proxy-01` and `proxy-02` from the current
vulnerable release to the vendor's fixed release, applied one node at a time behind
the load balancer. No configuration files change. No application code changes. No
model, prompt, or weights change — the model card version stays at 2.3.0 because
nothing in the behavior-producing stack moved.

## WHY

`patch_triage.py` scored CVE-2026-10122 at **-9**, the only advisory in the feed
that crosses the EMERGENCY threshold of 10. It is CVSS 9.8, on CISA's KEV list
(actively exploited in the wild), internet-facing, and a vendor fix exists. It is
unauthenticated remote code execution on the box that terminates public traffic to
our inference API — an attacker who lands there is inside the request path for
every prompt and every response. There is no compensating control that makes
waiting for the next maintenance window defensible.

## WHEN

- 22:00 — snapshot both nodes, verify snapshot restores
- 22:10 — drain `proxy-01` from the load balancer, patch, restart, health-check
- 22:25 — soak 10 minutes; watch error rate and p95 latency
- 22:35 — return `proxy-01` to the pool, repeat for `proxy-02`
- 23:00 — post-change verification, close ticket

## HOW TO ROLL BACK

1. **Trigger conditions (any one, no debate):** health check fails after restart;
   5xx rate above 1% for 3 consecutive minutes; p95 latency above 2x baseline;
   any TLS handshake failure on the public listener.
2. **Rollback, in order:**
   - Drain the affected node from the load balancer immediately.
   - `apt-get install <package>=<previous-pinned-version>` (exact prior version is
     recorded in the pre-change inventory captured at 22:00 — the rollback is not
     "the last version," it is *this* version string).
   - Restart the service, health-check, return to pool.
   - If package rollback fails, restore the 22:00 snapshot — this is the escape
     hatch, targeted at under 10 minutes per node.
3. **Rollback owner:** the implementer, with no additional approval needed. An
   emergency change that cannot be reversed without a meeting is not reversible.
4. **Rollback leaves us exposed to CVE-2026-10122 again**, so a rollback
   automatically re-opens this change record as a P1 rather than closing it.

## VERIFICATION (how we know it worked)

- Package version reports the fixed release on both nodes.
- Vendor's proof-of-concept request returns 400, not 200.
- `/healthz` green on both nodes; error rate and p95 back to baseline.
- Re-run `python3 code/patch_triage.py code/cve_feed.json` against the refreshed
  feed and confirm CVE-2026-10122 has dropped out of EMERGENCY.

## RISK ACCEPTANCE FOR DEFERRED CVEs

**CVE-2026-10588** — GPU driver privilege escalation, CVSS 8.1, `has_fix: false`.
Deferred because there is no vendor fix to apply. Compensating controls in place
for the deferral period: GPU node access restricted to the platform-ai group,
privilege-escalation detection rules enabled on those hosts, vendor advisory
recheck scheduled for **2026-08-13** and every 14 days after.

> This is a **residual risk accepted by a named human**, not a decision to ignore
> the vulnerability. If the recheck date passes without action, this record is
> re-opened.

**Accepted by (print name):** ______________________________

**Signature:** ______________________________  **Date:** ____________

*(CVE-2026-10477, 10610, and 10733 are scheduled, not deferred — see Rep 1 tiers.
CVE-2026-10733 is scheduled for the current week per its HIGH tier.)*

---

## Reflection

**Which field is the one an AI must never fill in?**

The **risk acceptance signature** — the line with a human name and a date on it,
at the bottom of the deferral section. (The approver signature is the same kind of
field for the same reason.)

An AI can legitimately draft almost everything else on this page. It can write the
rollback steps, propose the maintenance window, summarize the CVE, even suggest
which items are safe to defer. Every one of those is a *recommendation*, and a
recommendation is checkable — I read it, I disagree or I don't, and my judgment
still sits between the draft and production.

A signature is a different kind of object. It is not information about the change;
it is the act of somebody assuming consequences for it. When I sign "I accept the
residual risk of CVE-2026-10588 remaining unpatched," I am saying that if a GPU
node gets rooted next month, the answer to "who decided to leave this open?" is a
person who can be asked, who has to explain the reasoning, and who has something at
stake in getting it right. That is the entire function of the line. A model cannot
supply any of it — it will not be in the incident review, it cannot be questioned
about what it knew on July 30th, and it bears nothing if it was wrong. A signature
from a language model is a signature from nobody.

That is exactly what separates a decision from an accident. Both look identical in
production: a vulnerability sits unpatched. The difference is entirely upstream. In
the decision case, someone looked at the CVSS, looked at the missing fix, looked at
the compensating controls, judged the trade-off, and put their name to it — so
there is a reason on the record, a review date, and a person to revisit it. In the
accident case, the CVE was simply never handled, and nobody knows whether that was
a choice or an oversight. Fill that field with an AI and you get the second case
wearing the paperwork of the first: the audit trail says a decision was made, but
no one actually decided anything and no one is answerable when it fails. That is
worse than a blank line, because a blank line at least tells the truth about itself.
