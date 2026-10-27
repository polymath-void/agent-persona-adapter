#!/usr/bin/env python3
"""APA cockpit server — stdlib-only HTTP wrapper over the apa.py engine.

Serves the vanilla-JS SPA (ui/) + a thin JSON API that mirrors the CLI 1:1.
Zero third-party deps: http.server + json only. Localhost bind, LMK guard.

    python3 server/serve.py [--port 8787] [--min-mem-mb 1024] [--no-guard]

Routes (all mutations return the equivalent CLI command string):
    GET  /                     -> ui/index.html (SPA shell)
    GET  /api/state            -> apa.py status --json (+ session)
    GET  /api/personas?tag=&q= -> registry index (filterable)
    GET  /api/personas/<id>    -> meta + full payload
    POST /api/switch  {name}   -> apa.py switch (response carries payload)
    POST /api/clear            -> apa.py clear
    GET  /api/audit?limit=N    -> tail of state/audit.log
    GET  /api/stats            -> aggregates (switches, tags, days)
    GET  /api/registrations    -> registry/registrations.json
    GET  /api/sessions         -> named session list
    GET  /api/export/<id>      -> .apa bundle download (tar.gz)
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tarfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import apa  # noqa: E402  (the engine itself — single source of truth)

UI_DIR = ROOT / "ui"
STATIC_TYPES = {".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml"}


# --- LMK guard ----------------------------------------------------------
def mem_available_mb() -> int | None:
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


# --- API helpers --------------------------------------------------------
def api_state() -> dict:
    st = apa._read_state()
    reg = apa._load_registry()
    active = st.get("active")
    return {
        "session": apa._current_session_name(),
        "active": active,
        "prev": st.get("prev"),
        "activated_at": st.get("activated_at"),
        "entry": reg["agents"].get(active) if active else None,
        "suppressed": bool(active),
        "cli": "apa.py status",
    }


def api_personas(tag: str, q: str) -> dict:
    reg = apa._load_registry()
    agents = reg["agents"]
    if tag:
        agents = {k: v for k, v in agents.items() if tag in v.get("tags", [])}
    if q:
        ql = q.lower()
        agents = {k: v for k, v in agents.items()
                  if ql in k.lower()
                  or ql in v.get("vendor", "").lower()
                  or ql in v.get("family", "").lower()
                  or any(ql in a.lower() for a in v.get("aliases", []))
                  or any(ql in t.lower() for t in v.get("tags", []))}
    out = []
    for pid, e in sorted(agents.items()):
        pfile = apa.persona_path(pid)
        out.append({**e, "id": pid,
                    "custom": pid in reg["_custom_ids"],
                    "bytes": pfile.stat().st_size if pfile.exists() else 0})
    return {"count": len(out), "personas": out, "cli": "apa.py list"}


def api_persona_detail(pid: str) -> dict | None:
    reg = apa._load_registry()
    if pid not in reg["agents"]:
        return None
    pfile = apa.persona_path(pid)
    payload = pfile.read_text(encoding="utf-8") if pfile.exists() else ""
    sp = apa._read_json(pfile.parent / "SOURCE.json", {})
    versions = []
    vdir = pfile.parent / "versions"
    if vdir.exists():
        versions = [{"sha256_12": f.stem, "bytes": f.stat().st_size}
                    for f in sorted(vdir.glob("*.md"))]
    return {"id": pid, "meta": reg["agents"][pid], "payload": payload,
            "source": sp, "versions": versions, "cli": f"apa.py info {pid}"}


def api_audit(limit: int) -> dict:
    rows = []
    if apa.AUDIT.exists():
        for ln in apa.AUDIT.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return {"count": len(rows), "events": rows, "cli": "tail state/audit.log"}


def api_stats() -> dict:
    reg = apa._load_registry()["agents"]
    events = api_audit(100000)["events"]
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
    return {
        "events_total": len(events),
        "switches": len(switches),
        "floor_overrides": sum(1 for e in events if e.get("event") == "floor_override"),
        "per_persona": dict(sorted(per_pid.items(), key=lambda x: -x[1])),
        "per_tag": dict(sorted(tag_use.items(), key=lambda x: -x[1])),
        "per_day": dict(sorted(days.items())),
        "cli": "apa.py stats",
    }


def api_sessions() -> dict:
    cur = apa._current_session_name()
    rows = [{"name": "default", "active": apa._read_json(apa.SESSION_STATE, {}).get("active")}]
    if apa.SESSIONS_DIR.exists():
        for p in sorted(apa.SESSIONS_DIR.glob("*.json")):
            rows.append({"name": p.stem,
                         "active": apa._read_json(p, {}).get("active")})
    return {"current": cur, "sessions": rows, "cli": "apa.py session list"}


def run_capture(fn, args) -> tuple[int, str]:
    """Run a CLI command function, capturing stdout (payload printing)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(args)
    return rc, buf.getvalue()


