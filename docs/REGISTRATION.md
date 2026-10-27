# REGISTRATION — Pre-Registration Map (All Ecosystems)

**Version**: 1.0.0
**Researched**: 2026-10-28 (official docs, live sources cited per entry)
**Machine-readable**: `registry/registrations.json`
**Executor**: `scripts/register.py`

> **Purpose**: Two universal standards now anchor the ecosystem —
> **Agent Skills** (`agentskills.io`, `SKILL.md` folders) and **AGENTS.md**
> (Linux Foundation AAIF, 60k+ repos). APA targets **both** plus every
> tool-native surface.
>
> ~70% of entries are `verified` against live docs; `BEST-EFFORT` entries are
> labeled honestly per `guards/ANTI_HALLUCINATION.md`.

---

## 1. Universal Standards

### 1.1 Agent Skills — `agentskills.io`
- **Format**: `<skill-dir>/SKILL.md` + YAML frontmatter (`name`, `description`)
- **Adopters**: Claude Code, OpenCode, Antigravity, Cline, Gemini CLI,
  GitHub Copilot (VS Code/CLI/app/cloud), Codex (experimental)
- **APA strategy**: every `personas/<id>/PERSONA.md` already conforms; the
  registrar re-emits frontmatter as `name: apa-<id>` + one-line `description`

### 1.2 AGENTS.md — Linux Foundation AAIF (`agents.md`)
- **Format**: plain Markdown at project root; global `~/.agents/AGENTS.md`
  (proposal: `~/.config/agents/AGENTS.md`)
- **Adopters**: Codex CLI, Cursor, Windsurf, Cline, Copilot, Junie, Kiro,
  Amp, Qwen, Augment, Roo, Trae, Warp, Replit
- **APA strategy**: managed marker block
  (`<!-- APA:BEGIN ... --> ... <!-- APA:END ... -->`) — idempotent,
  diff-able, cleanly removable

---

## 2. Per-Agent Registration Table

| Agent | Native surface(s) | Format | Status |
|---|---|---|---|
| **claude-code** | `.claude/skills/apa-<id>/SKILL.md`, `~/.claude/skills/`, `.claude/agents/apa-<id>.md`, `CLAUDE.md` | SKILL.md (name+desc) | verified |
| **cursor-agent** | `.cursor/rules/apa-<id>.mdc`, `~/.cursor/rules/`, `AGENTS.md` | MDC: `description`/`globs`/`alwaysApply: true` | verified |
| **antigravity** | `.agents/skills/apa-<id>/SKILL.md`, `~/.gemini/antigravity-cli/plugins/apa-<id>/`, `.agents/rules/`, `.agents/hooks.json` | SKILL.md + plugin.json | verified |
| **codex-cli** | `AGENTS.md` (root), `~/.codex/AGENTS.md`, `.agents/skills/` | AGENTS.md / SKILL.md | verified |
| **gemini-cli** | `~/.gemini/extensions/apa-<id>/{gemini-extension.json,GEMINI.md}`, `.gemini/GEMINI.md`, `~/.gemini/commands/apa/<id>.toml` | extension / GEMINI.md / TOML | verified |
| **opencode** | `.opencode/skills/apa-<id>/SKILL.md`, `.agents/skills/`, `~/.agents/skills/`, `~/.config/opencode/skills/`, `.claude/skills/` (compat) | SKILL.md | verified |
| **cline** | `.clinerules/apa-<id>.md`, `.cline/rules/`, `~/.cline/rules/`, `~/.cline/skills/`, `AGENTS.md` | merged .md rules | verified |
| **roo-code** | `.roomodes` (custom mode), `.roo/rules/`, `.roo/rules-apa-<id>/`, `~/.roo/custom_modes.yaml` | mode YAML (slug/roleDefinition/groups) | verified |
| **windsurf** | `.devin/rules/apa-<id>.md` (preferred), `.windsurf/rules/` (fallback), `~/.codeium/windsurf/memories/global_rules.md`, `AGENTS.md` | md per rule + activation mode | verified |
| **copilot** | `.github/copilot-instructions.md`, `.github/instructions/apa-<id>.instructions.md`, `.github/prompts/apa-<id>.prompt.md`, `.github/agents/apa-<id>.md`, `.github/skills/` | instructions/prompt/agent-profile/SKILL.md | verified |
| **kiro** | `.kiro/steering/apa-<id>.md`, `~/.kiro/steering/` | steering md (`inclusion: always/fileMatch/manual`) | verified |
| **junie** | `.junie/AGENTS.md`, `.junie/rules/<id>.md`, `.junie/memory/`, `AGENTS.md`, `~/.junie/AGENTS.md` | AGENTS.md / rules | verified |
| **devin** | `.devin/rules/apa-<id>.md`, `~/.devin/rules/` | md per rule + activation mode | verified |
| **amp** | `AGENTS.md` | AGENTS.md | verified |
| **augment** | `AGENTS.md` | AGENTS.md | verified |
| **qwen-code** | `QWEN.md` (fallback `AGENTS.md`) | context md | best-effort |
| **kilo-code** | `.kilocode/rules/<id>.md`, `AGENTS.md` | rules md | best-effort |
| **trae** | `.trae/rules/<id>.md`, `~/.trae/rules/` | rules md | best-effort |
| **warp-agent** | `AGENTS.md` (Warp workflows are cmd templates, not personas) | AGENTS.md | best-effort |
| **replit-agent** | `AGENTS.md` (cloud knowledge in-app) | AGENTS.md | best-effort |
| **hermes** | `AGENTS.md` | AGENTS.md | best-effort |
| **mimo-code** | `AGENTS.md` | AGENTS.md | best-effort |
| **cloud-only** | *no filesystem surface*: lovable, bolt-new, manus, notion-ai, perplexity, comet, lumo, traycer, qoder | paste `apa.py switch` output into app knowledge field | n/a |

