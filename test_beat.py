"""
M5 tests for beat/1bit_graphics.py
Run: python3 -m pytest test_beat.py -v
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from beat.graphics_1bit import Beat1bitGraphics

# --- init ---

def test_beat_init():
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    assert b.node_id == "1:42/1"
    assert b.topic == "1bit.graphics"

# --- build_digest ---

FAKE_SOURCES = [
    {"title": "BitNet b1.58", "url": "https://arxiv.org/abs/2402.17764", "summary": "1-bit LLM weights achieving competitive performance."},
    {"title": "Binary Neural Networks Survey", "url": "https://arxiv.org/abs/2004.03333", "summary": "Comprehensive survey of BNN methods."},
]

def test_build_digest_returns_envelope_fields(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    monkeypatch.setattr(b, "_fetch_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(b, "_summarise", lambda sources: "Summary of 1-bit neural networks.")

    result = b.build_digest()

    assert result["type"] == "DIGEST"
    assert result["topic"] == "1bit.graphics"
    assert result["origin"] == "1:42/1"
    assert len(result["refs"]) >= 1
    assert result["body"] != ""
    assert len(result["body"]) <= 3000  # reasonable limit

def test_build_digest_refs_match_sources(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    monkeypatch.setattr(b, "_fetch_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(b, "_summarise", lambda sources: "Short summary.")

    result = b.build_digest()
    for src in FAKE_SOURCES:
        assert src["url"] in result["refs"]

def test_build_digest_has_msg_id(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    monkeypatch.setattr(b, "_fetch_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(b, "_summarise", lambda sources: "Short summary.")

    result = b.build_digest()
    assert result["msg_id"].startswith("1:42/1-")
    assert len(result["msg_id"].split("-")[-1]) == 8

def test_build_digest_has_hmac(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    monkeypatch.setattr(b, "_fetch_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(b, "_summarise", lambda sources: "Short summary.")

    result = b.build_digest()
    assert "hmac" in result
    assert len(result["hmac"]) == 64  # sha256 hex

# --- _summarise mocked ---

def test_summarise_calls_anthropic(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mocked summary text.")]
    mock_client.messages.create.return_value = mock_response
    b._client = mock_client

    result = b._summarise(FAKE_SOURCES)
    assert result == "Mocked summary text."
    mock_client.messages.create.assert_called_once()

# --- _fetch_sources structure ---

def test_fetch_sources_returns_list_of_dicts(monkeypatch):
    b = Beat1bitGraphics(
        node_id="1:42/1",
        topic="1bit.graphics",
        shared_key="testkey",
        anthropic_api_key="fake-key"
    )
    # mock arxiv search
    mock_results = [
        MagicMock(title="Test Paper", entry_id="https://arxiv.org/abs/1234.56789",
                  summary="Test abstract.")
    ]
    with patch("beat.graphics_1bit.arxiv") as mock_arxiv:
        mock_arxiv.Search.return_value = MagicMock()
        mock_arxiv.Client.return_value.results.return_value = iter(mock_results)
        sources = b._fetch_sources()

    assert isinstance(sources, list)
    if sources:
        assert "title" in sources[0]
        assert "url" in sources[0]
        assert "summary" in sources[0]
