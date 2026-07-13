import os
import json
import secrets
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, request, Response
import requests

from db import DB
from envelope import Envelope, make_msg_id, sign

load_dotenv()

F42BBS_NODE_ID = os.getenv("F42BBS_NODE_ID")
F42BBS_KEY = os.getenv("F42BBS_KEY")
F42BBS_DB = os.getenv("F42BBS_DB", "f42bbs.db")
STEP_PORT = int(os.getenv("STEP_PORT", "8766"))

db = DB(F42BBS_DB)

otp_chain = {}
OTP_TTL = 3600

with open("nodes.json", "r") as f:
    nodes_data = json.load(f)
    peer_urls = []
    for node in nodes_data["nodes"]:
        for transport in node["transports"]:
            if transport.startswith("https:"):
                peer_urls.append(transport[6:])

app = Flask(__name__)

# Register HTTP inbound blueprint
from transport.http import http_transport, init_http_transport, HttpTransport
from daemon import Daemon
app.register_blueprint(http_transport)


def generate_otp() -> str:
    return secrets.token_hex(8)


def validate_otp(otp_str: str) -> bool:
    if otp_str not in otp_chain:
        return False
    created_at = otp_chain[otp_str]
    if time.time() - created_at > OTP_TTL:
        del otp_chain[otp_str]
        return False
    return True


def execute_command(command: str) -> str:
    parts = command.strip().split()
    if not parts:
        return "error: empty command"
    
    cmd = parts[0]
    
    if cmd == "ping":
        return "ok"
    
    elif cmd == "publish":
        topic = None
        body = None
        for part in parts[1:]:
            if part.startswith("topic="):
                topic = part[6:]
            elif part.startswith("body="):
                body = "=".join(part.split("=")[1:])
        
        if not topic or not body:
            return "error: publish requires topic=<name> body=<text>"
        
        timestamp = datetime.now(timezone.utc).isoformat()
        msg_id = make_msg_id(F42BBS_NODE_ID, timestamp, body)
        hmac_val = sign(F42BBS_KEY, msg_id, F42BBS_NODE_ID, topic, body)
        
        envelope = Envelope(
            ver="0.2",
            type="POST",
            msg_id=msg_id,
            origin=F42BBS_NODE_ID,
            topic=topic,
            from_=F42BBS_NODE_ID,
            to="*",
            subject=f"POST {topic}",
            timestamp=timestamp,
            hops=[F42BBS_NODE_ID],
            max_hops=10,
            hmac=hmac_val,
            body=body,
            refs=[]
        )
        
        raw_envelope = json.dumps(envelope.emit())
        db.store_msg(msg_id, "POST", F42BBS_NODE_ID, topic, raw_envelope)
        
        for peer_url in peer_urls:
            try:
                requests.post(peer_url, json=envelope.emit(), timeout=5)
            except Exception:
                pass
        
        return f"published to topic {topic}"
    
    elif cmd == "get":
        topic = None
        for part in parts[1:]:
            if part.startswith("topic="):
                topic = part[6:]
        
        if not topic:
            return "error: get requires topic=<name>"
        
        msg_body = db.get_latest(topic)
        if msg_body is None:
            return f"no messages in topic {topic}"
        
        try:
            msg_dict = json.loads(msg_body)
            return msg_dict.get("body", msg_body)
        except:
            return msg_body
    
    elif cmd == "request":
        topic = None
        query = None
        for part in parts[1:]:
            if part.startswith("topic="):
                topic = part[6:]
            elif part.startswith("query="):
                query = "=".join(part.split("=")[1:])
        if not topic:
            return "error: request requires topic=<name>"
        if not query:
            query = f"latest on {topic}"

        import time as _t
        ts = str(int(_t.time()))
        msg_id = make_msg_id(F42BBS_NODE_ID, ts, query)
        hmac_val = sign(F42BBS_KEY, msg_id, F42BBS_NODE_ID, topic, query)
        req_env = Envelope(
            ver="0.2", type="REQUEST",
            msg_id=msg_id, origin=F42BBS_NODE_ID,
            topic=topic, from_=F42BBS_NODE_ID, to="*",
            subject=f"REQUEST {topic}",
            timestamp=ts, hops=[], max_hops=10,
            hmac=hmac_val, body=query, refs=[]
        )
        _daemon.inbound(req_env)

        for _ in range(20):
            _t.sleep(0.5)
            digest = db.get_digest(msg_id)
            if digest:
                return digest
        return "no digest received (timeout 10s)"

    else:
        return "error: unknown command"


@app.route("/step", methods=["POST"])
def step():
    body = request.get_data(as_text=True).strip()
    
    if body.startswith(","):
        command = body[1:].strip()
        new_otp = generate_otp()
        otp_chain[new_otp] = time.time()
        result = execute_command(command)
        return Response(f"%{new_otp}% {result}", content_type="text/plain")
    
    elif body.startswith("%"):
        parts = body.split("%", 2)
        if len(parts) < 3:
            return Response("error: invalid otp", content_type="text/plain", status=400)
        
        otp_str = parts[1].strip()
        command = parts[2].strip()
        
        if not validate_otp(otp_str):
            return Response("error: invalid otp", content_type="text/plain", status=401)
        
        del otp_chain[otp_str]
        new_otp = generate_otp()
        otp_chain[new_otp] = time.time()
        
        result = execute_command(command)
        return Response(f"%{new_otp}% {result}", content_type="text/plain")
    
    return Response("error: invalid request", content_type="text/plain", status=400)



@app.route("/health", methods=["GET"])
def health():
    return "step ok", 200

# Init inbound transport
# Init inbound transport with real vars
import copy as _copy
_http_transport_obj = HttpTransport()
_peer_urls_raw = os.getenv("F42BBS_PEER_URLS", "") or os.getenv("F42BBS_PEER_URL", "")
_peer_urls = [u.strip() for u in _peer_urls_raw.split(",") if u.strip()]
_db_path = os.getenv("F42BBS_DB", "f42bbs.db")
from db import DB as _DB
_daemon_db = _DB(_db_path)
_daemon = Daemon(F42BBS_NODE_ID, _daemon_db, _http_transport_obj, F42BBS_KEY)

def _http_fanout(env):
    for peer_url in _peer_urls:
        ec = _copy.deepcopy(env)
        ec.hops = env.hops + [F42BBS_NODE_ID]
        _http_transport_obj.send(ec, peer_url)
_daemon._fanout = _http_fanout
init_http_transport(_daemon, F42BBS_KEY)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=STEP_PORT, debug=False)