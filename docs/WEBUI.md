# WEBUI — Phase 4 Blueprint (Cockpit)

**Version**: 0.1.0-draft
**Status**: PLANNED (Phase 4 in `docs/PLAN.md`)
**Principle**: The UI is a *window + throttle* onto the CLI engine. Every pixel
maps to state the CLI already owns (`registry/*.json`, `personas/`,
`state/active.json`, `state/audit.log`). Zero duplicate databases.

---

## 1. Why a UI (what CLI can't show)

| CLI strength | UI gap it leaves |
|---|---|
| Fast switch/clear | No *at-a-glance* view of what's active across time |
| `list` prints 42 rows | No browsing/filtering/comparison of 42 personas |
| `status` shows 1 persona | No *matrix* of persona × 22 registration surfaces |
| `audit.log` is JSONL | No timeline, no usage stats, no "which persona do I actually use" |
| `new/edit` in $EDITOR | No in-browser authoring with live preview |

The UI answers 5 questions instantly:
1. **Who am I right now?** (active persona + suppression state)
2. **What can I become?** (42-persona grid, tag/search filter)
3. **Where have I been deployed?** (registration matrix, per-surface status)
4. **What happened?** (audit timeline, usage stats)
5. **How do I extend it?** (custom persona authoring, bundle import/export)

---

## 2. Stack (Termux/LMK-aware)

| Layer | Choice | Rationale |
|---|---|---|
| Backend | FastAPI + uvicorn (`pip install --break-system-packages`) | thin async wrapper; imports `apa.py`/`register.py` as modules |
| Frontend | React (Vite) → **static build** served by FastAPI | no Node runtime at serve time; build once on device |
| State | existing JSON files, read/write via same code paths | single source of truth shared with CLI |
| Live | 2s polling of `/api/state` (WebSocket optional) | polling is LMK-cheap; WS deferred |
| Port | `127.0.0.1:8787` localhost-only | no LAN exposure; optional `APA_UI_TOKEN` bearer |

Memory budget: FastAPI + static ≈ 60–120 MB resident — safe on 12 GB
Dimensity 7200 Pro; no bundler/dev-server left running.

---

## 3. Screens (SPA routes)

### 3.1 `/` — COCKPIT (default)
```
┌────────────────────────────────────────────────────────────┐
│ APA COCKPIT            [42 personas] [22 surfaces]  8787●  │
├────────────────────────────────────────────────────────────┤
│  ● ACTIVE: claude-code (Anthropic/claude)                  │
│    HOST PERSONA: SUPPRESSED since 03:30 · prev: —          │
│    [ /APA clear ]  [ swap → … ]                            │
│  tags: terminal · tdd · git-flow        sha 8319763fd3ed  │
├────────────────────────────────────────────────────────────┤
│ QUICK SWITCH   [claude][agy][cursor][codex][gemini-cli]…   │
│ search… ▸ 5 browser personas · 3 tdd personas              │
├────────────────────────────────────────────────────────────┤
│ HUD: battery 34°C · audit 128 events · store 1.2 MB        │
└────────────────────────────────────────────────────────────┘
```
- Big active-persona banner (color = vendor hue)
- **SUPPRESSED** badge is the visual core of the whole product
- One-click clear + quick-switch chips + fuzzy search box
- Terminal-equivalent line under every action: `exec: apa.py switch claude-code`

### 3.2 `/personas` — GRID + INSPECTOR
- Card grid of all 42: vendor color chip, id, family, tag pills, byte/token size,
  origin badge (`ref-repo` / `custom` / `import`)
- Filters: tag dropdown (browser/tdd/terminal/…), vendor, free-text
- Click card → right drawer:
  - full `PERSONA.md` rendered (frontmatter as key-value table)
  - provenance: source path, `sha256_12`, bytes, `SOURCE.json`
  - actions: **Activate**, **Export .apa**, **Edit**, **Push →** (goes to matrix preselected)
- **Compare mode**: select 2 personas → side-by-side diff of body + metadata

