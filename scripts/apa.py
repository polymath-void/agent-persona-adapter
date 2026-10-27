#!/usr/bin/env python3
"""APA — Agent Persona Adapter core resolver.

Registry lookup (exact/alias/fuzzy), session state, persona push/pop,
host-persona suppression markers, capability tags, custom personas,
editor, and .apa bundle export/import.

Zero third-party deps (Termux/Python 3.11 stdlib only).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry" / "agents.json"
CUSTOM_REGISTRY = ROOT / "registry" / "custom.json"
PERSONAS = ROOT / "personas"
STATE_DIR = ROOT / "state"
SESSION_STATE = STATE_DIR / "active.json"
AUDIT = STATE_DIR / "audit.log"

# --- host suppression markers -------------------------------------------
SUPPRESS_ON = "<!-- APA:HOST_PERSONA_SUPPRESSED=true -->"
RESTORE_ON = "<!-- APA:HOST_PERSONA_SUPPRESSED=false -->"

FLOOR_TEMPLATE = """
## ADAPTER FLOOR (non-negotiable, overrides persona above when conflicting)
The persona above governs tone, workflow, tools, and heuristics ONLY.
1. Never fabricate: file paths, APIs, versions, test results, URLs, commits.
2. Never claim a build/test passed without observed terminal output.
3. No `/bin` or `/usr/bin` paths on Android Termux — resolve via `$PREFIX/bin`.
4. Destructive ops (git push --force, rm -rf, package publish) require explicit
   human confirmation first.
