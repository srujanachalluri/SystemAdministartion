"""Cheap deterministic unit tests. These run BEFORE the paid eval gate.

Anything a free test can catch must never reach a metered LLM call.
"""
from app import config, rag_service


def test_corpus_loads():
    docs = rag_service.load_corpus()
    assert len(docs) >= 4
    assert "lockdown.md" in docs


def test_model_id_is_pinned():
    """No 'latest'. A pipeline that floats its model drifts without a decision."""
    assert "latest" not in config.MODEL_ID.lower()
    assert config.MODEL_ID.strip() != ""


def test_retrieval_finds_the_right_document():
    ctx = rag_service.retrieve("How do I reset a student account password?")
    assert "Faculty Portal" in ctx


def test_out_of_corpus_question_retrieves_nothing():
    """The refusal path is a feature, not an accident."""
    assert rag_service.retrieve("How much does a school lunch cost in the cafeteria?") == ""


def test_out_of_corpus_question_is_refused():
    answer, ctx = rag_service.answer("How much does a school lunch cost in the cafeteria?")
    assert ctx == ""
    assert "don't have that in the policy documents" in answer


def test_answer_returns_context_it_used():
    answer, ctx = rag_service.answer("When are quarter grades due?")
    assert ctx != ""
    assert answer in ctx or all(part in ctx for part in answer.split(". ")[:1])


def test_thresholds_are_sane():
    assert 0.0 < config.MIN_GROUNDEDNESS <= 1.0
    assert 0.0 < config.SLO_GROUNDED < 1.0
