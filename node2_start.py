"""ARM2 node starter — sets env and runs the F42BBS node."""
import os
import sys

# Node config
os.environ.setdefault("F42BBS_NODE_ID", "1:42/2")
os.environ.setdefault("F42BBS_INBOX", "f42bbs-arm2@agentmail.to")
os.environ.setdefault("F42BBS_KEY", "f42bbs-dev-key")
os.environ.setdefault("F42BBS_POLL", "30")
os.environ.setdefault("F42BBS_BEAT_INTERVAL", "0")
os.environ.setdefault("F42BBS_HELLO", "0")

# Load API key from .env
try:
    from dotenv import load_dotenv
    for p in ["/home/mac/foxtrot/.env", "/home/doo/foxtrot/.env"]:
        if os.path.exists(p):
            load_dotenv(p)
            break
except Exception:
    pass

# Run
sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(__file__), "run.py")).read())
