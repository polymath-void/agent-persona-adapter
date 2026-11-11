# agent-persona-adapter (APA)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://python.org)
[![Personas: 42](https://img.shields.io/badge/Personas-42%20Active-brightgreen)](registry/agents.json)
[![Host Runtimes: 6](https://img.shields.io/badge/Host%20Runtimes-6%20Supported-purple)](hosts/)
[![Fidelity: 100% Passed](https://img.shields.io/badge/Fidelity%20Verification-100%25%20Grade%20A%2FB-success)](scripts/apa_render.py)
[![Dependencies: Zero](https://img.shields.io/badge/Dependencies-Zero%20(Stdlib%20Only)-orange)](scripts/apa.py)
[![Platform: Cross-Platform](https://img.shields.io/badge/Platform-Termux%20%7C%20Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)](https://github.com/polymath-void/agent-persona-adapter)
[![Corpus: Cited](https://img.shields.io/badge/Corpus-Cited%20%26%20Attributed-informational)](#citations--references)

> **One command. Any agent persona. Instantly.**
>
> `/APA claude` `/APA agy` `/APA cursor` `/APA codex` `/APA devin` `/APA windsurf` … 42 personas.
> Real agent persona adaptation with live host tool binding and multi-model portability — not raw simulation.

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

# Host detection & model adaptation
python3 scripts/apa.py hosts                  # detect current host runtime (antigravity, claude-code, etc.)
python3 scripts/apa.py models                 # list target model profiles & token budgets
python3 scripts/apa.py verify cursor-agent    # verify fidelity, coverage & zero-leak tool binding
python3 scripts/apa.py verify --all           # grade all 42 personas against active host

# Filter by capability
python3 scripts/apa.py list --tag browser     # 5 personas
python3 scripts/apa.py search tdd             # claude-code, opencode, roo-code

# Activate a persona (prints the model-adapted, host-bound payload)
python3 scripts/apa.py switch claude-code

# Target a specific model family or host explicitly
python3 scripts/apa.py switch cursor-agent --model claude
python3 scripts/apa.py switch cursor-agent --model small --budget 1200
python3 scripts/apa.py switch devin --host claude-code

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

# Rebuild and compile personas from ref-repo (custom.json survives)
python3 scripts/ingest.py
```

---

## Real Agent Persona Adapter vs. Raw Prompt Simulation

Traditional prompt adapters take a vendor's raw system prompt and dump it into an LLM context. This results in **prompt simulation**: the host model reads schemas for tools it cannot invoke (e.g., Cursor's `codebase_search` or Devin's `browser_click`), begins hallucinating XML tool calls as plain text, or fails when expected environment paths clash with the host runtime.

**APA compiles and adapts personas into real execution agents**:

```
Vendor Prompt (ref-repo/)
         │
         ▼
[apa_compiler.py]  ──► Canonical Persona Spec IR (personas/<id>/spec.json)
         │             • Identity statement & role abstraction
         │             • Capability ontology (read_file, edit_file, shell, semantic_search, etc.)
         │             • Directives classified into voice, workflow, code_change, tool_policy, safety
         │             • Directives scored by imperative strength (3=MUST/NEVER, 2=should, 1=imperative)
         │
         ▼
[apa_render.py]    ──► Dynamic Synthesis (Host Runtime × Target Model Profile)
         │
         ├── Host Runtime Profile (hosts/antigravity.json, claude-code.json, opencode.json, ...)
         │   • Live Tool Binding: persona tools dynamically map to host native tools
         │   • Zero Foreign Tool Leaks: unmapped/unavailable tools trigger graceful fallbacks
         │   • Execution Contract: instructs model to execute via host tools, not pretend
         │
         └── Target Model Profile (claude, gpt, gemini, open, small)
             • Claude: Structured XML blocks (<apa_persona>, <tool_binding>, <workflow>)
             • GPT / Gemini: High-adherence Markdown headings and task bullets
             • Open-weight: 2,500 token ceiling filtered for mid-tier open models
             • Small (<8B local): 1,200 token compact format containing only strength-3 hard rules
```

---

## Invocations

| Form | Example | Resolves to |
|------|---------|-------------|
| Natural prompt adapt | `adapt claude`, `adapt to cursor`, `apa adapt claude` | claude-code / cursor-agent |
| Passive mention | `act as claude code`, `switch to cursor`, `be antigravity` | claude-code / cursor-agent / antigravity |
| Direct CLI invocation | `apa claude`, `apa cursor-agent` | claude-code / cursor-agent |
| Slash command | `/APA claude-code` | claude-code |
| At-mention | `@APA antigravity` | antigravity |
| Alias | `/APA claude` | claude-code |
| Fuzzy match | `/APA cursr` | cursor-agent |
| Uppercase | `/APA CLAUDE` | claude-code |

**Control**: `apa list`, `apa status`, `apa info <id>`, `apa search <q>`, `apa clear`, `apa off`, `apa reset`

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
- Dynamic Trigger Rule: `~/.gemini/config/rules/apa_dynamic_persona.md` +
  `~/Projects/.agents/rules/apa_dynamic_persona.md`
- Active Context Injection: `~/.gemini/config/rules/apa_active_persona.md`

---

## Dynamic Context Auto-Injection & Live Telemetry Proof

### 1. Zero-Search Direct Execution Protocol
When a user issues conversational directives (`adapt claude`, `act as claude`, `apa claude`, `switch to claude`):
1. **Zero Scans**: The agent is bound by [`rules/apa_dynamic_persona.md`](rules/apa_dynamic_persona.md) to skip all tree scans, file searches, or architecture document reads.
2. **Dynamic Path Linking**: Direct execution of `apa switch <name>` without hardcoded directories. Resolves dynamically via `$PREFIX/bin/apa`, `apa` in `$PATH`, or `APA_ROOT`.
3. **Host Suppression & Floor**: The native host persona is suppressed for the session; the target persona instructions take total precedence over style and heuristics, while the immutable `ADAPTER FLOOR` preserves safety rails.

### 2. Live Context Auto-Injection Pipeline
- On `apa switch <id>` (or `apa adapt <id>`), the resolver writes the full payload to `state/active_persona.md` and atomically refreshes `~/.gemini/config/rules/apa_active_persona.md`.
- In Antigravity / OpenCode runtimes, rules in `~/.gemini/config/rules/` are auto-injected into `<user_rules>` in the agent prompt context on the next turn.
- On `apa clear` / `apa off`, the injected rule is deleted atomically, cleanly restoring native host persona with 0 token overhead and no cross-persona leakage.

### 3. Empirical Telemetry Proof (Live Session Transcript)
Telemetry captured from the live session transcript (`transcript.jsonl`) confirms accurate persona ingestion:

| Stage | Telemetry Metric | Observed Value | Validation Note |
|---|---|---|---|
| **Command Execution** (Step 176) | Exit code & output | `Exit: 0`, `ACTIVE: claude-code` | Host suppressed, tags recorded |
| **Audit Trail** (`state/audit.log`) | Event log | `{"event":"switch","from":null,"to":"claude-code"}` | Clean transition, zero residue |
| **Active State** (`state/active.json`) | State tracking | `"active": "claude-code"` | Preserved with transition history |
| **Context Injection** | File size | `14,532 bytes` (221 lines) | Mounted at `~/.gemini/config/rules/apa_active_persona.md` |
| **Prompt Re-Cache** (Step 181 ➔ 183) | Input Tokens | `2,524` ➔ `114,243` tokens | System prompt ingested newly synchronized rules |

```text
# Live verification output:
$ apa adapt claude | head -n 4
<!-- APA:HOST_PERSONA_SUPPRESSED=true -->
# ACTIVE PERSONA: claude-code (Anthropic)

$ apa status
APA status: ACTIVE persona = claude-code (Anthropic / claude)
  activated: 2026-10-28T06:05:42+0600
  tags: terminal, tdd, git-flow, refactoring, general
  host persona: SUPPRESSED for this session
```

---

## Documentation map

| Doc | Purpose |
|-----|---------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System blueprint, component specs, data flow |
| [`docs/TRD.md`](docs/TRD.md) | Tech stack, interfaces, constraints, NFRs |
| [`docs/PLAN.md`](docs/PLAN.md) | Phased roadmap (Phases 1–7 complete) |
| [`docs/APPFLOW.md`](docs/APPFLOW.md) | State machine, detailed flows |
| [`docs/SCHEMA.md`](docs/SCHEMA.md) | Registry, state, persona, audit schemas |
| [`policy/PERSONA_POLICY.md`](policy/PERSONA_POLICY.md) | Legal, provenance, consent |
| [`policy/SAFETY.md`](policy/SAFETY.md) | Destructive-op gates, human-in-the-loop |
| [`guards/ANTI_HALLUCINATION.md`](guards/ANTI_HALLUCINATION.md) | No-fabrication contract |
| [`context/CONTEXT_MANAGEMENT.md`](context/CONTEXT_MANAGEMENT.md) | Token budget, injection protocol |
| [`rules/`](rules/) | Executable behavioral rules & trigger specs |
| [`rules/apa_dynamic_persona.md`](rules/apa_dynamic_persona.md) | Dynamic trigger & context auto-injection rule |
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
python3 -c "import json; d=json.load(open('registry/agents.json')); assert len(d['agents'])==42; print('REGISTRY OK: 42 personas')"
```

---

## License

MIT — see [`LICENSE.md`](LICENSE.md).

Reference corpus (`ref-repo/`) is cloned from
[`x1xhlol/system-prompts-and-models-of-ai-tools`](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools)
for research/educational/interoperability purposes. See
[`policy/PERSONA_POLICY.md`](policy/PERSONA_POLICY.md).

---

## Citations & References

If you use or build upon the Agent Persona Adapter (APA) in your research, agent frameworks, or benchmarks, please cite the project and the underlying corpus:

### Academic Citation (BibTeX)

```bibtex
@software{agent_persona_adapter_2026,
  author       = {Polymath-Void and APA Contributors},
  title        = {Agent Persona Adapter (APA): A Zero-Dependency Model-Portable Persona and Tool-Binding Architecture for Autonomous Coding Agents},
  year         = {2026},
  publisher    = {GitHub},
  journal      = {GitHub repository},
  howpublished = {\url{https://github.com/polymath-void/agent-persona-adapter}}
}
```

### Upstream Reference Corpus

APA extracts its foundational persona directives from the curated open-source AI prompt corpus:
- **Corpus Repository**: [`x1xhlol/system-prompts-and-models-of-ai-tools`](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools)
- **License / Terms**: Cloned as a Git submodule in `ref-repo/` for educational, interoperability, and research analysis.

### Related Frameworks & Systems

- **Anthropic Claude Code**: [Claude Code Architecture & Tools](https://code.claude.com/docs)
- **Model Context Protocol (MCP)**: [Anthropic MCP Specification](https://modelcontextprotocol.io)
- **Google Antigravity & Gemini CLI**: [Google DeepMind Agent Architecture](https://antigravity.google)
- **OpenAI Codex & SWE-bench**: Jimenez et al., *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* (ICLR 2024).
- **Cursor IDE & Agent**: Anysphere, *Cursor Agentic Coding System* (2024–2025).
- **Cognition Devin**: Cognition AI, *Devin: The First AI Software Engineer* (2024).
