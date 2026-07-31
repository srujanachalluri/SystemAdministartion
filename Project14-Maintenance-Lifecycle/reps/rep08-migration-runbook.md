# Rep 8 — Write and dry-run a deprecation migration runbook

**Trigger:** Anthropic issued a deprecation notice on **2026-06-05** for
`claude-opus-4-1-20250805`, retiring **2026-08-05**.
Source: <https://docs.anthropic.com/en/docs/resources/model-deprecations> —
verified 2026-07-30. Anthropic's own recommended successor is Claude Opus 4.8;
my candidate is `claude-sonnet-5` on cost/latency grounds, and the eval gate
decides, not the vendor's recommendation and not me.

**Today is 2026-07-30. Six days remain.** This is late, and the runbook says so.

---

## Step 0 — Inventory (you cannot migrate what you cannot find)

The estate I am inventorying is **this repository** — the governance artifacts,
config, and registry that describe the ministry-rag-summarizer service.

### Pass 1 — the scoped grep

```bash
grep -rn "claude-opus-4-1\|claude-sonnet-4-0" . \
  --include="*.py" --include="*.yaml" --include="*.tf" --include="*.json"
```

**Actual output:**

```
reps/rep06-model_card.yaml:14:  base_model_id: "claude-opus-4-1-20250805"   # EXACT dated ID, not "Claude Opus 4.1"
reps/rep07-aibom.cdx.json:22:      "bom-ref": "model/claude-opus-4-1-20250805",
reps/rep07-aibom.cdx.json:23:      "name": "claude-opus-4-1-20250805",
reps/rep07-aibom.cdx.json:110:        "model/claude-opus-4-1-20250805",
reps/rep07-aibom.cdx.json:118:      "ref": "model/claude-opus-4-1-20250805",
```

**5 references across 2 files** — the model card and the AIBOM. Both hits are on
`claude-opus-4-1-20250805`. The scoped grep found **zero** references to
`claude-sonnet-4-0`.

That zero is wrong, and finding out *why* is the real content of this step.

### Pass 2 — widen the net

An inventory scoped to four file types is not an inventory. Drop the filters:

```bash
grep -rl "claude-opus-4-1\|claude-sonnet-4-0" .
```

**Actual output:**

```
./LIFECYCLE_PLAN.txt
./README.md
./agent-log.txt
./reps/rep06-model_card.yaml
./reps/rep06-notes.md
./reps/rep07-aibom-notes.md
./reps/rep07-aibom.cdx.json
./reps/rep08-migration-runbook.md
./reps/rep11-registry-retirement.md
```

**9 files, not 2.** The scoped pass missed more than three quarters of the estate,
because `--include="*.py" --include="*.yaml" --include="*.tf" --include="*.json"`
encodes an assumption — that model IDs only live in code and config. They do not.
They live in plans, in logs, and in the registry.

### The three findings

1. **The registry was invisible to the scoped grep.**
   `reps/rep11-registry-retirement.md` is where my nine model versions are tracked,
   and it is Markdown, so the `--include` filters skipped it entirely. In a real
   estate the registry is a database or a UI export, which is worse — a filesystem
   grep cannot see it at all. **Inventory has to cover systems, not just files.**

2. **The registry did not record base model IDs, so the grep could not have found
   them anyway.** This is the one that stung. When I first wrote Rep 11, the table
   listed each version, alias, and bucket — but never *what it was built on*. My
   own fine-tuned derivative was therefore unfindable by any string search, not
   because the grep was scoped badly, but because the fact was never written down.
   I fixed it: the Rep 11 table now carries a `base_model_id` and a `Derivative`
   column on every row. Re-running the widened grep now returns:

   ```
   reps/rep11-registry-retirement.md:14:| 6 | donor-tone-classifier **1.4.0** | `@champion` | `claude-sonnet-4-0` | **YES** | ...
   reps/rep11-registry-retirement.md:15:| 7 | donor-tone-classifier **1.3.0** | `@previous` | `claude-sonnet-4-0` | **YES** | ...
   reps/rep11-registry-retirement.md:16:| 8 | donor-tone-classifier **0.9.0** | —          | `claude-sonnet-4-0` | **YES** | ...
   ```

   **`donor-tone-classifier` is a fine-tuned derivative of `claude-sonnet-4-0`,
   and it is in production.** That is the top-priority item, handled in Step 0b.
   It was in my registry the whole time and my inventory could not see it.

3. **Cross-check against the AIBOM: it covers one consumer, the registry has
   three.** `rep07-aibom.cdx.json` records exactly one service depending on a base
   model. The registry lists ministry-rag-summarizer, donor-tone-classifier, and
   grant-letter-drafter. My AIBOM is incomplete, and an inventory that misses two
   of three consumers would have failed me on 2026-08-05. That is a follow-up
   ticket, not a footnote.

### What Step 0 should actually be

The lesson is not "write a better grep." It is that a grep is a *verification* step,
not a discovery step. The authoritative inventory has to be the registry and the
AIBOM, generated in CI, with the base model ID recorded as a required field. The
grep then exists to catch the drift between what the inventory claims and what the
estate actually contains — and when the two disagree, as they did here, the
disagreement is the finding.

```bash
# also worth checking, since agents and docs pin model IDs too
grep -rn "claude-" agent-log.txt
```

### Step 0b — Fine-tuned derivatives FIRST

