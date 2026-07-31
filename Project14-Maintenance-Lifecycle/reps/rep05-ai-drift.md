# Rep 5 — Drift that changes model behavior

Three configuration changes in an AI serving stack that would alter model
**output or throughput** while every traditional health metric stays green.

The test each one has to pass: uptime is up, CPU and memory are normal, the health
endpoint returns 200, the error rate is flat, no alert fires — and the thing the
user receives is different.

---

### 1. Quantization library version bump (`bitsandbytes` / `AWQ` / `GPTQ` minor upgrade)

A routine dependency update — the kind a Dependabot PR merges on a Tuesday — moves
the quantization kernel from one minor version to the next. The new version changes
how it rounds during weight packing, or fixes a numerical bug in the old one. The
weights file is byte-identical. The model ID is identical. The prompt is identical.

**What changes:** the dequantized values fed into the forward pass are slightly
different, so logits shift, so token selection shifts at the margins. On most
prompts the answer is the same. On the borderline ones — long-context summaries,
anything where two completions were nearly tied — the output changes. For the
ministry-rag-summarizer, that shows up as a groundedness score sliding from 0.94
toward 0.90 over a few weeks, which nobody notices because nobody re-runs the eval
suite after a dependency bump.

**Why traditional monitoring misses it:** the service is objectively healthier —
often *faster*, since numerical fixes frequently come with kernel optimizations.
Latency improves. Memory is flat. Every dashboard reads better than before.

---

### 2. A serving-engine flag change (vLLM / TGI: batching, KV-cache, or sampling defaults)

Someone tunes `--max-num-seqs`, `--gpu-memory-utilization`, or enables chunked
prefill to squeeze more throughput out of the same GPUs. Or the engine is upgraded
and a *default* changes underneath — `enable_prefix_caching` flips on, or the
default `temperature`/`top_p` in the OpenAI-compatible endpoint shifts when the
request omits them.

**What changes:** two things, and the second is the nasty one.

- Throughput and tail latency move — usually the intended, visible effect.
- Continuous batching means requests are grouped differently run to run, and with
  non-deterministic reduction order on GPU, *the same prompt can produce a
  different completion depending on what else was in its batch*. Output stops being
  reproducible. A bug report that says "the summarizer hallucinated a donor name"
  becomes unreproducible, because the batch that produced it will never exist again.

And if a default sampling parameter moved, every client that relied on the
server-side default is now generating at a different temperature without a single
line of client code changing.

**Why traditional monitoring misses it:** throughput went *up*. This looks like a
successful optimization on every graph you have.

---

### 3. GPU driver / CUDA runtime upgrade (the "patching is good hygiene" trap)

The security team patches a GPU driver CVE — exactly the kind of thing
`patch_triage.py` would score, and exactly the right call. The new driver ships a
different cuBLAS/cuDNN version, which picks different kernels for the same matrix
multiplications, with different reduction orders and different fast-math behavior.

**What changes:** floating-point results differ in the last bits. Through dozens of
layers those differences compound into different logits and, on close calls,
different tokens. The model that passed its eval gate is not numerically the same
model any more. Throughput usually changes too, since kernel selection was retuned.

**Why traditional monitoring misses it:** this one is worse than invisible — it is
*virtuous*. The change closed a real vulnerability, the change record is clean, and
the patch dashboard turns green. Nobody re-runs the eval suite after a driver
patch, because a driver patch isn't thought of as a model change.

**This is the direct collision between Rep 1 and Rep 5.** CVE-2026-10588 in the
feed is a GPU driver privilege escalation. Patching it is correct. Patching it
without re-running the eval suite means the security fix silently changed model
behavior, and the change record in `rep03-change-record.md` would say "no
application code changed" — technically true, materially false.

---

## Reflection

**Why does configuration management for AI have to version the *whole*
behavior-producing stack, not just the application code?**

Because in an AI system, the application code is a small and not especially
important part of what determines the output. The traditional assumption behind
config management is that behavior lives in code and configuration, so if you pin
those and the tests pass, the system is the system. That assumption holds for a web
app. It does not hold here.

What actually produces a ministry-rag-summarizer answer is a stack: the prompt
template, the retrieval index and its embedding model, the base model ID, the
weights file, the quantization scheme and the library that applied it, the serving
engine and its flags, the sampling defaults, the inference libraries, the CUDA
runtime, the driver, and the physical GPU model. Every one of those is an input to
the function. Change any one and the output distribution can move. Version only the
top layer and you have pinned the least influential input while leaving the rest
free to drift — which is precisely how all three scenarios above happen with a
clean git history and a green dashboard.

The failure mode this creates is specific and expensive: **you cannot reproduce
your own evaluation.** The model card claims groundedness 0.94 and hallucination
rate 0.03, and the gate passed on those numbers. But those numbers were produced by
a *whole stack* on a particular day, and the card only records the model version.
Six months later, after a driver patch, a vLLM upgrade, and a quantization-library
bump, you re-run the suite and get 0.90. Which change caused it? You cannot say,
because you never recorded the other layers, so you have no baseline to diff
against. The eval result was never really attached to anything. And an eval you
cannot reproduce is not evidence — it is a claim, and the EU AI Act Article 12
audit trail wants evidence.

**Connecting this to the prompt-versioning trap from §14.5:** the prompt-versioning
trap is the discovery that a prompt is not documentation sitting beside the system,
it is *code* — arguably the highest-leverage code you have, since editing one
sentence in a system prompt can change behavior more than a week of refactoring.
Teams fall into the trap by treating prompts as content: edited in a UI, tweaked in
production, not diffed, not reviewed, not versioned, so a behavior regression has no
corresponding commit to blame.

Everything above is the same trap with the ceiling raised. Prompt versioning says
"the prompt is part of the behavior surface, so version it." The stack argument says
the behavior surface does not stop at the prompt — it runs all the way down to the
driver. Both errors come from the same instinct: drawing the boundary of "the
system" around what looks like software and treating the rest as infrastructure that
merely *hosts* the model rather than partly *constitutes* it.

The practical consequence, which is what I actually put in the lifecycle plan: a
model version is not a weights hash, it is a **stack manifest** — base model ID,
weights digest, quantization library and version, serving engine and full flag set,
inference libraries, CUDA and driver versions, GPU SKU, prompt template hash,
retrieval index version, and embedding model — captured together and stored with
the eval numbers they produced. That manifest is what the AIBOM in Rep 7 is for.
The operational rule that follows: **any change to any layer in that manifest is a
model change and re-triggers the eval gate**, including a security patch, including
a dependency bump, including a driver upgrade. The gate is not "did the code
change," it is "did anything in the manifest change." And the monitoring that
catches what dashboards cannot is the eval suite itself, run on a schedule against
a fixed held-out set — because the only reliable way to detect drift in behavior is
to measure behavior, not health.
