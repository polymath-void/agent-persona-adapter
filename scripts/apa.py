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


def _write_state(st: dict) -> None:
    _write_json(SESSION_STATE, st)


def _read_state() -> dict:
    st = _read_json(SESSION_STATE, {"active": None, "prev": None, "history": []})
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
        with tarfile.open(bundle, "r:gz") as tf:
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
    _audit("snapshot", {"file": str(out), "mode": mode, "personas": len(personas)})
    print(f"apa: snapshot ({mode}) -> {out} ({out.stat().st_size} bytes, "
          f"{len(personas)} personas)")
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

    args = ap.parse_args()
    fn = {"list": cmd_list, "switch": cmd_switch, "info": cmd_info,
          "clear": cmd_clear, "status": cmd_status, "search": cmd_search,
          "new": cmd_new, "edit": cmd_edit, "export": cmd_export,
          "import": cmd_import, "snapshot": cmd_snapshot}[args.cmd]
    try:
        return fn(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
