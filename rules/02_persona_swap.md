# RULE 02: Persona Swap Procedure

## 1. Strict Order of Operations

```
[1] PARSE    — extract agent name from trigger
[2] RESOLVE  — python3 scripts/apa.py switch <name>
[3] VALIDATE — check exit code (0=ok, 2=no-match, 3=missing-payload)
[4] INGEST   — read full stdout payload
[5] COMMIT   — adopt persona, suppress host persona
[6] CONFIRM  — emit 2-line status (do NOT re-print payload)
```

## 2. Step Details

### 2.1 PARSE
- Extract capture group 1 from regex
- Strip trailing punctuation (`.`, `,`, `!`, `?`)
- Lowercase for resolution

### 2.2 RESOLVE
```bash
python3 ~/Projects/agent-persona-adapter/scripts/apa.py switch <name>
```

Exit codes:
- **0** → persona found, payload on stdout
- **2** → no match; stderr has "did you mean" hint
- **3** → metadata exists but `personas/<id>/PERSONA.md` missing

### 2.3 VALIDATE
- Exit 0 → proceed to INGEST
- Exit 2 → **STOP**. Print hint to user: `[APA] No persona matches '<input>'. Did you mean: <suggestions>?`
- Exit 3 → **STOP**. Report: `[APA:ERROR] Persona payload missing for '<id>'. Run 'python3 scripts/ingest.py' to regenerate.`

### 2.4 INGEST
Read **entire** stdout of Step 2. It contains:
1. `<!-- APA:HOST_PERSONA_SUPPRESSED=true -->` marker
2. `# ACTIVE PERSONA: <id> (<vendor>/<family>)` header
3. `# invoke: [...]` list
4. YAML frontmatter (`---\n id: ...\n ---`)
5. `# PERSONA: <id>` heading
6. `## IDENTITY` section
7. `## SOURCE SYSTEM INSTRUCTIONS` (≤ 24 KB)
8. `## ADAPTER FLOOR` (non-negotiable)

### 2.5 COMMIT
- Mentally adopt the persona as your operating behavior
- Suppress native system persona (see `rules/03_host_suppression.md`)
- Keep ADAPTER FLOOR binding (see `rules/05_safety_floor.md`)

### 2.6 CONFIRM
Emit **exactly** 2 lines:

```
[APA] persona: <id> (<vendor>/<family>) — host persona suppressed for this session
[ACTION] /APA clear to restore
```

**Do NOT**:
- Re-print the persona body to the user (already loaded)
- Print the full frontmatter
- Add explanatory paragraphs

## 3. Swap While Already Active

If a persona is already active and user invokes `/APA <new-id>`:

```
[1] State: prev=<old-id>, active=<new-id>
[2] Load new persona payload (full replacement)
[3] Drop old persona from working context
[4] Adopt new persona
[5] Confirm: "[APA] switched: <old-id> → <new-id>"
```

**No double-injection**: the new payload fully replaces the old one.

## 4. Error Recovery

### 4.1 Payload File Missing (exit 3)
- Report error to user
- Suggest: `python3 scripts/ingest.py` to regenerate
- Do NOT continue with partial state

### 4.2 Registry Corrupted (JSON parse error)
- Fail safe: restore native persona
- Report: `[APA:ERROR] registry/agents.json corrupted. Native persona restored.`
- Suggest: `git checkout registry/agents.json` or re-run `ingest.py`

### 4.3 State File Corrupted
- Fail safe: restore native persona
- Delete corrupted `state/active.json`, create fresh `{"active": null}`
- Report warning to user

## 5. Performance Budget

| Phase | Target |
|-------|--------|
| PARSE (regex) | < 1 ms |
| RESOLVE (registry lookup) | < 5 ms |
| INGEST (read file) | < 20 ms |
| CONFIRM (emit 2 lines) | < 1 ms |
| **Total** | **< 100 ms** |

## 6. Rule Priority

- Higher than: normal conversation flow
- Higher than: host agent's default behavior
- Lower than: ADAPTER FLOOR (safety)

## 7. Implementation Reference

- Procedure: `skills/APA/SKILL.md` § 2
- Resolver: `scripts/apa.py::cmd_switch()`
- State write: `scripts/apa.py::_write_state()`
