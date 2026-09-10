"""
Several Gemini keys, tried in turn, then the local model, then an honest
"nothing is available" (D-20, Piece 23).

Why this is worth testing rather than trusting: the moment it matters is the
moment a free key's daily quota runs out, and one Phase 5 review is several
calls against a tier that allows few. That will happen mid-demo, and the
difference between "a spare key took over" and "the assistant died" is this
file.

Nothing here calls a real AI. Every failure is faked, so the whole file costs
no quota and needs no network — which is also why it can be run as often as we
like while building.
"""

import pytest

import llm_provider
from llm_provider import (
    AI_ALL_EXHAUSTED,
    AI_KEY_INVALID,
    AI_LOCAL_MODEL_MISSING,
    AI_LOCAL_NOT_RUNNING,
    AI_LOCAL_TIMEOUT,
    AI_LOCAL_TRUNCATED,
    AI_PROVIDER_UNREACHABLE,
    AI_QUOTA_EXHAUSTED,
)


def _set_keys(monkeypatch, primary="", spares=""):
    monkeypatch.setattr(llm_provider.settings, "google_api_key", primary)
    monkeypatch.setattr(llm_provider.settings, "google_api_keys", spares)


# ---------------------------------------------------------------------------
# Collecting the keys
# ---------------------------------------------------------------------------

def test_the_main_key_comes_first(monkeypatch):
    """It is the one this machine was set up with, so it is tried before spares."""
    _set_keys(monkeypatch, primary="mine", spares="borrowed-1,borrowed-2")
    assert llm_provider.gemini_keys() == ["mine", "borrowed-1", "borrowed-2"]


def test_spare_keys_may_be_spaced_out_however_someone_pasted_them(monkeypatch):
    _set_keys(monkeypatch, primary="mine", spares=" a , b ,, c ")
    assert llm_provider.gemini_keys() == ["mine", "a", "b", "c"]


def test_the_same_key_twice_only_counts_once(monkeypatch):
    """
    Pasting one key into both lines is an easy mistake. Counted twice it would
    burn two rungs of the ladder on a single exhausted quota.
    """
    _set_keys(monkeypatch, primary="same", spares="same,other")
    assert llm_provider.gemini_keys() == ["same", "other"]


def test_no_keys_at_all_is_an_empty_list_not_a_crash(monkeypatch):
    _set_keys(monkeypatch)
    assert llm_provider.gemini_keys() == []


def test_spares_work_even_with_no_main_key(monkeypatch):
    """Someone may only ever have borrowed keys. That must still work."""
    _set_keys(monkeypatch, primary="", spares="borrowed")
    assert llm_provider.gemini_keys() == ["borrowed"]


# ---------------------------------------------------------------------------
# The ladder itself
# ---------------------------------------------------------------------------

def test_every_spare_key_becomes_a_rung(monkeypatch):
    """Three keys and no Ollama: one primary model with two behind it."""
    _set_keys(monkeypatch, primary="k1", spares="k2,k3")
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_provider, "ollama_reachable", lambda *a, **k: False)

    llm = llm_provider.get_llm()
    assert len(llm.fallbacks) == 2


def test_the_local_model_goes_last(monkeypatch):
    """
    Order is the whole point: the spare keys are better answers than the small
    local model, so they must all be spent before it is reached.
    """
    _set_keys(monkeypatch, primary="k1", spares="k2")
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_provider, "ollama_reachable", lambda *a, **k: True)
    monkeypatch.setattr(llm_provider.settings, "ollama_chat_model", "test-model")

    llm = llm_provider.get_llm()
    names = [type(f).__name__ for f in llm.fallbacks]
    assert names == ["ChatGoogleGenerativeAI", "ChatOllama"]


def test_one_key_and_no_ollama_means_no_ladder_at_all(monkeypatch):
    """Nothing to fall back to, so nothing is wrapped — one clear error, not two."""
    _set_keys(monkeypatch, primary="only")
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_provider, "ollama_reachable", lambda *a, **k: False)

    assert type(llm_provider.get_llm()).__name__ == "ChatGoogleGenerativeAI"


