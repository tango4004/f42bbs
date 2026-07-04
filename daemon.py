import json
import copy
from typing import Optional, List, Dict
from envelope import Envelope
from db import DB


class Daemon:
    def __init__(self, node_id: str, db: DB, transport, shared_key: str) -> None:
        self.node_id = node_id
        self.db = db
        self.transport = transport
        self.shared_key = shared_key

    def inbound(self, env: Envelope) -> str:
        # 1. SEEN-BY check (only for relay, not origin)
        if self.node_id in env.hops and env.origin != self.node_id:
            return "loop"
        
        # 2. max_hops check
        if len(env.hops) >= env.max_hops:
            return "max_hops"
        
        # 3. Dedup
        if self.db.seen(env.msg_id):
            return "duplicate"
        
        # 4. Store
        self.db.store_msg(
            env.msg_id,
            env.type,
            env.origin,
            env.topic,
            json.dumps(env.emit())
        )
        
        # 5. Areafix
        if env.topic == "areafix":
            return self._handle_areafix(env)
        
        # 6. Fan-out
        self._fanout(env)
        
        # 7. Return ok
        return "ok"

    def _handle_areafix(self, env: Envelope) -> str:
        body = env.body.strip()
        
        if body.startswith("+"):
            topic = body[1:].strip()
            self.db.subscribe(env.origin, topic)
            return "areafix_sub"
        
        if body.startswith("-"):
            topic = body[1:].strip()
            self.db.unsubscribe(env.origin, topic)
            return "areafix_unsub"
        
        if body == "%LIST":
            return "areafix_list"
        
        if body == "%QUERY":
            return "areafix_query"
        
        return "areafix_unknown"

    def _fanout(self, env: Envelope) -> None:
        subscribers = self.db.get_subscribers(env.topic)
        
        for node_id in subscribers:
            if node_id == env.origin:
                continue
            if node_id == self.node_id:
                continue
            peers = self.db.get_peers()
            peer = next((p for p in peers if p["node_id"] == node_id), None)
            if peer is None:
                continue
            if peer["trust"] == "blocked":
                continue
            address = peer["address"]
            if address.startswith("agentmail:"):
                address = address[len("agentmail:"):]
            env_copy = copy.deepcopy(env)
            env_copy.hops = env.hops + [self.node_id]
            self.transport.send(env_copy, to_address=address)