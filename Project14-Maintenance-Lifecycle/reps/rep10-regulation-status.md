# Rep 10 — Track the moving regulation

**Answer dated: 2026-07-30.** Re-verify before relying on this; that is the whole
point of the rep.

## Current status of the EU AI Act high-risk obligations

| Item | Status as of 2026-07-30 |
|---|---|
| **Statutory date in the original AI Act** | **2 August 2026** — the date Regulation (EU) 2024/1689 originally set for high-risk obligations to apply |
| **Digital Omnibus deferral (Annex III)** | **2 December 2027** — a 16-month deferral for stand-alone Annex III high-risk systems |
| **Has the Omnibus been formally adopted?** | **Yes.** It is no longer a proposal. |

### Adoption timeline

- **19 Nov 2025** — European Commission publishes the Digital Omnibus package.
- **7 May 2026** — provisional agreement reached in trilogue (Council, Parliament,
  Commission).
- **16 June 2026** — European Parliament endorses the package.
- **29 June 2026** — Council of the EU gives final approval.
- **27 July 2026** — enters into force as **Regulation (EU) 2026/1744**.

So the honest answer to "has it been formally adopted yet" changed **three days
ago**, and would have been "no — provisional agreement only" if I had written this
in early July. That is not a footnote; it is the lesson of the rep.

### Sources (cited and dated)

- Council of the EU / European Parliament adoption coverage, retrieved 2026-07-30.
- Gibson Dunn, "EU AI Act Omnibus Agreement — Postponed High-Risk Deadlines and
  Other Key Changes," retrieved 2026-07-30.
- Cloud Security Alliance research note, "EU AI Act High-Risk Deadline Pushed to
  December 2027," retrieved 2026-07-30.
- Primary source to confirm against before acting: the consolidated text of
  Regulation (EU) 2024/1689 as amended, on EUR-Lex.

**Verification note:** law-firm commentary is fast but secondary. Before any real
compliance decision I would pull the amending regulation from EUR-Lex and read the
transitional provisions myself, because commentary compresses and compression is
where nuance dies. Also worth stating plainly: the deferral applies to **stand-alone
Annex III** systems. Other parts of the Act — prohibitions, AI-literacy duties,
GPAI obligations, and the Art. 50 transparency rules — are already in application on
their own timetable, and Art. 6(1) high-risk systems embedded in regulated products
follow a different (later) track. "The deadline moved" is true of one slice, not the
whole law.

### What this means for my system

ministry-rag-summarizer is classified **limited-risk** (Rep 9), so the Annex III
deferral does not change my obligations at all. It changes my *risk of being wrong*:
if my classification is ever revisited and lands on high-risk, I now have until
December 2027 instead of next Sunday. That is breathing room I did not earn and
should not spend.

---

## Reflection

**Why is "the regulation is fixed" a maintenance bug?**

Because it is the same class of error as "the server is patched" — a statement about
a moment being treated as a statement about a state. Both are true when you write
them down and quietly decay afterward, and both fail in the same way: silently, with
no alert, until something external forces the discovery at the worst possible time.

The specific bug is that compliance gets modeled as a *build-time* property instead
of a *runtime* one. You classify the system, write "EU AI Act: limited risk, 2 Aug
2026 deadline" into the model card, pass the audit, and move on. The card is now a
cached value with no invalidation strategy. Nothing in my repository knows that the
statutory date moved on 27 July 2026, because the field is a string and strings do
not watch the Official Journal.

And notice the direction this instance moved. The deadline got *later*, which is the
sneaky case. A deadline moving earlier causes a panic that at least produces
attention. A deadline moving later means teams keep working against 2 August 2026,
burning sprint capacity on a date that no longer exists — or worse, they hear "it got
delayed," relax, and never learn that the deferral covers stand-alone Annex III
systems and not the prohibitions, the AI-literacy duties, or the GPAI obligations
that are already live. Stale regulatory knowledge causes wasted work and false
comfort at the same time, and neither shows up on a dashboard.

The three failure modes, named: a **stale date** (you plan against a deadline that
moved), a **stale classification** (your system's use changed and its tier did not),
and a **stale scope** (the law changed which systems are covered, and you never
re-read the annex).

**The recurring task I would schedule**

A **quarterly regulatory review**, on the calendar with an owner, producing a dated
written finding even when the finding is "no change." Concretely: re-read the
current consolidated text of the AI Act on EUR-Lex plus the AI Office's published
guidance; re-confirm the applicable dates for every tier my estate touches;
re-validate the tier classification of each registered AI system against the current
Annex III, asking specifically whether any system's *use* has drifted since last
quarter; check for new delegated acts, standards, or codes of practice; and update
the `governance.eu_ai_act_tier` and `eu_ai_act_basis` fields on every model card with
a fresh date stamp. Between quarters, a subscription tier: alerts on the EUR-Lex
document and the AI Office's page, routed to a ticket queue rather than an inbox,
because an email nobody owns is not a control. Anything found out of band gets
triaged into the next review or escalated if a date moved.

**How this connects to re-checking a CVE feed**

It is structurally the identical control, and I think that is the real insight of
this rep.

In Rep 1 I do not decide once that my systems are secure. I ingest a feed that
changes daily, score it deterministically, tier it, and act on the tiers — and the
whole apparatus exists because *the world changes underneath a system that is not
itself changing*. A server that was compliant with best practice last month is
vulnerable today because a researcher published, not because anyone touched the
server. That is exactly what happened here: my compliance posture changed on
27 July 2026 without a single commit to my repository.

So regulation is a feed. It has publications with dates, it has severity (a
prohibition is EMERGENCY; a deferral that grants me more time is LOW-but-track), it
has an equivalent of `has_fix: false` (a rule that applies before any standard or
guidance exists to conform to — you cannot patch it, you can only mitigate and
document), and it has a KEV analogue (is this being *enforced*, or is it merely on
the books?). It deserves the same treatment: scheduled ingestion, deterministic
triage, a named owner, and a dated written record of each decision.

The cadence differs because the change rate differs — CVEs daily, regulation
quarterly — but the discipline is the same, and so is the failure mode when you skip
it. In both cases the ticking clock is invisible and external, and in both cases
"nobody told us" is not a defense anyone accepts. The one asymmetry worth noting:
you can roll back a bad patch. You cannot roll back a missed statutory deadline.
