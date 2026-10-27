# SCHEMA — Registry, State, and Persona Schemas

## 1. Registry (`registry/agents.json`)

### 1.1 Top-Level Structure

```json
{
  "agents": {
    "<id>": { ...persona entry... }
  }
}
```

### 1.2 Persona Entry

```json
{
  "vendor": "Anthropic",
  "family": "claude",
  "aliases": ["claude", "cc", "claudecode", "anthropic"],
  "invocations": ["/APA claude-code", "@APA claude-code", "@APA claude", "@APA cc"],
  "payload": "personas/claude-code/PERSONA.md",
  "sha256_12": "abc123def456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vendor` | string | ✅ | Vendor name (e.g., "Anthropic", "OpenAI", "Google") |
| `family` | string | ✅ | Model family (e.g., "claude", "codex", "agy") |
| `aliases` | string[] | ✅ | Alternative names for fuzzy/exact matching |
| `invocations` | string[] | ✅ | User-facing invocation examples |
| `payload` | string | ✅ | Relative path to `PERSONA.md` |
| `sha256_12` | string | ✅ | 12-char content hash of normalized persona body |

### 1.3 Current Registry (31 Personas)

**Vendors**:
- Anthropic (claude-code)
- OpenAI (codex-cli)
- Google (antigravity, gemini-cli)
- Cursor (cursor-agent)
- Cline (cline)
- Roo (roo-code)
- Windsurf (windsurf)
- Qwen (qwen-code)
- GitHub (copilot)
- Sourcegraph (amp)
- Warp (warp-agent)
- ByteDance (trae)
- AWS (kiro)
- JetBrains (junie)
- Cognition (devin)
- Replit (replit-agent)
- Lovable (lovable)
- StackBlitz (bolt-new)
- Augment (augment)
- Kilo (kilo-code)
- Manus (manus)
- Qoder (qoder)
- Traycer (traycer)
- Notion (notion-ai)
- Perplexity (perplexity, comet)
- Nous (hermes)
- Proton (lumo)
- Xiaomi (mimo-code)

---

## 2. State (`state/active.json`)

### 2.1 Structure

