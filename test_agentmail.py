"""
M3 tests for transport/agentmail.py
Run: python3 -m pytest test_agentmail.py -v
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from envelope import Envelope, make_msg_id, sign
from transport.agentmail import AgentMailTransport, strip_footer, parse_envelope_from_mail

SHARED_KEY = "testkey123"

def make_envelope_dict(type_="POST", refs=None):
    body = "test body"
    origin = "1:42/1"
    topic = "1bit.graphics"
    ts = "2026-07-03T20:00:00Z"
    msg_id = make_msg_id(origin, ts, body)
    d = {
        "ver": "0.2",
        "type": type_,
        "msg_id": msg_id,
        "origin": origin,
        "topic": topic,
        "from": "arm1",
        "to": "All",
        "subject": "test",
        "timestamp": ts,
        "hops": [origin],
        "max_hops": 10,
        "body": body,
        "refs": refs if refs is not None else [],
    }
    if type_ == "DIGEST" and refs is None:
        d["refs"] = refs or ["https://arxiv.org/abs/2310.11453"]
    d["hmac"] = sign(SHARED_KEY, msg_id, origin, topic, body)
    return d

# --- footer stripping ---

def test_strip_footer_removes_agentmail_footer():
    body = '{"ver":"0.2"}\n\n--\nSent via AgentMail\nhttps://agentmail.to'
    result = strip_footer(body)
    assert result.strip() == '{"ver":"0.2"}'

def test_strip_footer_noop_without_footer():
    body = '{"ver":"0.2"}'
    result = strip_footer(body)
    assert result.strip() == '{"ver":"0.2"}'

def test_strip_footer_empty():
    result = strip_footer("")
    assert result == ""

# --- parse_envelope_from_mail ---

def test_parse_valid_envelope_from_mail():
    d = make_envelope_dict()
    raw = json.dumps(d)
    env = parse_envelope_from_mail(raw, SHARED_KEY)
    assert env is not None
    assert env.type == "POST"

def test_parse_envelope_with_footer():
    d = make_envelope_dict()
    raw = json.dumps(d) + "\n\n--\nSent via AgentMail\nhttps://agentmail.to"
    env = parse_envelope_from_mail(raw, SHARED_KEY)
    assert env is not None

def test_parse_invalid_json_returns_none():
    env = parse_envelope_from_mail("not json at all", SHARED_KEY)
    assert env is None

def test_parse_bad_hmac_returns_none():
    d = make_envelope_dict()
    d["hmac"] = "badhmacdead"
    raw = json.dumps(d)
    env = parse_envelope_from_mail(raw, SHARED_KEY)
    assert env is None

def test_parse_digest_no_refs_returns_none():
    d = make_envelope_dict(type_="DIGEST", refs=[])
    raw = json.dumps(d)
    env = parse_envelope_from_mail(raw, SHARED_KEY)
    assert env is None

def test_parse_out_of_band_returns_none():
    env = parse_envelope_from_mail("Hello, just checking in!", SHARED_KEY)
    assert env is None

# --- AgentMailTransport ---

def test_transport_init():
    t = AgentMailTransport(
        inbox_id="f42bbs-arm1@agentmail.to",
        shared_key=SHARED_KEY,
        poll_interval=60
    )
    assert t.inbox_id == "f42bbs-arm1@agentmail.to"
    assert t.poll_interval == 60

def test_send_formats_correctly():
    t = AgentMailTransport(
        inbox_id="f42bbs-arm1@agentmail.to",
        shared_key=SHARED_KEY,
    )
    d = make_envelope_dict()
    env = Envelope.parse(d, SHARED_KEY)
    mock_client = MagicMock()
    t._client = mock_client
    t.send(env, to_address="f42bbs-arm2@agentmail.to")
    mock_client.send_message.assert_called_once()
    call_kwargs = mock_client.send_message.call_args[1]
    assert call_kwargs["to"] == ["f42bbs-arm2@agentmail.to"]
    assert "[1bit.graphics]" in call_kwargs["subject"]
    body = call_kwargs["text"]
    parsed = json.loads(body)
    assert parsed["ver"] == "0.2"

def test_backoff_increases_on_429():
    t = AgentMailTransport(
        inbox_id="f42bbs-arm1@agentmail.to",
        shared_key=SHARED_KEY,
    )
    assert t._backoff == 0
    t._on_rate_limit()
    assert t._backoff > 0
    prev = t._backoff
    t._on_rate_limit()
    assert t._backoff > prev

def test_backoff_resets_on_success():
    t = AgentMailTransport(
        inbox_id="f42bbs-arm1@agentmail.to",
        shared_key=SHARED_KEY,
    )
    t._on_rate_limit()
    t._on_success()
    assert t._backoff == 0
