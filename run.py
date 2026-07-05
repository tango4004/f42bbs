"""
run.py — F42BBS node runner (assembly over the tested M0-M7 components).

This is the missing entrypoint: it wires the AgentMail transport (send + a
receive/poll loop), the Daemon (inbound: SEEN-BY / dedup / store / fan-out),
peers/subscriptions seeded from nodes.json, and an optional beat, into one
persistent process.

It does NOT modify any reviewed/tested module. Receive is done here via the
AgentMail client (mirroring test_live.py, which is proven live); send is wired
by setting transport._client to a thin adapter. All protocol logic stays in the
tested components.

Config (env; .env is loaded if present):
  AGENTMAIL_API_KEY     required
  F42BBS_KEY            shared HMAC key (default: f42bbs-dev-key)
  F42BBS_NODE_ID        this node, e.g. 1:42/1        (required)
  F42BBS_INBOX          this node's inbox             (required)
  F42BBS_TOPIC          beat/echo topic (default: 1bit.graphics)
  F42BBS_NODES          nodes.json path (default: nodes.json)
  F42BBS_DB             sqlite path (default: f42bbs.db)
  F42BBS_POLL           poll seconds (default: 60)
  F42BBS_HELLO          if "1", send a POST hello to each peer at startup
  F42BBS_BEAT_INTERVAL  seconds between beat digests; 0 disables (default: 0)
  ANTHROPIC_API_KEY     required only if beat is enabled

Run: python3 run.py
"""
import os
import sys
import json
import time
from datetime import datetime

try:
    from dotenv import load_dotenv
    for candidate in (os.environ.get("F42BBS_ENV"), ".env",
                      "/home/doo/foxtrot/.env", "/home/mac/foxtrot/.env"):
        if candidate and os.path.exists(candidate):
            load_dotenv(candidate)
            break
except Exception:
    pass

from envelope import Envelope, make_msg_id, sign
from db import DB
from daemon import Daemon
from transport.agentmail import AgentMailTransport, parse_envelope_from_mail

# ---- config -----------------------------------------------------------------

API_KEY = os.environ.get("AGENTMAIL_API_KEY")
KEY = os.environ.get("F42BBS_KEY", "f42bbs-dev-key")
NODE_ID = os.environ.get("F42BBS_NODE_ID")
INBOX = os.environ.get("F42BBS_INBOX")
TOPIC = os.environ.get("F42BBS_TOPIC", "1bit.graphics")
NODES_PATH = os.environ.get("F42BBS_NODES", "nodes.json")
DB_PATH = os.environ.get("F42BBS_DB", "f42bbs.db")
POLL = int(os.environ.get("F42BBS_POLL", "60"))
HELLO = os.environ.get("F42BBS_HELLO", "0") == "1"
BEAT_INTERVAL = int(os.environ.get("F42BBS_BEAT_INTERVAL", "0"))


def die(msg):
    print("run.py: %s" % msg, file=sys.stderr)
    sys.exit(2)


if not API_KEY:
    die("AGENTMAIL_API_KEY not set")
if not NODE_ID:
    die("F42BBS_NODE_ID not set")
if not INBOX:
    die("F42BBS_INBOX not set")


# ---- AgentMail client + send adapter ----------------------------------------

from agentmail import AgentMail

_client = AgentMail(api_key=API_KEY)


class _SendAdapter:
    """Adapts AgentMail Client to the send_message() shape transport expects."""
    def __init__(self, client):
        self._c = client

    def send_message(self, inbox_id, to, subject, text):
        self._c.messages.send(inbox_id=inbox_id, to=to, subject=subject, text=text)


# ---- assembly ---------------------------------------------------------------

db = DB(DB_PATH)
transport = AgentMailTransport(inbox_id=INBOX, shared_key=KEY, poll_interval=POLL)
transport._client = _SendAdapter(_client)
daemon = Daemon(node_id=NODE_ID, db=db, transport=transport, shared_key=KEY)


