# APPFLOW — State Machine & Invocation Flow

## 1. Top-Level State Machine

```
                    ┌─────────────┐
         ┌─────────│   IDLE      │◄─────────────┐
         │         │ (no persona)│               │
         │         └──────┬──────┘               │
         │                │                      │
         │   /APA <agent> │                      │ /APA clear
         │   @APA <agent> │                      │ /APA off
         │   "act as X"   │                      │ session end
         │                ▼                      │
         │         ┌─────────────┐               │
         └────────►│  RESOLVING  │               │
                   └──────┬──────┘               │
                          │                      │
              ┌───────────┼───────────┐          │
              ▼           ▼           ▼          │
         ┌────────┐ ┌─────────┐ ┌─────────┐     │
         │ exact  │ │ alias   │ │ fuzzy   │     │
         │ match  │ │ match   │ │ match   │     │
         └───┬────┘ └────┬────┘ └────┬────┘     │
             │           │           │          │
             └───────────┼───────────┘          │
                         ▼                      │
                  ┌──────────────┐              │
                  │   NO MATCH   │──exit 2──────┘
                  │ (did you mean)│
                  └──────────────┘
                         │
                         ▼ match found
                  ┌──────────────┐
                  │   LOADING    │
                  │  persona.md  │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   ACTIVE     │──────────────────┐
                  │ (suppresses  │                  │
                  │ host persona)│   /APA <other>   │
                  └──────┬───────┘                  │
                         │                          │
                         │ /APA clear               │
                         │ session end              │
                         ▼                          ▼
                  ┌──────────────┐         ┌──────────────┐
                  │   RESTORING  │         │   SWAPPING   │
                  │ host persona │         │ new persona  │
                  └──────┬───────┘         └──────┬───────┘
                         │                        │
                         ▼                        ▼
                  ┌──────────────┐         ┌──────────────┐
                  │    IDLE      │◄────────│   ACTIVE     │
                  └──────────────┘         │ (new persona)│
                                           └──────────────┘
```

---

## 2. Detailed Flow: Activation

```
USER: "/APA claude"

[1] TRIGGER RECOGNIZER
    - regex: (?:^|\s)(?:/|@)APA\s+([A-Za-z0-9._-]+)
    - match: "claude"
    - pass to resolver

[2] APA RESOLVER
    - $ python3 scripts/apa.py switch claude
    - load registry/agents.json
    - check: id == "claude"? no
    - check aliases: "claude" in ["claude","cc","claudecode"]? yes
    - resolve to: claude-code

[3] PAYLOAD LOADER
    - read personas/claude-code/PERSONA.md
    - parse frontmatter
    - extract body

[4] STATE WRITER
    - read state/active.json: {active: null}
    - write: {active: "claude-code", prev: null, activated_at: "..."}
    - append to audit.log: {event: "switch", from: null, to: "claude-code"}

[5] CONTEXT INJECTOR
    - print to stdout:
      <!-- APA:HOST_PERSONA_SUPPRESSED=true -->
      # ACTIVE PERSONA: claude-code (Anthropic/claude)
      # invoke: ['/APA claude-code', '@APA claude']
      ---
      id: claude-code
      vendor: Anthropic
      ...
      ---
      # PERSONA: claude-code (Anthropic / claude)
      ## IDENTITY
      ...
      ## SOURCE SYSTEM INSTRUCTIONS
      You are an interactive CLI tool that helps users with software...
      ## ADAPTER FLOOR
      ...

[6] HOST AGENT
    - read full stdout
    - adopt persona (tone, workflow, tools, heuristics)
    - suppress native persona
    - emit confirmation:
      [APA] persona: claude-code (Anthropic/claude) — host persona suppressed for this session
      [ACTION] /APA clear to restore
```

---

## 3. Detailed Flow: Swap

```
PREVIOUS: active = "claude-code"

USER: "/APA cursor"

[1-4] Same as activation, but:
    - read state: {active: "claude-code"}
    - write: {active: "cursor-agent", prev: "claude-code", ...}
    - audit: {event: "switch", from: "claude-code", to: "cursor-agent"}

[5] CONTEXT INJECTOR
    - print cursor-agent payload (full replacement)

[6] HOST AGENT
    - drop claude-code persona from working context
    - adopt cursor-agent persona
    - emit confirmation:
      [APA] switched: claude-code → cursor-agent
      [ACTION] /APA clear to restore
```

---

## 4. Detailed Flow: Clear

```
PREVIOUS: active = "cursor-agent"

USER: "/APA clear"

[1] TRIGGER RECOGNIZER
    - match: "clear"
    - pass to clear handler

[2] APA CLEAR
    - $ python3 scripts/apa.py clear
    - read state: {active: "cursor-agent"}
    - write: {active: null, ...}
    - audit: {event: "clear", from: "cursor-agent"}

[3] CONTEXT INJECTOR
    - print restore marker:
      <!-- APA:HOST_PERSONA_SUPPRESSED=false -->
      # APA persona cleared (was: cursor-agent); host persona restored for this session

[4] HOST AGENT
    - drop cursor-agent persona from context
    - resume native system persona
    - emit confirmation:
      [APA] host persona restored (was: cursor-agent)
```

