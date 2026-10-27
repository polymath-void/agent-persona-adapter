# PERSONA_POLICY — Legal, Provenance & Consent

**Version**: 1.0.0
**Effective**: 2026-10-28

---

## 1. Purpose

This policy governs the collection, transformation, and deployment of agent
personas extracted from the reference corpus (`ref-repo/`) for the Agent
Persona Adapter (APA).

---

## 2. Reference Corpus

**Source**: `github.com/x1xhlol/system-prompts-and-models-of-ai-tools`
**License**: See `ref-repo/LICENSE.md` (educational/research purpose)
**Scope**: System prompts and behavioral specifications for 40+ AI coding tools

### 2.1 Allowed Use
- ✅ Research and educational analysis
- ✅ Interoperability testing
- ✅ Behavioral abstraction for non-commercial tooling
- ✅ Academic study of agent design patterns

### 2.2 Prohibited Use
- ❌ Commercial redistribution of proprietary prompts
- ❌ Trademark or brand impersonation
- ❌ Claiming authorship of extracted personas
- ❌ Using personas to deceive users about actual model identity

---

## 3. Persona Transformation

### 3.1 Normalization Rules
- Strip excessive whitespace
- Cap at 24 KB (head-preserving truncation)
- Prepend APA identity header (see `scripts/ingest.py` `normalize()`)
- Append `## ADAPTER FLOOR` (non-negotiable safety layer)

### 3.2 Provenance Tracking
Every persona includes:
- `source`: original path in `ref-repo/`
- `sha256_12`: 12-char hash of normalized content
- `SOURCE.json`: full provenance metadata

### 3.3 Attribution
Personas are **behavioral abstractions**, not vendor copies. The APA:
- ✅ Preserves behavioral directives (tone, workflows, tools)
- ✅ Preserves safety instructions
- ✅ Preserves reasoning patterns
- ❌ Does NOT claim to be the vendor's product
- ❌ Does NOT use vendor trademarks in persona titles
- ❌ Does NOT imply official affiliation

---

## 4. User Consent

### 4.1 Explicit Invocation Required
Personas activate **only** via explicit user invocation:
- `/APA <agent>`
- `@APA <agent>`
- "act as <agent>" (passive detection)

No autonomous persona activation.

### 4.2 Session-Scoped
Personas are **session-scoped** and do not persist without explicit consent:
- Activation ends on `/APA clear`, `/APA off`, or session end
- Next session prompts: *"Resume `<id>` persona? (y/n)"*
- No silent re-activation across sessions

### 4.3 User Control
- ✅ User can swap personas mid-session (`/APA <other>`)
- ✅ User can clear persona (`/APA clear`)
- ✅ User can refuse resume prompt (drops persona permanently)
- ✅ User can inspect persona (`/APA info <id>`, read `personas/<id>/PERSONA.md`)

---

## 5. Safety Floor (Non-Negotiable)

The `## ADAPTER FLOOR` overrides **any** persona instruction that conflicts:

1. **No Fabrication**: Never invent file paths, APIs, versions, tests, URLs, commits
2. **No False Claims**: Never claim build/test passed without observed output
3. **Termux Paths**: No `/bin`, `/usr/bin` — resolve via `$PREFIX/bin`
4. **Human Confirmation**: Destructive ops (git push --force, rm -rf, publish)
   require explicit human approval first
5. **Bounded Search**: fd/rg scoped only; no unbounded `find /` or `grep -r /`
6. **Session-Scoped**: No persistence without consent; no cross-session leakage

Personas **cannot** disable or modify the ADAPTER FLOOR.

---

## 6. Liability

- APA is a **local, single-user tool** with no authentication
- Users are responsible for their own compliance with vendor terms of service
- APA makes **no warranties** about persona accuracy or fitness for purpose
- APA is provided "as is" under MIT License (see `LICENSE.md`)

---

## 7. Removal Requests

If a vendor or copyright holder requests removal of a persona:

1. Open an issue in the APA repository
2. Provide: persona id, source path, legal basis
3. Maintainer will remove within 5 business days
4. `ref-repo/` submodule may need independent removal (upstream)

---

## 8. Updates to This Policy

- **Minor**: typo fixes, clarifications (no version bump)
- **Major**: substantive changes to allowed/prohibited use (version bump)
- All changes require: commit message tagged `policy:` + CHANGELOG entry
