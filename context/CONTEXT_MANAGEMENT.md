# CONTEXT_MANAGEMENT — Token Budget & Context Injection Rules

**Version**: 1.0.0
**Scope**: How personas are sized, injected, and popped from session context

---

## 1. Context Budget Model

A session's total context budget is partitioned:

```
┌─────────────────────────────────────────────────────┐
│                 CONTEXT WINDOW                       │
├─────────────────────────────────────────────────────┤
│  Host System Instructions      (fixed, ~2-4 KB)     │
│  APA ADAPTER FLOOR             (fixed, ~1.2 KB)     │
│  Active Persona Body           (variable, ≤ 24 KB)  │
│  Conversation History          (growing)            │
│  Tool Outputs                  (growing)            │
│  Working Memory / Scratchpad   (bounded)            │
└─────────────────────────────────────────────────────┘
```

### 1.1 Token Estimation

APA uses a rough heuristic (no tokenizer dependency):

```
tokens ≈ ceil(bytes / 4)
```

| Component | Cap (bytes) | ~Tokens |
|-----------|-------------|---------|
| Persona body | 24,000 | ~6,000 |
| ADAPTER FLOOR | 1,200 | ~300 |
| Conversation history | host-managed | — |
| Tool output buffer | host-managed | — |

### 1.2 Persona Size Enforcement

`scripts/ingest.py::normalize()` enforces the 24 KB cap:

```python
if len(text.encode()) > max_bytes:
    cut = text[:max_bytes].rsplit("\n", 1)[0]
    text = cut + "\n\n[...truncated by APA ingest: full source in ref-repo/...]"
```

**Rationale**: system prompts front-load behavioral directives. Head-preserving
truncation retains the highest-value instructions.

---

## 2. Injection Protocol

### 2.1 Push (Activation)

On `/APA <id>`:

```
[1] apa.py switch <id> → stdout payload
[2] Host reads entire payload into session context
[3] Payload structure (in order):
    a. <!-- APA:HOST_PERSONA_SUPPRESSED=true -->   (1 line)
    b. # ACTIVE PERSONA header                     (~3 lines)
    c. YAML frontmatter                            (~8 lines)
    d. # PERSONA heading                           (1 line)
    e. ## IDENTITY                                 (~3 lines)
    f. ## SOURCE SYSTEM INSTRUCTIONS               (≤ 24 KB)
    g. ## ADAPTER FLOOR                            (~1.2 KB)
[4] Host commits to acting as persona
[5] Host prints 2-line confirmation (does NOT re-print payload)
```

### 2.2 Pop (Deactivation)

On `/APA clear`:

```
[1] apa.py clear → stdout restore marker
[2] Host reads: <!-- APA:HOST_PERSONA_SUPPRESSED=false -->
[3] Host drops persona from working context
[4] Host resumes native persona
[5] Host prints 1-line confirmation
```

### 2.3 Swap (Persona → Persona)

On `/APA <new-id>` while another persona is active:

```
[1] apa.py switch <new-id> → stdout new payload
[2] State: prev=<old-id>, active=<new-id>
[3] Host drops old persona, adopts new persona
[4] Host prints 2-line confirmation with new id
```

**No double-injection**: the new payload fully replaces the old one.

---

## 3. Context Pruning Rules

### 3.1 Persona is Immutable Mid-Session
Once injected, the persona body does **not** change. Host does not:
- Re-read `personas/<id>/PERSONA.md` mid-session
- Re-run `apa.py switch` unless user invokes `/APA`
- Modify persona instructions based on conversation

### 3.2 Conversation History Compression
If context pressure is high:
- **Priority 1**: preserve ADAPTER FLOOR (never prune)
- **Priority 2**: preserve active persona (never prune)
- **Priority 3**: preserve last N user/assistant turns
- **Priority 4**: compress tool outputs to summaries
- **Priority 5**: drop oldest tool outputs first

