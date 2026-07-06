"""
ARM1 executor node — charlie2 serve_exec over f42bbs inbox.
Run: python3 -u executor_arm1.py
Requires: pip install agentmail anthropic flask
"""
import sys, os

# charlie2 SDK embedded (vendored transport + executor logic)
# using the same envelope/transport already in f42bbs
sys.path.insert(0, '/home/doo/f42bbs')

# Load API key
try:
    from dotenv import load_dotenv
    for p in ['/home/doo/foxtrot/.env']:
        if os.path.exists(p):
            load_dotenv(p)
            break
except Exception:
    pass

import json, time, subprocess
from envelope import Envelope, make_msg_id, sign
from transport.agentmail import AgentMailTransport, parse_envelope_from_mail
from agentmail import AgentMail

API_KEY = os.environ.get('AGENTMAIL_API_KEY', '')
KEY = 'f42bbs-dev-key'
NODE_ID = '1:42/1'
INBOX = 'f42bbs-arm1@agentmail.to'
ALLOWED = {'1:42/0', '1:42/1', '1:42/2'}
POLL = 15

client = AgentMail(api_key=API_KEY)

def execute(env):
    """Run command from envelope body, return result string."""
    body = env.body.strip()
    # Try JSON
    try:
        d = json.loads(body)
        cmd = d.get('cmd', '')
        code = d.get('code') or d.get('run') or d.get('text', '')
    except Exception:
        parts = body.split(None, 1)
        cmd = parts[0] if parts else 'ping'
        code = parts[1] if len(parts) > 1 else ''

    if cmd == 'ping':
        import platform
        return f"pong from {NODE_ID} ({platform.node()})"

    if cmd in ('python', 'py'):
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=30)
            out = r.stdout.rstrip()
            err = r.stderr.strip()
            return (out + ('\n[stderr] ' + err if err else '') + (f'\n[rc={r.returncode}]' if r.returncode else '')) or '(no output)'
        finally:
            os.unlink(tmp)

    if cmd in ('bash', 'sh', 'run'):
        r = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=30)
        out = r.stdout.rstrip()
        err = r.stderr.strip()
        return (out + ('\n[stderr] ' + err if err else '') + (f'\n[rc={r.returncode}]' if r.returncode else '')) or '(no output)'

    return f"error: unknown command '{cmd}'. Try: ping, python, bash"

def reply(env, result):
    """Send signed DIGEST back to sender."""
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    body = result
    msg_id = make_msg_id(NODE_ID, ts, body)
    sig = sign(KEY, msg_id, NODE_ID, env.topic, body)
    digest = {
        'ver': '0.2', 'type': 'DIGEST',
        'msg_id': msg_id, 'origin': NODE_ID,
        'topic': env.topic, 'from': INBOX,
        'to': env.origin, 'subject': f'[{env.topic}] response',
        'timestamp': ts, 'hops': [NODE_ID], 'max_hops': 10,
        'hmac': sig, 'body': body, 'refs': [env.msg_id],
    }
    to_addr = env.frm if env.frm and '@' in env.frm else INBOX
    client.inboxes.messages.send(
        inbox_id=INBOX, to=[to_addr],
        subject=f'[{env.topic}] response',
        text=json.dumps(digest),
    )
    print(f'executor: replied to {to_addr} ({len(result)} chars)')

def poll_once():
    result = client.inboxes.messages.list(INBOX)
    for msg in (getattr(result, 'messages', None) or []):
        raw = parse_envelope_from_mail(getattr(msg, 'text', '') or '', KEY)
        if raw is None:
            continue
        if raw.type != 'REQUEST':
            continue
        if raw.origin not in ALLOWED:
            print(f'executor: rejected {raw.origin}')
            continue
        print(f'executor: {raw.msg_id} cmd={raw.body[:60]!r}')
        try:
            out = execute(raw)
        except Exception as e:
            out = f'error: {e}'
        reply(raw, out)
        client.inboxes.messages.update(INBOX, msg.id, add_labels=['processed'])

print(f'=== ARM1 executor {NODE_ID} inbox={INBOX} poll={POLL}s ===')
while True:
    try:
        poll_once()
    except KeyboardInterrupt:
        print('stopped'); break
    except Exception as e:
        print(f'executor: poll error: {e}')
    time.sleep(POLL)