### 3.3 `/registrations` — MATRIX (the killer view)
- Rows: 42 personas · Columns: 22 targets (claude-code, cursor, antigravity,
  gemini, opencode, cline, roo, windsurf, copilot, kiro, junie, devin, amp,
  qwen, augment, kilo, trae, warp, replit, hermes, mimo, +cloud-only)
- Cell states: `INSTALLED` (green) · `available` (gray) · `n/a cloud` (hatched)
- Row action: **push --all** · Column action: **fill column** (one persona → every surface)
- Cell click → detail popover: emitted file path, bytes, frontmatter preview,
  verified/BEST-EFFORT flag + source URL from `registrations.json`
- Cell INSTALLED → **remove** button (marker-aware uninstall)
- Project path selector at top (`--project`), `--dry-run` toggle before apply

### 3.4 `/audit` — TIMELINE + STATS
- Vertical timeline from `state/audit.log`: switch/clear/new/edit/export/
  import/floor_override/error, colored by event, from→to labels
- Session bands (from `state/active.json` history)
- Aggregate cards:
  - **most-used personas** (bar: switch counts)
  - **tag cloud** weighted by usage (which capability do I actually run?)
  - avg session duration, switches/day sparkline
  - **floor_override count** (safety telemetry — should trend to 0)

### 3.5 `/editor` — AUTHOR
- Split view: markdown editor (left) + rendered preview (right)
- Frontmatter form on top: id, vendor, family, aliases (chip input), tags
- Buttons: **Save** (→ `POST /api/personas`, sha recompute), **Activate**,
  **Export**, **Import .apa** (file drop)
- Live validation: 24 KB cap meter, duplicate-id check, alias collision check

---

## 4. API surface (thin wrapper — mirrors CLI 1:1)

| Method | Route | CLI equivalent |
|---|---|---|
| GET | `/api/personas?tag=&q=` | `apa.py list` / `search` |
| GET | `/api/personas/{id}` | `apa.py info` + payload |
| GET | `/api/state` | `apa.py status --json` |
| POST | `/api/switch {name}` | `apa.py switch` |
| POST | `/api/clear` | `apa.py clear` |
| POST | `/api/personas` | `apa.py new` |
| PUT | `/api/personas/{id}` | `apa.py edit` |
| GET | `/api/export/{id}` | `apa.py export` (download) |
| POST | `/api/import` | `apa.py import` (upload) |
| GET | `/api/registrations` | `register.py list` + status scan |
| POST | `/api/register {persona,agent,project,dry}` | `register.py install` |
| GET | `/api/audit?limit=` | `tail state/audit.log` |
| GET | `/api/stats` | aggregates over audit + history |

Every mutating response includes the `cli` command string it represents
(transparency rule: UI never does what CLI couldn't).

---

## 5. Non-goals (v1)

- ❌ Multi-user / auth (localhost single-user; optional bearer only)
- ❌ Remote access / tunnels (security policy)
- ❌ Editing ref-repo-derived payloads in place (shadow via custom.json instead)
- ❌ Replacing the CLI (UI is additive; headless servers keep using CLI)
- ❌ Real-time agent streaming (personas are pushed at session start, not streamed)

---

## 6. Build & run (Termux)

```bash
pip install --break-system-packages fastapi uvicorn
cd ~/Projects/agent-persona-adapter/ui && npm install && npm run build   # → ui/dist
python3 server/serve.py            # FastAPI serves api + ui/dist on :8787
termux-open-url http://127.0.0.1:8787
```

LMK guard: `serve.py` refuses to start if free RAM < 1 GB (`pmc status` probe).

---

## 7. Milestone breakdown

| Task | Size |
|---|---|
| `server/serve.py` — FastAPI app, imports apa/register as modules | S |
| Read-only endpoints (personas/state/audit/stats/registrations) | M |
| Mutating endpoints (switch/clear/new/edit/export/import/register) | M |
| UI shell + cockpit screen | M |
| Personas grid + inspector | M |
| Registration matrix | L |
| Audit timeline + stats | M |
| Editor screen | M |
| Polish: vendor hues, HUD strip, copy-to-clipboard for cloud paste | S |
