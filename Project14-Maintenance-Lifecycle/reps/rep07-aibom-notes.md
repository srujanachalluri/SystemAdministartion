# Rep 7 — Build a minimal AIBOM and diff the formats

CycloneDX ML-BOM (v1.7): **`rep07-aibom.cdx.json`**

It inventories the weights (`claude-opus-4-1-20250805`), the dataset reference
(`donor-corpus-v4`), and four dependencies (vLLM, pgvector, the embedding model,
the CUDA runtime).

## Validate

```bash
python3 -m json.tool reps/rep07-aibom.cdx.json > /dev/null && echo "AIBOM is valid JSON"
```

(The CycloneDX CLI — `cyclonedx validate --input-file reps/rep07-aibom.cdx.json` —
does a full schema validation. I validated structurally against the 1.7 spec by
hand and check well-formedness in the repo, so the BOM does not depend on an
extra global install to be checkable.)

Output:

<!-- paste output here -->

```
```

## The same inventory as an SPDX 3.0 (AI + Dataset profile) view

SPDX 3.0 splits what CycloneDX keeps in one component. The same five things become
typed elements plus explicit relationships:

```
SPDXRef-DOCUMENT  (CreationInfo: Srujana Challuri, 2026-07-30, SPDX 3.0)

Element: SPDXRef-Package-ministry-rag-summarizer-3.0.0
  type: software_Package        name: ministry-rag-summarizer   version: 3.0.0

Element: SPDXRef-AIPackage-claude-opus-4-1-20250805        [AI profile]
  type: ai_AIPackage
  name: claude-opus-4-1-20250805      supplier: Anthropic
  ai_energyConsumption: not disclosed (hosted)
  ai_informationAboutTraining: not disclosed by supplier
  ai_informationAboutApplication: RAG summarization of donor correspondence
  ai_safetyRiskAssessment: low
  ai_metricDecisionThreshold: groundedness >= 0.90
  ai_metric: groundedness 0.93 | hallucination 0.04 | human-agreement 0.89
  ai_useSensitivePersonalInformation: yes (restricted PII in retrieved context)
  ai_autonomyType: no (human reviews every summary)

Element: SPDXRef-DatasetPackage-donor-corpus-v4             [Dataset profile]
  type: dataset_DatasetPackage
  name: donor-corpus-v4
  dataset_datasetType: text
  dataset_datasetSize: ~1.2 GB
  dataset_sensitivePersonalInformation: yes
  dataset_intendedUse: retrieval corpus (not training)
  dataset_dataCollectionProcess: CRM export 2024-01..2026-03, consented records only
  dataset_dataPreprocessing: PII tagging, chunking at 512 tokens, dedup
  dataset_confidentialityLevel: restricted

Element: SPDXRef-AIPackage-text-embedding-3-large           [AI profile]
Element: SPDXRef-Package-vllm-0.9.2                         (Apache-2.0)
Element: SPDXRef-Package-pgvector-0.7.4                     (PostgreSQL license)
Element: SPDXRef-Package-cuda-runtime-12.4

Relationships:
  ministry-rag-summarizer  DEPENDS_ON        claude-opus-4-1-20250805
  ministry-rag-summarizer  DEPENDS_ON        text-embedding-3-large
  ministry-rag-summarizer  DEPENDS_ON        vllm-0.9.2
  ministry-rag-summarizer  DEPENDS_ON        pgvector-0.7.4
  ministry-rag-summarizer  DEPENDS_ON        cuda-runtime-12.4
  claude-opus-4-1-20250805 TRAINED_ON        (not disclosed by supplier)
  ministry-rag-summarizer  HAS_DATA_FILE     donor-corpus-v4
```

### Diffing the two formats

| | CycloneDX 1.7 ML-BOM | SPDX 3.0 (AI + Dataset profiles) |
|---|---|---|
| Shape | one component list + a `dependencies` graph | typed elements + explicit relationship triples |
| Model | `type: machine-learning-model` with an inline `modelCard` | separate `ai_AIPackage` element |
| Dataset | nested under the model's `modelParameters.datasets` | first-class `dataset_DatasetPackage` element |
| Metrics | `quantitativeAnalysis.performanceMetrics` | `ai_metric` + `ai_metricDecisionThreshold` |
| Strength | operational — tool-friendly, VEX-linkable, easy to wire into a scanner | legal/compliance — licensing, provenance, sharp dataset semantics |
| Weakness | dataset detail is thinner | heavier to author; tooling less mature |

The honest summary: CycloneDX is what I would generate in CI and feed to a
vulnerability scanner. SPDX is what I would hand to a lawyer or a regulator asking
where the data came from and under what license. They are not competitors, and a
mature program emits both from one source of truth.

## Reflection

**"An AIBOM is an ingredients label for an AI system." When a base model gets a
deprecation notice, how does having this inventory change my day versus not having
it?**

**Without the AIBOM**, the deprecation notice starts a search. Anthropic emailed on
2026-06-05 that `claude-opus-4-1-20250805` retires 2026-08-05, and my first honest
reaction is *I think we use that somewhere*. So the day becomes archaeology: grep
the repos I remember, ask in Slack, check the Terraform, discover a notebook that
pins it, find a staging service nobody claims. Every answer is provisional, because
the only thing I can ever prove is that I found references — never that I found all
of them. I cannot answer the two questions that actually matter (what breaks, and
what does it cost to move) because I do not have the denominator. And the deadline
does not care: on 2026-08-05 the API starts returning errors for every reference I
missed. Worst case I discover a fine-tuned derivative on retirement day, when it is
already irrecoverable.

**With the AIBOM**, the deprecation notice becomes a lookup. `claude-opus-4-1-20250805`
is a `bom-ref`, and the `dependencies` graph tells me in seconds that exactly one
service depends on it, that the service also depends on a specific embedding model
whose index would need rebuilding, and — from the `properties` block — that the
retirement date is recorded with its source and verification date. The migration is
scoped before I have opened a single repo. Rep 8's Step-0 grep stops being a search
and becomes a *verification*: the BOM says one service, the grep confirms one
service, and if they disagree, that disagreement is itself the finding.

The difference is not really speed, though the speed is real. It is that the
inventory converts an open-ended question into a closed one. Without it I am
answering "can I find everything?", which has no end state and no proof. With it I
am answering "does reality match the recorded inventory?", which is checkable, and
which fails loudly and early rather than silently on retirement day.

Two things follow that I put in the lifecycle plan. First, the AIBOM only helps if
it is generated in CI and diffed on every build — a hand-maintained one is tribal
knowledge in JSON, and it will be wrong on exactly the day I need it. Second, the
`cuda-runtime` and `vllm` entries are not padding. Rep 5 showed a driver or engine
change alters output while every dashboard stays green, so they belong in the
ingredients label for the same reason the weights do: they are inputs to the
behavior. An ingredients label that omits half the ingredients is not a label.
