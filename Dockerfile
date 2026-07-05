FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV F42BBS_NODE_ID=""
ENV F42BBS_INBOX=""
ENV F42BBS_TOPIC="1bit.graphics"
ENV F42BBS_KEY="f42bbs-dev-key"
ENV F42BBS_POLL="60"
ENV AGENTMAIL_API_KEY=""
ENV ANTHROPIC_API_KEY=""

CMD ["python", "-u", "run.py"]
