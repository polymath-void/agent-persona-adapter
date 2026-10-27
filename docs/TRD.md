# TRD — Technical Requirements Document (Agent Persona Adapter)

**Version**: 1.0.0
**Date**: 2026-10-28
**Status**: DRAFT-IMPLEMENTED

---

## 1. Goals

- G1: Instant persona swap on `/APA <agent>` or `@APA <agent>` invocation
- G2: Native persona suppression for the duration of the APA session
- G3: Zero third-party dependencies (Python 3 stdlib only)
- G4: Deterministic, auditable resolution with fuzzy fallback
- G5: Session-scoped lifecycle (no persistence without consent)

---

## 2. Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11 | `$PREFIX/bin/python3`, stdlib only |
| Registry | JSON | `registry/agents.json` |
| State | JSON | `state/active.json` |
| Audit | JSONL | `state/audit.log` (append-only) |
| Persona format | Markdown + YAML front | `personas/<id>/PERSONA.md` |
| Search | difflib | stdlib fuzzy matching (cutoff 0.72) |
| Hashing | hashlib.sha256 | provenance (12-char prefix) |

---

## 3. Interfaces

### 3.1 CLI (`scripts/apa.py`)

```
apa.py list [--json]
apa.py switch <name> [-v]
apa.py info <name>
apa.py clear
apa.py status [--json]
apa.py search <query>
```

**Exit codes**:
- `0` — success
- `2` — no persona match (with "did you mean" hint on stderr)
- `3` — persona metadata exists but payload file missing

### 3.2 Registry Schema (`registry/agents.json`)

```json
{
  "agents": {
    "<id>": {
      "vendor": "string",
      "family": "string",
      "aliases": ["string"],
      "invocations": ["/APA <id>", "@APA <alias>"],
      "payload": "personas/<id>/PERSONA.md",
      "sha256_12": "string"
    }
  }
}
```

### 3.3 State Schema (`state/active.json`)

```json
{
  "active": "<id> | null",
  "prev": "<id> | null",
  "activated_at": "ISO8601",
  "history": [{"from": "<id>|null", "to": "<id>", "ts": "ISO8601"}]
}
```

### 3.4 Persona Frontmatter (`personas/<id>/PERSONA.md`)

```yaml
---
id: claude-code
vendor: Anthropic
family: claude
source: ref-repo/Anthropic/Claude Code/Prompt.txt
sha256_12: abc123def456
invocations: ['claude-code', 'claude', 'cc', 'claudecode']
---
```

### 3.5 Ingest Spec (`scripts/ingest.py` `SPEC`)

```python
{
  "id": "string",
  "vendor": "string",
  "family": "string",
  "aliases": ["string"],
  "files": ["ref-repo-relative/path.txt"]
}
```

---

## 4. Constraints

- C1: Android Termux `aarch64` / Bionic libc — no `/bin`, `/usr/bin`
- C2: Persona payload capped at ~24 KB (head-preserving truncation)
- C3: Fuzzy match cutoff = 0.72 (tunable via `difflib.get_close_matches`)
- C4: Audit log is append-only; no rotation (manual cleanup)
- C5: `personas/` and `registry/` are generated (read-only for hand edits)

---

## 5. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| Latency | < 100 ms for resolution + persona load |
| Memory | < 10 MB resident |
| Size | Persona payload < 24 KB |
| Determinism | Same input → same persona id (fuzzy cutoff stable) |
| Auditability | Every switch/clear logged with timestamp + from/to |

---

## 6. Dependencies

- **Zero** third-party Python packages
- Standard library: `argparse`, `json`, `os`, `sys`, `time`, `difflib`, `pathlib`, `hashlib`, `re`

---

## 7. Testing

### Unit Tests (manual smoke)
```bash
# Resolver: exact match
python3 scripts/apa.py switch claude-code  # exit 0

# Resolver: alias match
python3 scripts/apa.py switch claude  # exit 0 → claude-code

# Resolver: fuzzy match
python3 scripts/apa.py switch cursr  # exit 0 → cursor-agent

# Resolver: no match
python3 scripts/apa.py switch nonexistent  # exit 2

# State: status reflects active
python3 scripts/apa.py switch agy >/dev/null && python3 scripts/apa.py status
# expect: ACTIVE persona = antigravity

# Clear: restore
python3 scripts/apa.py clear && python3 scripts/apa.py status
# expect: inactive

# Registry: integrity
python3 -c "import json; d=json.load(open('registry/agents.json')); assert len(d['agents'])==31; print('OK')"
```

### QA Analyzer
```bash
python3 ~/.gemini/config/skills/qa-analyzer/scripts/analyzer.py ~/Projects/agent-persona-adapter
```
Must report zero unmatched brackets / syntax errors.

---

## 8. Deployment

- **Local**: `python3 scripts/apa.py` works immediately after clone
- **Skill integration**: drop `skills/APA/SKILL.md` into host agent's skill directory
- **Hook integration**: add pre-session hook that reads `state/active.json` and prompts for resume
- **Cross-agent**: any agent that accepts system prompt injection can use the CLI

---

## 9. Versioning

- **Semantic**: `MAJOR.MINOR.PATCH`
- **1.0.0** (2026-10-28): initial implementation (31 personas, CLI, registry, state)
- **1.1.0** (planned): hook-based auto-resume, additional personas
- **2.0.0** (planned): web UI, persona editor, cross-session persistence with consent

---

## 10. Known Limitations

- L1: Persona prose is capped at 24 KB; long prompts truncated head-preserving
- L2: Fuzzy match is heuristic; may miss edge cases (mitigated by "did you mean")
- L3: No concurrent session support (single `state/active.json`)
- L4: No authentication/authorization (local single-user tool)
- L5: `ref-repo/` updates require manual re-ingest
