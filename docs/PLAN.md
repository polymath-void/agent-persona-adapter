# PLAN — Agent Persona Adapter (Phased Implementation Checklist)

**Version**: 1.0.0
**Status**: Phase 1 COMPLETE

---

## Phase 1 — Core Engine ✅ (2026-10-28)

- [x] Clone reference corpus (`ref-repo/`)
- [x] Design registry schema (`registry/agents.json`)
- [x] Implement resolver CLI (`scripts/apa.py`)
  - [x] Exact id match
  - [x] Alias match
  - [x] Fuzzy match (difflib, cutoff 0.72)
  - [x] "Did you mean" suggestions on no-match
  - [x] State read/write (`state/active.json`)
  - [x] Audit log (`state/audit.log`, JSONL)
- [x] Implement ingest pipeline (`scripts/ingest.py`)
  - [x] 31 persona specs (15+ vendors)
  - [x] Normalization (whitespace, 24 KB cap, head-preserving truncation)
  - [x] Frontmatter injection (id, vendor, family, source, sha256_12)
  - [x] ADAPTER FLOOR injection
  - [x] Provenance tracking (`SOURCE.json`)
- [x] Generate persona payloads (`personas/<id>/PERSONA.md`)
- [x] Smoke test resolver (exact, alias, fuzzy, clear)

**Deliverables**: 31 personas, working CLI, registry, state, audit

---

## Phase 2 — Skill Integration ✅ (v1.1.0, 2026-10-28)

- [x] Write `skills/APA/SKILL.md` (canonical trigger + activation spec)
- [x] **Web research**: all major agent registration formats (Claude Code,
  Cursor, Antigravity, Gemini CLI, Cline, Roo, Windsurf/Devin, Copilot, Kiro,
  Junie, Codex, Amp, Qwen, Augment, Trae + two universal standards
  `agentskills.io` / AGENTS.md-AAIF)
- [x] Machine-readable pre-registration map (`registry/registrations.json`,
  24 targets, verified/BEST-EFFORT flags + sources)
- [x] Universal registrar (`scripts/register.py`): skill_md, rule_mdc,
  rules_md, agents_md block, Roo custom_mode, Copilot agent_profile,
  Gemini extension, Antigravity plugin — idempotent, managed markers
- [x] Docs: `docs/REGISTRATION.md` (per-agent table + research notes)
- [x] OpenCode skill auto-discovery: `~/.agents/skills/APA` symlink
- [x] Antigravity skill registration: `~/.gemini/config/skills/APA` symlink
- [x] `/APA` slash command: `~/.config/opencode/commands/apa.md` (global) +
  `~/Projects/.opencode/commands/apa.md` (project)
- [x] Session resume: documented in skill + command (`Resume '<id>'? (y/n)`,
  default n after 30s); `state/active.json` persists
- [x] Smoke tests: 12-surface install, auto-detect, idempotency, QWEN fallback

---

## Phase 3 — Extended Personas ✅ (v1.2.0, 2026-10-28)

- [x] Extended corpus: +11 vendors (42 total) — cluely, codebuddy, emergent,
  leap-new, orchids, poke, same-dev, v0, xcode, zai-code, claude-chrome
- [x] Capability tags per persona (TAGS map in ingest; emitted to registry)
  — `apa.py list --tag browser`, `apa.py search tdd`
- [x] Custom persona support: `apa.py new <id> --vendor --family --aliases
  --tags` → scaffolds `personas/<id>/PERSONA.md` + `registry/custom.json`
  (custom shadows generated registry; survives `ingest.py` regeneration)
- [x] Persona editor: `apa.py edit <id>` → `$EDITOR`, recomputes sha256_12,
  updates SOURCE.json, shadows registry entry
- [x] Bundle export/import: `apa.py export <id> [-o f.apa]` /
  `apa.py import <f.apa> [--as newid] [--force]` — tar.gz with
  manifest.json (apa-bundle/1) + PERSONA.md + SOURCE.json
- [x] Registrar `--all` mode: push persona into EVERY known surface
  (project: claude/cursor/agents/opencode/cline/roo/devin/copilot/kiro/
  junie + user-global: Gemini extension, Antigravity plugin)
