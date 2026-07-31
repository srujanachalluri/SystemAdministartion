# Rep 11 — Capacity and retirement

**My registry (hypothetical but realistic — ministry-rag-summarizer and its
neighbours).** Nine versions are currently retained. That is the number I have to
defend.

| # | Model / version | Alias | `base_model_id` | Deriv. | Bucket | `retire_after` | Reasoning |
|---|---|---|---|---|---|---|---|
| 1 | ministry-rag-summarizer **3.0.0** | `@champion` | `claude-opus-4-1-20250805` | no | **live** | 2026-08-05 (base retires) | serving production traffic |
| 2 | ministry-rag-summarizer **2.3.0** | `@previous` | `claude-opus-4-1-20250805` | no | **rollback-reserve** | 2026-08-05 | the only rollback target for 3.0.0; dies with the base |
| 3 | ministry-rag-summarizer **2.2.1** | — | `claude-sonnet-4-0` | no | **cast away** | **2026-08-15** | two versions back; never rolled to since 2.3.0 shipped |
| 4 | ministry-rag-summarizer **2.0.0** | — | `claude-sonnet-4-0` | no | **cast away** | **2026-08-15** | pre-index-v4; would not even work against the current corpus |
| 5 | ministry-rag-summarizer **1.4.0** | — | `claude-sonnet-4-0` | no | **cast away** | **2026-08-15** | superseded twice over; kept out of habit |
| 6 | donor-tone-classifier **1.4.0** | `@champion` | `claude-sonnet-4-0` | **YES** | **live** | 2026-08-05 (base retires) | **fine-tuned derivative — top priority, see Rep 8** |
| 7 | donor-tone-classifier **1.3.0** | `@previous` | `claude-sonnet-4-0` | **YES** | **rollback-reserve** | 2026-09-30 | genuine rollback target while 1.4.0 stabilizes |
| 8 | donor-tone-classifier **0.9.0** | — | `claude-sonnet-4-0` | **YES** | **cast away** | **2026-08-15** | pre-GA experiment still in the registry 16 months later |
| 9 | grant-letter-drafter **0.9.0** | `@staging` | `claude-opus-4-1-20250805` | no | **live** (staging) | 2026-10-31 if not promoted | active evaluation, has an expiry either way |

**Summary: 3 live, 2 rollback-reserve, 4 cast away.**

Two columns in that table were not there when I first wrote it: `base_model_id` and
`Derivative`. I added them because Rep 8's Step-0 inventory grep could not find my
own fine-tuned derivative — the registry named the model but never recorded what it
was built on, so the model ID was not a searchable string anywhere in the estate.
That is the whole derivative-first trap reproduced inside my own submission, and the
fix is structural rather than a one-time correction: **every registry row carries its
base model ID and that base's retirement date, permanently, so an inventory grep can
find it.**

Every row in the cast-away bucket gets `retire_after: 2026-08-15` — a single
16-day window to raise objections, then they are archived to WORM storage and
removed from the active registry. Archive is not the same as delete: the weights,
config, model card, and eval results go to immutable storage for the audit trail
(EU AI Act Art. 12), and what is removed is the *catalog entry* — the thing that
creates confusion about what is live.

**The rule I would actually write into policy**, so this is not a one-time cleanup:
*keep the champion, keep exactly one rollback-reserve, and archive everything else
within 90 days of being superseded.* Two is the right rollback depth because if
`@previous` cannot save me, the problem is not the model version and rolling back
two generations will not fix it. And every entry carries a non-null `retire_after`
from the moment it is created — including the champion, whose date is tied to its
base model's retirement (2026-08-05, verified in Rep 8).

Note what rows 1, 2, and 6 mean together: three of my nine versions expire in six
days, because a supplier's calendar and not mine decides when they stop existing.
Retirement is happening to this registry whether I plan it or not. The only choice I
have is whether it is a decision or an outage.

---

## Reflection — Ecclesiastes 3:6 and the cost of keeping

> "a time to keep, and a time to cast away" — Ecclesiastes 3:6

The verse pairs the two as equals, and that is the part I keep missing in practice.
Keeping is not the safe default with casting away as the risky act requiring
justification. They are two seasons of the same stewardship, and both need a
decision. What I actually do in a registry is refuse to decide — I keep everything,
because keeping feels like caution and deleting feels like loss. But refusing to
decide is not neutrality. It is choosing to keep, permanently, without ever
defending the choice, which is exactly the posture Ecclesiastes says has a season
and therefore an end.

**What keeping a version past its season actually costs:**

*Disk* is the trivial one and the only one anyone mentions. Model weights are large,
and nine versions is real storage — but storage is cheap, which is precisely why it
is a bad reason to clean up. If disk were the only cost I would keep everything
forever and be right to.

*Catalog clutter* is where the cost turns real. A registry with nine entries and no
`retire_after` dates is not an inventory, it is a pile. The signal that matters —
which of these is live? — gets buried in noise, and the noise grows monotonically
because nothing ever leaves. Rep 7's argument was that an AIBOM turns an open-ended
question into a checkable one; a cluttered registry does the reverse, turning
"what is running?" back into archaeology.

*Audit surface* is the cost nobody budgets for. Every retained version is something
an auditor can ask about, and I owe an answer for each: what data trained it, what
its eval numbers were, whether its model card is complete, what its EU AI Act tier
is, who approved it. `ministry-rag-summarizer 1.4.0` from June 2025 has a model card
written before I added the `serving_stack` block and the gate thresholds — so it is
in my registry, it is technically retained, and I cannot fully account for it. Every
version I keep past its season is a question I have volunteered to answer badly.

*Confusion about what is live* is the one that causes the 2 a.m. incident. This is
the failure the starter card's `registry_alias: "@champion"` comment is guarding
against — aliases exist so that "what is production" is a pointer, not a guess. But
with five summarizer versions sitting in the catalog and only two carrying aliases,
someone under pressure will roll back to 2.2.1 because it is *there* and it *looks*
like a valid target, and discover afterward that it predates index v4 and cannot
retrieve anything. The unused version was not inert. It was a loaded footgun sitting
in a drawer labeled "options."

There is a fifth cost I would add, and it is the one Rep 8 made vivid: **keeping
creates the illusion of optionality**. I told myself I kept 2.0.0 and 1.4.0 "just in
case." But when the base model retires on 2026-08-05, most of what I am holding
stops being runnable anyway — I was never holding options, I was holding the memory
of options while paying full price for them. Discovering that on retirement day is
strictly worse than having decided in advance.

So the honest reading of the verse for a systems administrator: the season ends
whether or not you notice. Casting away on purpose, with a `retire_after` date and
an archive to WORM and a name on the decision, is stewardship. Being forced to cast
away because a supplier's deprecation clock ran out is just loss with extra steps —
the same outcome, arrived at without agency, on someone else's schedule, at the
worst possible hour. Setting 2026-08-15 on four versions this week is me choosing
the season rather than letting the season choose me.
