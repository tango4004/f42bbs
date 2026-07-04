import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

with open("/home/doo/f42bbs/daemon.py") as f:
    code = f.read()

PROMPT = f"""Fix the following issues in this F42BBS daemon.py:

1. SEEN-BY check: "if self.node_id in env.hops" — this fires when node is the ORIGIN too.
   Fix: only check if self.node_id is in env.hops AND self.node_id != env.origin.
   Actually correct fix: SEEN-BY means "have I already relayed this". Check should be:
   if self.node_id in env.hops -> return "loop"
   BUT the test makes env with hops=["1:42/1"] where 1:42/1 is both origin AND node_id.
   The SEEN-BY rule per spec: before retransmitting, drop if own node_id already in hops.
   So on FIRST receipt, node should NOT have its own id in hops yet.
   Fix: the test has hops=["1:42/1"] for a message FROM 1:42/1 TO node 1:42/1.
   The daemon node_id is also "1:42/1". So it IS in hops on first receipt.
   Solution: check SEEN-BY only for relay (when origin != self.node_id), or
   check: if self.node_id in env.hops and env.origin != self.node_id -> "loop"

2. max_hops: test sets hops to 10 items with max_hops=10. Condition should be
   len(env.hops) >= env.max_hops -> "max_hops"

3. store_msg: daemon must call self.db.store_msg(...) for new messages.
   Make sure it calls it AFTER the loop/max_hops/dedup checks.

4. fanout: _fanout must look up peer by subscriber node_id using db.get_peers(),
   find the matching peer dict, extract address from "agentmail:EMAIL" format,
   create a copy of env with hops appended, call self.transport.send(env_copy, to_address=address).
   The transport.send call signature is: send(env, to_address=str)

Output ONLY the fixed Python code. No markdown. No explanation.

CODE:
{code}"""

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
r = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=3000,
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
print(code[:400])
