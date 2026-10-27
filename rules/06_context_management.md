# RULE 06: Context Management Rules

## 1. Context Budget

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

Token estimation heuristic: `tokens ≈ ceil(bytes / 4)`

## 2. Persona Injection (Push)

On `/APA <id>`:
```
[1] Read persona payload from stdout (apa.py switch)
[2] Inject into session context IN ORDER:
    a. Suppression marker (1 line)
    b. Active persona header (~3 lines)
    c. YAML frontmatter (~8 lines)
    d. Identity section (~3 lines)
    e. Source system instructions (≤ 24 KB)
    f. Adapter floor (~1.2 KB)
[3] Do NOT re-print payload to user
[4] Emit 2-line confirmation
```

## 3. Persona Removal (Pop)

On `/APA clear`:
```
[1] Read restore marker from stdout (apa.py clear)
[2] Drop persona from working context
[3] Resume native persona
[4] Emit 1-line confirmation
```

## 4. Swap (Persona → Persona)

On `/APA <new-id>` while active:
```
[1] Load new payload (full replacement)
[2] Drop old persona from context
[3] Adopt new persona
[4] Confirm: "switched: <old-id> → <new-id>"
```

**No double-injection.**

## 5. Pruning Priority (Context Pressure)

If context exceeds budget:
```
PRIORITY 1 (never prune):  ADAPTER FLOOR
PRIORITY 2 (never prune):  Active persona
PRIORITY 3 (preserve):     Last N user/assistant turns
PRIORITY 4 (compress):     Tool outputs → summaries
PRIORITY 5 (drop first):   Oldest tool outputs
```

## 6. Tool Output Buffering

Large tool outputs (`cat`, `git log`, test runs):
- Truncate to head + tail (e.g., first 50 lines, last 20 lines)
- Summarize: "Ran `pytest`: 47 passed, 2 failed (failures at tests/test_a.py::test_x, tests/test_b.py::test_y)"
- Write full output to scratchpad file if needed later

## 7. Persona Immutability

Once injected, persona body is **immutable** for the session:
- ❌ Do NOT re-read `personas/<id>/PERSONA.md` mid-session
- ❌ Do NOT re-run `apa.py switch` unless user invokes `/APA`
- ❌ Do NOT modify persona instructions based on conversation
- ✅ DO continue with loaded version

If persona file changes on disk mid-session:
- Continue with loaded copy
- Warn: `[APA] Warning: persona file changed on disk. Session continues with loaded copy.`

## 8. Session Resume

At session start, if `state/active.json` has `active != null`:
```
[APA] Previous session ended with persona '<id>' active.
[APA] Resume `<id>` persona? (y/n)
```

- **y** → `apa.py switch <id>`, inject persona
- **n** → `apa.py clear`, drop persona, resume native
- **timeout (30s)** → default **n** (fail-safe)

Resume requires explicit consent — no auto-activation.

## 9. Overflow Handling

If persona + history exceeds context window:
```
[1] DO NOT drop ADAPTER FLOOR (non-negotiable)
[2] DO NOT drop persona (user requested it)
[3] Compress conversation history (see § 5)
[4] If still overflowing, warn:
    [APA] Context pressure high. Persona + history exceeds budget.
    [APA] Options:
      1. /APA clear (drop persona, restore native)
      2. /compact (compress history, keep persona)
      3. /new (new session, persona persists to state/)
```

## 10. Multi-Persona Scenarios

### 10.1 Sequential Swap (Supported)
```
/APA claude → acts as claude
/APA cursor → drops claude, acts as cursor
/APA clear  → drops cursor, resumes native
```

### 10.2 Parallel / Stacked (Not Supported)
APA does **not** support running multiple personas simultaneously. Each `/APA`
invocation fully replaces the previous persona.

**Rationale**: personas are holistic behavioral specs. Stacking would produce
incoherent behavior (e.g., Claude's tone + Cursor's workflow + Codex's tools).

### 10.3 Persona Mixing (Discouraged)
If user asks "combine claude and cursor personas":
- Refuse: "APA does not support persona mixing. Pick one: `/APA claude` or `/APA cursor`."
- Offer alternative: "I can create a custom persona in `personas/custom-*/PERSONA.md`. Interested?"

## 11. Performance Targets

| Operation | Target |
|-----------|--------|
| Resolution (registry lookup) | < 5 ms |
| Persona load (read + parse) | < 20 ms |
| Full switch (resolve + load + state write) | < 100 ms |
| Clear (state write + marker) | < 10 ms |
| Status read | < 5 ms |

## 12. Memory Footprint

- **Persona in memory**: ≤ 24 KB (one active persona)
- **State file**: < 1 KB
- **Audit log**: grows unbounded (manual cleanup recommended quarterly)
- **Registry**: ~10 KB (31 personas)

Total APA overhead: **< 50 MB** (Python interpreter + data)

## 13. Rule Priority

- Higher than: conversation flow
- Lower than: ADAPTER FLOOR (safety)
- Lower than: trigger recognition (must still detect `/APA clear`)

## 14. Implementation Reference

- Context rules: `context/CONTEXT_MANAGEMENT.md`
- Persona size cap: `scripts/ingest.py::normalize(max_bytes=24000)`
- State schema: `docs/SCHEMA.md`
