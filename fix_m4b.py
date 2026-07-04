import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

with open("/home/doo/f42bbs/daemon.py") as f:
    code = f.read()

PROMPT = f"""Fix these three specific bugs in daemon.py:

BUG 1: SEEN-BY check must be:
  if self.node_id in env.hops and env.origin != self.node_id:
      return "loop"
This means: loop if self was already a relay hop, but NOT if self is the original sender.

BUG 2: _fanout must work like this exactly:
  def _fanout(self, env):
      subscribers = self.db.get_subscribers(env.topic)
      for node_id in subscribers:
          if node_id == env.origin:
              continue
          if node_id == self.node_id:
              continue
          peers = self.db.get_peers()
          peer = next((p for p in peers if p["node_id"] == node_id), None)
          if peer is None:
              continue
          if peer["trust"] == "blocked":
              continue
          address = peer["address"]
          if address.startswith("agentmail:"):
              address = address[len("agentmail:"):]
          env_copy = copy.deepcopy(env)
          env_copy.hops = env.hops + [self.node_id]
          self.transport.send(env_copy, to_address=address)

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
