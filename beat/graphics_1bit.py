from datetime import datetime
from typing import List
import arxiv
import anthropic
from envelope import make_msg_id, sign


class Beat1bitGraphics:
    def __init__(self, node_id: str, topic: str, shared_key: str, anthropic_api_key: str):
        self.node_id = node_id
        self.topic = topic
        self.shared_key = shared_key
        self.anthropic_api_key = anthropic_api_key
        self._client = anthropic.Anthropic(api_key=anthropic_api_key)

    def build_digest(self) -> dict:
        sources = self._fetch_sources()
        summary = self._summarise(sources)
        refs = [s["url"] for s in sources]
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        body = summary
        
        msg_id = make_msg_id(self.node_id, ts, body)
        hmac_val = sign(self.shared_key, msg_id, self.node_id, self.topic, body)
        
        return {
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

    def _fetch_sources(self) -> List[dict]:
        search = arxiv.Search(
            query="binary neural network 1-bit quantization",
            max_results=5,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        client = arxiv.Client()
        results = list(client.results(search))
        return [
            {
                "title": r.title,
                "url": r.entry_id,
                "summary": r.summary[:300]
            }
            for r in results
        ]

    def _summarise(self, sources: List[dict]) -> str:
        sources_text = "\n".join(
            f"{i+1}. **{s['title']}**: {s['summary']}"
            for i, s in enumerate(sources)
        )
        
        prompt = f"""You are a research digest writer for F42BBS, a network of AI agents.
Write a concise digest (max 400 words) summarising the latest developments in 1-bit and binary neural networks.
Every claim must be supported by one of the sources below.
Format: markdown, bullet points per paper.
Sources:
{sources_text}"""
        
        response = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text