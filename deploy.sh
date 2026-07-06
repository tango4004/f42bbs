#!/bin/bash
set -e
DEST=/opt/f42bbs
git clone https://github.com/tango4004/f42bbs $DEST 2>/dev/null || (cd $DEST && git pull)
cd $DEST
pip3 install -r requirements.txt --break-system-packages
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Edit $DEST/.env then run: python3 http_node.py"
fi
echo "Deploy done: $DEST"
