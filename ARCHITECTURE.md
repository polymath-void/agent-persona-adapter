# ARCHITECTURE — Agent Persona Adapter (APA)

## 1. Vision

One entry point. Any agent. Any persona. Instantly.

```
User: "@APA claude"
Host Agent: (loads claude persona) → acts as Claude Code for this session.
```

```
User: "/APA agy"
Host Agent: (loads Antigravity persona) → acts as Google Antigravity.
```

```
User: "/APA clear"
Host Agent: (restores native persona)
```

---

## 2. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│         "/APA <agent>"   or   "@APA <agent>"                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               TRIGGER RECOGNIZER (regex)                    │
│         pattern: (?:^|\s)(?:/|@)APA\s+([A-Za-z0-9._-]+)     │
└───────────┬─────────────────────────────────┬───────────────┘
            │ matched                         │ no match
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────────┐
│   APA RESOLVER (CLI)  │         │   Normal agent behavior   │
│   apa.py switch <id>  │         │   (native persona)        │
└───────────┬───────────┘         └───────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│              REGISTRY LOOKUP (registry/agents.json)          │
│  1. Exact id match     → claude-code                        │
│  2. Exact alias match  → claude → claude-code               │
│  3. Fuzzy match        → cursr → cursor-agent (cutoff .72)  │
│  4. No match           → exit 2 + "did you mean"            │
└───────────┬─────────────────────────────────────────────────┘
            │ persona id resolved
            ▼
┌─────────────────────────────────────────────────────────────┐
│           PERSONA PAYLOAD LOADER (personas/<id>/)            │
│  reads PERSONA.md → frontmatter + identity + source system  │
│  instructions + ADAPTER FLOOR                                │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│           SESSION CONTEXT INJECTOR                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ <!-- APA:HOST_PERSONA_SUPPRESSED=true -->            │   │
│  │ # ACTIVE PERSONA: <id> (<vendor>/<family>)           │   │
│  │ ## SOURCE SYSTEM INSTRUCTIONS                        │   │
│  │ ...full persona prose...                             │   │
│  │ ## ADAPTER FLOOR                                     │   │
│  │ ...safety + anti-hallucination rules...              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ HOST PERSONA SUPPRESSION PROTOCOL                    │   │
│  │ - Native identity not referenced                     │   │
│  │ - Native behavior overridden by persona              │   │
│  │ - Persona cannot override ADAPTER FLOOR              │   │
│  │ - Session-scoped only; no persistence                │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                  ACTING AS PERSONA                           │
│  The agent now operates with the injected persona's:         │
│  - Tone & communication style                                │
│  - Tool preferences & workflows                              │
│  - Naming conventions & heuristics                           │
│  - Domain expertise & reasoning patterns                     │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│              DEACTIVATION PATHWAYS                           │
│  - User: /APA clear / off / reset                           │
│  - Session end                                               │
│  - User: /APA <other-agent> (swap)                          │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│           HOST PERSONA RESTORED                              │
│  Native persona resumed; APA session ends.                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 Trigger Recognizer
- **Pattern**: `(?:^|\s)(?:/|@)APA\s+([A-Za-z0-9._-]+)`
- **Scope**: matches at start of line or after whitespace
- **Case-insensitive**: `/APA CLAUDE` ≡ `/APA claude`
- **Passive detection**: also triggers on "act as <agent>", "switch to <agent> persona"

### 3.2 APA Resolver (`scripts/apa.py`)
- **Function**: `switch(name)` — main entry
- **Input**: agent name/alias/fuzzy string
- **Output**: exit code + persona payload to stdout
- **State**: writes `state/active.json`
- **Audit**: appends to `state/audit.log`

