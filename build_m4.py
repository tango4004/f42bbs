import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

PROMPT = """Write a Python 3.8 module daemon.py for the F42BBS protocol.

Export class Daemon:

__init__(self, node_id: str, db: DB, transport, shared_key: str)
  - store all args as self.node_id, self.db, self.transport, self.shared_key

inbound(self, env: Envelope) -> str
  Process an inbound envelope. Return value indicates result:
  1. SEEN-BY check: if self.node_id in env.hops -> return "loop"
  2. max_hops check: if len(env.hops) >= env.max_hops -> return "max_hops"
  3. Dedup: if self.db.seen(env.msg_id) -> return "duplicate"
  4. Store: self.db.store_msg(env.msg_id, env.type, env.origin, env.topic, json.dumps(env.emit()))
  5. Areafix: if env.topic == "areafix" -> call _handle_areafix(env) and return its result
  6. Fan-out: call _fanout(env)
  7. return "ok"

_handle_areafix(self, env: Envelope) -> str
  Parse env.body (strip whitespace):
  - starts with "+": self.db.subscribe(env.origin, body[1:].strip()) -> return "areafix_sub"
  - starts with "-": self.db.unsubscribe(env.origin, body[1:].strip()) -> return "areafix_unsub"
  - "%LIST": return "areafix_list"
  - "%QUERY": return "areafix_query"
  - else: return "areafix_unknown"

_fanout(self, env: Envelope)
  For each subscriber of env.topic:
    - skip if subscriber == env.origin (don't echo back)
    - skip if subscriber == self.node_id (no self-delivery, R3)
    - get peer from db; skip if not found or trust == "blocked"
    - get peer address (format: "agentmail:EMAIL" -> EMAIL)
    - append self.node_id to a copy of env.hops
    - update env copy hops
    - call self.transport.send(env_copy, to_address=address)

Imports: json, copy, from typing import Optional
from envelope import Envelope
from db import DB

Python 3.8 compatible. Use List, Dict, Optional from typing.
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

with open("/home/doo/f42bbs/daemon.py", "w") as f:
    f.write(code)

print(f"OK: {len(code)} bytes")
print(code[:300])