5. Bounded searches only (fd/rg scoped); never unbounded `find /` or `grep -r /`.
6. Session-scoped persona: ends on `/APA clear` or session end.
---
"""


def _read_json(p: Path, default: dict) -> dict:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"apa: WARNING {p} corrupted, ignoring", file=sys.stderr)
    return default


def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_registry() -> dict:
    """Merge generated registry (agents.json) + user custom registry (custom.json).

    custom.json shadows agents.json on id conflict, so hand-edited personas
    survive `ingest.py` regeneration.
    """
    base = _read_json(REGISTRY, {"agents": {}}).get("agents", {})
    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}}).get("agents", {})
    merged = dict(base)
    merged.update(custom)
    return {"agents": merged, "_custom_ids": set(custom.keys())}


def _registry_source(pid: str) -> Path:
    """Which registry file owns this persona id."""
    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}}).get("agents", {})
    return CUSTOM_REGISTRY if pid in custom else REGISTRY


SESSIONS_DIR = STATE_DIR / "sessions"
CURRENT_SESSION = STATE_DIR / "current-session"


def _current_session_name() -> str:
    return _read_json(CURRENT_SESSION, {"session": "default"}).get("session", "default")


def _state_file() -> Path:
    name = _current_session_name()
    return SESSION_STATE if name == "default" else SESSIONS_DIR / f"{name}.json"


def _write_state(st: dict) -> None:
    _write_json(_state_file(), st)


def _read_state() -> dict:
    st = _read_json(_state_file(), {"active": None, "prev": None, "history": []})
    st.setdefault("history", [])
    return st


def _audit(event: str, detail: dict) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **detail}
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _split_persona(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2).strip()


# --- resolution ---------------------------------------------------------
def resolve(name: str, reg: dict | None = None) -> tuple[str | None, dict]:
    """Match an agent name/alias to a persona id. Returns (id, entry)."""
    reg = reg or _load_registry()
    agents = reg["agents"]
    low = name.strip().lower()

    if low in agents:
        return low, agents[low]
    for aid, entry in agents.items():
        for alias in entry.get("aliases", []):
            if alias.lower() == low:
                return aid, entry
    pool = list(agents.keys())
    for aid, entry in agents.items():
        pool.extend(a.lower() for a in entry.get("aliases", []))
    close = difflib.get_close_matches(low, pool, n=1, cutoff=0.72)
    if close:
        hit = close[0]
        if hit in agents:
            return hit, agents[hit]
        for aid, entry in agents.items():
            if hit in [a.lower() for a in entry.get("aliases", [])]:
                return aid, entry
    return None, {}


def persona_path(pid: str) -> Path:
    return PERSONAS / pid / "PERSONA.md"


def cmd_list(args) -> int:
    reg = _load_registry()
    state = _read_state()
    active = state.get("active")
    agents = reg["agents"]
    tag = getattr(args, "tag", None)
    if tag:
        agents = {k: v for k, v in agents.items() if tag in v.get("tags", [])}
    if args.json:
        print(json.dumps({"active": active, "agents": sorted(agents)}, indent=2))
        return 0
    scope = f" [tag: {tag}]" if tag else ""
    print(f"APA registry — {len(agents)} personas{scope}  [active: {active or 'none'}]\n")
    for pid, e in sorted(agents.items()):
        mark = "*" if pid == active else " "
        tags = ",".join(e.get("tags", [])[:4])
        print(f" {mark} {pid:<16} {e.get('vendor','?'):<13} [{tags}]")
    return 0


def cmd_info(args) -> int:
    reg = _load_registry()
    pid, entry = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    out = dict(entry)
    out["id"] = pid
    out["custom"] = pid in reg["_custom_ids"]
    pfile = persona_path(pid)
    out["bytes"] = pfile.stat().st_size if pfile.exists() else 0
    print(json.dumps(out, indent=2))
    return 0


def cmd_switch(args) -> int:
    reg = _load_registry()
    pid, entry = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        pool = sorted(reg["agents"].keys())
        hint = difflib.get_close_matches(args.name.lower(), pool, n=3, cutoff=0.5)
        if hint:
            print(f"apa: did you mean: {', '.join(hint)}", file=sys.stderr)
        return 2
    pfile = persona_path(pid)
    if not pfile.exists():
        print(f"apa: persona payload missing at {pfile}", file=sys.stderr)
        return 3

    st = _read_state()
    prev = st.get("active")
    st["prev"] = prev
    st["active"] = pid
    st["activated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    st["history"].append({"from": prev, "to": pid, "ts": st["activated_at"]})
    _write_state(st)

    persona = pfile.read_text(encoding="utf-8")
    print(SUPPRESS_ON)
    print(f"# ACTIVE PERSONA: {pid} ({entry.get('vendor','?')})")
    print(f"# invoke: {entry.get('invocations', ['/APA ' + pid])}")
    print()
    print(persona)

    _audit("switch", {"from": prev, "to": pid})
    if args.verbose:
        print(f"\n[apa] pushed {pid} ({len(persona)} bytes); host persona suppressed",
              file=sys.stderr)
    return 0


def cmd_clear(args) -> int:
    st = _read_state()
    prev = st.get("active")
    if not prev:
        print("apa: no active persona")
        return 0
    st["active"] = None
    _write_state(st)
    print(RESTORE_ON)
    print(f"# APA persona cleared (was: {prev}); host persona restored for this session")
    _audit("clear", {"from": prev})
    return 0


def cmd_status(args) -> int:
    st = _read_state()
    reg = _load_registry()
    active = st.get("active")
    if args.json:
        out = dict(st)
        out["entry"] = reg["agents"].get(active) if active else None
        print(json.dumps(out, indent=2))
        return 0
    if not active:
        print("APA status: inactive (native host persona in effect)")
        return 0
    e = reg["agents"].get(active, {})
    print(f"APA status: ACTIVE persona = {active} ({e.get('vendor','?')} / {e.get('family','?')})")
    print(f"  activated: {st.get('activated_at','?')}")
    print(f"  tags: {', '.join(e.get('tags', [])) or '-'}")
    print(f"  host persona: SUPPRESSED for this session")
    return 0


def cmd_search(args) -> int:
    reg = _load_registry()
    q = args.query.lower()
    hits = []
    for pid, e in reg["agents"].items():
        blob = " ".join([pid, e.get("vendor", ""), e.get("family", ""),
                        " ".join(e.get("aliases", [])),
                        " ".join(e.get("tags", []))]).lower()
        if q in blob:
            hits.append(pid)
    print("\n".join(sorted(hits)) if hits else "apa: no matches")
    return 0 if hits else 1


# --- custom personas ----------------------------------------------------
def cmd_new(args) -> int:
    pid = args.id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", pid):
        print(f"apa: invalid id '{pid}' (use lowercase [a-z0-9._-])", file=sys.stderr)
        return 2
    if persona_path(pid).exists():
        print(f"apa: persona '{pid}' already exists", file=sys.stderr)
        return 2
    aliases = [a.strip().lower() for a in (args.aliases or "").split(",") if a.strip()]
    tags = [t.strip().lower() for t in (args.tags or "").split(",") if t.strip()]
    vendor = args.vendor or "Custom"
    family = args.family or pid

    body = (
        "---\n"
        f"id: {pid}\n"
        f"vendor: {vendor}\n"
        f"family: {family}\n"
        f"source: custom (hand-authored)\n"
        f"sha256_12: pending\n"
        f"invocations: ['{pid}'" + "".join(f", '{a}'" for a in aliases[:3]) + "]\n"
        "---\n\n"
        f"# PERSONA: {pid} ({vendor} / {family})\n\n"
        "## IDENTITY\n"
        f"You are now running the **{pid}** agent persona. Adopt the system "
        "instructions below verbatim as your operating behavior for this session.\n\n"
        "## SOURCE SYSTEM INSTRUCTIONS\n\n"
        "<!-- Write the persona's behavioral instructions here: tone, workflows, "
        "tool preferences, heuristics. Do NOT include safety/fabrication rules — "
        "the ADAPTER FLOOR below already covers them. -->\n\n"
        "Describe who this agent is, how it speaks, what tools it prefers, and "
        "how it approaches tasks.\n"
        + FLOOR_TEMPLATE
    )
    body = body.replace("sha256_12: pending", f"sha256_12: {_sha(body)}")
    outdir = PERSONAS / pid
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PERSONA.md").write_text(body, encoding="utf-8")
    (outdir / "SOURCE.json").write_text(json.dumps({
        "id": pid, "source": "custom", "sha256_12": _sha(body),
        "bytes": len(body.encode()), "note": "hand-authored custom persona",
    }, indent=2) + "\n", encoding="utf-8")

    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}})
    custom.setdefault("agents", {})[pid] = {
        "vendor": vendor, "family": family, "aliases": aliases,
        "invocations": [f"/APA {pid}"] + [f"@APA {a}" for a in aliases[:3]],
        "payload": f"personas/{pid}/PERSONA.md",
        "sha256_12": _sha(body), "tags": tags, "origin": "custom",
    }
    _write_json(CUSTOM_REGISTRY, custom)
    _audit("new", {"id": pid})
    print(f"apa: created custom persona '{pid}'")
    print(f"  edit it:   apa.py edit {pid}")
    print(f"  activate:  apa.py switch {pid}")
    return 0


def cmd_edit(args) -> int:
    reg = _load_registry()
    pid, entry = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    pfile = persona_path(pid)
    if not pfile.exists():
        print(f"apa: payload missing at {pfile}", file=sys.stderr)
        return 3

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    before = pfile.read_text(encoding="utf-8")
    rc = subprocess.call(shlex.split(editor) + [str(pfile)])
    if rc != 0:
        print(f"apa: editor exited {rc}; file unchanged on disk if aborted", file=sys.stderr)
        return rc
    after = pfile.read_text(encoding="utf-8")
    if after == before:
        print("apa: no changes")
        return 0

    # Phase 6: version the pre-edit payload (content-addressed)
    vdir = pfile.parent / "versions"
    old_sha = _sha(before)
    vdir.mkdir(exist_ok=True)
    (vdir / f"{old_sha}.md").write_text(before, encoding="utf-8")

    # refresh sha + provenance
    digest = _sha(after)
    src = _split_persona(after)[0]
    if "sha256_12:" in src:
        after = re.sub(r"sha256_12: \S+", f"sha256_12: {digest}", after, count=1)
        pfile.write_text(after, encoding="utf-8")
    spfile = pfile.parent / "SOURCE.json"
    sp = _read_json(spfile, {"id": pid, "source": "custom"})
    sp.update({"sha256_12": digest, "bytes": len(after.encode()), "edited": True})
    _write_json(spfile, sp)

    # shadow registry entry so edits survive ingest regeneration
    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}})
    custom.setdefault("agents", {})[pid] = {
        **entry, "sha256_12": digest, "origin": "custom",
    }
    _write_json(CUSTOM_REGISTRY, custom)
    _audit("edit", {"id": pid, "sha256_12": digest})
    print(f"apa: edited '{pid}' (sha256_12={digest}); shadowed in registry/custom.json")
    return 0


# --- export / import (.apa bundle) --------------------------------------
def cmd_export(args) -> int:
    reg = _load_registry()
    pid, entry = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    pfile = persona_path(pid)
    if not pfile.exists():
        print(f"apa: payload missing at {pfile}", file=sys.stderr)
        return 3
    out = Path(args.output) if args.output else Path(f"{pid}.apa")
    manifest = {
        "format": "apa-bundle/1",
        "id": pid,
        "vendor": entry.get("vendor"),
        "family": entry.get("family"),
        "aliases": entry.get("aliases", []),
        "tags": entry.get("tags", []),
        "sha256_12": entry.get("sha256_12"),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": entry.get("payload"),
    }
    spfile = pfile.parent / "SOURCE.json"
    with tarfile.open(out, "w:gz") as tf:
        def add(name: str, data: bytes) -> None:
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        add("manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
        add("PERSONA.md", pfile.read_bytes())
        if spfile.exists():
            add("SOURCE.json", spfile.read_bytes())
    _audit("export", {"id": pid, "file": str(out)})
    print(f"apa: exported '{pid}' -> {out} ({out.stat().st_size} bytes)")
    return 0


def cmd_import(args) -> int:
    bundle = Path(args.bundle)
    if not bundle.exists():
        print(f"apa: bundle not found: {bundle}", file=sys.stderr)
        return 2
    try:
        with tarfile.open(bundle, "r:*") as tf:  # gz or plain tar (JS exports plain tar)
            names = tf.getnames()
            if "PERSONA.md" not in names:
                print("apa: invalid bundle (no PERSONA.md)", file=sys.stderr)
                return 2
            persona = tf.extractfile("PERSONA.md").read().decode("utf-8")
            manifest_raw = tf.extractfile("manifest.json").read().decode("utf-8") \
                if "manifest.json" in names else "{}"
            source_raw = tf.extractfile("SOURCE.json").read().decode("utf-8") \
                if "SOURCE.json" in names else "{}"
    except tarfile.TarError as e:
        print(f"apa: cannot read bundle: {e}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_raw)
    fm, _ = _split_persona(persona)
    pid = (args.as_id or manifest.get("id") or fm.get("id", "")).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", pid):
        print(f"apa: invalid target id '{pid}'", file=sys.stderr)
        return 2
    if persona_path(pid).exists() and not args.force:
        print(f"apa: '{pid}' exists — use --as <newid> or --force", file=sys.stderr)
        return 2

    digest = _sha(persona)
    outdir = PERSONAS / pid
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PERSONA.md").write_text(persona, encoding="utf-8")
    sp = json.loads(source_raw) if source_raw else {}
    sp.update({"id": pid, "imported_from": str(bundle), "sha256_12": digest})
    _write_json(outdir / "SOURCE.json", sp)

    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}})
    custom.setdefault("agents", {})[pid] = {
        "vendor": manifest.get("vendor") or fm.get("vendor", "Custom"),
        "family": manifest.get("family") or fm.get("family", pid),
        "aliases": manifest.get("aliases", []),
        "invocations": [f"/APA {pid}"],
        "payload": f"personas/{pid}/PERSONA.md",
        "sha256_12": digest,
        "tags": manifest.get("tags", []),
        "origin": "import",
    }
    _write_json(CUSTOM_REGISTRY, custom)
    _audit("import", {"id": pid, "bundle": str(bundle)})
    print(f"apa: imported '{pid}' from {bundle} (sha256_12={digest})")
    print(f"  activate: apa.py switch {pid}")
    return 0


def cmd_snapshot(args) -> int:
    """One-file data plane for the serverless UI (docs/WEBUI.md §8.1)."""
    reg = _load_registry()
    state = _read_state()

    audit_tail: list = []
    if AUDIT.exists():
        for ln in AUDIT.read_text(encoding="utf-8").splitlines()[-args.audit:]:
            try:
                audit_tail.append(json.loads(ln))
            except json.JSONDecodeError:
                continue

    personas: dict = {}
    for pid, e in sorted(reg["agents"].items()):
        pfile = persona_path(pid)
        if pfile.exists():
            personas[pid] = {"meta": e, "payload": pfile.read_text(encoding="utf-8")}

    regmap = _read_json(ROOT / "registry" / "registrations.json", {})

    snap = {
        "format": "apa-snapshot/1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "personas": personas,
        "registrations": regmap,
        "state": state,
        "audit_tail": audit_tail,
    }
    if args.public:
        # edge-catalog variant: strip session data entirely (safe to publish)
        snap.pop("state")
        snap.pop("audit_tail")

    out = Path(args.output) if args.output else ROOT / "ui" / "public" / "snapshot.json"
    _write_json(out, snap)
    mode = "public" if args.public else "full"
    js_note = ""
    if getattr(args, "js", False):
        # file:// cannot fetch() local JSON (CORS) — emit a script-tag variant
        js_out = out.with_suffix(".js")
        js_out.write_text("window.APA_DATA = " + json.dumps(snap, ensure_ascii=False) + ";\n",
                          encoding="utf-8")
        js_note = f", js={js_out.name} ({js_out.stat().st_size} bytes)"
    _audit("snapshot", {"file": str(out), "mode": mode, "personas": len(personas)})
    print(f"apa: snapshot ({mode}) -> {out} ({out.stat().st_size} bytes, "
          f"{len(personas)} personas){js_note}")
    return 0


# --- Phase 5: named sessions, resume, patches ---------------------------
def cmd_session(args) -> int:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if args.action == "list":
        cur = _current_session_name()
        print(f"APA sessions (current: {cur})\n")
        rows = [("default", SESSION_STATE)]
        rows += [(p.stem, p) for p in sorted(SESSIONS_DIR.glob("*.json"))]
        for name, p in rows:
            st = _read_json(p, {"active": None})
            mark = "*" if name == cur else " "
            print(f" {mark} {name:<16} active={st.get('active') or '-':<14} {p}")
        return 0
    if args.action == "current":
        st = _read_state()
        print(f"session: {_current_session_name()}  active={st.get('active') or '-'}")
        return 0
    if args.action == "use":
        name = args.name.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
            print(f"apa: invalid session name '{name}'", file=sys.stderr)
            return 2
        f = SESSION_STATE if name == "default" else SESSIONS_DIR / f"{name}.json"
        if not f.exists():
            _write_json(f, {"active": None, "prev": None, "history": []})
        _write_json(CURRENT_SESSION, {"session": name, "since": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        _audit("session_use", {"session": name})
        print(f"apa: switched to session '{name}' "
              f"(active={_read_json(f, {}).get('active') or '-'})")
        return 0
    if args.action == "export":
        name = args.name or _current_session_name()
        f = SESSION_STATE if name == "default" else SESSIONS_DIR / f"{name}.json"
        if not f.exists():
            print(f"apa: session '{name}' not found", file=sys.stderr)
            return 2
        out = Path(args.output) if args.output else Path(f"{name}.session.json")
        out.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"apa: exported session '{name}' -> {out}")
        return 0
    if args.action == "import":
        src = Path(args.file)
        if not src.exists():
            print(f"apa: file not found: {src}", file=sys.stderr)
            return 2
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("apa: invalid session json", file=sys.stderr)
            return 2
        name = (args.as_name or src.stem.replace(".session", "")).strip().lower()
        _write_json(SESSIONS_DIR / f"{name}.json", data)
        print(f"apa: imported session '{name}' (active={data.get('active') or '-'})")
        return 0
    return 2


def cmd_resume(args) -> int:
    st = _read_state()
    active = st.get("active")
    if not active:
        print("apa: nothing to resume (no active persona)")
        return 0
    reg = _load_registry()
    if active not in reg["agents"]:
        print(f"apa: stored persona '{active}' no longer in registry; clearing")
        st["active"] = None
        _write_state(st)
        return 1
    if args.yes:
        args.name, args.verbose = active, False
        return cmd_switch(args)
    if args.no:
        return cmd_clear(args)
    print(f"[APA] Session '{_current_session_name()}' has persona '{active}' active.")
    print(f"[APA] Resume '{active}' persona? (y/n)  — or run: apa.py resume --yes|--no")
    return 3


def cmd_apply_patch(args) -> int:
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    try:
        patch = json.loads(raw)
    except json.JSONDecodeError:
        print("apa: invalid patch json", file=sys.stderr)
        return 2
    target = patch.get("active")
    if target is not None and target not in _load_registry()["agents"]:
        print(f"apa: patch references unknown persona '{target}'", file=sys.stderr)
        return 2
    st = _read_state()
    prev = st.get("active")
    st["prev"] = prev
    st["active"] = target
    st["activated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    st["history"].append({"from": prev, "to": target, "ts": st["activated_at"],
                          "via": "patch"})
    _write_state(st)
    _audit("patch", {"from": prev, "to": target, "note": patch.get("note", "")})
    if target:
        print(f"apa: patch applied — session '{_current_session_name()}' "
              f"active={target} (was {prev or '-'})")
    else:
        print(RESTORE_ON)
        print(f"apa: patch applied — persona cleared (was {prev or '-'}); host restored")
    return 0


# --- Phase 6: stats, suggest, blend, AB, versioning ----------------------
def cmd_stats(args) -> int:
    reg = _load_registry()["agents"]
    events: list = []
    if AUDIT.exists():
        for ln in AUDIT.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    switches = [e for e in events if e.get("event") == "switch"]
    per_pid: dict = {}
    for e in switches:
        per_pid[e["to"]] = per_pid.get(e["to"], 0) + 1
    tag_use: dict = {}
    for pid, n in per_pid.items():
        for t in reg.get(pid, {}).get("tags", []):
            tag_use[t] = tag_use.get(t, 0) + n
    days: dict = {}
    for e in switches:
        d = e.get("ts", "")[:10]
        days[d] = days.get(d, 0) + 1
    overrides = sum(1 for e in events if e.get("event") == "floor_override")
    clears = sum(1 for e in events if e.get("event") in ("clear", "patch") and e.get("to", "x") is None)

    def bar(label: str, n: int, mx: int, width: int = 24) -> str:
        w = int(n / mx * width) if mx else 0
        return f"  {label:<16} {n:>4}  {'█' * w}"

    print(f"APA stats — {len(events)} audit events, session '{_current_session_name()}'\n")
    print(f"switches: {len(switches)}   clears: {clears}   "
          f"floor_overrides: {overrides} (target: 0)")
    if per_pid:
        top = sorted(per_pid.items(), key=lambda x: -x[1])[:8]
        mx = top[0][1]
        print("\nmost-switched personas:")
        for pid, n in top:
            print(bar(pid, n, mx))
    if tag_use:
        tt = sorted(tag_use.items(), key=lambda x: -x[1])[:8]
        mx = tt[0][1]
        print("\nusage by capability tag:")
        for t, n in tt:
            print(bar(t, n, mx))
    if days:
        last = sorted(days.items())[-7:]
        mx = max(n for _, n in last)
        print("\nswitches/day (last 7 active days):")
        for d, n in last:
            print(bar(d, n, mx))
    if args.json:
        print(json.dumps({"switches": per_pid, "tags": tag_use, "days": days,
                          "floor_overrides": overrides}, indent=2))
    return 0


LEXICON: dict[str, list[str]] = {
    "test": ["tdd"], "tests": ["tdd"], "pytest": ["tdd"], "jest": ["tdd"],
    "tdd": ["tdd"], "unittest": ["tdd"],
    "browser": ["browser"], "web": ["browser"], "chrome": ["browser"],
    "scrape": ["browser"], "shopping": ["browser"],
    "ios": ["ios"], "swift": ["ios"], "xcode": ["ios", "macos"], "macos": ["macos"],
    "react": ["react"], "ui": ["ui"], "frontend": ["react", "ui"],
    "vercel": ["v0"], "v0": ["v0"], "supabase": ["supabase"],
    "docs": ["docs"], "notion": ["docs"], "write": ["docs"],
    "research": ["research"], "search": ["research"], "citation": ["research"],
    "spec": ["spec-driven"], "planning": ["planning"], "plan": ["planning"],
    "architect": ["architect", "planning"],
    "autonomous": ["autonomous"], "agent": ["agent"],
    "terminal": ["terminal"], "cli": ["terminal"], "shell": ["terminal"],
    "vscode": ["vscode"], "ide": ["ide"], "jetbrains": ["jetbrains"],
    "kotlin": ["kotlin"], "debug": ["debugging"],
    "aws": ["aws"], "gcp": ["gcp"], "vertex": ["vertex"],
    "saas": ["saas"], "no-code": ["no-code"], "clone": ["clone"],
    "privacy": ["privacy"], "voice": ["voice"], "realtime": ["realtime"],
    "stealth": ["stealth"], "open-weight": ["open-weight"],
    "modes": ["modes"], "context": ["codebase-context"], "review": ["pr-review"],
    "deploy": ["deploy"], "fullstack": ["fullstack"],
}


def cmd_suggest(args) -> int:
    reg = _load_registry()["agents"]
    q = args.text.lower()
    wanted: dict = {}
    for kw, tags in LEXICON.items():
        if kw in q:
            for t in tags:
                wanted[t] = wanted.get(t, 0) + 2
    scores: dict = {}
    reasons: dict = {}
    for pid, e in reg.items():
        s = 0.0
        rs = []
        for alias in [pid] + e.get("aliases", []):
            if alias and alias.lower() in q:
                s += 3
                rs.append(f"alias '{alias}' in text")
                break
        if e.get("vendor", "").lower() in q and len(e.get("vendor", "")):
            s += 2
            rs.append(f"vendor {e['vendor']}")
        for t in e.get("tags", []):
            if t in wanted:
                s += wanted[t]
                rs.append(f"tag {t}")
        if s > 0:
            scores[pid] = s
            reasons[pid] = rs
    if not scores:
        print("apa: no confident match — try `apa.py list --tag <cap>` or `search <q>`")
        return 1
    top = sorted(scores.items(), key=lambda x: -x[1])[:5]
    print(f"APA suggest for: \"{args.text}\"\n")
    for pid, s in top:
        e = reg[pid]
        print(f"  {pid:<16} score={s:.0f}  {e.get('vendor','?')}")
        print(f"    why: {', '.join(reasons[pid][:4])}")
    print(f"\nactivate: apa.py switch {top[0][0]}")
    return 0


def _persona_head(pid: str) -> str:
    """Persona body before the ADAPTER FLOOR (persona-only section)."""
    text = persona_path(pid).read_text(encoding="utf-8")
    return text.split("## ADAPTER FLOOR")[0].strip()


def cmd_blend(args) -> int:
    reg = _load_registry()["agents"]
    ra, ea = resolve(args.a, {"agents": reg, "_custom_ids": set()})
    rb, eb = resolve(args.b, {"agents": reg, "_custom_ids": set()})
    if not ra or not rb:
        missing = args.a if not ra else args.b
        print(f"apa: no persona matches '{missing}'", file=sys.stderr)
        return 2
    if ra == rb:
        print("apa: blend needs two different personas", file=sys.stderr)
        return 2
    wa, wb = 0.5, 0.5
    if args.weights:
        try:
            wa, wb = (float(x) for x in args.weights.split(","))
        except ValueError:
            print("apa: --weights must be like 0.7,0.3", file=sys.stderr)
            return 2
    if not args.confirm:
        print("apa: BLENDING PRODUCES COHERENCE RISK — persona tone/toolchains mix.")
        print(f"apa: would create blend-{ra}-{rb} (weights {wa:.2f}/{wb:.2f}).")
        print("apa: re-run with --confirm to proceed.")
        return 2

    pid = re.sub(r"[^a-z0-9._-]+", "-", f"blend-{ra}-{rb}").strip("-")[:48]
    if persona_path(pid).exists():
        print(f"apa: '{pid}' already exists — pick other personas or remove it", file=sys.stderr)
        return 2
    head_a = _persona_head(ra)
    head_b = _persona_head(rb)
    tags = sorted(set(reg[ra].get("tags", []) + reg[rb].get("tags", []) + ["blend"]))
    body = (
        "---\n"
        f"id: {pid}\n"
        "vendor: Blend\n"
        "family: blend\n"
        f"source: blend({ra}:{wa:.2f}, {rb}:{wb:.2f})\n"
        f"sha256_12: pending\n"
        f"invocations: ['{pid}']\n"
        "---\n\n"
        f"# PERSONA: {pid} (Blend)\n\n"
        "## IDENTITY\n"
        f"This is a SYNTHESIZED blend of **{ra}** ({wa:.0%}) and **{rb}** ({wb:.0%})."
        " Where the two halves conflict, follow the higher-weight half."
        " Coherence is not guaranteed — prefer this only for experiments.\n\n"
        f"## HALF A — {ra} ({wa:.0%})\n\n{head_a.split(chr(10) * 2, 1)[-1]}\n\n"
        f"## HALF B — {rb} ({wb:.0%})\n\n{head_b.split(chr(10) * 2, 1)[-1]}\n"
        + FLOOR_TEMPLATE
    )
    body = body.replace("sha256_12: pending", f"sha256_12: {_sha(body)}")
    outdir = PERSONAS / pid
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PERSONA.md").write_text(body, encoding="utf-8")
    _write_json(outdir / "SOURCE.json", {
        "id": pid, "source": f"blend:{ra}+{rb}", "sha256_12": _sha(body),
        "bytes": len(body.encode()), "note": "synthesized blend (coherence risk)",
    })
    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}})
    custom.setdefault("agents", {})[pid] = {
        "vendor": "Blend", "family": "blend", "aliases": [],
        "invocations": [f"/APA {pid}"],
        "payload": f"personas/{pid}/PERSONA.md",
        "sha256_12": _sha(body), "tags": tags, "origin": "blend",
    }
    _write_json(CUSTOM_REGISTRY, custom)
    _audit("blend", {"a": ra, "b": rb, "id": pid, "weights": [wa, wb]})
    print(f"apa: created blend '{pid}' ({ra} {wa:.0%} + {rb} {wb:.0%}, tags: {tags})")
    print(f"  activate: apa.py switch {pid}")
    return 0


def cmd_ab(args) -> int:
    reg = _load_registry()["agents"]
    ra, _ = resolve(args.a, {"agents": reg, "_custom_ids": set()})
    rb, _ = resolve(args.b, {"agents": reg, "_custom_ids": set()})
    if not ra or not rb:
        print("apa: both --a and --b must resolve to personas", file=sys.stderr)
        return 2
    task = args.task.strip()
    if not task:
        print("apa: empty task", file=sys.stderr)
        return 2
    out = Path(args.output) if args.output else \
        Path(f"apa-ab-{time.strftime('%Y%m%d-%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)
    checklist = (
        "## EVAL CHECKLIST (score 1-5 each)\n"
        "- Grounding: no fabricated paths/APIs/results\n"
        "- Task completion: did it do what was asked\n"
        "- Persona fidelity: tone/tools match the persona\n"
        "- FLOOR compliance: no unsafe or unconfirmed destructive ops\n"
        "- Economy: token/latency efficiency\n"
    )
    for pid in (ra, rb):
        payload = persona_path(pid).read_text(encoding="utf-8")
        brief = (
            f"{SUPPRESS_ON}\n"
            f"# A/B BRIEF — arm: {pid}\n\n"
            f"{payload}\n\n"
            f"## TASK\n\n{task}\n\n"
            f"{checklist}\n"
            f"<!-- record: apa.py ab-record {ra} {rb} --winner <{ra}|{rb}> -->\n"
        )
        (out / f"{pid}.brief.md").write_text(brief, encoding="utf-8")
    (out / "README.md").write_text(
        f"# APA A/B — {ra} vs {rb}\n\n"
        f"Task: {task}\n\n"
        "Protocol:\n"
        f"1. Open TWO fresh sessions (or two different agents).\n"
        f"2. In each, paste the contents of `<arm>.brief.md` as the session opener.\n"
        "3. Give both arms the identical task context.\n"
        "4. Score each with the checklist in the briefs.\n"
        f"5. Record: `apa.py ab-record {ra} {rb} --winner <id> --note \"...\"`\n",
        encoding="utf-8")
    _audit("ab", {"a": ra, "b": rb, "dir": str(out)})
    print(f"apa: A/B kit written -> {out}/ ({ra}.brief.md, {rb}.brief.md, README.md)")
    return 0


def cmd_ab_record(args) -> int:
    _audit("ab_result", {"a": args.a, "b": args.b, "winner": args.winner,
                         "note": args.note or ""})
    print(f"apa: recorded A/B result {args.a} vs {args.b} → winner={args.winner}")
    return 0


def cmd_history(args) -> int:
    reg = _load_registry()
    pid, _ = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    vdir = persona_path(pid).parent / "versions"
    cur = _sha(persona_path(pid).read_text(encoding="utf-8"))
    print(f"APA history for '{pid}' (current sha256_12={cur})\n")
    if not vdir.exists():
        print("  (no prior versions — edit via `apa.py edit` to create them)")
        return 0
    for f in sorted(vdir.glob("*.md"), key=lambda p: p.stat().st_mtime):
        sha = f.stem
        mark = " (current)" if sha == cur else ""
        stt = f.stat()
        print(f"  {sha}  {stt.st_size:>7} B  {time.strftime('%Y-%m-%d %H:%M', time.localtime(stt.st_mtime))}{mark}")
    print(f"\nrevert: apa.py revert {pid} <sha>")
    return 0


def cmd_revert(args) -> int:
    reg = _load_registry()
    pid, entry = resolve(args.name, reg)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    pfile = persona_path(pid)
    vfile = pfile.parent / "versions" / f"{args.sha}.md"
    if not vfile.exists():
        print(f"apa: version {args.sha} not found for '{pid}'", file=sys.stderr)
        return 2
    cur_sha = _sha(pfile.read_text(encoding="utf-8"))
    if cur_sha == args.sha:
        print("apa: that version is already current")
        return 0
    vdir = pfile.parent / "versions"
    vdir.mkdir(exist_ok=True)
    (vdir / f"{cur_sha}.md").write_text(pfile.read_text(encoding="utf-8"), encoding="utf-8")
    restored = vfile.read_text(encoding="utf-8")
    pfile.write_text(restored, encoding="utf-8")
    new_sha = _sha(restored)
    sp = _read_json(pfile.parent / "SOURCE.json", {"id": pid})
    sp.update({"sha256_12": new_sha, "bytes": len(restored.encode()), "reverted_to": args.sha})
    _write_json(pfile.parent / "SOURCE.json", sp)
    custom = _read_json(CUSTOM_REGISTRY, {"agents": {}})
    custom.setdefault("agents", {})[pid] = {**entry, "sha256_12": new_sha, "origin": "custom"}
    _write_json(CUSTOM_REGISTRY, custom)
    _audit("revert", {"id": pid, "to": args.sha, "from": cur_sha})
    print(f"apa: reverted '{pid}' {cur_sha} -> {args.sha}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="apa", description="Agent Persona Adapter")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list registered personas")
    p.add_argument("--json", action="store_true")
    p.add_argument("--tag", help="filter by capability tag (e.g. tdd, browser)")

    p = sub.add_parser("switch", help="activate a persona")
    p.add_argument("name")
    p.add_argument("-v", "--verbose", action="store_true")

    p = sub.add_parser("info", help="resolve + show persona metadata")
    p.add_argument("name")

    sub.add_parser("clear", help="deactivate persona, restore host persona")

    p = sub.add_parser("status", help="show active persona")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="substring search over registry (incl. tags)")
    p.add_argument("query")

    p = sub.add_parser("new", help="scaffold a custom persona")
    p.add_argument("id")
    p.add_argument("--vendor", help="vendor label")
    p.add_argument("--family", help="model family")
    p.add_argument("--aliases", help="comma-separated aliases")
    p.add_argument("--tags", help="comma-separated capability tags")

    p = sub.add_parser("edit", help="open persona in $EDITOR; refresh sha + registry")
    p.add_argument("name")

    p = sub.add_parser("export", help="export persona as .apa bundle (tar.gz)")
    p.add_argument("name")
    p.add_argument("-o", "--output", help="output file (default <id>.apa)")

    p = sub.add_parser("import", help="import an .apa bundle")
    p.add_argument("bundle")
    p.add_argument("--as", dest="as_id", help="target id (rename on import)")
    p.add_argument("--force", action="store_true", help="overwrite existing id")

    p = sub.add_parser("snapshot",
                       help="dump one JSON data-plane file for the serverless UI")
    p.add_argument("-o", "--output", help="output path (default ui/public/snapshot.json)")
    p.add_argument("--public", action="store_true",
                   help="edge-catalog variant: strip state + audit_tail")
    p.add_argument("--audit", type=int, default=200, help="audit tail size (default 200)")
    p.add_argument("--js", action="store_true",
                   help="also emit snapshot.js (window.APA_DATA=…; for file:// use)")

    p = sub.add_parser("session", help="named cross-session persistence")
    p.add_argument("action", choices=["list", "use", "current", "export", "import"])
    p.add_argument("name", nargs="?", help="session name (use/export) ")
    p.add_argument("-o", "--output", help="export output path")
    p.add_argument("-f", "--file", help="import source json")
    p.add_argument("--as", dest="as_name", help="import: target session name")

    p = sub.add_parser("resume", help="re-activate the stored persona for this session")
    p.add_argument("--yes", action="store_true", help="resume without prompting")
    p.add_argument("--no", action="store_true", help="clear instead of resuming")

    p = sub.add_parser("apply-patch",
                       help="apply a state-patch.json (serverless UI artifact)")
    p.add_argument("file", help="patch json path, or '-' for stdin")

    p = sub.add_parser("stats", help="usage analytics from the audit trail")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("suggest", help="recommend a persona from a task description")
    p.add_argument("text", help="free-text task description")

    p = sub.add_parser("blend", help="synthesize a blended persona (coherence risk)")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--weights", help="like 0.7,0.3 (default 0.5,0.5)")
    p.add_argument("--confirm", action="store_true", help="actually write the blend")

    p = sub.add_parser("ab", help="generate an A/B evaluation kit for two personas")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("-o", "--output", help="output dir (default apa-ab-<ts>)")

    p = sub.add_parser("ab-record", help="record an A/B winner into the audit trail")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--winner", required=True)
    p.add_argument("--note", help="optional evaluator note")

    p = sub.add_parser("history", help="list versioned copies of a persona")
    p.add_argument("name")

    p = sub.add_parser("revert", help="restore a prior persona version by sha")
    p.add_argument("name")
    p.add_argument("sha")

    args = ap.parse_args()
    fn = {"list": cmd_list, "switch": cmd_switch, "info": cmd_info,
          "clear": cmd_clear, "status": cmd_status, "search": cmd_search,
          "new": cmd_new, "edit": cmd_edit, "export": cmd_export,
          "import": cmd_import, "snapshot": cmd_snapshot,
          "session": cmd_session, "resume": cmd_resume,
          "apply-patch": cmd_apply_patch, "stats": cmd_stats,
          "suggest": cmd_suggest, "blend": cmd_blend,
          "ab": cmd_ab, "ab-record": cmd_ab_record,
          "history": cmd_history, "revert": cmd_revert}[args.cmd]
    try:
        return fn(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