- [x] Smoke tests: tag search, new/edit/export/import roundtrip, `--all` e2e
  (12 surfaces + 2 home-global), cleanup verified

---

## Phase 4 — Web UI ✅ (v2.0.0, 2026-10-28)

**Built as zero-dep dual-mode SPA** (deviation from the FastAPI+React v1
blueprint — see `docs/WEBUI.md` §9; vanilla JS + stdlib `http.server`,
no npm, no pip, LMK-immune).

- [x] `server/serve.py` — stdlib ThreadingHTTPServer on 127.0.0.1:8787,
  imports `apa.py` as module (single source of truth), LMK guard
  (refuses <1 GB MemAvailable, `--no-guard` escape), SPA fallback
- [x] API routes (verified by urllib suite): /api/state, /api/personas
  (?tag=, ?q=), /api/personas/<id> (payload+source+versions), /api/switch,
  /api/clear, /api/audit, /api/stats, /api/registrations, /api/sessions,
  /api/export/<id> (.apa gzip bundle); every mutation returns its `cli:` string
- [x] 5-screen vanilla SPA (`ui/index.html` + `styles.css` + `app.js`):
  cockpit (active banner + SUPPRESSED badge + quick-switch + HUD),
  personas grid (tag/vendor/text filter + drawer inspector + export),
  registrations matrix (personas × surfaces), audit timeline + bar stats,
  editor (split author/preview + 24 KB cap meter + sha256_12 via SubtleCrypto)
- [x] Dual-mode boot: feature-detect `/api/state` → LIVE; else SNAPSHOT
  (embedded `public/snapshot.js`, drag-drop re-sync, IndexedDB virtual state,
  mutations = clipboard payload + downloadable artifacts)
- [x] JS logic parity golden-tested vs Python: resolver 43/43 (difflib
  recursive longest-match port, cutoff 0.72), sha256_12 byte-identical,
  JS ustar+gzip writer produces bundles `apa.py import` accepts (roundtrip)

