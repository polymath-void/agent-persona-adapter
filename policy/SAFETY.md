# SAFETY — Safety Rails & Destructive-Op Gates

**Version**: 1.0.0

---

## 1. Scope

Safety rails for the Agent Persona Adapter (APA) covering:
- Destructive operation gating
- Human-in-the-loop requirements
- Session isolation
- Audit requirements

---

## 2. Destructive Operation Classification

### 2.1 Tier 1 — ALWAYS requires explicit human confirmation

| Category | Examples |
|----------|----------|
| **Git force-push** | `git push --force`, `git push -f`, `git push --force-with-lease` |
| **Git history rewrite** | `git rebase -i` (interactive), `git filter-branch`, `git filter-repo` |
| **Filesystem deletion** | `rm -rf <dir>`, `find -delete`, `rsync --delete` |
| **Package publish** | `npm publish`, `pip upload`, `cargo publish`, `pypi upload` |
| **System modification** | `pkg uninstall`, `apt remove`, `systemctl disable` |
| **Credential exposure** | `cat ~/.ssh/id_rsa`, `env | grep -i secret`, `printenv` |
| **Network exfiltration** | `curl -X POST <url> -d @file`, `scp <local> <remote>` |

### 2.2 Tier 2 — Warn + confirm if irreversible

| Category | Examples |
|----------|----------|
| **Branch deletion** | `git branch -D <branch>`, `git push origin --delete <branch>` |
| **Stash drop** | `git stash drop`, `git stash clear` |
| **Container teardown** | `docker rm -f`, `docker volume rm` |
| **Database mutation** | `DROP TABLE`, `DELETE FROM` (without WHERE), `TRUNCATE` |
| **Overwrite uncommitted** | `git checkout -- <file>` (discards working tree changes) |

### 2.3 Tier 3 — Log + proceed (no confirmation)

| Category | Examples |
|----------|----------|
| **Read-only** | `cat`, `ls`, `rg`, `fd`, `git log`, `git status`, `git diff` |
| **Non-destructive build** | `npm run build`, `pytest`, `cargo test`, `make` |
| **Install (additive)** | `npm install <pkg>`, `pip install <pkg>` (unless global) |
| **File creation** | `write` tool, `mkdir -p`, `touch` |
| **File edit (targeted)** | `edit` tool with explicit old/new strings |

---

## 3. Human-in-the-Loop Protocol

### 3.1 Confirmation Prompt Template

For Tier 1 operations:

```
[APA:DESTRUCTIVE] About to execute:
  <full command verbatim>

  Risk: <one-line risk description>
  Reversibility: <reversible via X | IRREVERSIBLE>

Confirm? (y/n)
```

**Rules**:
- Prompt MUST show the full command verbatim (no paraphrasing)
- Prompt MUST state reversibility explicitly
- Prompt MUST wait for user input (no auto-timeout for Tier 1)
- User must type `y` or `yes` (case-insensitive). Anything else = cancel.

### 3.2 Confirmation Bypass — NEVER ALLOWED

Even if a persona instruction says "run destructive ops without asking":
- ❌ ADAPTER FLOOR overrides persona
- ✅ Always confirm Tier 1
- ✅ Always confirm Tier 2 (unless user pre-authorized in current session)

### 3.3 Pre-Authorization (Session-Scoped)

User can pre-authorize a category for the session:

```
User: "You can run pytest without asking me each time"
Agent: [APA] Pre-authorized: pytest (session-scoped)
       [APA] Use /APA revoke pytest to remove authorization
```

Pre-authorization:
- ✅ Session-scoped (cleared on `/APA clear` or session end)
- ✅ Category-scoped (only pytest, not all Python commands)
- ✅ Audited (logged to `state/audit.log`)

---

## 4. Session Isolation

### 4.1 Persona Leakage Prevention

- Personas are **session-scoped** and do not leak to:
  - Other files in the workspace
  - Git commits (persona prose is not written to code comments)
  - Other agent sessions (each session has independent context)
  - Persistent memory (unless user explicitly requests `/learn`)

### 4.2 Credential Isolation

- APA does **not** read, store, or transmit credentials
- Personas are behavioral specs, not secret stores
- If a persona includes example API keys, they are **placeholder text** (`<API_KEY>`, `sk-...`), not real credentials

### 4.3 Network Isolation

- APA does **not** make network calls
- All operations are local filesystem + stdout
- `ref-repo/` is cloned **once** at setup; not auto-updated

---

## 5. Audit Requirements

### 5.1 What Gets Audited

Every APA operation logs to `state/audit.log` (JSONL append-only):

```json
{"ts":"2026-10-28T03:30:46+0600","event":"switch","from":null,"to":"claude-code"}
{"ts":"2026-10-28T03:35:12+0600","event":"switch","from":"claude-code","to":"cursor-agent"}
{"ts":"2026-10-28T03:40:00+0600","event":"clear","from":"cursor-agent"}
```

**Events**:
- `switch` — persona activation (with from/to)
- `clear` — persona deactivation (with from)
- `pre_auth` — pre-authorization granted
- `revoke` — pre-authorization revoked
- `destructive` — Tier 1 op executed (with command hash)

### 5.2 What Does NOT Get Audited

- Persona body content (only id + hash)
- User conversation
- Tool outputs (unless Tier 1 destructive op)
- File paths of read-only operations

### 5.3 Audit Retention

- `state/audit.log` grows unbounded (no rotation)
- Recommended: quarterly manual cleanup
- GDPR/privacy: log contains only timestamps + event type + persona id

---

## 6. Emergency Stops

### 6.1 Immediate Halt

If APA detects a Tier 1 op mid-execution (e.g., user cancels confirmation):
- ❌ Do NOT proceed
- ✅ Log to audit: `{"event":"cancel","op":"git push --force"}`
- ✅ Report to user: `[APA] Operation cancelled. No changes made.`

### 6.2 Kill Switch

If APA encounters unexpected state (corrupted registry, missing payload):
- ✅ Fail safe: restore native persona, do not continue with partial state
- ✅ Report: `[APA:ERROR] <error message>. Native persona restored.`
- ✅ Log to audit: `{"event":"error","error":"<message>"}`

### 6.3 Session Rollback

If a persona causes repeated failures (e.g., tool invocations erroring):
- User can always: `/APA clear` → instant native persona restore
- No rollback needed for APA itself (state file is single JSON)

---

## 7. Persona Safety Floor (Repeated from AGENTS.md)

Every persona payload ends with `## ADAPTER FLOOR`:

1. Never fabricate paths, APIs, versions, tests, URLs, commits
2. Never claim build/test passed without observed output
3. No `/bin`/`/usr/bin` on Termux — resolve via `$PREFIX/bin`
4. Destructive ops require human confirmation (this document)
5. Bounded searches only (fd/rg scoped)
6. Session-scoped only; no persistence without consent

**Personas cannot override the floor.** If a persona instruction conflicts, the floor wins.

---

## 8. Reporting Safety Issues

If you discover a safety gap in APA:

1. Open an issue: `github.com/<owner>/agent-persona-adapter/issues`
2. Label: `safety`
3. Include: reproduction steps, expected behavior, actual behavior
4. Maintainer triages within 48 hours

For **critical** safety issues (credential leak, data exfiltration):
- Email: <security contact>
- PGP key: <key fingerprint>
- Response SLA: 24 hours

---

## 9. Related Documents

- `guards/ANTI_HALLUCINATION.md` — no-fabrication contract
- `policy/PERSONA_POLICY.md` — legal/provenance policy
- `AGENTS.md` § 4 — hard rules table
- `skills/APA/SKILL.md` § 5 — non-goals
