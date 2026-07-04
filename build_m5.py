import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

PROMPT = """Write a Python 3.8 module beat/graphics_1bit.py for the F42BBS beat node.

Export class Beat1bitGraphics:

__init__(self, node_id: str, topic: str, shared_key: str, anthropic_api_key: str)
  - store all args
  - self._client = anthropic.Anthropic(api_key=anthropic_api_key)

build_digest(self) -> dict
  - call sources = self._fetch_sources()
  - call summary = self._summarise(sources)
  - refs = [s["url"] for s in sources]
  - ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
  - body = summary
  - from envelope import make_msg_id, sign
  - msg_id = make_msg_id(self.node_id, ts, body)
  - hmac_val = sign(self.shared_key, msg_id, self.node_id, self.topic, body)
  - return dict:
    {
      "ver": "0.2",
      "type": "DIGEST",
      "msg_id": msg_id,
      "origin": self.node_id,
      "topic": self.topic,
      "from": self.node_id,
      "to": "All",
      "subject": "1bit.graphics weekly digest",
      "timestamp": ts,
      "hops": [self.node_id],
      "max_hops": 10,
      "hmac": hmac_val,
      "body": body,
      "refs": refs
    }

_fetch_sources(self) -> List[dict]
  - import arxiv
  - search = arxiv.Search(query="binary neural network 1-bit quantization", max_results=5, sort_by=arxiv.SortCriterion.SubmittedDate)
  - client = arxiv.Client()
  - results = list(client.results(search))
  - return [{"title": r.title, "url": r.entry_id, "summary": r.summary[:300]} for r in results]

_summarise(self, sources: List[dict]) -> str
  - Build prompt listing each source title + summary
  - Call self._client.messages.create(
      model="claude-haiku-4-5",
      max_tokens=1000,
      messages=[{"role": "user", "content": prompt}]
    )
  - return response.content[0].text

The prompt for _summarise should be:
"You are a research digest writer for F42BBS, a network of AI agents.
Write a concise digest (max 400 words) summarising the latest developments in 1-bit and binary neural networks.
Every claim must be supported by one of the sources below.
Format: markdown, bullet points per paper.
Sources:
{numbered list of title + summary}"

Imports needed: datetime, from typing import List
import arxiv
import anthropic
from envelope import make_msg_id, sign

Python 3.8 compatible. Output ONLY valid Python code. No markdown. No explanation."""

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

os.makedirs("/home/doo/f42bbs/beat", exist_ok=True)
with open("/home/doo/f42bbs/beat/__init__.py", "w") as f:
    f.write("")
with open("/home/doo/f42bbs/beat/graphics_1bit.py", "w") as f:
    f.write(code)

print(f"OK: {len(code)} bytes")
print(code[:300])
