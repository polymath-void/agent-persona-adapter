---
description: Agent Persona Adapter — activate any agent persona (/APA claude | /APA agy | /APA cursor | /APA clear | /APA list)
---

# APA — Agent Persona Adapter

Argument: `$ARGUMENTS`

Run the APA resolver and follow its output exactly. Binary resolves dynamically from `$PREFIX/bin/apa` or `$PATH`.

## Dispatch

| Argument | Action |
|----------|--------|
| *(empty)* or `list` | `apa list` → show personas, stop |
| `status` | `apa status` → show active persona, stop |
| `info <name>` | `apa info <name>` → show metadata, stop |
| `search <q>` | `apa search <q>` → show matches, stop |
| `verify [<name>]` | `apa verify [<name>]` → show fidelity & capability verification, stop |
| `hosts` | `apa hosts` → list supported host runtimes & detected host, stop |
| `models` | `apa models` → list supported model target profiles, stop |
| `clear` / `off` / `reset` | `apa clear` → print restore marker, host persona restored |
| `adapt <agent>` / `<agent>` | `apa switch <agent>` → **persona activation** |

## Activation protocol (switch path only)

1. Run `apa switch <agent>` (or `apa adapt <agent>`).
2. Exit 0 → ingest the FULL stdout (suppression marker + persona + ADAPTER
   FLOOR). The active persona is also automatically synchronized into session rules.
   Act fully as that persona for the rest of the session; suppress your native persona.
   If another APA persona was active, it is cleanly replaced without conflict.
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
