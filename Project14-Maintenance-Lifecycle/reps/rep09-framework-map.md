# Rep 9 — Map one system across all three frameworks

**System:** ministry-rag-summarizer v3.0.0 (the model card in
`rep06-model_card.yaml`) — RAG summarization of donor correspondence.

---

## (a) NIST AI RMF 1.0 — which of Govern / Map / Measure / Manage my card's fields support

My card touches all four functions, and the fields sort cleanly between them.
**Govern** is carried by `owner.team`, `owner.approver`, `governance.audit_log`, and
`governance.human_oversight` — these are the standing structures that say who is
accountable and where the evidence lives, and they are the reason the risk
acceptance in Rep 3 has a name on it rather than a shrug. **Map** is carried by
`model.task`, `training_data.provenance`, `training_data.pii_class`,
`governance.eu_ai_act_tier`, and the `serving_stack` block — context-setting: what
this system is for, what it is built from, and where its risks live (the stack
manifest is Map work, because you cannot characterize risk in a component you have
not listed). **Measure** is the `evaluation` block — groundedness 0.93, hallucination
0.04, `human_label_agreement` 0.89, PII leak 0.00 — with `gate_thresholds` making
those measurements decision-relevant rather than decorative, and `human_label_agreement`
serving as Measure applied to the measuring instrument itself. **Manage** is
`lifecycle` — stage, `promoted_on`, `deprecation_notice`, `retire_after`,
`rollback_target` — plus the migration runbook in Rep 8; this is the function that
turns measurement into ongoing action and eventual retirement. If I had to name the
card's single `nist_rmf_function` value, it is **Manage**, because the system is in
production and the live work is maintenance — but that field names the current
center of gravity, not the only function in play.

## (b) EU AI Act — my honest risk-tier classification

**Limited risk (transparency obligations), not high risk** — and I want to show the
reasoning rather than assert the conclusion, because this is the classification an
AI must never make for me. The system summarizes donor correspondence for internal
staff review. It is not a safety component of a regulated product (so not Art. 6(1)),
and I walked Annex III point by point: not biometrics, not critical infrastructure,
not education access, not employment or worker management, not access to essential
public or private services, not law enforcement, not migration or border control,
not justice. The nearest miss is Annex III point 5 — access to essential services,
including creditworthiness — and the reason it misses is specific: no output of this
system determines whether any person receives anything. A staff member reads every
summary and makes every donor-facing decision, and the model never sends outbound
correspondence. **Honest caveats, stated because a classification with no stated
fragility is not honest:** first, if this system were ever extended to score or rank
donors for eligibility, prioritization, or benefit decisions, the Annex III analysis
changes and I would re-classify — so the classification is pinned to the current
intended use, and a change in use is a governance event that re-opens it. Second,
"a human reviews everything" is a real control only while it is real; rubber-stamp
review at volume is how limited-risk systems drift into high-risk behavior without
anyone filing a change. The obligations I do owe at limited risk are the Art. 50
transparency ones (staff know they are reading machine-generated summaries) plus
GDPR in full, since the corpus is `pii_class: restricted` consented donor data.
Being classified limited-risk removes AI Act high-risk duties; it removes nothing
about data protection.

## (c) ISO/IEC 42001 — one AIMS control this system would satisfy

**A.6.2.4 — AI system lifecycle (design, development, deployment, operation,
retirement).** This is the control my card and my reps most directly evidence,
which is why it is the value in `governance.iso_42001_control`. 42001 asks for a
defined, documented, repeatable lifecycle with gates between stages, and the
evidence is concrete rather than aspirational: `lifecycle.stage` names the current
stage in an explicit dev → staging → production → deprecated → retired progression;
`gate_thresholds` defines what a promotion gate actually requires, so "passed" is a
measurement and not an opinion; `promoted_on` plus `promoted_by` records who moved
it and when; `deprecation_notice` and `retire_after` show the back half of the
lifecycle is planned rather than improvised; and Rep 8's migration runbook is the
documented retirement procedure with the derivative-first rule attached. I could
also reasonably claim A.5.2 (AI system impact assessment) via the EU tier reasoning
above and A.7.x (data management) via the datasheet, provenance, TDM opt-out, and
retention fields — but A.6.2.4 is the one this week's work most defensibly
demonstrates, because the artifacts exist and are dated.

---

## Reflection — these are layers, not competitors

**NIST AI RMF** gives me the *vocabulary and the risk-thinking process* — a
voluntary, non-certifiable framework that tells me how to reason about AI risk
across Govern/Map/Measure/Manage, which neither of the others supplies, because
the EU AI Act tells me what is required but never how to think, and ISO 42001 tells
me to have a system but not what good risk reasoning looks like inside it.

**The EU AI Act** gives me *legally binding obligations with penalties and dates* —
a classification that determines what I must do, backed by fines and enforced by
regulators, which neither of the others has: NIST is entirely voluntary and ISO
certification is a market signal, not a legal duty, so only the AI Act can make
`retire_after` something I must fill in rather than something I ought to.

**ISO/IEC 42001** gives me an *auditable, certifiable management system* — the
organizational machinery of policy, roles, internal audit, and continual improvement
that a third party can certify, which neither of the others provides: NIST offers no
certification path at all, and the AI Act tells me the outcome required without
specifying the management structure that reliably produces it year after year.

Stacked in practice: the AI Act sets the floor I must clear, ISO 42001 is the
management system that clears it repeatably and provably, and NIST RMF is the
reasoning I do inside that system to decide what "clearing it" means for this
particular model. Anyone treating them as alternatives — "we do NIST *instead of*
42001" — has confused a thinking tool, a law, and an operating manual for three
options on a menu.