---

## 3. Registrar Usage

```bash
cd ~/Projects/agent-persona-adapter

# List all registration targets
python3 scripts/register.py list

# Install persona into ONE agent's native surface
python3 scripts/register.py install claude-code --agent cursor-agent --project /path/to/repo

# Auto-detect every known agent surface in a project and fill them all
python3 scripts/register.py install claude-code --agent auto --project /path/to/repo

# Preview without writing
python3 scripts/register.py install claude-code --agent antigravity --project . --dry-run

# Check what's installed where
python3 scripts/register.py status claude-code --project /path/to/repo
```

### 3.1 Emitted Formats

| Target capability | Emission |
|---|---|
| `skill_md` | `apa-<id>/SKILL.md` with agentskills.io frontmatter |
| `rule_mdc` | `.mdc` with `alwaysApply: true` + managed marker block |
| `rules_md` | `<id>.md` with agent-appropriate frontmatter + marker block |
| `agents_md` | Managed `APA:BEGIN/END` block appended to AGENTS.md/CLAUDE.md/QWEN.md |
| `custom_mode` | Roo `.roomodes` entry (slug `apa-<id>`, roleDefinition = persona) |
| `agent_profile` | Copilot `.github/agents/apa-<id>.md` (name/description/tools frontmatter) |
| `extension` | Gemini `gemini-extension.json` + `GEMINI.md` |
| `plugin` | Antigravity `plugin.json` + `skills/apa-<id>/SKILL.md` (user-global, `--user`) |

### 3.2 Safety Properties

- **Idempotent**: re-install refreshes the managed block; never duplicates.
- **Managed markers**: every injected region carries
  `<!-- APA:BEGIN ... -->` / `<!-- APA:END ... -->` for clean removal.
- **No clobber**: refuses to overwrite non-JSON `.roomodes`.
- **Session-scoped by design**: registration makes the persona *available*;
  activation still requires the user's `/APA <id>` invocation.

---

## 4. Research Notes (2026-06 → 2026-10)

- **Gemini CLI → Antigravity CLI**: free tier replaced 2026-06-18; extensions
  still valid for Gemini CLI users; Antigravity uses `.agents/skills` +
  staged plugins at `~/.gemini/antigravity-cli/plugins/`.
- **Windsurf → Devin/Cascade**: `.devin/rules/` is now preferred over
  `.windsurf/rules/`; legacy `.windsurfrules` still read. Global rules cap
  6,000 chars; per-rule file cap 12,000 chars.
- **AGENTS.md**: originated at OpenAI (Aug 2025), now Linux Foundation AAIF;
  60k+ repos. Cross-tool (Cursor/Windsurf/Cline/Copilot/Junie/Kiro all read it).
- **Roo custom modes** are the closest native "persona" primitive (slug +
  roleDefinition + tool groups) — APA maps personas to modes 1:1.
- **Copilot agent profiles** (`.github/agents/*.md`) are the Copilot-native
  persona primitive (name/description/prompt/tools).

---

## 5. Verification

```bash
# registrar syntax
python3 -c "import ast; ast.parse(open('scripts/register.py').read()); print('OK')"

# registry integrity
python3 -c "import json; d=json.load(open('registry/registrations.json')); print(len(d['targets'])-1, 'targets OK')"

# end-to-end install into a scratch dir
T=$PREFIX/tmp/apa-e2e; rm -rf $T; mkdir -p $T
python3 scripts/register.py install claude-code --agent auto --project $T
python3 scripts/register.py status claude-code --project $T
rm -rf $T
```
