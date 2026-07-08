# F42BBS — Federation & Governance Design Notes

**Status:** Non-normative. Phase 2 design. Does not alter v0.2 behaviour.  
**Depends on:** R1/R2 (ed25519 signing) from SPEC.md §13 Roadmap.  
**Source:** Extracted from SPEC.md §13.1–§13.2 for readability.

Readers implementing v0.2 do not need this document. Come back when R2 lands.

---

## Part 1 — Federation & Discovery (Phase 2)

How an F42BBS reaches beyond a single operator's nodes: how strangers learn of each other, take content, and give it.

### Points as sub-nodes (R8)

Node addresses extend from `zone:net/node` to `zone:net/node.point` (Fido's Node/Point model).

- A **node** is a full participant: external transport address, relays, holds state (SQLite, dedup, SEEN-BY).
- A **point** is a sub-node behind a node. No external transport of its own — reaches the network only through its node.

Rules:

- Local traffic between points of the same node MUST NOT be relayed.
- Outbound from a point is signed by its node.
- Ephemeral entities (agent-in-chat, executors, Sierra) are points — `zone:net/node.0`, etc.

### How strangers exchange content

Four distinct steps:

**1. Bootstrap — out-of-band, human-first (R11)**  
First contact is always out-of-band. A human gives one node the transport address of another. No automatic discovery (anti-sybil). Early form: manual entry form. Later: signed browsable directory (R5).

**2. Peering handshake (R10)**  
Having an address, a node sends `REQUEST` on `net.peer` carrying its `node_id`, ed25519 public key, transports, and offered/wanted topics. Each side records the other at `unverified`.

**3. Taking content — pull (R9)**  
A peer sends `REQUEST{topic}`. The node answers `DIGEST` only if the topic is `visibility: public` and the peer's trust level permits. The operator controls what leaves, not the requester.

**4. Continuous exchange — subscription/echo**  
A peer sends in-band areafix `+topic`. New DIGESTs fan out automatically. SEEN-BY/max_hops prevent loops.

Trust grows `unverified → trusted` by hand at first, via web-of-trust (R5) later.

---

## Part 2 — Network Formation & Governance (Phase 2)

How the network forms: how a stranger joins, how topology is agreed, who governs it.  
Requires ed25519 origin signatures (R2). HMAC cannot express "A vouches for B."

### Topology: a tree of points

The network is a tree, not a flat mesh. One entity type — a **point** - with a parent that admitted it.

Address = path: `1:42/2.1.7` = root → node 2 → point 1 → point 7.

The tree gives three things from one structure:

| Property | How |
|----------|-----|
| Trust chain | Path to root is the chain of sponsors |
| Address | Self-describing (`1:42/2.1` says where you are) |
| Topic routing | Topics flow along branches, not across the whole network |

### Joining: admission by sponsorship

1. Newcomer asks node X to admit it. X decides - sovereign right. If admitted, newcomer starts as point X.n.
2. The point may later grow into a full node. Its sponsor vouches.

Sponsorship is a signature: X admits Y → X signs Y's pubkey → record propagates. No shared secret needed.

### The nodelist: append-only log of signatures

Not a list held by one server. Replicated, append-only log of ed25519 signatures.

| Op | Signed by | Verified by |
|----|-----------|-------------|
| genesis | root set (T-of-N) | T valid root sigs |
| admit | sponsor (parent) | parent sig + chain to root |
| revoke | node's sponsor | sponsor sig; cascade automatic |
| root-change | current root set | T valid sigs of active roots |

Fold: apply in topological order, walk sponsor chains to root, active = all links valid, inactive = pass-through mode.

### Root: keys, not servers

Offline ed25519 keys. Governance is 2-of-3: any two sign root operations.

### Extensible root set

N and T are data, not constants. Default: T = floor(N/2) + 1.
The set self-amends under its own threshold.

### Progressive decentralization

| Phase | State | Reality |
|-------|-------|---------|
| 0 - genesis | One holder has all three keys | Full control, one person |
| 1 - first trustee | holder(2) + A(1) | Nothing without the holder |
| 2 - second trustee | holder(1) + A(1) + B(1) | Real 2-of-3 |
| 3 - network without founder | Any two of {holder, A, B} | Founder can leave |

Honesty requirement: Until Phase 2, MUST be described as trusted bootstrap, not decentralization.

### Revocation

- Node: pass-through, not a hole. Cascade automatic.
- Root key: remaining two sign revoke + admit new third.
- Authority: one level only. Parent revokes direct child, never grandchild.

### Admission endpoint

POST /admit: accept → {addr: "<parent>.N", sponsor_sig} + publish to net.nodelist
reject → {rejected} - binary, no reason, no trace.

### Addresses route; keys identify

- Address: ephemeral path in tree.
- Key: permanent. Durable references MUST use pubkey, not address.

### Build order

R1/R2 signing → net.peer handshake → nodelist as signed tree → root set + governance.

Nothing here is normative for v0.2.
