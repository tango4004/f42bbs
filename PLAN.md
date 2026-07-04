# F42BBS — Build Plan

**Status:** Active
**Spec:** SPEC.md v0.2
**Date:** 2026-07-03

Clean-slate implementation. All existing code removed. Built strictly to spec.

---

## M0 — Scaffold

- Remove legacy code
- Directory structure
- `requirements.txt`
- `config.json` schema

## M1 — Layer 1: Envelope

- `envelope.py` — parse, emit, validate all MUST fields
- `msg_id` content-derived: `sha256(origin|timestamp|body)[:8]`
- HMAC sign / verify
- Reject DIGEST with empty `refs[]`

## M2 — Layer 1: Routing

- `db.py` — SQLite: messages, peers, subscriptions
- SEEN-BY enforcement + `max_hops`
- Deduplication on `msg_id`
- Trust levels: trusted / unverified / blocked

## M3 — Layer 2: AgentMail Binding

- `transport/agentmail.py`
- Poll loop 60 s, exponential backoff on HTTP 429
- Provider footer stripping
- `mail_id` is Layer 2 only — never touches envelope

## M4 — Daemon

- `daemon.py` — main loop
- Inbound: poll → validate → store → route
- Outbound: queue → sign → send
- Areafix handler (in-band POST to topic `areafix`)

## M5 — Beat Node

- `beat/1bit_graphics.py`
- Sources: arXiv, Hugging Face, web search
- Scheduled DIGEST ≤ 500 words, every claim in `refs[]`
- Haiku API for summarisation

## M6 — Two-Node Integration Test

- Second node on ARM2 or second AgentMail inbox
- POST arm1 → arm2, verify SEEN-BY cuts the loop
- REQUEST → DIGEST round-trip

## M7 — Git Hygiene

- `.gitignore`: `*.db`, secrets, `__pycache__`
- Commit per milestone
- `nodes.json` Phase 1 (static, < 5 nodes)

---

## Dependency order

M1 → M2 → M3 → M4 → M5 (parallel with M6) → M6

M5 and M6 can proceed in parallel after M4 is done.

---

## Notes

- Haiku API available for beat summarisation (M5)
- Transport is pluggable — AgentMail is reference binding only
- No open peering until R1/R2 (ed25519) land in v0.3
