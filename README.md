# agent-persona-adapter (APA)

> **One command. Any agent persona. Instantly.**
>
> `/APA claude` `/APA agy` `/APA cursor` `/APA codex` `/APA gemini-cli` … 31 personas.

---

## What it does

APA is a **session-scoped persona injection system** for coding agents.

```
User: /APA claude
Agent: (loads the Claude Code system-prompt persona from the registry)
       (suppresses its own native persona for this session)
       (acts fully as the requested agent until /APA clear)
```

- **Trigger**: `/APA <agent>`, `@APA <agent>`, or "act as `<agent>`"
- **Lookup**: exact id → alias → fuzzy match against `registry/agents.json`
- **Push**: the persona's full system-skill is loaded into session context
- **Act**: the host agent adopts the persona and suppresses its own
- **Restore**: `/APA clear` (or session end) instantly restores the host persona

---

## Quick start

```bash
cd ~/Projects/agent-persona-adapter

# List all 31 personas
python3 scripts/apa.py list

# Activate a persona (prints the persona payload)
python3 scripts/apa.py switch claude-code

# Fuzzy match also works
python3 scripts/apa.py switch agy        # → antigravity
python3 scripts/apa.py switch cursr      # → cursor-agent

# Show what's active
python3 scripts/apa.py status

# Restore your native persona
python3 scripts/apa.py clear

# Rebuild personas from ref-repo
python3 scripts/ingest.py
```

---

## Invocations

| Form | Example | Resolves to |
|------|---------|-------------|
| Slash | `/APA claude-code` | claude-code |
| At-mention | `@APA antigravity` | antigravity |
| Alias | `/APA claude` | claude-code |
| Fuzzy | `/APA cursr` | cursor-agent |
| Uppercase | `/APA CLAUDE` | claude-code |
| Passive | "act as cursor" | cursor-agent |

**Control**: `/APA`, `/APA list`, `/APA status`, `/APA info <id>`, `/APA search <q>`, `/APA clear`

---

## Registered personas (31)

| Persona | Vendor | Aliases |
|---------|--------|---------|
| claude-code | Anthropic | claude, cc, claudecode |
| codex-cli | OpenAI | codex, openai-codex |
| antigravity | Google | agy, ag, google-antigravity |
| gemini-cli | Google | gemini, gcli |
| cursor-agent | Cursor | cursor, cur |
| opencode | OpenCode | oc, opn |
| cline | Cline | cl, clinerobot |
| roo-code | Roo | roo, roocode |
| windsurf | Windsurf | ws, cascade, codeium |
| copilot | GitHub | gh, github-copilot |
| qwen-code | Qwen | qwen, qw |
| amp | Sourcegraph | amper, sg |
| warp-agent | Warp | warp, wp |
| trae | ByteDance | bytedance, tr |
| kiro | AWS | aws-kiro, kr |
| junie | JetBrains | jb, jetbrains |
| devin | Cognition | cognition, dv |
| replit-agent | Replit | replit, rp |
| lovable | Lovable | lov, lv |
| bolt-new | StackBlitz | bolt, stackblitz |
| augment | Augment | aug, augment-code |
| kilo-code | Kilo | kilo, kl |
| manus | Manus | mn |
| qoder | Qoder | qd, quest |
| traycer | Traycer | tc |
| notion-ai | Notion | notion, nt |
| perplexity | Perplexity | pplx |
| comet | Perplexity | comet-assistant |
| hermes | Nous | nous, her |
| lumo | Proton | proton, lm |
| mimo-code | Xiaomi | mimo, xi |

Full metadata: [`registry/agents.json`](registry/agents.json)

---

## Architecture