```json
{
  "active": "claude-code | null",
  "prev": "cursor-agent | null",
  "activated_at": "2026-10-28T03:30:46+0600",
  "history": [
    {"from": "null | <id>", "to": "<id>", "ts": "ISO8601"}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `active` | string \| null | ✅ | Currently active persona ID (null = inactive) |
| `prev` | string \| null | ✅ | Previously active persona (for swap tracking) |
| `activated_at` | string | ✅ | ISO8601 timestamp of last activation |
| `history` | array | ✅ | Chronological list of all switches |

### 2.2 History Entry

```json
{
  "from": "null | claude-code",
  "to": "cursor-agent",
  "ts": "2026-10-28T03:35:12+0600"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | string \| null | Previous persona (null = first activation) |
| `to` | string | New persona ID |
| `ts` | string | ISO8601 timestamp |

### 2.3 Example State

**After `/APA claude`**:
```json
{
  "active": "claude-code",
  "prev": null,
  "activated_at": "2026-10-28T03:30:46+0600",
  "history": [
    {"from": null, "to": "claude-code", "ts": "2026-10-28T03:30:46+0600"}
  ]
}
```

**After `/APA cursor` (swap)**:
```json
{
  "active": "cursor-agent",
  "prev": "claude-code",
  "activated_at": "2026-10-28T03:35:12+0600",
  "history": [
    {"from": null, "to": "claude-code", "ts": "2026-10-28T03:30:46+0600"},
    {"from": "claude-code", "to": "cursor-agent", "ts": "2026-10-28T03:35:12+0600"}
  ]
}
```

**After `/APA clear`**:
```json
{
  "active": null,
  "prev": "cursor-agent",
  "activated_at": "2026-10-28T03:35:12+0600",
  "history": [
    {"from": null, "to": "claude-code", "ts": "2026-10-28T03:30:46+0600"},
    {"from": "claude-code", "to": "cursor-agent", "ts": "2026-10-28T03:35:12+0600"}
  ]
}
```

---

## 3. Audit Log (`state/audit.log`)

### 3.1 Format

JSONL (JSON Lines), append-only, one event per line.

### 3.2 Event Types

**Switch** (persona activation):
```json
{"ts":"2026-10-28T03:30:46+0600","event":"switch","from":null,"to":"claude-code"}
{"ts":"2026-10-28T03:35:12+0600","event":"switch","from":"claude-code","to":"cursor-agent"}
```

**Clear** (persona deactivation):
```json
{"ts":"2026-10-28T03:40:00+0600","event":"clear","from":"cursor-agent"}
```

**Floor Override** (ADAPTER FLOOR overrode persona):
```json
{"ts":"2026-10-28T03:32:00+0600","event":"floor_override","persona":"claude-code","rule":"no_fabrication","detail":"Persona claimed tests passed; floor required observed output"}
```

**Error**:
```json
{"ts":"2026-10-28T03:41:00+0600","event":"error","error":"registry/agents.json corrupted"}
```

### 3.3 Audit Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | string | ✅ | ISO8601 timestamp |
| `event` | string | ✅ | Event type (switch, clear, floor_override, error) |
| `from` | string \| null | for switch/clear | Previous persona |
| `to` | string | for switch | New persona |
| `persona` | string | for floor_override | Persona ID that triggered override |
| `rule` | string | for floor_override | Floor section violated |
| `detail` | string | optional | Human-readable detail |
| `error` | string | for error | Error message |

---

## 4. Persona (`personas/<id>/PERSONA.md`)

### 4.1 Frontmatter (YAML)

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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Persona ID (matches directory name) |
| `vendor` | string | ✅ | Vendor name |
| `family` | string | ✅ | Model family |
| `source` | string | ✅ | Path to source in `ref-repo/` |
| `sha256_12` | string | ✅ | 12-char content hash |
| `invocations` | string[] | ✅ | Invocation examples |

### 4.2 Body Structure

```markdown
# PERSONA: claude-code (Anthropic / claude)

## IDENTITY
You are now running the **claude-code** agent persona. Adopt the system
instructions below verbatim as your operating behavior for this session.

## SOURCE SYSTEM INSTRUCTIONS

[Extracted persona prose from ref-repo, ≤ 24 KB]

## ADAPTER FLOOR (non-negotiable, overrides persona below when conflicting)

[Fixed safety/anti-hallucination layer]
```

### 4.3 Size Constraints

- **Max body size**: 24,000 bytes (~6,000 tokens)
- **Truncation**: head-preserving (behavioral directives live early in system prompts)
- **Truncation marker**: `[...truncated by APA ingest: full source in ref-repo/...]`

---

## 5. Provenance (`personas/<id>/SOURCE.json`)

### 5.1 Structure

```json
{
  "id": "claude-code",
  "source": "ref-repo/Anthropic/Claude Code/Prompt.txt",
  "sha256_12": "abc123def456",
  "bytes": 13019,
  "note": "educational persona extraction — see policy/PERSONA_POLICY.md"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Persona ID |
| `source` | string | Relative path to source file |
| `sha256_12` | string | 12-char hash of normalized body |
| `bytes` | integer | Byte count of normalized body |
| `note` | string | Legal/provenance note |

---

## 6. Ingest Spec (`scripts/ingest.py::SPEC`)

### 6.1 Structure

```python
{
  "id": "claude-code",
  "vendor": "Anthropic",
  "family": "claude",
  "aliases": ["claude", "cc", "claudecode", "anthropic"],
  "files": [
    "Anthropic/Claude Code/Prompt.txt",
    "Anthropic/Claude Code 2.0.txt"
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Persona ID (becomes directory name) |
| `vendor` | string | ✅ | Vendor name |
| `family` | string | ✅ | Model family |
| `aliases` | string[] | ✅ | Alternative names for matching |
| `files` | string[] | ✅ | Source file paths (relative to `ref-repo/`), in priority order |

### 6.2 File Priority

If multiple files listed, ingest uses the **first existing** file. Fallback:
scan parent directory for any `.txt` or `.md` file (alphabetical order).

---

## 7. Schema Validation

### 7.1 Registry Validation

```bash
python3 -c "
import json
d = json.load(open('registry/agents.json'))
assert 'agents' in d
for pid, e in d['agents'].items():
    assert 'vendor' in e
    assert 'family' in e
    assert 'aliases' in e and isinstance(e['aliases'], list)
    assert 'invocations' in e and isinstance(e['invocations'], list)
    assert 'payload' in e
    assert 'sha256_12' in e
print(f'Registry valid: {len(d[\"agents\"])} personas')
"
```

### 7.2 State Validation

```bash
python3 -c "
import json
d = json.load(open('state/active.json'))
assert 'active' in d
assert 'prev' in d
assert 'activated_at' in d
assert 'history' in d and isinstance(d['history'], list)
for h in d['history']:
    assert 'from' in h
    assert 'to' in h
    assert 'ts' in h
print('State valid')
"
```

### 7.3 Persona Frontmatter Validation

```bash
python3 -c "
from pathlib import Path
import re
for p in Path('personas').glob('*/PERSONA.md'):
    text = p.read_text()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    assert m, f'Invalid frontmatter: {p}'
    fm = m.group(1)
    for field in ['id:', 'vendor:', 'family:', 'source:', 'sha256_12:', 'invocations:']:
        assert field in fm, f'Missing {field} in {p}'
print('Persona frontmatter valid')
"
```

---

## 8. Schema Evolution

### 8.1 Backward Compatibility

- **Minor schema changes**: add optional fields (no version bump)
- **Major schema changes**: breaking changes (version bump, migration script)

### 8.2 Migration Example (v1.0 → v1.1)

If adding `tags` field to registry:
```python
# scripts/migrate_v1_0_to_v1_1.py
import json
d = json.load(open('registry/agents.json'))
for pid, e in d['agents'].items():
    e.setdefault('tags', [])
json.dump(d, open('registry/agents.json', 'w'), indent=2)
```

---

## 9. Related Documents

- `docs/TRD.md` § 3 — interface definitions
- `scripts/apa.py` — state read/write implementation
- `scripts/ingest.py` — registry + persona generation