### 3.3 Registry (`registry/agents.json`)
- **Structure**: `{ "agents": { "<id>": { ...metadata } } }`
- **31 personas** across 15+ vendors (Anthropic, OpenAI, Google, Cursor, Cline, etc.)
- **Generated by**: `scripts/ingest.py` (read-only; regenerate, don't hand-edit)

### 3.4 Persona Payload (`personas/<id>/PERSONA.md`)
- **Format**: Markdown with YAML frontmatter
- **Sections**:
  1. `---` frontmatter (id, vendor, family, source, sha256_12)
  2. `# PERSONA` heading
  3. `## IDENTITY` — one-line role statement
  4. `## SOURCE SYSTEM INSTRUCTIONS` — full extracted persona prose
  5. `## ADAPTER FLOOR` — non-negotiable safety/anti-hallucination layer

### 3.5 Session Context Injector
- **Mechanism**: prints the persona payload + suppression marker to stdout
- **Host responsibility**: reads the stdout, adopts the persona, suppresses native persona
- **Suppression marker**: `<!-- APA:HOST_PERSONA_SUPPRESSED=true -->`

### 3.6 Host Persona Suppression Protocol
When a persona is active:
- ✅ **DO**: act fully as the persona (tone, tools, workflows, heuristics)
- ✅ **DO**: keep ADAPTER FLOOR binding (safety > persona)
- ❌ **DON'T**: reference native identity/provider/model
- ❌ **DON'T**: revert to native behavior mid-session
- ❌ **DON'T**: let persona override ADAPTER FLOOR

If asked "what model are you", answer:
> *"This session is running the `<id>` persona via the Agent Persona Adapter."*

---

## 4. Data Flow

### Activation Flow
```
USER: /APA claude
  ↓
TRIGGER: regex matches → captures "claude"
  ↓
RESOLVER: switch("claude")
  ↓
REGISTRY: alias "claude" → id "claude-code"
  ↓
PERSONA: read personas/claude-code/PERSONA.md
  ↓
STATE: write state/active.json {active:"claude-code"}
  ↓
INJECT: print payload + suppression marker to stdout
  ↓
HOST: adopt persona, suppress native persona
  ↓
CONFIRM: 2-line status to user
```

### Swap Flow (persona already active)
```
USER: /APA cursor
  ↓
STATE: active="claude-code" → prev="claude-code", active="cursor-agent"
  ↓
INJECT: print cursor-agent payload
  ↓
HOST: drop claude persona, adopt cursor persona
```

### Clear Flow
```
USER: /APA clear
  ↓
STATE: active=null
  ↓
INJECT: print restore marker `<!-- APA:HOST_PERSONA_SUPPRESSED=false -->`
  ↓
HOST: resume native persona
```

---

## 5. Integration Points

### 5.1 OpenCode Skill Auto-Discovery
- Skill at `skills/APA/SKILL.md`
- OpenCode discovers skills in `.agents/skills/<id>/SKILL.md` or project `skills/`
- Once loaded, OpenCode recognizes the trigger pattern and follows the activation procedure

### 5.2 Antigravity Customization System
- Can be registered as an Antigravity skill
- Follows `agy-customizations` skill conventions

### 5.3 CLI-Only Mode (no skill integration)
- Users can run `scripts/apa.py switch <agent>` manually
- Read the printed payload, paste into any agent's context
- Works with ANY agent that accepts system prompt injection

### 5.4 Hook-Based Auto-Activation (optional)
- Pre-session hook: checks `state/active.json`
- If active persona found, prompts: *"Resume `<id>` persona? (y/n)"*
- On `y`, auto-injects persona without user re-invoking `/APA`

---

## 6. Safety & Compliance

### 6.1 Legal
- `ref-repo/` used for **research / educational / interoperability** purposes
- No proprietary claims; no trademark use
- Personas are behavioral abstractions, not vendor copies
- See `policy/PERSONA_POLICY.md`

### 6.2 Safety Floor (ADAPTER FLOOR — non-negotiable)
1. Never fabricate paths, APIs, versions, tests, URLs, commits
2. Never claim build/test passed without observed output
3. No `/bin`/`/usr/bin` on Termux — resolve via `$PREFIX/bin`
4. Destructive ops require human confirmation
5. Bounded searches only (fd/rg scoped)
6. Session-scoped only; no persistence without consent

### 6.3 Anti-Hallucination
- Persona prose is extracted verbatim from reference corpus
- No synthetic expansion or invention
- Provenance tracked via `sha256_12` in frontmatter + `SOURCE.json`
- See `guards/ANTI_HALLUCINATION.md`

---

## 7. Context Management

- **Persona size**: capped at ~24 KB (normalized, head-preserving truncation)
- **Session budget**: persona + host instructions + conversation history
- **Token estimation**: `len(text) // 4` (rough heuristic)
- **Overflow strategy**: truncate persona to head (behavioral directives live early)
- See `context/CONTEXT_MANAGEMENT.md`

---

## 8. Extension Points

### Adding a New Persona
1. Drop source prompt in `ref-repo/<vendor>/<agent>/Prompt.txt`
2. Add spec to `scripts/ingest.py` `SPEC` list:
   ```python
   {"id": "new-agent", "vendor": "Vendor", "family": "family",
    "aliases": ["alias1", "alias2"],
    "files": ["Vendor/Agent/Prompt.txt"]}
   ```
3. Run `python3 scripts/ingest.py`
4. Test: `python3 scripts/apa.py switch new-agent`

### Custom Persona (not from ref-repo)
1. Create `personas/<id>/PERSONA.md` manually with frontmatter
2. Add to `registry/agents.json`:
   ```json
   "<id>": {"vendor":"Custom","family":"custom","aliases":[...],
             "payload":"personas/<id>/PERSONA.md"}
   ```
3. Test: `python3 scripts/apa.py switch <id>`

---

## 9. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Zero-dependency** | Python 3.11 stdlib only; Termux/Bionic-safe |
| **Session-scoped** | No persistence outside `state/` + explicit resume prompt |
| **Safety > Persona** | ADAPTER FLOOR overrides any persona instruction |
| **Provenance-tracked** | Every persona has `source` + `sha256_12` |
| **Deterministic resolution** | Exact → alias → fuzzy; never invent |
| **Human-in-the-loop** | Destructive ops gated; no autonomous high-risk actions |

---

## 10. Success Criteria

- ✅ `/APA claude` instantly activates claude-code persona
- ✅ `@APA agy` activates antigravity persona via alias
- ✅ `/APA cursr` fuzzy-matches cursor-agent (cutoff 0.72)
- ✅ `/APA clear` restores host persona
- ✅ Native persona fully suppressed while APA persona active
- ✅ ADAPTER FLOOR never overridden by persona
- ✅ No fabrication; provenance tracked
- ✅ Zero third-party dependencies
