"""
M4 tests for daemon.py
Run: python3 -m pytest test_daemon.py -v
"""
import pytest
import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call
from envelope import Envelope, make_msg_id, sign
from db import DB
from daemon import Daemon

SHARED_KEY = "testkey123"

def make_env(type_="POST", topic="1bit.graphics", body="hello", refs=None, origin="1:42/1", hops=None):
    ts = "2026-07-03T20:00:00Z"
    msg_id = make_msg_id(origin, ts, body)
    if refs is None:
        refs = ["https://arxiv.org/abs/2310.11453"] if type_ == "DIGEST" else []
    d = {
        "ver": "0.2", "type": type_, "msg_id": msg_id,
        "origin": origin, "topic": topic, "from": "arm1",
        "to": "All", "subject": "test", "timestamp": ts,
        "hops": hops or [origin], "max_hops": 10,
        "body": body, "refs": refs,
    }
    d["hmac"] = sign(SHARED_KEY, msg_id, origin, topic, body)
    return Envelope.parse(d, SHARED_KEY)

@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    d = DB(path)
    yield d
    d.close()
    os.unlink(path)

@pytest.fixture
def daemon(db):
    transport = MagicMock()
    d = Daemon(
        node_id="1:42/1",
        db=db,
        transport=transport,
        shared_key=SHARED_KEY
    )
    return d

# --- inbound: dedup ---

def test_inbound_new_msg_stored(daemon, db):
    env = make_env()
    daemon.inbound(env)
    assert db.seen(env.msg_id)

def test_inbound_duplicate_dropped(daemon, db):
    env = make_env()
    daemon.inbound(env)
    result = daemon.inbound(env)
    assert result == "duplicate"
    assert db.msg_count() == 1

# --- inbound: SEEN-BY ---

def test_inbound_drops_if_self_in_hops(daemon):
    env = make_env(hops=["1:42/1", "1:42/2"], origin="1:42/2")  # self already in hops
    result = daemon.inbound(env)
    assert result == "loop"

def test_inbound_accepts_if_self_not_in_hops(daemon):
    env = make_env(hops=["1:42/2"])
    result = daemon.inbound(env)
    assert result != "loop"

# --- inbound: max_hops ---

def test_inbound_drops_if_max_hops_exceeded(daemon, db):
    env = make_env()
    env.hops = ["1:42/%d" % i for i in range(10)]  # 10 hops = max
    result = daemon.inbound(env)
    assert result == "max_hops"

def test_inbound_accepts_under_max_hops(daemon):
    env = make_env(hops=["1:42/2", "1:42/3"])
    result = daemon.inbound(env)
    assert result not in ("max_hops", "loop")

# --- inbound: areafix ---

def test_areafix_subscribe(daemon, db):
    env = make_env(topic="areafix", body="+1bit.graphics", origin="1:42/2", hops=["1:42/2"])
    daemon.inbound(env)
    assert "1:42/2" in db.get_subscribers("1bit.graphics")

def test_areafix_unsubscribe(daemon, db):
    db.subscribe("1:42/2", "1bit.graphics")
    env = make_env(topic="areafix", body="-1bit.graphics", origin="1:42/2", hops=["1:42/2"])
    daemon.inbound(env)
    assert "1:42/2" not in db.get_subscribers("1bit.graphics")

def test_areafix_list(daemon, db):
    db.subscribe("1:42/1", "1bit.graphics")
    db.subscribe("1:42/1", "ai.arch")
    env = make_env(topic="areafix", body="%LIST", origin="1:42/2", hops=["1:42/2"])
    result = daemon.inbound(env)
    assert result == "areafix_list"

# --- outbound: fan-out ---

def test_outbound_sends_to_subscribers(daemon, db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "trusted")
    env = make_env(topic="1bit.graphics", origin="1:42/3", hops=["1:42/3"])
    daemon.inbound(env)
    daemon.transport.send.assert_called_once()

def test_outbound_no_send_to_blocked_peer(daemon, db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "blocked")
    env = make_env(topic="1bit.graphics", origin="1:42/2", hops=["1:42/2"])
    daemon.inbound(env)
    daemon.transport.send.assert_not_called()

def test_outbound_appends_self_to_hops(daemon, db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "trusted")
    env = make_env(topic="1bit.graphics", origin="1:42/3", hops=["1:42/3"])
    daemon.inbound(env)
    sent_env = daemon.transport.send.call_args[0][0]
    assert "1:42/1" in sent_env.hops
