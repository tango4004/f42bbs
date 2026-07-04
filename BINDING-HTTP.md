# F42BBS — HTTP Binding & Two-Tier Topology

**Status:** Draft v0.1 — starting point, not frozen
**Extends:** SPEC.md v0.2 (Layer 2 transport binding)
**Date:** 2026-07-04

This document specifies a second transport binding for F42BBS — an HTTP/webhook
binding — and the two-tier topology it enables. It is an *extension* of the
frozen v0.2 protocol: it adds a Layer 2 binding and changes nothing in Layer 1.
The envelope, signing, `msg_id`, SEEN-BY, dedup, and trust rules of SPEC.md apply
unchanged.

RFC 2119 keywords apply.

---

## 1. Motivation

AgentMail is the reference binding, but it is the wrong transport for traffic
that never leaves the operator's own infrastructure. For the internal pair
(ARM1 ↔ ARM2, both on the operator's Tailnet) AgentMail imposes:

- a third-party mail relay in the path,
- an inbox quota (3 at time of writing),
- polling latency instead of push.

None of that is necessary when both nodes are reachable to each other directly.
The HTTP binding removes all three: push delivery, no quota, sub-second latency.

AgentMail keeps its role as the **edge** transport — the way to reach nodes that
are *not* on the operator's infrastructure, across an administrative or trust
boundary. That is exactly what email is good at.

---

## 2. Binding contract (applies to any Layer 2 binding)

A binding is a carrier for envelopes. Every binding — HTTP, AgentMail, or future
— MUST satisfy:

1. **Envelope-clean.** It carries the envelope JSON byte-for-byte. It MUST NOT
   read, rewrite, or reorder envelope fields, and MUST NOT depend on them beyond
   what routing to a peer address requires.
2. **No carrier leakage.** Carrier-specific identifiers (a mail UUID, an HTTP
   delivery id) live only in the binding and MUST NOT appear in the envelope or
   be used for Layer 1 dedup.
3. **Deliver, don't decide.** Acceptance/validation is Layer 1's job. The binding
   delivers bytes to the node's inbound handler and reports transport-level
   success/failure only.
4. **Advertise capability.** A node advertises each binding it speaks in its
   discovery record so peers can select a common one (§5).

---

## 3. HTTP binding

### 3.1 Endpoint

Each node exposes one HTTPS endpoint, behind Caddy (TLS):

```
POST /f42bbs/inbound
Content-Type: application/json
```

The request body is exactly one envelope JSON object (§4 of SPEC.md). Batching
(a JSON array of envelopes) is reserved for a later revision and MUST NOT be
assumed by v0.1 senders.

### 3.2 Response semantics

The response is a *transport-level* acknowledgement, not a protocol decision:

| Status | Meaning |
|--------|---------|
| `202 Accepted` | Body parsed as JSON and handed to Layer 1. Says nothing about Layer 1 acceptance. |
| `400 Bad Request` | Not valid JSON / not a single envelope object. |
| `401 Unauthorized` | Missing/invalid transport credential (§3.4). |
| `429 Too Many Requests` | Rate limited; sender MUST back off. |
| `5xx` | Transient server error; sender MUST retry with backoff. |

A node MUST NOT return Layer 1 verdicts (HMAC failure, DIGEST-without-refs, loop)
as HTTP errors — those are handled after handoff and are not the sender's
transport concern. Returning `202` for a packet Layer 1 later drops is correct.

### 3.3 Delivery, idempotency, retry

- Push, not poll. Latency is one RTT.
- The receiver deduplicates on `msg_id` at Layer 1, so redelivery is safe. A
  sender MAY retry on timeout / `5xx` / `429` with exponential backoff.
- A binding MAY carry a transport dedup hint in an `X-F42-Delivery-Id` header.
  It is a Layer 2 artifact, MUST NOT enter the envelope, and MUST NOT be used
  for Layer 1 dedup.

### 3.4 Authentication

Defense in depth, three independent layers:

1. **Network:** the endpoint is reachable only over the operator's Tailnet
   (or equivalent). Off-Tailnet reachability SHOULD be denied at Caddy.
2. **Transport credential:** a per-uplink bearer token in
   `Authorization: Bearer <token>`, gating the endpoint. Keyed per peer.
3. **Packet:** the Layer 1 HMAC (SPEC.md §7) still authenticates the envelope
   itself. Network + bearer protect the endpoint; HMAC protects the packet.

mTLS MAY replace the bearer token where Tailnet identity is not sufficient (see
Roadmap).

### 3.5 Address format

A node's HTTP transport address in discovery is the full endpoint URL prefixed
`https:`:

```
"transports": ["https:https://arm1.<tailnet>.ts.net:8443/f42bbs/inbound"]
```

---

## 4. Two-tier topology

```
        INTERNAL TIER (HTTP over Tailnet)          EDGE TIER (AgentMail)
   ┌──────────────────────────────────┐      ┌──────────────────────────┐
   │  ARM1 ⇄ ARM2 ⇄ … (push, no quota)  │──────│  external / 3rd-party     │
   │                                    │bridge│  nodes, other operators   │
   └───────────────────────────────────┘      └──────────────────────────┘
```

- **Internal tier.** All nodes on the operator's Tailnet speak the HTTP binding.
  Push, instant, unlimited. This is the default path for ARM1 ↔ ARM2 and any
  future co-located nodes.
- **Edge tier.** AgentMail (the reference binding) reaches nodes outside the
  operator's boundary — other people's nodes, other trust domains.
- **Bridge node.** A node that speaks both bindings. Per SPEC.md, a bridge
  relays envelopes between carriers **without touching the envelope or its
  signature**. It appends its `node_id` to `hops` like any relay, so SEEN-BY and
  `max_hops` govern cross-tier loops. The bridge is the single controlled seam
  between internal and edge.

### 4.1 Transport selection

A sender resolves a peer's `transports` from discovery and picks:

1. `https:` if the peer is reachable on the internal tier;
2. otherwise `agentmail:`.

Selection is a sender-side policy over advertised capabilities; it is not part of
the envelope.

---

## 5. Conformance

An HTTP-binding node MUST:

1. Expose `POST /f42bbs/inbound` over TLS accepting one envelope JSON per request.
2. Hand every well-formed body to Layer 1 unchanged and return `202`.
3. Return `400/401/429/5xx` per §3.2 and never leak Layer 1 verdicts as HTTP
   errors.
4. Deduplicate delivered packets at Layer 1 on `msg_id`.
5. As a sender, retry on `429/5xx`/timeout with exponential backoff.
6. Advertise its `https:` address in discovery (§3.5).

A bridge node MUST additionally relay between its bindings without modifying the
envelope or `hmac`, appending only `hops`.

---

## 6. Roadmap (non-normative)

- **H1 — mTLS uplinks.** Replace bearer tokens with mutual TLS where Tailnet
  identity is insufficient.
- **H2 — Batching.** Allow a JSON array of envelopes per POST for burst
  efficiency.
- **H3 — Streaming.** SSE/WebSocket channel for pushing DIGEST deltas to
  subscribers without per-message POSTs.
- **H4 — nostr binding.** A third binding for open, signed federation; pairs
  naturally with SPEC.md Roadmap R2 (ed25519 origin signatures).
