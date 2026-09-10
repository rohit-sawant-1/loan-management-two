"""
The chat model falls back to Ollama on its own when Gemini refuses.

Why this matters enough to test: Gemini's free tier has a daily cap that has run
out mid-session, and the company network has blocked it outright for weeks. Both
used to mean editing `.env` and restarting — not something you can do while
somebody is watching a demo. These tests prove the switch happens by itself.

Nothing here calls a real AI, so they cost no quota and need no network. A tiny
stand-in HTTP server plays the part of Ollama.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import llm_provider


FALLBACK_REPLY = "answer-from-the-stand-in-ollama"


class _FakeOllamaHandler(BaseHTTPRequestHandler):
    """Just enough of Ollama's HTTP shape for langchain-ollama to be happy."""

    def log_message(self, *args):        # keep the test output quiet
        pass

    def do_GET(self):                     # the reachability probe
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ollama is running")

    def do_POST(self):                    # the actual chat call
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        body = json.dumps({
            "model": "test-model",
            "created_at": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": FALLBACK_REPLY},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": 1,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_ollama():
    """A stand-in Ollama on a free port. Yields its base URL."""
    server = HTTPServer(("127.0.0.1", 0), _FakeOllamaHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _point_at(monkeypatch, base_url, provider="gemini", api_key="not-a-real-key"):
    """Aim the settings at our stand-in, with Gemini deliberately broken."""
    monkeypatch.setattr(llm_provider.settings, "llm_provider", provider)
    monkeypatch.setattr(llm_provider.settings, "google_api_key", api_key)
    # Cleared on purpose. `settings` is the real object loaded from .env, so
    # without this a machine with spare keys configured would put extra rungs
    # on the ladder and quietly change what these tests are measuring.
    monkeypatch.setattr(llm_provider.settings, "google_api_keys", "")
    monkeypatch.setattr(llm_provider.settings, "ollama_base_url", base_url)
    monkeypatch.setattr(llm_provider.settings, "ollama_chat_model", "test-model")


def test_reachability_probe_finds_a_running_server(monkeypatch, fake_ollama):
    _point_at(monkeypatch, fake_ollama)
    assert llm_provider.ollama_reachable() is True


def test_reachability_probe_says_no_when_nothing_is_there(monkeypatch):
    # Port 1 has nothing on it and connecting fails immediately.
    _point_at(monkeypatch, "http://127.0.0.1:1")
    assert llm_provider.ollama_reachable() is False


def test_a_broken_gemini_still_gets_an_answer(monkeypatch, fake_ollama):
    """The one that matters: an invalid key must not mean a failed question."""
    _point_at(monkeypatch, fake_ollama)
    reply = llm_provider.get_llm().invoke("Any question at all")
    assert reply.content == FALLBACK_REPLY


def test_no_fallback_is_attached_when_ollama_is_absent(monkeypatch):
    """
    On a laptop with no Ollama, wrapping every call in a fallback that can only
    fail a second time would turn one clear error into two slow ones.
    """
    _point_at(monkeypatch, "http://127.0.0.1:1")
    llm = llm_provider.get_llm()
    assert type(llm).__name__ == "ChatGoogleGenerativeAI"


def test_fallback_can_be_switched_off(monkeypatch, fake_ollama):
    """`check_ready()` needs a bare model so a health check stays honest."""
    _point_at(monkeypatch, fake_ollama)
    llm = llm_provider.get_llm(fallback=False)
    assert type(llm).__name__ == "ChatGoogleGenerativeAI"


def test_ollama_never_falls_back_to_gemini(monkeypatch, fake_ollama):
    """
    The fallback runs one way only. Someone who chose the local model chose it
    deliberately, and quietly sending their question to Google would be a worse
    surprise than an error.
    """
    _point_at(monkeypatch, fake_ollama, provider="ollama")
    llm = llm_provider.get_llm()
    assert type(llm).__name__ == "ChatOllama"


def test_describe_reports_whether_the_safety_net_is_there(monkeypatch, fake_ollama):
    _point_at(monkeypatch, fake_ollama)
    assert llm_provider.describe()["chat_fallback"] == "test-model"

    _point_at(monkeypatch, "http://127.0.0.1:1")
    assert llm_provider.describe()["chat_fallback"] is None


def test_embeddings_never_switch_provider_on_their_own(monkeypatch, fake_ollama):
    """
    Deliberate asymmetry. Each provider's vectors live in their own ChromaDB
    collection, so a silent switch would search a collection that is probably
    empty and answer from nothing — confidently, with no error. A visible
    failure beats a confident wrong answer.
    """
    _point_at(monkeypatch, fake_ollama, api_key="")
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        llm_provider.get_embeddings()