```
User input ──► Trigger recognizer ──► APA resolver (CLI)
                                          │
                            registry/agents.json (exact → alias → fuzzy)
                                          │
                            personas/<id>/PERSONA.md (≤ 24 KB + FLOOR)
                                          │
                            state/active.json (session state + audit)
                                          │
                            stdout: persona payload + suppression marker
                                          │
                            Host agent adopts persona, suppresses native
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full blueprint.

---

## The safety floor

Every persona payload ends with a non-negotiable **ADAPTER FLOOR** that
overrides any persona instruction:

1. Never fabricate paths, APIs, versions, tests, URLs, commits
2. Never claim build/test passed without observed output
3. No `/bin`/`/usr/bin` on Termux — resolve via `$PREFIX/bin`
4. Destructive ops require explicit human confirmation
5. Bounded searches only (fd/rg scoped)
6. Session-scoped — no persistence without consent

See [`rules/05_safety_floor.md`](rules/05_safety_floor.md) and
[`guards/ANTI_HALLUCINATION.md`](guards/ANTI_HALLUCINATION.md).

---

## Repository layout

```
agent-persona-adapter/
├── AGENTS.md                  # binding rules for agents in this repo
├── ARCHITECTURE.md            # system blueprint
├── README.md                  # this file
├── docs/
│   ├── TRD.md                 # technical requirements
│   ├── PLAN.md                # phased roadmap
│   ├── APPFLOW.md             # state machine / invocation flow
│   └── SCHEMA.md              # registry + state + persona schemas
├── policy/
│   ├── PERSONA_POLICY.md      # legal / provenance / consent
│   └── SAFETY.md              # destructive-op gates, audit
├── guards/
│   └── ANTI_HALLUCINATION.md  # no-fabrication contract
├── context/
│   └── CONTEXT_MANAGEMENT.md  # token budget, push/pop rules
├── rules/
│   ├── 01_trigger.md
│   ├── 02_persona_swap.md
│   ├── 03_host_suppression.md
│   ├── 04_session_lifecycle.md
│   ├── 05_safety_floor.md
│   └── 06_context_management.md
├── skills/APA/SKILL.md        # canonical skill definition
├── scripts/
│   ├── apa.py                 # resolver + state CLI (stdlib only)
│   └── ingest.py              # ref-repo → personas builder
├── personas/<id>/             # 31 generated persona payloads
├── registry/agents.json       # id/alias → persona index
└── state/                     # active.json + audit.log (gitignored)
```

---

## Requirements

- Python 3.11+ (`$PREFIX/bin/python3` on Termux) — **stdlib only, zero deps**
- Android Termux `aarch64` / Bionic libc compatible
- No `/bin`, `/usr/bin` — all paths resolve via `$PREFIX`

---

## Adding a persona

**From the reference corpus:**

1. Drop the source prompt in `ref-repo/<vendor>/<agent>/Prompt.txt`
2. Add a spec to `scripts/ingest.py` `SPEC` list
3. `python3 scripts/ingest.py`

**Custom (hand-written):**

1. Create `personas/<id>/PERSONA.md` with the YAML frontmatter
2. Add an entry to `registry/agents.json`
3. `python3 scripts/apa.py switch <id>`

---

## Documentation map

| Doc | Purpose |
|-----|---------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System blueprint, component specs, data flow |
| [`docs/TRD.md`](docs/TRD.md) | Tech stack, interfaces, constraints, NFRs |
| [`docs/PLAN.md`](docs/PLAN.md) | Phased roadmap (Phase 1 complete) |
| [`docs/APPFLOW.md`](docs/APPFLOW.md) | State machine, detailed flows |
| [`docs/SCHEMA.md`](docs/SCHEMA.md) | Registry, state, persona, audit schemas |
| [`policy/PERSONA_POLICY.md`](policy/PERSONA_POLICY.md) | Legal, provenance, consent |
| [`policy/SAFETY.md`](policy/SAFETY.md) | Destructive-op gates, human-in-the-loop |
| [`guards/ANTI_HALLUCINATION.md`](guards/ANTI_HALLUCINATION.md) | No-fabrication contract |
| [`context/CONTEXT_MANAGEMENT.md`](context/CONTEXT_MANAGEMENT.md) | Token budget, injection protocol |
| [`rules/`](rules/) | 6 executable behavioral rules |
| [`skills/APA/SKILL.md`](skills/APA/SKILL.md) | Canonical skill definition |

---

## Verification

```bash
# QA analyzer (bracket/structure check)
python3 ~/.gemini/config/skills/qa-analyzer/scripts/analyzer.py ~/Projects/agent-persona-adapter

# Resolver smoke test
python3 scripts/apa.py switch claude-code >/dev/null && echo "SWITCH OK"
python3 scripts/apa.py clear >/dev/null && echo "CLEAR OK"

# Registry integrity
python3 -c "import json; d=json.load(open('registry/agents.json')); assert len(d['agents'])==31; print('REGISTRY OK: 31 personas')"
```

---

## License

MIT — see [`LICENSE.md`](LICENSE.md).

Reference corpus (`ref-repo/`) is cloned from
[`x1xhlol/system-prompts-and-models-of-ai-tools`](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools)
for research/educational/interoperability purposes. See
[`policy/PERSONA_POLICY.md`](policy/PERSONA_POLICY.md).
