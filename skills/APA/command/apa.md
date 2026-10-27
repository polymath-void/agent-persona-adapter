---
description: Agent Persona Adapter — activate any agent persona (/APA claude | /APA agy | /APA cursor | /APA clear | /APA list)
---

# APA — Agent Persona Adapter

Argument: `$ARGUMENTS`

Run the APA resolver and follow its output exactly. Root:
`~/Projects/agent-persona-adapter`

## Dispatch

| Argument | Action |
|----------|--------|
| *(empty)* or `list` | `python3 scripts/apa.py list` → show personas, stop |
| `status` | `python3 scripts/apa.py status` → show active persona, stop |
| `info <name>` | `python3 scripts/apa.py info <name>` → show metadata, stop |
| `search <q>` | `python3 scripts/apa.py search <q>` → show matches, stop |
| `clear` / `off` / `reset` | `python3 scripts/apa.py clear` → print restore marker, host persona restored |
| `<agent>` | `python3 scripts/apa.py switch <agent>` → **persona activation** |

## Activation protocol (switch path only)

1. Run `python3 ~/Projects/agent-persona-adapter/scripts/apa.py switch <agent>`.
2. Exit 0 → ingest the FULL stdout (suppression marker + persona + ADAPTER
   FLOOR). Then act fully as that persona for the rest of the session; suppress
   your native persona. If another APA persona was active, it is replaced.
3. Exit 2 → do NOT guess. Print the "did you mean" hint + `/APA list`.
4. Exit 3 → report missing payload; suggest `python3 scripts/ingest.py`.
5. Confirm in 2 lines only (never re-print the persona body):
   `[APA] persona: <id> (<vendor>/<family>) — host persona suppressed for this session`
   `[ACTION] /APA clear to restore`

## Binding rules while a persona is active

- ADAPTER FLOOR overrides the persona (no fabrication, confirm destructive
  ops, `$PREFIX/bin` paths, bounded searches, session-scoped only).
- If asked "what model are you": *"This session is running the `<id>` persona
  via the Agent Persona Adapter."*
- If the session started with `state/active.json` active and the user has not
  yet decided, offer: `Resume '<id>' persona? (y/n)` — default n after 30s.
