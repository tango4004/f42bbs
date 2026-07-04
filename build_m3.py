import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

PROMPT = """Write a Python module transport/agentmail.py for the F42BBS protocol AgentMail transport binding.

Python 3.8 compatible. Use List, Dict, Optional from typing.

Export:

1. strip_footer(body: str) -> str
   - Remove trailing AgentMail footer starting with "\\n--\\n" or "\\n\\n--\\n"
   - If no footer found, return body unchanged

2. parse_envelope_from_mail(raw: str, key: str) -> Optional[Envelope]
   - Strip footer from raw
   - Try json.loads; return None if fails
   - Try Envelope.parse(data, key); return None if EnvelopeError
   - Return Envelope on success

3. class AgentMailTransport:
   __init__(self, inbox_id: str, shared_key: str, poll_interval: int = 60)
     - store inbox_id, shared_key, poll_interval
     - self._backoff = 0
     - self._client = None  (injected externally or via agentmail SDK)

   send(self, env: Envelope, to_address: str)
     - call self._client.send_message(
         inbox_id=self.inbox_id,
         to=[to_address],
         subject=f"[{env.topic}] {env.subject}",
         text=json.dumps(env.emit())
       )

   _on_rate_limit(self)
     - if self._backoff == 0: self._backoff = 60
     - else: self._backoff = min(self._backoff * 2, 3600)

   _on_success(self)
     - self._backoff = 0

Imports needed: json, from typing import Optional
from envelope import Envelope, EnvelopeError

Output ONLY valid Python 3.8 code. No markdown. No explanation."""

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

os.makedirs("/home/doo/f42bbs/transport", exist_ok=True)
with open("/home/doo/f42bbs/transport/__init__.py", "w") as f:
    f.write("")
with open("/home/doo/f42bbs/transport/agentmail.py", "w") as f:
    f.write(code)

print(f"OK: {len(code)} bytes")
print(code[:300])