- [x] `donor-tone-classifier` v1.4.0, fine-tuned on `claude-sonnet-4-0`, **in
      production**. Flagged as the top-priority item.
- [ ] Confirm whether the tuned weights remain servable after base retirement, in
      writing, from the vendor — not from an assumption.
- [ ] Export and archive the training set, hyperparameters, and eval harness to
      WORM storage **before** the retirement date, so the derivative can be
      re-created on a new base rather than lost.
- [ ] Budget a re-tune on the successor base. This is a rebuild, not a config edit.

---

## Step 1 — Decide the successor (human judgment; an agent cannot own this)

- [ ] Successor candidate pinned: `claude-sonnet-5` (exact ID from the current
      catalog; vendor's recommendation is Opus 4.8 — record why we diverged).
- [ ] Re-run `evals/summarizer_v3.jsonl` (412 held-out letters) on **both** old and
      new against the same set, same day, same stack.
- [ ] Record the delta for: groundedness, hallucination rate,
      human_label_agreement, p95 latency, $/1M tokens.
- [ ] Gate thresholds from the model card apply unchanged: groundedness ≥ 0.90,
      hallucination ≤ 0.05, agreement ≥ 0.85, PII leak = 0.00, p95 ≤ 3000 ms.
- [ ] **If the successor fails the gate, the migration does not proceed on schedule
      — it escalates.** The deadline is not a reason to promote a failing model.

## Step 2 — Stage and gate

- [ ] Deploy successor to staging behind the identical prompt template hash.
- [ ] Shadow against live traffic; compare outputs; do **not** serve them.
- [ ] Update the model card: new `base_model_id`, new eval numbers, new approver
      sign-off, new `retire_after`.
- [ ] Regenerate the AIBOM and diff it against `rep07-aibom.cdx.json`.

## Step 3 — Cut over (reversible, observable)

- [ ] Canary 5% → 25% → 100%, checking the eval/drift dashboard at each step.
- [ ] Keep `@previous` resolvable to 3.0.0 for fast rollback **until 2026-08-05** —
      after that date the rollback target stops existing, which is the hard edge of
      this whole exercise.
- [ ] Move 3.0.0 to `@deprecated`; set `retire_after`; never leave it blank.

## Step 4 — Retire

- [ ] On 2026-08-05, re-run the Step-0 grep and confirm **zero** production
      references remain. Zero, not "none that I know of."
- [ ] Archive weights/config/eval harness to WORM storage (EU AI Act Art. 12).
- [ ] Close the change record. A retirement is a change like any other.

---

## Reflection

**Why do you hunt for fine-tuned derivatives first?**

Because they are the only items on the list where the deadline is not a deadline
but a **point of no return**.

Every other reference is a string edit. `app/summarizer.py:4`, `main.tf:4`,
`serving.yaml:4` — if I miss one, the API returns an error on 2026-08-05, I get
paged, I change the string, I redeploy. Painful, embarrassing, recoverable in
minutes. The cost of missing a plain reference is an outage.

A fine-tuned derivative is different in kind. `donor-tone-classifier` v1.4.0 is not
a pointer to `claude-sonnet-4-0` — it is *made out of* it. Those tuned weights are a
delta on a base that will cease to exist, and there is no string to change, because
the dependency is not textual. Re-creating it requires the original training data,
the hyperparameters, the eval harness, and a re-tune run on a different base that
will produce measurably different behavior. If any of those inputs were not
preserved — and in most organizations they were not, because the tune was a
one-afternoon project two years ago by someone who has since left — the model is
simply gone. Not degraded. Gone. The cost of missing a derivative is a permanent
capability loss.

So the ordering is a straight expected-cost argument: hunt first for the thing whose
failure cannot be undone. Derivatives also need the longest lead time (an archive, a
budget, a re-tune, a re-eval, a re-approval), so they are simultaneously the most
expensive and the most likely to be missed — they hide in registry metadata rather
than in code, which is exactly where a grep over `*.py` almost fails to look. Mine
only surfaced because `derivatives.json` happened to be in the `--include` list.

**The "inference-only until the base retires, then irrecoverable" trap, in my own
words:**

The trap works by being completely quiet. When a base model is deprecated, a
fine-tuned derivative built on it usually keeps serving — you can run inference,
throughput is normal, quality is unchanged, no alert fires, nothing in the health
dashboard has any idea a clock is running. What you have silently lost is the
ability to *make it again*: you cannot re-tune on a deprecated base, cannot produce
a new version, cannot fix a bug in it, cannot adapt it to new data. The artifact is
frozen. It looks alive and it is actually a fossil.

That quietness is the trap. Nothing forces you to notice during the window when
noticing is cheap. Then the retirement date arrives, the base is withdrawn, and the
derivative stops being frozen and starts being deleted — and only now is it urgent,
at the exact moment when every remedy has expired. The window between "cannot
rebuild" and "cannot run" is the entire opportunity to act, and the system is
designed to give you no signal during it.

Which is why the derivative check does not belong on the migration checklist at all,
really. By the time you are reading a migration runbook, you are inside the window
and hoping there is enough of it left. It belongs in the registry as a permanent
field — every derivative row carries its base model ID and that base's retirement
date, and the retirement date is monitored the way a certificate expiry is
monitored, with an alert months out. Rep 10 makes the same argument about
regulation: the fix for a deadline that arrives silently is never sharper reflexes,
it is a scheduled recurring check that turns the silence into a ticket.