**Exit criteria**: ✅ Browser cockpit (live + file://), CLI untouched

---

## Phase 5 — Cross-Session Persistence ✅ (v2.0.0, 2026-10-28)

- [x] Named sessions: `apa.py session list|use|current|export|import`
  (`state/sessions/<name>.json`, pointer `state/current-session`, default
  session keeps legacy `state/active.json` path — zero migration)
- [x] `apa.py resume` — re-activates the stored persona for a new host
  session (`--yes`/`--no`, interactive prompt exits 3 for host agents to
  relay); clears gracefully if the persona left the registry
- [x] `apa.py apply-patch <state-patch.json|->` — serverless-UI state
  artifact applier (validates persona exists, audits, `via: patch` history)
- [x] Export/import session JSON (backup or move across devices)
- [x] Cockpit sessions panel (live switching via POST /api/session/use)

**Deviations (honest)**: explicit consent flow replaced by the patch
protocol (mutations from untrusted surfaces must be applied consciously);
`polymath-core` `pm log` integration deferred to backlog.

**Exit criteria**: ✅ Named sessions + resume + patch, audit trail per session

---

## Phase 6 — Advanced Features ✅ (v2.0.0, 2026-10-28)

- [x] Persona blending: `apa.py blend <a> <b> [--weights 0.7,0.3]
  [--confirm]` — refuses without `--confirm` (coherence-risk gate), unions
  capability tags, registers as `blend-*` custom persona
- [x] A/B testing: `apa.py ab --a x --b y --task "..."` writes an eval kit
  (2 paste-ready briefs + README protocol + 5-axis scorecard incl. FLOOR
  compliance); `apa.py ab-record x y --winner z --note "..."` → audit
- [x] Analytics: `apa.py stats [--json]` — switches/clears/floor_overrides,
  most-switched personas, tag-usage, switches-per-day (ASCII bars); same
  data powers the cockpit /audit screen via /api/stats
- [x] Task-based recommendation: `apa.py suggest "<task text>"` — lexicon
  (LEXICON map) → capability-tag scoring + alias/vendor hits, ranked with
  reasons (deliberately NOT ML — deterministic, auditable, offline)
- [x] Persona versioning: `apa.py edit` versions the pre-edit payload
  (content-addressed `versions/<sha>.md`); `apa.py history <id>` lists;
  `apa.py revert <id> <sha>` restores (re-verions current, updates sha
  + SOURCE.json + registry shadow)
- [x] Editor screen in cockpit emits versioned `.apa` bundles (real
  sha256_12 computed in-browser via SubtleCrypto)

**Deviations (honest)**: ML recommendation replaced by deterministic lexicon
scoring (offline, zero-dep, explainable); cross-device sync = `.apa` bundles
+ serverless deploy (no encrypted sync service — out of scope, see backlog).

**Exit criteria**: ✅ Blend/AB/stats/suggest/versioning + cockpit parity

---

## Phase 7 — Dynamic Context Auto-Injection & Live Transcript Telemetry Proof ✅ (v2.1.0, 2026-10-28)

- [x] **Zero-Search Direct Execution**: natural language prompt triggers (`adapt <name>`, `act as <name>`, `apa <name>`, `switch to <name>`) immediately execute `apa switch <name>` without reading repo architecture docs or running tree scans.
- [x] **Dynamic Path Resolution**: eliminate all hardcoded directories. Dynamic resolution via `PREFIX` (`$PREFIX/bin/apa`), `APA_ROOT`, and standard library path resolution.
- [x] **Dynamic Rule Auto-Injection**: `scripts/apa.py` automatically injects `state/active_persona.md` and synchronizes `~/.gemini/config/rules/apa_active_persona.md` and workspace `.agents/rules/` on `switch`/`adapt`.
- [x] **Zero-Leakage Cleanup**: `apa clear` / `apa off` atomically removes active rule files, guaranteeing 0 residual token overhead and restoring native host persona.
- [x] **CLI Subcommand Aliases & Interception**: support `apa adapt`, `apa use`, `apa activate`, `apa off`, `apa reset`, and direct bare persona names (`apa claude`).
- [x] **Live Session Telemetry Proof**: verified via live transcript (`transcript.jsonl`) — Step 176 execution, audit trail transition, and Step 181 ➔ 183 prompt re-cache delta (`2,524` ➔ `114,243` input tokens), proving authentic context injection into `<user_rules>`.

**Exit criteria**: ✅ Zero-search triggers, dynamic rules auto-injection, live transcript telemetry validated.

---

## Backlog (Unscheduled)

- [x] Persona versioning — **done in Phase 6** (history/revert)
- [x] Dynamic context injection & telemetry — **done in Phase 7**
- [ ] `polymath-core` session tracker integration (`pm log` / `pmc events`)
- [ ] Encrypted cross-device sync service (current: `.apa` bundles + serverless deploy)
- [ ] Team sharing (multi-user registry with auth)
- [ ] Plugin system (persona providers as plugins)
- [ ] Voice persona (text-to-speech with persona-specific voice)
- [ ] Video persona (avatar with persona-specific appearance)

---

## Milestone Summary

| Phase | Version | Status | Key Feature |
|-------|---------|--------|-------------|
| 1 | 1.0.0 | ✅ DONE | Core engine, 31 personas, CLI |
| 2 | 1.1.0 | ✅ DONE | Skill integration, universal registrar |
| 3 | 1.2.0 | ✅ DONE | Extended personas (42), custom, bundles |
| 4 | 2.0.0 | ✅ DONE | Dual-mode Web UI cockpit SPA |
| 5 | 2.0.0 | ✅ DONE | Cross-session persistence & resume |
| 6 | 2.0.0 | ✅ DONE | Advanced features (blend, AB, stats, history) |
| 7 | 2.1.0 | ✅ DONE | Dynamic triggers, auto-injection, telemetry proof |

---

## Definition of Done (Per Phase)

A phase is "done" when:
- [ ] All checklist items complete
- [ ] QA analyzer reports zero errors
- [ ] Smoke tests pass (resolver, state, registry integrity)
- [ ] Documentation updated (README, AGENTS.md, TRD.md)
- [ ] CHANGELOG.md updated
- [ ] Git tag created (`v1.0.0`, `v1.1.0`, etc.)