---

## 5. Detailed Flow: No Match

```
USER: "/APA nonexistent-agent"

[1] TRIGGER RECOGNIZER
    - match: "nonexistent-agent"
    - pass to resolver

[2] APA RESOLVER
    - $ python3 scripts/apa.py switch nonexistent-agent
    - load registry
    - check id: "nonexistent-agent" not in agents
    - check aliases: no match
    - fuzzy: difflib.get_close_matches("nonexistent-agent", pool, n=1, cutoff=0.72)
    - result: no match

[3] EXIT 2
    - stderr: "apa: no persona matches 'nonexistent-agent'"
    - stderr: "apa: did you mean: claude-code, cursor-agent, codex-cli" (if close)

[4] HOST AGENT
    - read exit code 2
    - emit error:
      [APA] No persona matches 'nonexistent-agent'.
      [APA] Did you mean: claude-code, cursor-agent, codex-cli?
      [APA] Run /APA list to see all 31 personas.
```

---

## 6. Detailed Flow: Session Resume

```
SESSION START
    - read state/active.json: {active: "claude-code"}
    - active != null → prompt user

[APA] Previous session ended with persona 'claude-code' active.
[APA] Resume 'claude-code' persona? (y/n)

USER: y

[1] APA RESOLVER
    - $ python3 scripts/apa.py switch claude-code
    - load persona, write state, emit payload

[2] HOST AGENT
    - adopt persona
    - emit confirmation

USER: n

[1] APA CLEAR
    - $ python3 scripts/apa.py clear
    - write state: {active: null}
    - emit restore marker

[2] HOST AGENT
    - resume native persona
    - emit confirmation

TIMEOUT (30s, no response)
    - default: n (drop persona)
    - run clear, resume native
```

---

## 7. Error States

### 7.1 Payload File Missing (exit 3)
```
$ python3 scripts/apa.py switch claude-code
apa: persona payload missing at /path/to/personas/claude-code/PERSONA.md

[APA:ERROR] Persona payload missing for 'claude-code'.
[APA] Run 'python3 scripts/ingest.py' to regenerate.
```

### 7.2 Registry Corrupted
```
$ python3 scripts/apa.py switch claude
Traceback: JSONDecodeError: Expecting value: line 1 column 1

[APA:ERROR] registry/agents.json corrupted.
[APA] Native persona restored.
[APA] Suggest: git checkout registry/agents.json
```

### 7.3 State File Corrupted
```
$ python3 scripts/apa.py status
Traceback: JSONDecodeError

[APA:ERROR] state/active.json corrupted. Reset to native persona.
```

---

## 8. Passive Trigger Flow

```
USER: "act as cursor now"

[1] PASSIVE DETECTOR
    - regex: /act as ([a-z-]+)/i
    - match: "cursor"
    - trigger APA activation

[2-6] Same as "/APA cursor" flow
```

---

## 9. Control Command Flows

### 9.1 `/APA` (no arg)
```
USER: "/APA"

[1] TRIGGER RECOGNIZER
    - match: no capture group (no agent name)
    - pass to list handler

[2] APA LIST
    - $ python3 scripts/apa.py list
    - print all 31 personas grouped by vendor

[3] HOST AGENT
    - emit list + usage hint
```

### 9.2 `/APA status`
```
USER: "/APA status"

[1] TRIGGER RECOGNIZER
    - match: "status"
    - pass to status handler

[2] APA STATUS
    - $ python3 scripts/apa.py status
    - print active persona + metadata

[3] HOST AGENT
    - emit status
```

### 9.3 `/APA search cursor`
```
USER: "/APA search cursor"

[1] TRIGGER RECOGNIZER
    - match: "search" (control command)
    - pass to search handler with query "cursor"

[2] APA SEARCH
    - $ python3 scripts/apa.py search cursor
    - substring match over registry
    - print: cursor-agent

[3] HOST AGENT
    - emit results
```

---

## 10. State Diagram (Formal)

```
States: {IDLE, RESOLVING, LOADING, ACTIVE, SWAPPING, RESTORING, ERROR}

Transitions:
  IDLE --/APA <agent>--> RESOLVING
  RESOLVING --match--> LOADING
  RESOLVING --no-match--> IDLE (exit 2)
  LOADING --file exists--> ACTIVE
  LOADING --file missing--> ERROR (exit 3)
  ACTIVE --/APA <other>--> SWAPPING
  SWAPPING --> ACTIVE (new persona)
  ACTIVE --/APA clear--> RESTORING
  RESTORING --> IDLE
  ACTIVE --session end--> IDLE (state persists)
  * --corrupted state--> ERROR (fail safe to IDLE)
```
