#!/bin/bash
cd /home/mac/f42bbs
export AGENTMAIL_API_KEY=am_us_a40e6a597a9560c3d604172e690b1940f49cfec076dd02aa01435a028c9f756e
export F42BBS_NODE_ID="1:42/2"
export F42BBS_INBOX="f42bbs-arm2@agentmail.to"
export F42BBS_TOPIC="1bit.graphics"
export F42BBS_KEY="f42bbs-dev-key"
export F42BBS_POLL="30"
export F42BBS_BEAT_INTERVAL="0"
/home/mac/miniforge3/bin/python3 -u run.py >> /home/mac/f42bbs/node.log 2>&1
