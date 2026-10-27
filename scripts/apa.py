#!/usr/bin/env python3
"""APA — Agent Persona Adapter core resolver.

Implements: registry lookup, alias->persona matching, session state,
persona push/pop, and host-persona suppression tokens.

Zero third-party deps (Termux/Python 3.11 stdlib only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry" / "agents.json"
PERSONAS = ROOT / "personas"
STATE_DIR = ROOT / "state"
SESSION_STATE = STATE_DIR / "active.json"
AUDIT = STATE_DIR / "audit.log"

SYS_EXIT = 0

# --- host suppression markers -------------------------------------------
SUPPRESS_ON = "<!-- APA:HOST_PERSONA_SUPPRESSED=true -->"
RESTORE_ON = "<!-- APA:HOST_PERSONA_SUPPRESSED=false -->"


def _load_registry() -> dict:
    if not REGISTRY.exists():
        return {"agents": {}}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_state() -> dict:
    if SESSION_STATE.exists():
        return json.loads(SESSION_STATE.read_text(encoding="utf-8"))
    return {"active": None, "prev": None, "history": []}


def _write_state(st: dict) -> None:
    _write_json(SESSION_STATE, st)


def _audit(event: str, detail: dict) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **detail}
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --- resolution ---------------------------------------------------------
def resolve(name: str) -> tuple[str | None, dict]:
    """Match an agent name/alias to a persona id. Returns (id, entry)."""
    reg = _load_registry().get("agents", {})
    low = name.strip().lower()

    # exact id
    if low in reg:
        return low, reg[low]
    # alias scan
    for aid, entry in reg.items():
        for alias in entry.get("aliases", []):
            if alias.lower() == low:
                return aid, entry
    # fuzzy
    pool = list(reg.keys())
    for aid, entry in reg.items():
        pool.extend(a.lower() for a in entry.get("aliases", []))
    close = difflib.get_close_matches(low, pool, n=1, cutoff=0.72)
    if close:
        hit = close[0]
        if hit in reg:
            return hit, reg[hit]
        for aid, entry in reg.items():
            if hit in [a.lower() for a in entry.get("aliases", [])]:
                return aid, entry
    return None, {}


def persona_path(pid: str) -> Path:
    return PERSONAS / pid / "PERSONA.md"


def cmd_list(args) -> int:
    reg = _load_registry().get("agents", {})
    state = _read_state()
    active = state.get("active")
    if args.json:
        print(json.dumps({"active": active, "agents": sorted(reg.keys())}, indent=2))
        return 0
    print(f"APA registry — {len(reg)} personas  [active: {active or 'none'}]\n")
    rows = sorted(reg.items())
    for pid, e in rows:
        mark = "*" if pid == active else " "
        aliases = ", ".join(e.get("aliases", [])[:5])
        print(f" {mark} {pid:<18} {e.get('vendor','?'):<14} {e.get('family','?'):<10} [{aliases}]")
    return 0


def cmd_info(args) -> int:
    pid, entry = resolve(args.name)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        return 2
    print(json.dumps({"id": pid, **entry}, indent=2))
    return 0


def cmd_switch(args) -> int:
    pid, entry = resolve(args.name)
    if not pid:
        print(f"apa: no persona matches '{args.name}'", file=sys.stderr)
        pool = sorted(_load_registry().get("agents", {}).keys())
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
    st.setdefault("history", []).append(
        {"from": prev, "to": pid, "ts": st["activated_at"]}
    )
    _write_state(st)

    # emit the persona payload for the host session to ingest
    persona = pfile.read_text(encoding="utf-8")
    print(SUPPRESS_ON)
    print(f"# ACTIVE PERSONA: {pid} ({entry.get('vendor','?')})")
    print(f"# invoke: {entry.get('invocations', ['/APA ' + pid])}")
    print()
    print(persona)

    _audit("switch", {"from": prev, "to": pid})
    if args.verbose:
        print(f"\n[apa] pushed {pid} ({len(persona)} bytes); host persona suppressed", file=sys.stderr)
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
    reg = _load_registry().get("agents", {})
    active = st.get("active")
    if args.json:
        out = dict(st)
        out["entry"] = reg.get(active) if active else None
        print(json.dumps(out, indent=2))
        return 0
    if not active:
        print("APA status: inactive (native host persona in effect)")
        return 0
    e = reg.get(active, {})
    print(f"APA status: ACTIVE persona = {active} ({e.get('vendor','?')} / {e.get('family','?')})")
    print(f"  activated: {st.get('activated_at','?')}")
    print(f"  host persona: SUPPRESSED for this session")
    return 0


def cmd_search(args) -> int:
    reg = _load_registry().get("agents", {})
    q = args.query.lower()
    hits = []
    for pid, e in reg.items():
        blob = " ".join([pid, e.get("vendor", ""), e.get("family", ""),
                        " ".join(e.get("aliases", []))]).lower()
        if q in blob:
            hits.append(pid)
    print("\n".join(sorted(hits)) if hits else "apa: no matches")
    return 0 if hits else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="apa", description="Agent Persona Adapter")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list registered personas").add_argument("--json", action="store_true")

    p = sub.add_parser("switch", help="activate a persona")
    p.add_argument("name")
    p.add_argument("-v", "--verbose", action="store_true")

    p = sub.add_parser("info", help="resolve + show persona metadata")
    p.add_argument("name")

    sub.add_parser("clear", help="deactivate persona, restore host persona")

    p = sub.add_parser("status", help="show active persona")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="substring search over registry")
    p.add_argument("query")

    args = ap.parse_args()
    fn = {"list": cmd_list, "switch": cmd_switch, "info": cmd_info,
          "clear": cmd_clear, "status": cmd_status, "search": cmd_search}[args.cmd]
    try:
        return fn(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