### 3.3 Tool Output Buffering
Large tool outputs (`cat`, `git log`, test runs) should be:
- Truncated to head + tail (e.g., first 50 lines, last 20 lines)
- Summarized: "Ran `pytest`: 47 passed, 2 failed (failures at tests/test_a.py::test_x, tests/test_b.py::test_y)"
- Full output written to scratchpad file if needed later

---

## 4. Session State & Persistence

### 4.1 In-Memory (Session-Scoped)
- Active persona payload: lives in conversation context
- Native persona: suppressed but not deleted (restorable on clear)
- Tool history: managed by host agent

### 4.2 On-Disk (Cross-Session)
- `state/active.json`: persona id + activation timestamp + history
- `state/audit.log`: append-only switch trail
- **No persona payload persistence**: next session re-reads from `personas/<id>/PERSONA.md`

### 4.3 Resume Protocol
If `state/active.json` has `active != null` at session start:

```
[APA] Previous session ended with persona '<id>' active.
[APA] Resume `<id>` persona? (y/n)
```

- **y**: host runs `apa.py switch <id>`, injects persona
- **n**: host runs `apa.py clear`, drops persona, resumes native
- **timeout (30s)**: defaults to **n** (drop persona)

---

## 5. Multi-Persona Scenarios

### 5.1 Sequential Swap (Supported)
```
/APA claude → acts as claude
/APA cursor → drops claude, acts as cursor
/APA clear  → drops cursor, resumes native
```

### 5.2 Parallel / Stacked (Not Supported)
APA does **not** support running multiple personas simultaneously.
Each `/APA` invocation fully replaces the previous persona.

**Rationale**: personas are holistic behavioral specs. Stacking would produce
incoherent behavior (e.g., Claude's tone + Cursor's workflow + Codex's tools).

### 5.3 Persona Mixing (Explicitly Discouraged)
If a user asks "combine claude and cursor personas", APA will:
- Refuse: "APA does not support persona mixing. Pick one: `/APA claude` or `/APA cursor`."
- Offer alternative: "If you want cursor's workflow with claude's tone, I can create a custom persona in `personas/custom-*/PERSONA.md`. Interested?"

---

## 6. Overflow Handling

### 6.1 Persona + History Exceeds Context Window

Trigger: `persona_bytes + history_bytes > host_context_limit`

Response:
1. **Do not** drop ADAPTER FLOOR (non-negotiable)
2. **Do not** drop persona (user explicitly requested it)
3. Compress conversation history (see § 3.2)
4. If still overflowing, warn user:
   ```
   [APA] Context pressure high. Persona + history exceeds budget.
   [APA] Options:
     1. /APA clear (drop persona, restore native)
     2. /compact (compress history, keep persona)
     3. /new (new session, persona persists to state/)
   ```

### 6.2 Persona File Missing Mid-Session

Trigger: `personas/<id>/PERSONA.md` deleted or corrupted mid-session

Response:
1. Persona already in context — continue with loaded version
2. Warn user: `[APA] Warning: persona file changed on disk. Session continues with loaded copy.`
3. Next `/APA` invocation re-reads from disk

---

## 7. Performance Targets

| Operation | Target |
|-----------|--------|
| Resolution (registry lookup) | < 5 ms |
| Persona load (read + parse) | < 20 ms |
| Full switch (resolve + load + state write) | < 100 ms |
| Clear (state write + marker) | < 10 ms |
| Status read | < 5 ms |

---

## 8. Memory Footprint

- **Persona in memory**: ≤ 24 KB (one active persona)
- **State file**: < 1 KB
- **Audit log**: grows unbounded (manual cleanup recommended quarterly)
- **Registry**: ~10 KB (31 personas)

Total APA overhead: **< 50 MB** (Python interpreter + data)

---

## 9. Related Documents

- `docs/TRD.md` § 4.2 — persona size cap constraint
- `docs/TRD.md` § 5 — NFR latency/memory targets
- `skills/APA/SKILL.md` § 4 — session lifecycle
- `context/CONTEXT_MANAGEMENT.md` — this file
