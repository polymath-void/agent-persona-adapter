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

# List all 42 personas
python3 scripts/apa.py list

# Filter by capability
python3 scripts/apa.py list --tag browser     # 5 personas
python3 scripts/apa.py search tdd             # claude-code, opencode, roo-code

# Activate a persona (prints the persona payload)
python3 scripts/apa.py switch claude-code

# Fuzzy match also works
python3 scripts/apa.py switch agy        # → antigravity
python3 scripts/apa.py switch cursr      # → cursor-agent

# Show what's active
python3 scripts/apa.py status

# Restore your native persona
python3 scripts/apa.py clear

# Custom persona lifecycle
python3 scripts/apa.py new my-agent --vendor Acme --family custom \
        --aliases ma --tags terminal,tdd
python3 scripts/apa.py edit my-agent          # opens $EDITOR, versions old copy
python3 scripts/apa.py export my-agent -o my-agent.apa
python3 scripts/apa.py import my-agent.apa --as my-agent-v2
python3 scripts/apa.py history my-agent       # content-addressed versions
python3 scripts/apa.py revert my-agent <sha>

# Named sessions (cross-session persistence)
python3 scripts/apa.py session list           # * marks current
python3 scripts/apa.py session use work       # create/switch named session
python3 scripts/apa.py resume                 # re-activate stored persona (--yes/--no)
echo '{"active":"claude-code"}' | python3 scripts/apa.py apply-patch -

# Advanced: analytics, recommendation, blending, A/B
python3 scripts/apa.py stats                  # switches/tags/days (ASCII bars)
python3 scripts/apa.py suggest "write pytest tests for my CLI"
python3 scripts/apa.py blend claude-code cursor-agent --weights 0.6,0.4 --confirm
python3 scripts/apa.py ab --a agy --b codex --task "fix a PTY bug"
python3 scripts/apa.py ab-record antigravity codex-cli --winner antigravity

# Web UI data plane (docs/WEBUI.md)
python3 scripts/apa.py snapshot --js          # data plane for the cockpit SPA

# Rebuild personas from ref-repo (custom.json survives)
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

## Registered personas (42)

<details>
<summary>Original 31 (click to expand)</summary>

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
</details>

**Phase 3 additions**: cluely · codebuddy (Tencent) · emergent · leap-new ·
orchids · poke · same-dev · v0 (Vercel) · xcode (Apple) · zai-code (Zhipu) ·
claude-chrome (Anthropic)

Every persona carries **capability tags** (`terminal`, `tdd`, `browser`,
`spec-driven`, …) — filter with `apa.py list --tag <tag>` or search with
`apa.py search <tag>`.

Full metadata: [`registry/agents.json`](registry/agents.json)

---

## Web UI (cockpit) — zero-dep, dual-mode

A 5-screen cockpit over the same engine — **no npm, no pip, no build step**:

```bash
# LIVE mode — full cockpit on this device (stdlib http.server, localhost only)
python3 server/serve.py                    # LMK guard: refuses < 1 GB free RAM
termux-open-url http://127.0.0.1:8787

# SNAPSHOT mode — zero daemon; open ui/index.html via file:// or any static host
python3 scripts/apa.py snapshot --js       # regenerate ui/public/snapshot.{json,js}
```

Boot-time feature detection: `/api/state` reachable → **LIVE** (mutations hit
real state files, every response carries its `cli:` equivalent). Unreachable →
**SNAPSHOT** (data from embedded `snapshot.js`, drag-drop re-sync, mutations
become clipboard payloads + downloadable artifacts you apply with the CLI).
`--public` snapshot strips state/audit → publishable edge catalog.

Screens: **Cockpit** (active persona + HOST SUPPRESSED badge, quick-switch) ·
**Personas** (42-card grid, filters, drawer inspector, export `.apa`) ·
**Registrations** (personas × surfaces matrix) · **Audit** (timeline + usage
bars) · **Editor** (author custom personas, real `sha256_12` via SubtleCrypto).

The JS resolver is golden-tested 43/43 against Python difflib, and
bundles written by the JS TAR writer import cleanly via `apa.py import`.
Spec + deviation record: [`docs/WEBUI.md`](docs/WEBUI.md).

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

## Pre-registration (native surfaces)

APA can push any persona into any agent's **native** registration format —
not just the session CLI. Researched map lives in
[`registry/registrations.json`](registry/registrations.json) +
[`docs/REGISTRATION.md`](docs/REGISTRATION.md) (24 targets, verified flags).

```bash
# What can I register into?
python3 scripts/register.py list

# Install the claude persona as a Cursor always-on rule
python3 scripts/register.py install claude-code --agent cursor-agent --project ~/myrepo
#   → ~/myrepo/.cursor/rules/apa-claude-code.mdc  (alwaysApply: true)

# Fill EVERY detected agent surface in a project at once
python3 scripts/register.py install claude-code --agent auto --project ~/myrepo
#   → .claude/skills/, .cursor/rules/, .agents/skills/, .opencode/skills/,
#     .clinerules/, .roomodes (Roo custom mode), .devin/rules/,
#     .kiro/steering/, .github/agents/ (Copilot), AGENTS.md block, …

# Push into EVERY known surface incl. user-global (Gemini extension,
# Antigravity plugin) — one command, full pre-registration
python3 scripts/register.py install claude-code --agent all --project ~/myrepo

# Preview / audit
python3 scripts/register.py install claude-code --agent kiro --project . --dry-run
python3 scripts/register.py status claude-code --project ~/myrepo
```

**Native formats emitted**: agentskills.io `SKILL.md`, Cursor `.mdc`
(alwaysApply), Roo custom modes (`.roomodes` persona mode), Copilot agent
profiles (`.github/agents/`), Gemini extensions (`gemini-extension.json` +
`GEMINI.md`), Antigravity plugins, Kiro steering, Junie rules, managed
AGENTS.md blocks. All idempotent with `APA:BEGIN/END` markers.

**Cloud-only agents** (lovable, bolt-new, manus, notion-ai, perplexity,
comet, lumo, traycer, qoder): run `apa.py switch <id>` and paste the payload
into the app's knowledge field.

### Live-registered on this machine

- `~/.agents/skills/APA` → `skills/APA/SKILL.md` (OpenCode + Cline + AGY)
- `~/.gemini/config/skills/APA` → symlink (Antigravity CLI global)
- `/APA` slash command: `~/.config/opencode/commands/apa.md` +
  `~/Projects/.opencode/commands/apa.md`

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
