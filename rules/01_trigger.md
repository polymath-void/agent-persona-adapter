# RULE 01: Trigger Recognition

## 1. Canonical Regex

```
(?:^|\s)(?:/|@)APA\s+([A-Za-z0-9._-]+)
```

Matches:
- Start-of-line or whitespace-prefixed
- `/APA` or `@APA` (case-insensitive)
- Whitespace separator
- Capture group 1: agent name (alphanumeric, dot, underscore, hyphen)

## 2. Accepted Invocation Forms

| Form | Example | Notes |
|------|---------|-------|
| Slash | `/APA claude-code` | primary form |
| At-mention | `@APA antigravity` | for chat contexts |
| Alias | `/APA claude` | resolves via registry |
| Fuzzy | `/APA cursr` | difflib cutoff 0.72 |
| Uppercase | `/APA CLAUDE` | case-insensitive |
| Embedded | "please /APA cursor now" | mid-sentence match |

## 3. Passive Trigger Detection

Also activate when user says (case-insensitive, any order):
- "act as <agent>"
- "switch to the <agent> persona"
- "be <agent>"
- "impersonate <agent>"
- "roleplay as <agent>"

Passive triggers run the **same resolution procedure** as slash invocations.

## 4. Control Commands

| Command | Action |
|---------|--------|
| `/APA` (no arg) | list all registered personas |
| `/APA list` | list all registered personas |
| `/APA status` | show active persona + metadata |
| `/APA info <id>` | resolve + show metadata (no activation) |
| `/APA search <query>` | substring search over registry |
| `/APA clear` | deactivate, restore host persona |
| `/APA off` | synonym for clear |
| `/APA reset` | synonym for clear |

## 5. Non-Triggers

Do NOT activate APA on:
- `/aperture` (different command)
- `/apaches` (different command)
- `@APACHE` (different mention)
- `APA` alone (no slash/at prefix)

## 6. Ambiguity Resolution

If user says `/APA` with no argument:
- Print list of 31 personas (grouped by vendor)
- Show active persona (if any)
- Prompt: "Usage: `/APA <agent-name>`"

If user says `/APA <unknown>`:
- Run fuzzy match (cutoff 0.72)
- If match found: activate + report "resolved `<input>` → `<match>`"
- If no match: exit 2 with "did you mean: `<suggestions>`"
- **Never guess** a persona not in registry

## 7. Rule Priority

Trigger recognition has **highest priority**:
- Overrides normal conversation flow
- Overrides persona instructions (persona cannot disable APA triggers)
- Overrides host agent's default command handling

## 8. Implementation Reference

- Regex source: `skills/APA/SKILL.md` § 1
- Resolver logic: `scripts/apa.py::resolve()`
- Alias table: `registry/agents.json`
