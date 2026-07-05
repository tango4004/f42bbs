# F42BBS — AgentMail↔Anthropic Connector

**Version:** 0.1 draft
**Status:** Starting point
**Date:** 2026-07-05
**Extends:** SPEC.md v0.2 (Layer 2 binding), BRAVO.md executor model

This document specifies a connector that turns an AgentMail inbox into an
Anthropic API executor: an incoming signed envelope addressed to the inbox
triggers a model call, and the response is returned as a signed DIGEST to the
sender. It is a **Layer 2 binding** for the Anthropic executor — it does not
alter the F42BBS envelope or protocol.

RFC 2119 keywords apply.

---

## 1. Concept

```
sender node                    connector (this spec)           Anthropic API
─────────────────────────────────────────────────────────────────────────────
envelope{type:REQUEST,       →  [1] poll AgentMail inbox
 body:"summarize X",         →  [2] verify HMAC signature
 hmac: ...}                  →  [3] extract body as prompt
via AgentMail transport       →  [4] call claude-* API        →  inference
                                 [5] sign DIGEST response
                              ←  [6] send reply via AgentMail  ←  response
envelope{type:DIGEST,
 body:"<model output>",
 refs:[...], hmac:...}
```

One address = one model endpoint. The connector is a robot:
- it receives, it verifies, it calls, it signs, it replies.
- it never executes without a valid signature.
- it never replies without signing.

---

## 2. Addressing

Each connector instance owns **one AgentMail inbox**, mapped to one model
configuration:

```
haiku@f42bbs.foxtrot42.org   →  claude-haiku-*   (fast, high-volume)
sonnet@f42bbs.foxtrot42.org  →  claude-sonnet-*  (balanced)
opus@f42bbs.foxtrot42.org    →  claude-opus-*    (deep reasoning)
```

In BBS terms this is an **executor node** (BRAVO.md §4): `node_id = 1:42/10`
(or similar reserved range), `capabilities: [inference:haiku]`.

A sender addresses the connector by its `node_id` or its AgentMail inbox
directly (discovery resolves the mapping per SPEC.md §9).

---

## 3. Wire protocol

The connector speaks the standard F42BBS envelope (SPEC.md §4). No new fields.

### 3.1 Inbound — REQUEST

A sender constructs a standard `REQUEST` envelope:

```json
{
  "ver": "0.2",
  "type": "REQUEST",
  "msg_id": "<content-derived>",
  "origin": "1:42/1",
  "topic": "inference:haiku",
  "from": "arm1",
  "to": "1:42/10",
  "subject": "[inference:haiku] summarize arxiv:2402.17764",
  "timestamp": "2026-07-05T10:00:00Z",
  "hops": ["1:42/1"],
  "max_hops": 10,
  "hmac": "<HMAC_SHA256(key, msg_id|origin|topic|body)>",
  "body": "Summarize the key findings of arxiv:2402.17764 in 3 bullet points.",
  "refs": []
}
```

`body` is the prompt verbatim. The connector uses it as the user-turn of the
Anthropic API call. Optional structured fields (system prompt, max_tokens,
model override) MAY be passed in a JSON object in `body` (see §6 roadmap).

### 3.2 Outbound — DIGEST

The connector returns a `DIGEST` envelope addressed to the sender:

```json
{
  "ver": "0.2",
  "type": "DIGEST",
  "msg_id": "<content-derived>",
  "origin": "1:42/10",
  "topic": "inference:haiku",
  "from": "haiku-executor",
  "to": "1:42/1",
  "subject": "[inference:haiku] response",
  "timestamp": "<utcnow>",
  "hops": ["1:42/10"],
  "max_hops": 10,
  "hmac": "<signed by connector key>",
  "body": "<model output text>",
  "refs": ["<corr_id of the originating REQUEST>"]
}
```

`refs` MUST contain the `msg_id` of the originating REQUEST (acts as
correlation until SPEC.md R4 `corr_id` lands). This is not a provenance ref
in the usual sense — mark it `type: corr` when R6 structured refs land.

---

## 4. Authentication (normative)

Authentication is two-sided and symmetric: the sender proves identity to the
connector, and the connector proves identity back to the sender.

### 4.1 Inbound verification

The connector MUST, in this order before calling the API:

1. **Parse** the body as a JSON envelope. Reject anything that is not a valid
   v0.2 envelope.
2. **Check `type`**: only `REQUEST` envelopes trigger inference. `POST`,
   `DIGEST`, and unrecognised types MUST be silently dropped (not replied to).
3. **Verify HMAC**: `HMAC_SHA256(shared_key, msg_id|origin|topic|body)`.
   The shared key is a **per-uplink secret** agreed out-of-band between the
   operator and the connector. Reject and do not call API on mismatch.
4. **Check `origin` authorisation**: the connector maintains an allowlist of
   authorised `origin` values (node_ids). If `origin` is not in the allowlist,
   reject.
