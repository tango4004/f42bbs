"""
M6 live integration test: two-node round-trip over real AgentMail.
Requires env: AGENTMAIL_API_KEY
Optional env: F42BBS_KEY, F42BBS_ARM1_INBOX, F42BBS_ARM2_INBOX, F42BBS_NODE1, F42BBS_NODE2, F42BBS_TOPIC
Run: python3 test_live.py
"""
import os, sys, json, time
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
from agentmail import AgentMail as Client
from envelope import make_msg_id, sign
from transport.agentmail import parse_envelope_from_mail
from datetime import datetime

SHARED_KEY = os.environ.get("F42BBS_KEY", "f42bbs-dev-key")
ARM1_INBOX = os.environ.get("F42BBS_ARM1_INBOX", "f42bbs-arm1@agentmail.to")
ARM2_INBOX = os.environ.get("F42BBS_ARM2_INBOX", "f42bbs-arm2@agentmail.to")
NODE1      = os.environ.get("F42BBS_NODE1", "1:42/1")
NODE2      = os.environ.get("F42BBS_NODE2", "1:42/2")
TOPIC      = os.environ.get("F42BBS_TOPIC", "1bit.graphics")

client = Client(api_key=os.environ["AGENTMAIL_API_KEY"])

def make_packet(type_, origin, body, refs=None, hops=None):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if refs is None:
        refs = ["https://arxiv.org/abs/2402.17764"] if type_ == "DIGEST" else []
    if hops is None:
        hops = [origin]
    msg_id = make_msg_id(origin, ts, body)
    hmac_val = sign(SHARED_KEY, msg_id, origin, TOPIC, body)
    return {
        "ver": "0.2", "type": type_, "msg_id": msg_id,
        "origin": origin, "topic": TOPIC, "from": origin,
        "to": "All", "subject": "[%s] live test" % TOPIC,
        "timestamp": ts, "hops": hops, "max_hops": 10,
        "hmac": hmac_val, "body": body, "refs": refs,
    }

def send_packet(from_inbox, to_inbox, packet):
    client.messages.send(
        inbox_id=from_inbox,
        to=[to_inbox],
        subject=packet["subject"],
        text=json.dumps(packet)
    )
    print("  SENT %s %s -> %s" % (packet["type"], packet["msg_id"], to_inbox))

def poll_inbox(inbox_id, msg_id, timeout=45):
    print("  polling %s for %s..." % (inbox_id, msg_id))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msgs = client.messages.list(inbox_id=inbox_id)
            for m in (msgs.messages or []):
                raw = getattr(m, "text", "") or ""
                env = parse_envelope_from_mail(raw, SHARED_KEY)
                if env and env.msg_id == msg_id:
                    return env
        except Exception as e:
            print("  poll error: %s" % e)
        time.sleep(4)
    return None

errors = []
print("=== F42BBS Live Integration Test ===")
print("  arm1: %s (%s)" % (NODE1, ARM1_INBOX))
print("  arm2: %s (%s)" % (NODE2, ARM2_INBOX))

print("\n[1] POST arm1 -> arm2")
p1 = make_packet("POST", NODE1, "Live integration test POST from arm1.")
send_packet(ARM1_INBOX, ARM2_INBOX, p1)
r1 = poll_inbox(ARM2_INBOX, p1["msg_id"])
if r1:
    print("  OK: %s hops=%s" % (r1.msg_id, r1.hops))
else:
    errors.append("TEST1 FAIL: POST not received at arm2")

print("\n[2] REQUEST arm2 -> arm1")
p2 = make_packet("REQUEST", NODE2, "Latest 1-bit neural network papers?")
send_packet(ARM2_INBOX, ARM1_INBOX, p2)
r2 = poll_inbox(ARM1_INBOX, p2["msg_id"])
if r2:
    print("  OK: %s type=%s" % (r2.msg_id, r2.type))
else:
    errors.append("TEST2 FAIL: REQUEST not received at arm1")

print("\n=== Result ===")
if errors:
    for e in errors:
        print("  FAIL: %s" % e)
    sys.exit(1)
else:
    print("  ALL PASSED")
    sys.exit(0)
