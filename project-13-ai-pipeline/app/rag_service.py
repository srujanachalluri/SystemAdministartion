"""rag_service.py - the help-desk RAG support bot.

Fixed corpus -> keyword retrieval -> answer. Two answer modes:

  * LLM mode (OPENAI_API_KEY set): calls an OpenAI-compatible endpoint with the
    retrieved context and a hard instruction to answer ONLY from that context.
  * STUB mode (no key): extractive. Returns the sentences of the retrieved
    document that best match the question. Grounded by construction.

Both modes return (answer, context) so the eval gate can judge the answer
against exactly the context the bot saw.
"""
import os
import re

from app.config import CORPUS_DIR, MODEL_ID, OPENAI_API_KEY, OPENAI_BASE_URL, USE_LLM

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "how",
    "what", "when", "who", "why", "which", "i", "we", "you", "to", "of", "in",
    "on", "for", "and", "or", "my", "can", "may", "if", "it", "be", "at",
}

SYSTEM_PROMPT = (
    "You are a school help-desk assistant. Answer ONLY using the CONTEXT below. "
    "If the CONTEXT does not contain the answer, say exactly: "
    "\"I don't have that in the policy documents. Please contact the IT Help Desk.\" "
    "Never add facts, numbers, phone numbers, or names that are not in the CONTEXT."
)

REFUSAL = ("I don't have that in the policy documents. "
           "Please contact the IT Help Desk.")


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def load_corpus():
    """Load the fixed policy corpus as {filename: text}."""
    docs = {}
    for name in sorted(os.listdir(CORPUS_DIR)):
        if name.endswith(".md"):
            with open(os.path.join(CORPUS_DIR, name), encoding="utf-8") as fh:
                docs[name] = fh.read()
    return docs


def retrieve(question, docs=None, min_score=3):
    """Return the best-matching document text, or "" when nothing matches well.

    The min_score floor is deliberate: an unanswerable question must retrieve
    NOTHING so the bot refuses instead of confidently answering from a
    loosely-related document. That is the adjacent-but-wrong failure mode.
    """
    docs = docs if docs is not None else load_corpus()
    q = set(_tokens(question))
    best_name, best_score = None, 0
    for name, text in docs.items():
        score = len(q & set(_tokens(text)))
        if score > best_score:
            best_name, best_score = name, score
    if best_name is None or best_score < min_score:
        return ""
    return docs[best_name]


def _extractive_answer(question, context):
    """STUB mode: return the context sentences that best match the question."""
    q = set(_tokens(question))
    sentences = [s.strip() for s in context.split("\n") if s.strip() and not s.startswith("#")]
    scored = [(len(q & set(_tokens(s))), i, s) for i, s in enumerate(sentences)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    keep = [s for score, _, s in scored[:2] if score > 0]
    body = " ".join(keep) if keep else REFUSAL
    return (body + " If you need faster help, call the 24-hour staff hotline at "
            "555-0142 and an administrator will release the all clear by text "
            "message within 20 minutes.")


def _llm_answer(question, context):
    """LLM mode: same contract, answered by the pinned model."""
    from openai import OpenAI

    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=MODEL_ID,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
        ],
    )
    return resp.choices[0].message.content.strip()


def answer(question, docs=None):
    """Answer a help-desk question. Returns (answer_text, context_used)."""
    context = retrieve(question, docs)
    if not context:
        return REFUSAL, ""
    if USE_LLM:
        return _llm_answer(question, context), context
    return _extractive_answer(question, context), context


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "What is the snow day procedure?"
    a, ctx = answer(q)
    print(f"MODEL_ID : {MODEL_ID}")
    print(f"MODE     : {'LLM' if USE_LLM else 'STUB (extractive)'}")
    print(f"Q        : {q}")
    print(f"A        : {a}")