def seed_from_nodes():
    """Load peers from nodes.json; subscribe each peer to THIS node's topic so
    our fan-out reaches them (establishes the echo link)."""
    if not os.path.exists(NODES_PATH):
        print("run.py: no %s, skipping peer seed" % NODES_PATH)
        return
    with open(NODES_PATH) as f:
        data = json.load(f)
    for n in data.get("nodes", []):
        nid = n["node_id"]
        if nid == NODE_ID:
            continue
        addr = (n.get("transports") or ["agentmail:"])[0]
        db.add_peer(nid, n.get("name", nid), addr, n.get("trust", "trusted"))
        db.subscribe(nid, TOPIC)
        print("run.py: peer %s (%s) subscribed to %s" % (nid, addr, TOPIC))


def build_hello():
    body = "hello from %s" % NODE_ID
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    msg_id = make_msg_id(NODE_ID, ts, body)
    data = {
        "ver": "0.2", "type": "POST", "msg_id": msg_id,
        "origin": NODE_ID, "topic": TOPIC, "from": NODE_ID, "to": "All",
        "subject": "[%s] link hello" % TOPIC, "timestamp": ts,
        "hops": [NODE_ID], "max_hops": 10,
        "hmac": sign(KEY, msg_id, NODE_ID, TOPIC, body),
        "body": body, "refs": [],
    }
    return Envelope.parse(data, KEY)


def send_hello():
    env = build_hello()
    for p in db.get_peers():
        addr = p["address"]
        if addr.startswith("agentmail:"):
            addr = addr[len("agentmail:"):]
        try:
            transport.send(env, to_address=addr)
            print("run.py: HELLO -> %s (%s)" % (p["node_id"], addr))
        except Exception as e:
            print("run.py: hello send failed to %s: %s" % (p["node_id"], e))


def _handle(raw):
    """Handle incoming message from threads."""
    env = parse_envelope_from_mail(raw, KEY)
    if env is None:
        return
    result = daemon.inbound(env)
    if result not in ("duplicate", "loop"):
        print("run.py: inbound %s %s -> %s" % (env.type, env.msg_id, result))


def poll_once():
    try:
        threads = _client.threads.list(inbox_id=INBOX)
        processed = 0
        for t in (getattr(threads, "threads", None) or []):
            for m in (getattr(t, "messages", None) or []):
                raw = getattr(m, "text", "") or ""
                _handle(raw)
                processed += 1
    except Exception as e:
        print("run.py: poll error: %s" % e)
        return 0
    return processed

def run_beat():
    """Optional. Build a digest and inject it locally so it is stored and
    fanned out to subscribers. Requires ANTHROPIC_API_KEY."""
    try:
        from beat.graphics_1bit import Beat1bitGraphics
        anth = os.environ.get("ANTHROPIC_API_KEY")
        if not anth:
            print("run.py: beat enabled but ANTHROPIC_API_KEY missing, skipping")
            return
        beat = Beat1bitGraphics(NODE_ID, TOPIC, KEY, anth)
        data = beat.build_digest()
        if "hmac" not in data:
            data["hmac"] = sign(KEY, data["msg_id"], data["origin"],
                                data["topic"], data["body"])
        env = Envelope.parse(data, KEY)
        result = daemon.inbound(env)
        print("run.py: beat digest %s -> %s" % (env.msg_id, result))
    except Exception as e:
        print("run.py: beat error: %s" % e)


def main():
    print("=== F42BBS node %s (%s) topic=%s ===" % (NODE_ID, INBOX, TOPIC))
    seed_from_nodes()
    if HELLO:
        send_hello()
    last_beat = 0.0
    print("run.py: polling every %ss (beat=%s)"
          % (POLL, "off" if BEAT_INTERVAL == 0 else "%ss" % BEAT_INTERVAL))
    while True:
        poll_once()
        if BEAT_INTERVAL > 0 and (time.time() - last_beat) >= BEAT_INTERVAL:
            run_beat()
            last_beat = time.time()
        time.sleep(POLL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nrun.py: stopped")
        db.close()
