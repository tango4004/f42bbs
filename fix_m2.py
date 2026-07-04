import os, sys
from dotenv import load_dotenv
load_dotenv('/home/doo/foxtrot/.env')
import anthropic

with open("/home/doo/f42bbs/db.py") as f:
    code = f.read()

PROMPT = f"""Fix this Python 3.8 compatibility issue: replace all uses of list[X] and dict[X,Y] type hints with List[X] and Dict[X,Y] from typing module. Also ensure "from typing import Optional, List, Dict" is at the top.

Output ONLY the fixed Python code. No markdown. No explanation.

CODE:
{code}"""

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
