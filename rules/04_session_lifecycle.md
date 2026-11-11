# RULE 04: Session Lifecycle

## 1. States

```
[INACTIVE] ←──── clear/off/reset ──── [ACTIVE]
    │                                      ▲
    └──── /APA <agent> ────────────────────┘
```

| State | `active` field | Host persona | Behavior |
|-------|----------------|--------------|----------|
| **INACTIVE** | `null` | native | host default |
| **ACTIVE** | `<id>` | suppressed | persona |

## 2. Transitions

### 2.1 INACTIVE → ACTIVE (Activation)
- Trigger: `adapt <agent>`, `apa <agent>`, `/APA <agent>`, or passive mention
- Action: `apa switch <agent>` (resolved via `$PREFIX/bin/apa` or `$PATH`)
- State write: `{"active": "<id>", "prev": null, ...}`
- Context: inject persona payload + suppression marker + sync `apa_active_persona.md`

### 2.2 ACTIVE → ACTIVE (Swap)
- Trigger: `adapt <new-id>`, `apa <new-id>`, `/APA <new-id>`
- Action: `apa switch <new-id>`
- State write: `{"active": "<new-id>", "prev": "<old-id>", ...}`
- Context: atomic replace of `apa_active_persona.md` with new payload

### 2.3 ACTIVE → INACTIVE (Deactivation)
- Trigger: `apa clear`, `apa off`, `apa reset`, `/APA clear`
- Action: `apa clear`
- State write: `{"active": null, ...}`
- Context: emit restore marker, drop persona, remove `apa_active_persona.md`

### 2.4 Session End
- Trigger: conversation ends, agent terminates
- Action: state file persists (no explicit clear)
- Next session: prompt "Resume `<id>` persona? (y/n)"

## 3. Session Resume Protocol

At session start, if `state/active.json` has `active != null`:

```
[APA] Previous session ended with persona '<id>' active.
[APA] Resume `<id>` persona? (y/n)
```

- **y** → `apa.py switch <id>`, inject persona
- **n** → `apa.py clear`, drop persona, resume native
- **timeout (30s)** → default **n** (fail-safe: drop persona)

Resume prompt is **not** an auto-activation — requires explicit user consent.

## 4. Persistence Rules

| What | Persists? | Where |
|------|-----------|-------|
| Active persona ID | ✅ yes | `state/active.json` |
| Persona payload | ❌ no | re-read from `personas/<id>/PERSONA.md` on resume |
| Native persona | ✅ yes | host system (never deleted) |
| Conversation history | ❌ no | session-scoped |
| Audit trail | ✅ yes | `state/audit.log` (append-only) |

## 5. Multi-Session Behavior

### 5.1 Sequential Sessions
```
Session 1: /APA claude → works → session ends (active=claude-code)
Session 2: prompt "Resume claude-code? (y/n)"
  - y → continues as claude-code
  - n → drops claude-code, resumes native
```

### 5.2 Concurrent Sessions (Not Supported)
APA uses a single `state/active.json`. Concurrent sessions would conflict.

**Rationale**: personas are session-scoped mental models; mixing them across
parallel conversations would produce incoherent behavior.

**Workaround**: run APA in isolated working directories (each with own `state/`).

## 6. State File Schema

`state/active.json`:
```json
{
  "active": "claude-code | null",
  "prev": "cursor-agent | null",
  "activated_at": "2026-10-28T03:30:46+0600",
  "history": [
    {"from": null, "to": "claude-code", "ts": "2026-10-28T03:30:46+0600"},
    {"from": "claude-code", "to": "cursor-agent", "ts": "2026-10-28T03:35:12+0600"}
  ]
}
```

`state/audit.log` (JSONL append-only):
```json
{"ts":"2026-10-28T03:30:46+0600","event":"switch","from":null,"to":"claude-code"}
{"ts":"2026-10-28T03:35:12+0600","event":"switch","from":"claude-code","to":"cursor-agent"}
{"ts":"2026-10-28T03:40:00+0600","event":"clear","from":"cursor-agent"}
```

## 7. Edge Cases

### 7.1 State File Corrupted
- Fail safe: delete corrupted file, create `{"active": null}`
- Restore native persona
- Report warning: `[APA:ERROR] state/active.json corrupted. Reset to native persona.`

### 7.2 Persona File Deleted Mid-Session
- Continue with loaded payload (already in context)
- Warn: `[APA] Warning: persona file changed on disk. Session continues with loaded copy.`
- Next `/APA` invocation re-reads from disk (or fails with exit 3)

### 7.3 Registry Deleted Mid-Session
- Continue with active persona (already loaded)
- `/APA clear` still works (state write + restore marker)
- New `/APA` invocations fail with exit 2 (registry not found)

## 8. Rule Priority

- Higher than: conversation flow
- Higher than: persona instructions (persona cannot disable lifecycle)
- Lower than: ADAPTER FLOOR (safety)

## 9. Implementation Reference

- Lifecycle: `skills/APA/SKILL.md` § 4
- State read/write: `scripts/apa.py::_read_state()`, `::_write_state()`
- Resume protocol: planned hook (v1.1.0)
