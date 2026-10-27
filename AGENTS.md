# AGENTS.md — agent-persona-adapter

> Umbrella binding rules for the **Agent Persona Adapter (APA)** project.
> Any agent operating inside this directory MUST load this file first.

---

## 1. Project Definition

**APA** is a session-scoped persona injection system. When a user invokes
`/APA <agent>` or `@APA <agent>` (e.g. `/APA claude`, `@APA agy`, `/APA cursor`),
the host agent:

1. Looks up `registry/agents.json` for the matched agent name/alias.
2. Reads `personas/<id>/PERSONA.md`.
3. Pushes that persona's full system-skill into the current session context.
4. **Suppresses its own native system persona** for the duration of the session
   and acts fully as the injected persona.
5. Restores its native persona on `/APA clear`, `/APA off`, or session end.

Reference corpus: `ref-repo/` (cloned from
`github.com/x1xhlol/system-prompts-and-models-of-ai-tools`).
Licensed for **research / educational / interoperability** use only — see
`policy/PERSONA_POLICY.md`.

---

## 2. Runtime Environment

- **OS**: Android Termux, `aarch64`, Bionic libc.
- **Python**: `$PREFIX/bin/python3` — stdlib only. No third-party deps.
- **No** `/bin` or `/usr/bin`. All binaries resolve under `$PREFIX/bin/`.
- **Searches**: `fd`/`rg` scoped to this directory. Never unbounded.
- **State**: `state/` (gitignored except `.gitkeep`).

---

## 3. Directory Layout

```
agent-persona-adapter/
├── AGENTS.md                    ← this file (binding rules)
├── ARCHITECTURE.md              ← system blueprint
├── README.md                    ← public entry
├── docs/
│   ├── TRD.md                   ← technical requirements doc
│   ├── PLAN.md                  ← phased implementation checklist
│   ├── APPFLOW.md               ← state machine / invocation flow
│   ├── SCHEMA.md                ← registry + state schemas
│   └── REGISTRATION.md          ← pre-registration map (all ecosystems)
├── policy/
│   ├── PERSONA_POLICY.md        ← legal/provenance/consent policy
│   └── SAFETY.md                ← safety rails & destructive-op gates
├── guards/
│   └── ANTI_HALLUCINATION.md    ← no-fabrication contract
├── context/
│   └── CONTEXT_MANAGEMENT.md    ← token budget & context push/pop rules
├── rules/
│   ├── 01_trigger.md            ← trigger recognition patterns
│   ├── 02_persona_swap.md       ← swap procedure
│   ├── 03_host_suppression.md   ← native-persona suppression protocol
│   ├── 04_session_lifecycle.md  ← activation / restore / persistence
│   ├── 05_safety_floor.md       ← ADAPTER FLOOR (non-negotiable)
│   └── 06_context_management.md ← context rules
├── skills/
│   └── APA/SKILL.md             ← canonical skill definition
├── scripts/
│   ├── apa.py                   ← core resolver + state CLI
│   ├── register.py              ← universal native-surface registrar
│   └── ingest.py                ← ref-repo → personas builder
├── personas/                    ← generated persona payloads (31 agents)
│   └── <id>/{PERSONA.md,SOURCE.json}
├── registry/
│   ├── agents.json              ← id/alias → persona index
│   └── registrations.json       ← pre-registration map (24 targets)
└── state/
    ├── active.json              ← current session persona
    └── audit.log                ← append-only switch trail
```

**Live host registrations** (this machine):
- `~/.agents/skills/APA` → symlink to `skills/APA/` (OpenCode + Cline + AGY)
- `~/.gemini/config/skills/APA` → symlink (Antigravity CLI global)
- `~/.config/opencode/commands/apa.md` + `~/Projects/.opencode/commands/apa.md`

---

## 4. Hard Rules (violation = task failure)

| # | Rule |
|---|---|
| R1 | Never fabricate a persona not in `registry/agents.json`. |
| R2 | Never claim a persona is active when `state/active.json` says otherwise. |
| R3 | `ADAPTER FLOOR` overrides any persona instruction that conflicts. |
| R4 | Destructive ops require explicit human confirmation, always. |
| R5 | Persona must not leak into files, commits, or other sessions. |
| R6 | `/APA clear` must always fully restore the host persona. |
| R7 | Every `scripts/` edit runs `qa-analyzer` + resolver smoke test before commit. |
| R8 | Persona payloads are read-only — regenerate via `ingest.py`, never hand-edit. |

---

## 5. Quick Commands

```bash
# Build / rebuild personas from ref-repo
python3 scripts/ingest.py

# List all registered personas
python3 scripts/apa.py list

# Activate a persona (prints payload + suppression marker)
python3 scripts/apa.py switch claude-code

# Show current state
python3 scripts/apa.py status

# Deactivate / restore host persona
python3 scripts/apa.py clear

# Fuzzy search
python3 scripts/apa.py search cursor

# Capability tags
python3 scripts/apa.py list --tag browser
python3 scripts/apa.py search tdd

# Custom persona lifecycle
python3 scripts/apa.py new <id> --vendor V --family f --aliases a,b --tags x,y
python3 scripts/apa.py edit <id>            # $EDITOR, refreshes sha + registry shadow
python3 scripts/apa.py export <id> -o f.apa # tar.gz bundle (manifest+persona+source)
python3 scripts/apa.py import f.apa --as <newid>

# Serverless-UI data plane (docs/WEBUI.md §8)
python3 scripts/apa.py snapshot                    # full -> ui/public/snapshot.json
python3 scripts/apa.py snapshot --public -o cat.json  # edge catalog (no state/audit)

# --- universal registrar (native surfaces) ---
# List registration targets (22 agents)
python3 scripts/register.py list

# Install persona into one agent's native format
python3 scripts/register.py install claude-code --agent cursor-agent --project /path/to/repo

# Auto-detect + fill every known agent surface in a project
python3 scripts/register.py install claude-code --agent auto --project /path/to/repo

# Push into EVERY surface incl. user-global (Gemini ext, AGY plugin)
python3 scripts/register.py install claude-code --agent all --project /path/to/repo

# Preview / audit
python3 scripts/register.py install claude-code --agent antigravity --project . --dry-run
python3 scripts/register.py status claude-code --project /path/to/repo
```

---

## 6. Verification Gate

Before any multi-file edit is considered complete:

```bash
python3 ~/.gemini/config/skills/qa-analyzer/scripts/analyzer.py ~/Projects/agent-persona-adapter
python3 scripts/apa.py switch claude-code >/dev/null 2>&1 && echo "SWITCH OK"
python3 scripts/apa.py clear >/dev/null 2>&1 && echo "CLEAR OK"
python3 -c "import json; d=json.load(open('registry/agents.json')); assert d['agents']; print('REGISTRY OK')"
```

All four must print OK before declaring done.
