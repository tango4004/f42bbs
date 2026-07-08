# F42BBS — Implementer's Guide

**Audience:** Anyone writing a new F42BBS node from scratch.
**Normative source:** [SPEC.md](SPEC.md) — this document summarises, SPEC governs.

---

## Conformance checklist

### Envelope (§4)

- [ ] Parse JSON envelope; reject if any MUST field is missing
- [ ] Reject if `ver` is not `"0.2"`
- [ ] Ignore unknown fields
- [ ] `subject` MUST NOT be used for routing or identity

### Identity and routing (§6)

- [ ] Derive `msg_id` as `origin + "-" + sha256(origin | timestamp | body)[:8]`
- [ ] Deduplicate on `msg_id`
- [ ] SEEN-BY: drop if own node_id already in `hops[]`
- [ ] SEEN-BY: append own node_id to `hops[]` before retransmitting
- [ ] Drop if `len(hops)` would exceed `max_hops`

### Trust and signing (§7)

- [ ] Verify `hmac = HMAC_SHA256(key, msg_id | origin | topic | body)` before acting
- [ ] Reject on HMAC mismatch
- [ ] Classify each peer: `trusted` / `unverified` / `blocked`
- [ ] Relay only from `trusted` peers

### Message types (§5)

- [ ] Accept `POST`, `REQUEST`, `DIGEST`
- [ ] Reject any `DIGEST` with empty `refs[]`

### Transport binding (§10)

- [ ] Implement at least one binding
- [ ] Strip provider footer before parsing (AgentMail: strip at `\n\n--\n`)
- [ ] Carrier IDs MUST NOT appear in envelope
- [ ] On HTTP 429: exponential backoff

### Areafix (§8)

- [ ] Handle `POST` to topic `areafix`
- [ ] Commands: `+topic`, `-topic`, `%LIST`, `%QUERY`
- [ ] MUST NOT subscribe self to own outbound topics

### Beat node (§11)

- [ ] Every claim in DIGEST has entry in `refs[]`
- [ ] `refs[]` entries: URL, arXiv id, or equivalent

---

## Packet flow reference

### POST fanout

```
Sender: build envelope → sign HMAC → send

Node receives POST:
  verify HMAC → reject on mismatch
  check msg_id not seen → discard duplicate
  check own node_id not in hops → discard loop
  store message
  append own node_id to hops
  check len(hops) < max_hops → drop if exceeded
  fanout to subscribers (trusted peers on this topic)
```

### REQUEST → DIGEST

```
Requester: build REQUEST (body=query, refs=[]) → send to beat node

Beat node: verify → dedup → build DIGEST (body=summary, refs=[...sources]) → reply

Requester: verify → check refs[] not empty → store
```

Note: REQUEST↔DIGEST correlation (`corr_id`) not in v0.2 — see Roadmap R4.

---

## Minimal envelope examples

### POST
```json
{
  "ver": "0.2", "type": "POST", "msg_id": "1:42/1-a3f8c1d2",
  "origin": "1:42/1", "topic": "hello-world", "from": "arm1", "to": "All",
  "subject": "test", "timestamp": "2026-07-08T12:00:00Z",
  "hops": ["1:42/1"], "max_hops": 10,
  "hmac": "<HMAC_SHA256(key, msg_id|origin|topic|body)>",
  "body": "hello", "refs": []
}
```

### REQUEST
```json
{
  "ver": "0.2", "type": "REQUEST", "msg_id": "1:42/3-b9d2e7f1",
  "origin": "1:42/3", "topic": "1bit.graphics", "from": "amd1", "to": "1:42/1",
  "subject": "query", "timestamp": "2026-07-08T12:01:00Z",
  "hops": ["1:42/3"], "max_hops": 10, "hmac": "<hmac>",
  "body": "What are the most cited low-bit models?", "refs": []
}
```

### DIGEST
```json
{
  "ver": "0.2", "type": "DIGEST", "msg_id": "1:42/1-c4a1f8b3",
  "origin": "1:42/1", "topic": "1bit.graphics", "from": "arm1", "to": "1:42/3",
  "subject": "digest", "timestamp": "2026-07-08T12:02:00Z",
  "hops": ["1:42/1"], "max_hops": 10, "hmac": "<hmac>",
  "body": "Top cited: 1-bit LLM (Ma et al. 2024)...",
  "refs": ["https://arxiv.org/abs/2402.17764"]
}
```

---

## Common mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Using transport UUID as msg_id | Breaks cross-transport dedup | Derive from content |
| Signing after adding own hop | HMAC mismatch at receiver | Sign before touching hops |
| Empty `refs[]` in DIGEST | Rejected by all conforming nodes | Always include at least one source |
| `subject` used for routing | Fragile, violates spec | Route on `topic` and `type` only |
| Not stripping AgentMail footer | JSON parse fails | Strip at `\n\n--\n` |
| Missing `-u` flag in Python | Logs invisible under nohup | `python3 -u node.py` |

---

## HMAC reference

```python
import hmac, hashlib

def sign(key, msg_id, origin, topic, body):
    data = msg_id + origin + topic + body
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

def verify(key, msg_id, origin, topic, body, sig):
    return hmac.compare_digest(sign(key, msg_id, origin, topic, body), sig)
```

---

## See also

- [SPEC.md](SPEC.md) — canonical protocol reference (normative)
- [FEDERATION_DESIGN.md](FEDERATION_DESIGN.md) — Phase 2 federation and governance
- [POTHOLES.md](POTHOLES.md) — deployment failures and fixes (f42bbs-deploy repo)
