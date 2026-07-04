import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

PROMPT = """Write a Python module implementing the F42BBS envelope layer.

Export exactly:
- EnvelopeError(Exception)
- make_msg_id(origin: str, timestamp: str, body: str) -> str
  logic: return origin + "-" + hashlib.sha256((origin+timestamp+body).encode()).hexdigest()[:8]
- sign(key: str, msg_id: str, origin: str, topic: str, body: str) -> str
  logic: hmac.new(key.encode(), (msg_id+origin+topic+body).encode(), hashlib.sha256).hexdigest()
- verify(key: str, msg_id: str, origin: str, topic: str, body: str, hmac_val: str) -> bool
  logic: hmac.compare_digest(sign(key,msg_id,origin,topic,body), hmac_val)
- Envelope dataclass with fields:
    ver: str, type: str, msg_id: str, origin: str, topic: str, from_: str,
    to: str, subject: str, timestamp: str, hops: list, max_hops: int,
    hmac: str, body: str, refs: list
  methods:
    @classmethod parse(cls, data: dict, key: str) -> "Envelope"
      - check MUST fields: ver,type,msg_id,origin,topic,from,to,timestamp,hops,max_hops,hmac,body,refs
        raise EnvelopeError("missing field: X") if any missing
      - raise EnvelopeError("unsupported ver") if ver != "0.2"
      - raise EnvelopeError("hmac mismatch") if verify() fails
      - raise EnvelopeError("DIGEST requires refs") if type=="DIGEST" and refs==[]
      - data["from"] maps to field from_
    emit(self) -> dict
      - return dict of all fields, from_ maps back to key "from"

Output ONLY valid Python code. No markdown. No explanation. No comments."""

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

with open("/home/doo/f42bbs/envelope.py", "w") as f:
    f.write(code)

print(f"OK: {len(code)} bytes")
print(code[:300])