# --- handler ------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "APA-Cockpit/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, body: bytes, ctype: str, code=200, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # -- GET ------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        try:
            if path == "/api/state":
                return self._json(api_state())
            if path == "/api/personas":
                return self._json(api_personas(qs.get("tag", [""])[0],
                                               qs.get("q", [""])[0]))
            if path.startswith("/api/personas/"):
                detail = api_persona_detail(path.rsplit("/", 1)[1])
                return self._json(detail if detail else {"error": "unknown persona"},
                                  200 if detail else 404)
            if path == "/api/audit":
                return self._json(api_audit(int(qs.get("limit", ["100"])[0])))
            if path == "/api/stats":
                return self._json(api_stats())
            if path == "/api/registrations":
                return self._json(apa._read_json(ROOT / "registry" / "registrations.json", {}))
            if path == "/api/sessions":
                return self._json(api_sessions())
            if path.startswith("/api/export/"):
                return self._export(path.rsplit("/", 1)[1])
            if path.startswith("/api/"):
                return self._json({"error": "not found"}, 404)
            return self._static(path)
        except BrokenPipeError:
            pass
        except Exception as e:  # surface errors, never crash the server
            try:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            except BrokenPipeError:
                pass

    # -- POST -----------------------------------------------------------
    def do_POST(self):
        u = urlparse(self.path)
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(ln) if ln else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "invalid json"}, 400)

            if u.path == "/api/switch":
                ns = argparse.Namespace(name=data.get("name", ""), verbose=False)
                rc, out = run_capture(apa.cmd_switch, ns)
                if rc != 0:
                    return self._json({"ok": False, "error": out or "switch failed",
                                       "cli": f"apa.py switch {ns.name}"}, 404)
                st = api_state()
                return self._json({"ok": True, "payload": out, "state": st,
                                   "cli": f"apa.py switch {ns.name}"})
            if u.path == "/api/clear":
                rc, out = run_capture(apa.cmd_clear, argparse.Namespace())
                return self._json({"ok": rc == 0, "output": out,
                                   "state": api_state(), "cli": "apa.py clear"})
            if u.path == "/api/session/use":
                ns = argparse.Namespace(action="use", name=data.get("name", ""),
                                        output=None, file=None, as_name=None)
                rc, out = run_capture(apa.cmd_session, ns)
                return self._json({"ok": rc == 0, "output": out,
                                   "sessions": api_sessions(),
                                   "cli": f"apa.py session use {ns.name}"})
            return self._json({"error": "not found"}, 404)
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            except BrokenPipeError:
                pass

    # -- helpers --------------------------------------------------------
    def _export(self, pid: str):
        reg = apa._load_registry()
        rid, _ = apa.resolve(pid, reg)
        if not rid:
            return self._json({"error": "unknown persona"}, 404)
        pfile = apa.persona_path(rid)
        if not pfile.exists():
            return self._json({"error": "payload missing"}, 404)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            manifest = {"format": "apa-bundle/1", "id": rid,
                        **{k: reg["agents"][rid].get(k)
                           for k in ("vendor", "family", "aliases", "tags", "sha256_12")},
                        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            for name, data in (("manifest.json", json.dumps(manifest, indent=2).encode()),
                               ("PERSONA.md", pfile.read_bytes())):
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        apa._audit("export", {"id": rid, "via": "cockpit"})
        return self._bytes(buf.getvalue(), "application/gzip",
                           extra={"Content-Disposition": f'attachment; filename="{rid}.apa"'})

    def _static(self, path: str):
        if path == "/":
            path = "/index.html"
        f = (UI_DIR / path.lstrip("/")).resolve()
        if not str(f).startswith(str(UI_DIR.resolve())) or not f.is_file():
            # SPA fallback: unknown paths get the shell (hash routing)
            f = UI_DIR / "index.html"
            if not f.is_file():
                return self._json({"error": "ui not built"}, 404)
        ctype = STATIC_TYPES.get(f.suffix, "application/octet-stream")
        self._bytes(f.read_bytes(), ctype)


def main() -> int:
    ap = argparse.ArgumentParser(prog="apa-serve", description="APA cockpit server")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default localhost)")
    ap.add_argument("--min-mem-mb", type=int, default=1024,
                    help="refuse to boot below this MemAvailable (LMK guard)")
    ap.add_argument("--no-guard", action="store_true", help="skip the memory guard")
    args = ap.parse_args()

    if not args.no_guard:
        avail = mem_available_mb()
        if avail is not None and avail < args.min_mem_mb:
            print(f"apa-serve: REFUSED — MemAvailable {avail} MB < "
                  f"{args.min_mem_mb} MB (Android LMK would kill the cockpit). "
                  f"Free memory or pass --no-guard.", file=sys.stderr)
            return 1

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    avail = mem_available_mb()
    print(f"APA cockpit on http://{args.host}:{args.port}  "
          f"(mem {avail if avail is not None else '?'} MB, ui={UI_DIR})")
    print("Ctrl-C to stop — CLI remains fully headless-capable.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\napa-serve: stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
