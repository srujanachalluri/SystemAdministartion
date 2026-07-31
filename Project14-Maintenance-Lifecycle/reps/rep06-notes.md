# Rep 6 — Notes and reflection (card is `rep06-model_card.yaml`)

I re-created the structure of `code/model_card.yaml` by hand for the
ministry-rag-summarizer, then extended it in three places:

1. **A `serving_stack:` block.** The starter card versions the model but not the
   stack that produces its behavior. Rep 5 showed why that is a gap, so my card
   carries the full manifest — engine, flags, embedding model, index version,
   prompt hash, CUDA, driver, GPU SKU.
2. **A `gate_thresholds:` block.** The starter has `gate_passed: true` but never
   says what the gate *is*. A boolean with no threshold behind it is an opinion.
3. **Measured/target tagging.** Every number is marked. Only
   `cost_per_1m_tokens_usd` is a target; everything else was measured on
   2026-07-28 against 412 held-out donor letters.

The base model ID is pinned as `claude-opus-4-1-20250805` — the exact dated API
string, not "Claude Opus 4.1." The retirement date (2026-08-05) was verified on
2026-07-30 against Anthropic's model-deprecations page, not copied from the
starter file.

## Reflection

**Which fields would block promotion if left blank or failing?**

Six, and they block for two different reasons.

*Blocking because the number itself fails the gate:*

- **`gate_passed: false`** — the whole point of the field. Anything else on the
  card can be excellent; if the gate failed, the model does not move.
- **`groundedness` below 0.90** — this is a RAG summarizer. Groundedness *is* the
  product. A summary of a donor letter that is fluent and unsupported is worse than
  no summary, because staff will trust it.
- **`hallucination_rate` above 0.05** and **`pii_leak_rate` above 0.00** — the PII
  threshold is zero rather than "low" on purpose. The training data is
  `pii_class: restricted` consented donor correspondence, and a single leaked donor
  name across contexts is a reportable privacy incident, not a quality regression.

*Blocking because a blank field means nobody is accountable:*

- **`approver`** — an unsigned card is a model that promoted itself. The name is
  what makes the risk acceptance a decision instead of an accident (Rep 3).
- **`retire_after: null`** — the starter comments "never leave this blank forever,"
  and mine is dated 2026-08-05 because the base model retires that day. A null here
  is how a system ends up running on a model that no longer exists.
- **`base_model_id` left as a marketing name** — "Claude Opus 4.1" is not pinnable,
  not greppable, and not migratable. Rep 8's Step-0 inventory grep only works
  because the exact dated string is in the card and in the code.

I would also *not* promote on a blank `datasheet_ref` or `provenance`. Those do not
fail a threshold, but they are the only evidence of what the model was built from,
and reconstructing them after the fact is close to impossible.

**Why is `human_label_agreement` on the card at all?**

Because it is the field that validates every other measured number on the card.

Groundedness 0.93 and hallucination rate 0.04 are not produced by a human reading
412 letters. They are produced by an LLM-as-judge scoring the outputs. So those
numbers are the *judge's* opinion, and the card is quietly asking me to trust a
model's assessment of a model. `human_label_agreement: 0.89` is the measurement of
whether that trust is earned — the judge's labels compared against two human raters
on a sampled subset, reported as Cohen's kappa.

Without it, the evaluation section is circular. A judge that has silently drifted
toward leniency — or that shares a base model with the system under test, and so
shares its blind spots — will happily report 0.93 groundedness on a model that is
inventing donor details. The eval passes, the gate passes, the card looks
governance-grade, and the number is meaningless. That failure is completely
invisible unless something on the card measures the measuring instrument.

The deeper reason it belongs on the card rather than in a lab notebook: it makes
the evaluation *falsifiable to an outsider*. An auditor reading "groundedness 0.93"
has no way to know if that is real. An auditor reading "groundedness 0.93, judge
validated against humans at kappa 0.89" can assess the whole chain of evidence. It
is the difference between a claim and a measurement.

It also has to be re-measured, not measured once. The judge is itself a model on a
stack that drifts (Rep 5), so agreement decays. My lifecycle plan schedules
re-validation of the judge on the same cadence as the eval suite — a stale kappa is
almost as bad as no kappa, because it looks like evidence and isn't.

If I had to set one more gate threshold, it would be a floor on
`human_label_agreement` itself: below 0.85, the eval suite is not producing usable
evidence and *no* promotion decision can be made from it, regardless of how good the
other numbers look.