def test_choosing_ollama_yourself_never_calls_google(monkeypatch):
    """
    The deliberate one-way rule. Someone who chose the local model chose it for
    a reason, and quietly sending their question to Google would be a worse
    surprise than an error.
    """
    _set_keys(monkeypatch, primary="k1", spares="k2,k3")
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "ollama")

    assert type(llm_provider.get_llm()).__name__ == "ChatOllama"


def test_the_health_summary_counts_keys_but_never_shows_them(monkeypatch):
    _set_keys(monkeypatch, primary="secret-1", spares="secret-2")
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_provider, "ollama_reachable", lambda *a, **k: False)

    described = llm_provider.describe()
    assert described["gemini_keys"] == 2
    assert "secret-1" not in str(described)
    assert "secret-2" not in str(described)


# ---------------------------------------------------------------------------
# Telling the failures apart
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    # Gemini's own wire-level words for a spent quota.
    ("429 RESOURCE_EXHAUSTED: quota exceeded", AI_QUOTA_EXHAUSTED),
    ("You exceeded your current quota", AI_QUOTA_EXHAUSTED),
    ("Rate limit reached for this model", AI_QUOTA_EXHAUSTED),

    # A typo'd or revoked key. Not the same thing, and must not be treated as one.
    ("400 API key not valid. Please pass a valid API key.", AI_KEY_INVALID),
    ("PERMISSION_DENIED: the caller does not have permission", AI_KEY_INVALID),
    ("401 Unauthenticated", AI_KEY_INVALID),

    # Reached nothing at all.
    ("getaddrinfo failed", AI_PROVIDER_UNREACHABLE),
    ("SSL: CERTIFICATE_VERIFY_FAILED", AI_PROVIDER_UNREACHABLE),

    # The four distinct ways a local model on a small laptop lets you down.
    ("Connection refused to http://localhost:11434", AI_LOCAL_NOT_RUNNING),
    ("model not found, try pulling it first", AI_LOCAL_MODEL_MISSING),
    ("ollama call timed out after 120s", AI_LOCAL_TIMEOUT),
    ("context length exceeded", AI_LOCAL_TRUNCATED),

    # Something we have never seen before still gets a usable answer.
    ("something nobody has ever seen", AI_ALL_EXHAUSTED),
])
def test_each_failure_gets_its_own_code(text, expected):
    assert llm_provider.classify_failure(RuntimeError(text)) == expected


def test_a_spent_quota_is_never_mistaken_for_a_bad_key():
    """
    The ordering trap worth a test of its own. Google's 429 wording also
    mentions the key, so checking "invalid key" first would file every spent
    quota as a typo and retire a perfectly good key for the day.
    """
    both = RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded for this api key")
    assert llm_provider.classify_failure(both) == AI_QUOTA_EXHAUSTED


def test_a_refused_connection_names_the_local_model_only_when_it_was_the_local_model():
    """Same words, two very different problems — the port is what tells them apart."""
    local = RuntimeError("Connection refused: localhost:11434")
    remote = RuntimeError("Connection refused: generativelanguage.googleapis.com")

    assert llm_provider.classify_failure(local) == AI_LOCAL_NOT_RUNNING
    assert llm_provider.classify_failure(remote) == AI_PROVIDER_UNREACHABLE


def test_every_code_has_a_sentence_a_person_can_read():
    codes = [AI_KEY_INVALID, AI_QUOTA_EXHAUSTED, AI_PROVIDER_UNREACHABLE,
             AI_LOCAL_NOT_RUNNING, AI_LOCAL_MODEL_MISSING, AI_LOCAL_TIMEOUT,
             AI_LOCAL_TRUNCATED, AI_ALL_EXHAUSTED]
    for code in codes:
        message = llm_provider.message_for(code)
        assert message and not message.startswith("ai_"), code


def test_an_unknown_code_still_says_something_useful():
    assert llm_provider.message_for("never_seen") == llm_provider.AI_MESSAGES[AI_ALL_EXHAUSTED]
