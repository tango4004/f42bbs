"""
M1 tests for envelope.py
Run: python3 -m pytest test_envelope.py -v
"""
import pytest
import json
import hmac
import hashlib
import time
from envelope import Envelope, EnvelopeError, make_msg_id, sign, verify

SHARED_KEY = "testkey123"

def valid_post():
    return {
        "ver": "0.2",
        "type": "POST",
        "origin": "1:42/1",
        "topic": "1bit.graphics",
        "from": "arm1",
        "to": "All",
        "subject": "test post",
        "timestamp": "2026-07-03T20:00:00Z",
        "hops": ["1:42/1"],
        "max_hops": 10,
        "body": "hello world",
        "refs": []
    }

def valid_digest():
    d = valid_post()
    d["type"] = "DIGEST"
    d["refs"] = ["https://arxiv.org/abs/2310.11453"]
    return d

# --- msg_id ---

def test_msg_id_format():
    mid = make_msg_id("1:42/1", "2026-07-03T20:00:00Z", "hello")
    assert mid.startswith("1:42/1-")
    assert len(mid.split("-")[-1]) == 8

def test_msg_id_deterministic():
    a = make_msg_id("1:42/1", "2026-07-03T20:00:00Z", "hello")
    b = make_msg_id("1:42/1", "2026-07-03T20:00:00Z", "hello")
    assert a == b

def test_msg_id_differs_on_body():
    a = make_msg_id("1:42/1", "2026-07-03T20:00:00Z", "hello")
    b = make_msg_id("1:42/1", "2026-07-03T20:00:00Z", "world")
    assert a != b

# --- parse / emit ---

def test_parse_valid_post():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    assert env.type == "POST"
    assert env.topic == "1bit.graphics"

def test_parse_valid_digest():
    data = valid_digest()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    assert env.type == "DIGEST"

def test_emit_roundtrip():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    out = env.emit()
    assert out["ver"] == "0.2"
    assert out["type"] == "POST"
    assert "hmac" in out

# --- missing fields ---

def test_missing_ver_rejected():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    del data["ver"]
    with pytest.raises(EnvelopeError):
        Envelope.parse(data, SHARED_KEY)

def test_missing_body_rejected():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    del data["body"]
    with pytest.raises(EnvelopeError):
        Envelope.parse(data, SHARED_KEY)

def test_wrong_ver_rejected():
    data = valid_post()
    data["ver"] = "0.1"
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    with pytest.raises(EnvelopeError):
        Envelope.parse(data, SHARED_KEY)

# --- HMAC ---

def test_bad_hmac_rejected():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = "deadbeef"
    with pytest.raises(EnvelopeError):
        Envelope.parse(data, SHARED_KEY)

def test_good_hmac_accepted():
    data = valid_post()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    assert env is not None

# --- DIGEST refs ---

def test_digest_empty_refs_rejected():
    data = valid_digest()
    data["refs"] = []
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    with pytest.raises(EnvelopeError):
        Envelope.parse(data, SHARED_KEY)

def test_digest_with_refs_accepted():
    data = valid_digest()
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    assert env.refs == ["https://arxiv.org/abs/2310.11453"]

def test_post_empty_refs_ok():
    data = valid_post()
    data["refs"] = []
    data["msg_id"] = make_msg_id(data["origin"], data["timestamp"], data["body"])
    data["hmac"] = sign(SHARED_KEY, data["msg_id"], data["origin"], data["topic"], data["body"])
    env = Envelope.parse(data, SHARED_KEY)
    assert env is not None
