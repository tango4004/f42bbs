"""
M6 integration test: two-node round-trip, in-memory transport.

Node 1:42/1 (arm1) -> POST -> Node 1:42/2 (arm2)
Node 1:42/2 (arm2) -> REQUEST -> Node 1:42/1 (arm1)
SEEN-BY loop prevention verified.
Areafix subscribe/unsubscribe verified.

Run: python3 -m pytest test_integration.py -v
"""
import pytest
import os
import tempfile
from envelope import Envelope, make_msg_id, sign
from db import DB
from daemon import Daemon

SHARED_KEY = "integration-test-key"
NODE1 = "1:42/1"
NODE2 = "1:42/2"
TOPIC = "1bit.graphics"


class MemTransport:
    """In-memory transport: send() delivers directly to target daemon."""
    def __init__(self):
        self.sent = []
        self.targets = {}  # node_id -> Daemon

    def send(self, env, to_address=None):
        self.sent.append((env, to_address))
        # deliver to target if registered
        for node_id, daemon in self.targets.items():
            if to_address and node_id in to_address:
                daemon.inbound(env)


def make_env(type_, origin, topic=TOPIC, body="test body", refs=None, hops=None):
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if refs is None:
        refs = ["https://arxiv.org/abs/2402.17764"] if type_ == "DIGEST" else []
    if hops is None:
        hops = [origin]
    msg_id = make_msg_id(origin, ts, body)
    d = {
        "ver": "0.2", "type": type_, "msg_id": msg_id,
        "origin": origin, "topic": topic, "from": origin,
        "to": "All", "subject": "test", "timestamp": ts,
        "hops": hops, "max_hops": 10,
        "hmac": sign(SHARED_KEY, msg_id, origin, topic, body),
        "body": body, "refs": refs,
    }
    return Envelope.parse(d, SHARED_KEY)


@pytest.fixture
def two_nodes():
    """Two daemons with shared in-memory transport."""
    fd1, p1 = tempfile.mkstemp(suffix=".db")
    fd2, p2 = tempfile.mkstemp(suffix=".db")
    os.close(fd1); os.close(fd2)

    db1 = DB(p1)
    db2 = DB(p2)

    t1 = MemTransport()
    t2 = MemTransport()

    d1 = Daemon(NODE1, db1, t1, SHARED_KEY)
    d2 = Daemon(NODE2, db2, t2, SHARED_KEY)

    # register peers
    db1.add_peer(NODE2, "arm2", f"agentmail:{NODE2}", "trusted")
    db2.add_peer(NODE1, "arm1", f"agentmail:{NODE1}", "trusted")

    # cross-wire transports
    t1.targets[NODE2] = d2
    t2.targets[NODE1] = d1

    yield d1, d2, db1, db2, t1, t2

    db1.close(); db2.close()
    os.unlink(p1); os.unlink(p2)


# --- POST delivery ---

def test_post_delivered_to_subscriber(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    env = make_env("POST", NODE1, body="hello from arm1")
    result = d1.inbound(env)

    assert result == "ok"
    assert len(t1.sent) == 1
    assert db2.seen(env.msg_id)


def test_post_not_delivered_to_non_subscriber(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    # node2 NOT subscribed

    env = make_env("POST", NODE1, body="unsubscribed post")
    d1.inbound(env)

    assert len(t1.sent) == 0


def test_post_not_echoed_back_to_origin(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    # node1 subscribes to its own topic — should not receive its own post
    db1.subscribe(NODE1, TOPIC)

    env = make_env("POST", NODE1, body="no echo")
    d1.inbound(env)

    # node1 is skipped in fanout (origin == self)
    sent_to_node1 = [s for s in t1.sent if NODE1 in (s[1] or "")]
    assert len(sent_to_node1) == 0


# --- SEEN-BY loop prevention ---

def test_seen_by_prevents_loop(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    # simulate env that already passed through node1
    env = make_env("POST", NODE2, hops=[NODE2, NODE1])
    result = d1.inbound(env)

    assert result == "loop"
    assert len(t1.sent) == 0


def test_max_hops_drops_packet(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    env = make_env("POST", NODE2, hops=["1:42/%d" % i for i in range(2, 12)])
    result = d1.inbound(env)
    assert result == "max_hops"


# --- Deduplication ---

def test_duplicate_dropped(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    env = make_env("POST", NODE2, hops=[NODE2])
    d1.inbound(env)
    result = d1.inbound(env)

    assert result == "duplicate"
    assert db1.msg_count() == 1


# --- REQUEST round-trip ---

def test_request_delivered(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db2.subscribe(NODE1, TOPIC)

    env = make_env("REQUEST", NODE2, body="latest 1-bit neural net papers?")
    result = d2.inbound(env)

    assert result == "ok"
    assert len(t2.sent) == 1
    sent_env = t2.sent[0][0]
    assert sent_env.type == "REQUEST"
    assert NODE2 in sent_env.hops


# --- DIGEST with refs ---

def test_digest_with_refs_delivered(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    env = make_env("DIGEST", NODE1,
                   body="BitNet achieves 1-bit weights.",
                   refs=["https://arxiv.org/abs/2402.17764"])
    result = d1.inbound(env)

    assert result == "ok"
    assert db2.seen(env.msg_id)


# --- Areafix ---

def test_areafix_subscribe_via_post(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes

    env = make_env("POST", NODE2, topic="areafix", body=f"+{TOPIC}", hops=[NODE2])
    result = d1.inbound(env)

    assert result == "areafix_sub"
    assert NODE2 in db1.get_subscribers(TOPIC)


def test_areafix_unsubscribe_via_post(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    env = make_env("POST", NODE2, topic="areafix", body=f"-{TOPIC}", hops=[NODE2])
    result = d1.inbound(env)

    assert result == "areafix_unsub"
    assert NODE2 not in db1.get_subscribers(TOPIC)


# --- Hops appended on relay ---

def test_relay_appends_self_to_hops(two_nodes):
    d1, d2, db1, db2, t1, t2 = two_nodes
    db1.subscribe(NODE2, TOPIC)

    # origin is NODE2 node 3 (not NODE1 or NODE2) so fanout proceeds to NODE2
    env = make_env("POST", "1:42/3", hops=["1:42/3"])
    d1.inbound(env)

    assert len(t1.sent) == 1
    relayed_env = t1.sent[0][0]
    assert NODE1 in relayed_env.hops
