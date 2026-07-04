import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

PROMPT = """Write a Python module db.py for the F42BBS protocol.

It wraps a SQLite database. Export a single class DB with:

__init__(self, path: str)
  - open sqlite3 connection at path
  - create tables if not exist:
    messages(msg_id TEXT PRIMARY KEY, type TEXT, origin TEXT, topic TEXT, raw TEXT, created_at TEXT)
    peers(node_id TEXT PRIMARY KEY, name TEXT, address TEXT, trust TEXT)
    subscriptions(node_id TEXT, topic TEXT, PRIMARY KEY(node_id, topic))

close(self)
  - close connection

seen(self, msg_id: str) -> bool
  - return True if msg_id exists in messages

store_msg(self, msg_id: str, type: str, origin: str, topic: str, raw: str)
  - INSERT OR IGNORE into messages, created_at = UTC ISO8601 now

msg_count(self) -> int
  - return count of rows in messages

add_peer(self, node_id: str, name: str, address: str, trust: str)
  - INSERT OR REPLACE into peers

get_peers(self, trust: str = None) -> list[dict]
  - return list of dicts with keys: node_id, name, address, trust
  - if trust given, filter by trust level

set_peer_trust(self, node_id: str, trust: str)
  - UPDATE peers SET trust=? WHERE node_id=?

subscribe(self, node_id: str, topic: str)
  - INSERT OR IGNORE into subscriptions

unsubscribe(self, node_id: str, topic: str)
  - DELETE from subscriptions WHERE node_id=? AND topic=?

get_subscribers(self, topic: str) -> list[str]
  - return list of node_id subscribed to topic

get_node_topics(self, node_id: str) -> list[str]
  - return list of topics for node_id

Output ONLY valid Python code. No markdown. No explanation."""

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
r = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=2048,
    messages=[{"role": "user", "content": PROMPT}]
)

code = r.content[0].text.strip()
if code.startswith("```"):
    lines = code.split("\n")
    end = len(lines)-1 if lines[-1].strip() == "```" else len(lines)
    code = "\n".join(lines[1:end])

with open("/home/doo/f42bbs/db.py", "w") as f:
    f.write(code)

print(f"OK: {len(code)} bytes")
print(code[:200])
