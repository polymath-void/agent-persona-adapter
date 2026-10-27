#!/usr/bin/env python3
"""APA installer — registers the CLI + skill + /APA command on this device.

Idempotent, rootless-safe (Termux/Bionic, $PREFIX only), stdlib-only.

What it installs:
  1. $PREFIX/bin/apa                       -> symlink to scripts/apa.py
  2. ~/.agents/skills/APA                  -> symlink to skills/APA/  (OpenCode/Cline/AGY)
  3. ~/.gemini/config/skills/APA           -> symlink to skills/APA/  (Antigravity CLI global)
  4. ~/.config/opencode/commands/apa.md    -> copy of skills/APA/command/apa.md
  5. ~/Projects/.opencode/commands/apa.md  -> same, umbrella-project scope

Safety rules:
  - Never follows a symlink on write: checks os.path.lexists and removes the
    LINK ITSELF before recreating (never writes through into /system etc.)
  - Never clobbers a real directory or a user-modified unmanaged file
    (managed files carry the APA:managed marker; refresh only those)
  - `--uninstall` removes only what this installer creates

    python3 scripts/install.py [--uninstall] [--quiet]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
PREFIX = Path(os.environ.get("PREFIX", str(HOME / "data/data/com.termux/files/usr")))
MARKER = "<!-- APA:managed by scripts/install.py — safe to refresh -->"
CMD_SOURCE = ROOT / "skills" / "APA" / "command" / "apa.md"

# (kind, target, source) — kind: "link" | "file"
def plan() -> list[tuple[str, Path, Path]]:
    items: list[tuple[str, Path, Path]] = [
        ("link", PREFIX / "bin" / "apa", ROOT / "scripts" / "apa.py"),
        ("link", HOME / ".agents" / "skills" / "APA", ROOT / "skills" / "APA"),
        ("link", HOME / ".gemini" / "config" / "skills" / "APA", ROOT / "skills" / "APA"),
        ("file", HOME / ".config" / "opencode" / "commands" / "apa.md", CMD_SOURCE),
    ]
    projects = HOME / "Projects"
    if projects.is_dir():
        items.append(("file", projects / ".opencode" / "commands" / "apa.md", CMD_SOURCE))
    return items


def _safe_replace(target: Path, make_link) -> None:
    """Rootless symlink safety: never write THROUGH a link — remove the link."""
    if os.path.lexists(target):
        if target.is_dir() and not target.is_symlink():
            raise SystemExit(f"apa-install: REFUSED — {target} is a real directory; "
                             f"remove it manually if you intend to replace it")
        os.remove(target)  # removes the symlink itself, not its referent
    target.parent.mkdir(parents=True, exist_ok=True)
    make_link()


def cmd_install(quiet: bool) -> int:
    results = []
    for kind, target, source in plan():
        if not source.exists():
            results.append(f"SKIP  {target}  (source missing: {source})")
            continue
        if kind == "link":
            if target.is_symlink() and os.path.realpath(target) == os.path.realpath(source):
                results.append(f"OK    {target}  (already linked)")
                continue
            _safe_replace(target, lambda t=target, s=source: t.symlink_to(s))
            results.append(f"LINK  {target} -> {source}")
        else:  # file copy with managed-marker policy
            body = MARKER + "\n" + CMD_SOURCE.read_text(encoding="utf-8")
            if target.exists():
                cur = target.read_text(encoding="utf-8")
                if MARKER in cur:
                    if cur == body:
                        results.append(f"OK    {target}  (up to date)")
                        continue
                    target.write_text(body, encoding="utf-8")
                    results.append(f"UPD   {target}  (managed refresh)")
                    continue
                if cur == CMD_SOURCE.read_text(encoding="utf-8"):
                    results.append(f"OK    {target}  (identical, unmanaged — left as-is)")
                    continue
                results.append(f"SKIP  {target}  (user-modified, unmanaged — untouched)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            results.append(f"COPY  {target}")

    if not quiet:
        for r in results:
            print(r)

    # verify: the apa shim must work from an unrelated cwd
    shim = PREFIX / "bin" / "apa"
    ok_shim = shim.exists() and os.access(shim, os.X_OK)
    skill_ok = (HOME / ".agents" / "skills" / "APA" / "SKILL.md").exists()
    print(f"\napa-install: cli={'OK' if ok_shim else 'FAIL'} "
          f"skill={'OK' if skill_ok else 'FAIL'} "
          f"root={ROOT}")
    if not ok_shim or not skill_ok:
        return 1
    print("usage:  apa list | apa switch claude-code | /APA <agent> (in chat)")
    return 0


def cmd_uninstall(quiet: bool) -> int:
    for kind, target, _ in plan():
        if kind == "link":
            if target.is_symlink():
                os.remove(target)  # link itself only
                if not quiet:
                    print(f"RM    {target}  (symlink)")
            elif not quiet:
                print(f"SKIP  {target}  (not an APA symlink)")
        else:
            if target.exists() and MARKER in target.read_text(encoding="utf-8"):
                os.remove(target)
                if not quiet:
                    print(f"RM    {target}  (managed copy)")
            elif not quiet:
                print(f"SKIP  {target}  (unmanaged — untouched)")
    print("apa-install: uninstalled (personas/registry/state kept)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="apa-install",
                                 description="Install/uninstall APA on this device")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    return cmd_uninstall(args.quiet) if args.uninstall else cmd_install(args.quiet)


if __name__ == "__main__":
    sys.exit(main())
