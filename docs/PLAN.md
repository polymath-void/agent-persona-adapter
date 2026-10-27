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

## Phase 3 — Extended Personas ⬜ (v1.2.0)

- [ ] Add remaining 10+ vendors from `ref-repo/` (Windsurf, Warp, Copilot, Amp, etc.)
- [ ] Custom persona support (`personas/custom-*/PERSONA.md`, manual creation)
- [ ] Persona editor CLI (`apa.py edit <id>`, opens `$EDITOR`)
- [ ] Persona export/import (`.apa` bundle format)
- [ ] Persona search by capability ("find a persona that prefers pytest")

**Exit criteria**: 50+ personas, custom persona creation works

---

## Phase 4 — Web UI ⬜ (v2.0.0)

- [ ] FastAPI backend (`/api/personas`, `/api/switch`, `/api/status`)
- [ ] React frontend (persona grid, search, activate button)
- [ ] Real-time state indicator (active persona badge)
- [ ] Session viewer (see loaded personas across sessions)
- [ ] Persona diff tool (compare two personas side-by-side)

**Exit criteria**: Browser-based persona management, CLI still works

---

## Phase 5 — Cross-Session Persistence ⬜ (v2.1.0)

- [ ] Explicit consent flow for persistence ("Save persona for future sessions?")
- [ ] Multiple named sessions ("work", "personal", "project-X")
- [ ] Session switching (`apa.py session switch work`)
- [ ] Export session history (which personas used when)
- [ ] Integration with `polymath-core` session tracker (`pm log`)

**Exit criteria**: Named sessions, persistence with consent, audit trail

---

## Phase 6 — Advanced Features ⬜ (v3.0.0)

- [ ] Persona blending (with explicit warnings about incoherence)
- [ ] A/B testing (run same task under two personas, compare output)
- [ ] Persona analytics (which personas used most, session durations)
- [ ] ML-based persona recommendation (suggest persona based on task type)
- [ ] Cross-device sync (encrypted persona bundle sync via GitHub)

**Exit criteria**: Advanced persona orchestration, analytics dashboard

---

## Backlog (Unscheduled)

- [ ] Persona versioning (track persona changes over time)
- [ ] Team sharing (multi-user registry with auth)
- [ ] Plugin system (persona providers as plugins)
- [ ] Voice persona (text-to-speech with persona-specific voice)
- [ ] Video persona (avatar with persona-specific appearance)

---

## Milestone Summary

| Phase | Version | Status | Key Feature |
|-------|---------|--------|-------------|
| 1 | 1.0.0 | ✅ DONE | Core engine, 31 personas, CLI |
| 2 | 1.1.0 | ⬜ TODO | Skill integration, auto-resume |
| 3 | 1.2.0 | ⬜ TODO | Extended personas, custom |
| 4 | 2.0.0 | ⬜ TODO | Web UI |
| 5 | 2.1.0 | ⬜ TODO | Cross-session persistence |
| 6 | 3.0.0 | ⬜ TODO | Advanced features |

---

## Definition of Done (Per Phase)

A phase is "done" when:
- [ ] All checklist items complete
- [ ] QA analyzer reports zero errors
- [ ] Smoke tests pass (resolver, state, registry integrity)
- [ ] Documentation updated (README, AGENTS.md, TRD.md)
- [ ] CHANGELOG.md updated
- [ ] Git tag created (`v1.0.0`, `v1.1.0`, etc.)