5. **Check `topic`**: if the REQUEST asks for a model the connector does not
   serve (e.g. `inference:opus` hitting the haiku connector), reject with a
   DIGEST error response (§4.3).

Steps 3 and 4 are independent checks; both MUST pass.

### 4.2 Outbound signing

Every DIGEST the connector sends MUST be signed with the connector's own
`shared_key` (the key it shares with the destination node). The recipient MUST
verify this signature before using the response.

The connector MUST NOT send unsigned or incorrectly signed replies.

### 4.3 Rejection response

When a REQUEST is rejected (bad HMAC, unauthorised origin, wrong topic), the
connector MUST:

- NOT call the Anthropic API.
- Send a signed DIGEST back to `origin` with `body` indicating the rejection
  reason (`"error: hmac_invalid"` / `"error: origin_not_authorised"` /
  `"error: topic_not_served"`).
- Log the rejection with timestamp, origin, and reason.

Silent drops (§4.1 step 2) are the exception: malformed or non-REQUEST
envelopes are discarded without reply to avoid reply-loop amplification.

---

## 5. Connector implementation

### 5.1 Poll loop

```python
while True:
    messages = agentmail_client.messages.list(inbox_id=INBOX)
    for msg in messages:
        raw = strip_footer(msg.text)
        env = parse_envelope_from_mail(raw, shared_key)
        if env is None:
            continue                      # not a valid envelope, drop
        if env.type != "REQUEST":
            continue                      # drop non-REQUEST silently
        result = handle(env)              # verify → call API → reply
        agentmail_client.messages.update(  # mark processed
            inbox_id=INBOX, message_id=msg.id, labels=["processed"])
    time.sleep(POLL_INTERVAL)
```

`parse_envelope_from_mail` from `transport/agentmail.py` already does footer
stripping and HMAC verification — reuse it.

### 5.2 Inference call

```python
def call_anthropic(prompt: str, model: str, max_tokens: int = 1000) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text
```

The connector MUST catch Anthropic API errors and return them as signed DIGEST
error responses rather than silently failing or crashing the loop.

### 5.3 Config (env)

```
AGENTMAIL_API_KEY      required
ANTHROPIC_API_KEY      required
F42BBS_CONNECTOR_KEY   shared HMAC key (same as node's shared_key)
F42BBS_NODE_ID         this connector's node_id, e.g. 1:42/10
F42BBS_INBOX           connector's inbox, e.g. haiku@agentmail.to
F42BBS_MODEL           anthropic model string, e.g. claude-haiku-4-5-20251001
F42BBS_ALLOWED_ORIGINS comma-separated list of authorised node_ids
F42BBS_POLL            poll interval in seconds (default: 15)
F42BBS_MAX_TOKENS      default max_tokens (default: 1000)
```

Secrets live in vault / `.env`, never in the envelope, never in logs.

---

## 6. Security properties

- **Signing is mandatory both ways.** An unsigned REQUEST is dropped; an
  unsigned DIGEST is not sent. There is no unauthenticated path to inference.
- **Allowlist, not denylist.** Only listed `origin` node_ids can trigger the
  connector. Adding a new caller = adding its node_id to `F42BBS_ALLOWED_ORIGINS`.
- **No prompt injection via envelope metadata.** Only `body` becomes the prompt.
  `subject`, `topic`, `from`, `hops` are never included in the inference call.
- **No secret in any channel output.** API keys, HMAC keys never appear in
  envelope body, logs, or DIGEST responses.
- **Rate limiting** (roadmap): the connector SHOULD track requests per origin
  per time window and reject over-limit origins before calling the API.

---

## 7. Conformance

A conforming connector MUST:

1. Accept only `REQUEST` envelopes; silently drop all others (§4.1 step 2).
2. Verify HMAC before calling the API (§4.1 step 3).
3. Verify `origin` against allowlist before calling the API (§4.1 step 4).
4. Return a signed DIGEST for every accepted REQUEST, including error cases (§4.3).
5. Include the originating `msg_id` in `refs[]` of the DIGEST (§3.2).
6. Never include secret values in any envelope, log, or output (§6).
7. Catch and return Anthropic API errors as DIGEST error responses (§5.2).

---

## 8. Roadmap

| ID | Item |
|----|------|
| C1 | **Structured REQUEST body.** Allow `body` to be a JSON object with `prompt`, `system`, `model`, `max_tokens` — overriding connector defaults per call. |
| C2 | **corr_id.** Once SPEC.md R4 lands, use `corr_id` for REQUEST↔DIGEST correlation instead of `refs` hack. |
| C3 | **Rate limiting per origin.** Track requests/origin/window; reject with signed error before API call. |
| C4 | **Multi-turn sessions.** Pass a `session_id` in REQUEST body; connector maintains a short conversation history for the session duration. |
| C5 | **Tool use.** Allow REQUEST to declare tools; connector proxies tool calls back through BBS as nested REQUEST/DIGEST pairs. |
| C6 | **Streaming.** Return partial DIGEST tokens as the model streams; aligns with BINDING-HTTP.md H3. |
