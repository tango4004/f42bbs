"""
M2 tests for db.py
Run: python3 -m pytest test_db.py -v
"""
import pytest
import os
import tempfile
from db import DB

@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    d = DB(path)
    yield d
    d.close()
    os.unlink(path)

# --- seen / dedup ---

def test_new_msg_not_seen(db):
    assert db.seen("1:42/1-aabbccdd") == False

def test_seen_after_store(db):
    db.store_msg("1:42/1-aabbccdd", "POST", "1:42/1", "1bit.graphics", "{}")
    assert db.seen("1:42/1-aabbccdd") == True

def test_dedup_same_msg(db):
    db.store_msg("1:42/1-aabbccdd", "POST", "1:42/1", "1bit.graphics", "{}")
    db.store_msg("1:42/1-aabbccdd", "POST", "1:42/1", "1bit.graphics", "{}")
    assert db.msg_count() == 1

def test_two_different_msgs(db):
    db.store_msg("1:42/1-aabbccdd", "POST", "1:42/1", "1bit.graphics", "{}")
    db.store_msg("1:42/1-11223344", "POST", "1:42/1", "1bit.graphics", "{}")
    assert db.msg_count() == 2

# --- peers ---

def test_add_peer(db):
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "trusted")
    peers = db.get_peers()
    assert len(peers) == 1
    assert peers[0]["node_id"] == "1:42/2"

def test_peer_trust_level(db):
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "trusted")
    peers = db.get_peers(trust="trusted")
    assert len(peers) == 1

def test_blocked_peer_not_in_trusted(db):
    db.add_peer("1:42/3", "rogue", "agentmail:rogue@agentmail.to", "blocked")
    peers = db.get_peers(trust="trusted")
    assert len(peers) == 0

def test_update_peer_trust(db):
    db.add_peer("1:42/2", "arm2", "agentmail:f42bbs-arm2@agentmail.to", "unverified")
    db.set_peer_trust("1:42/2", "trusted")
    peers = db.get_peers(trust="trusted")
    assert len(peers) == 1

# --- subscriptions ---

def test_subscribe(db):
    db.subscribe("1:42/2", "1bit.graphics")
    subs = db.get_subscribers("1bit.graphics")
    assert "1:42/2" in subs

def test_unsubscribe(db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.unsubscribe("1:42/2", "1bit.graphics")
    subs = db.get_subscribers("1bit.graphics")
    assert "1:42/2" not in subs

def test_multiple_topics(db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.subscribe("1:42/2", "ai.arch")
    subs1 = db.get_subscribers("1bit.graphics")
    subs2 = db.get_subscribers("ai.arch")
    assert "1:42/2" in subs1
    assert "1:42/2" in subs2

def test_no_subscribers(db):
    subs = db.get_subscribers("no.such.topic")
    assert subs == []

def test_list_topics(db):
    db.subscribe("1:42/2", "1bit.graphics")
    db.subscribe("1:42/2", "ai.arch")
    topics = db.get_node_topics("1:42/2")
    assert set(topics) == {"1bit.graphics", "ai.arch"}
