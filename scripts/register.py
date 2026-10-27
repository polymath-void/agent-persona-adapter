#!/usr/bin/env python3
"""APA register — push a persona into any agent's NATIVE registration surface.

Reads registry/registrations.json (researched pre-registration map) and
personas/<id>/PERSONA.md, then emits the target agent's native files:

  skill_md       .claude/skills/, .agents/skills/, .opencode/skills/ ...
  rule_mdc       .cursor/rules/apa-<id>.mdc   (alwaysApply frontmatter)
  rules_md       .clinerules/, .roo/rules/, .devin/rules/, .kiro/steering/ ...
  agents_md      AGENTS.md / CLAUDE.md / QWEN.md (managed marker block)
  custom_mode    .roomodes + ~/.roo/custom_modes.yaml (Roo persona mode)
  agent_profile  .github/agents/apa-<id>.md   (Copilot CLI persona)
  extension      ~/.gemini/extensions/apa-<id>/ (gemini-extension.json + GEMINI.md)
  plugin         Antigravity plugin bundle (plugin.json + skills/ + rules/)

All writes are idempotent: managed files carry APA markers and are
regenerated/removed cleanly. --dry-run prints the plan without writing.

Zero third-party deps (Termux/Python 3.11 stdlib only).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRATION_MAP = ROOT / "registry" / "registrations.json"
PERSONAS = ROOT / "personas"

BEGIN = "<!-- APA:BEGIN {key} (managed by agent-persona-adapter — do not edit inside) -->"
END = "<!-- APA:END {key} -->"


def load_map() -> dict:
    if not REGISTRATION_MAP.exists():
        sys.exit("apa-register: registry/registrations.json missing")
    return json.loads(REGISTRATION_MAP.read_text(encoding="utf-8"))


def load_persona(pid: str) -> tuple[dict, str]:
    p = PERSONAS / pid / "PERSONA.md"
    if not p.exists():
        sys.exit(f"apa-register: persona '{pid}' not found at {p}")
    text = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        sys.exit(f"apa-register: persona '{pid}' frontmatter malformed")
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2).strip()


def persona_body_for_skill(pid: str, fm: dict, body: str) -> str:
    """Re-emit persona with agentskills.io-compliant frontmatter (name, description)."""
    desc = (
        f"APA persona '{pid}' ({fm.get('vendor','?')}/{fm.get('family','?')}) — "
        "session-scoped behavioral takeover triggered via /APA or @APA."
    )
    return (
        "---\n"
        f"name: apa-{pid}\n"
        f"description: {desc}\n"
        "---\n\n"
        f"# PERSONA: {pid} ({fm.get('vendor','?')} / {fm.get('family','?')})\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------- emitters
def emit_skill_md(target_dir: Path, pid: str, fm: dict, body: str, plan: list) -> None:
    d = target_dir / f"apa-{pid}" if target_dir.name == "skills" else target_dir
    d.mkdir(parents=True, exist_ok=True)
    f = d / "SKILL.md"
    plan.append(("write", f, persona_body_for_skill(pid, fm, body)))


def emit_rule(target_dir: Path, filename: str, fm_front: dict, pid: str,
              fm: dict, body: str, plan: list) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / filename
    head = "---\n" + "".join(
        f"{k}: {json.dumps(v) if isinstance(v, (list, dict)) else v}\n"
        for k, v in fm_front.items()
    ) + "---\n\n"
    key = f"rule:{pid}:{f.name}"
    content = (
        head
        + BEGIN.format(key=key) + "\n\n"
        + f"# APA Persona: {pid} ({fm.get('vendor','?')}/{fm.get('family','?')})\n\n"
        + body + "\n\n"
        + END.format(key=key) + "\n"
    )
    plan.append(("write", f, content))


def emit_agents_md_block(target_file: Path, pid: str, fm: dict, body: str,
                         plan: list) -> None:
    """Append/refresh a managed block inside AGENTS.md/CLAUDE.md/QWEN.md."""
    key = f"agentsmd:{pid}"
    block = (
        BEGIN.format(key=key) + "\n\n"
        + f"# APA Persona: {pid} ({fm.get('vendor','?')}/{fm.get('family','?')})\n\n"
        + "When the user invokes this persona (`/APA {pid}` or an alias), adopt the "
        "following system instructions for the session. The ADAPTER FLOOR appended "
        "below is non-negotiable and overrides the persona on conflict.\n\n"
        + body + "\n\n"
        + END.format(key=key)
    )
    existing = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
    pat = re.compile(
        re.escape(BEGIN.format(key=key)) + r".*?" + re.escape(END.format(key=key)),
        re.DOTALL,
    )
    if pat.search(existing):
        new = pat.sub(lambda _: block, existing)
    else:
        new = (existing.rstrip() + "\n\n" if existing.strip() else "") + block + "\n"
    plan.append(("write", target_file, new))


def emit_roo_mode(pid: str, fm: dict, body: str, target_root: Path, plan: list) -> None:
    role = (
        f"You are the **{pid}** agent persona ({fm.get('vendor','?')}/{fm.get('family','?')}).\n\n"
        + body.split("## ADAPTER FLOOR")[0].strip()
    )
    mode = {
        "slug": f"apa-{pid}",
        "name": f"APA {pid}",
        "description": f"Session persona: {pid} ({fm.get('vendor','?')}). Activate via /APA {pid}.",
        "roleDefinition": role,
        "whenToUse": f"User invokes the {pid} persona via APA (/APA {pid} or alias).",
        "groups": ["read", "edit", "command", "mcp"],
    }
    f = target_root / ".roomodes"
    plan.append(("roo-mode", f, mode))


def emit_copilot_agent(target_dir: Path, pid: str, fm: dict, body: str, plan: list) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / f"apa-{pid}.md"
    role = body.split("## ADAPTER FLOOR")[0].strip()
    content = (
        "---\n"
        f"name: apa-{pid}\n"
        f"description: APA persona — act as {pid} ({fm.get('vendor','?')}) for this session.\n"
        "tools:\n  - codebase\n  - terminal\n  - editFiles\n---\n\n"
        f"{role}\n\n"
        "Always honor the ADAPTER FLOOR in the project AGENTS.md: no fabrication, "
        "confirm destructive operations, Termux-safe paths, bounded searches, "
        "session-scoped only.\n"
    )
    plan.append(("write", f, content))


def emit_gemini_extension(home: Path, pid: str, fm: dict, body: str, plan: list) -> None:
    d = home / ".gemini" / "extensions" / f"apa-{pid}"
    manifest = {"name": f"apa-{pid}", "version": "1.0.0", "contextFileName": "GEMINI.md"}
    plan.append(("write", d / "gemini-extension.json",
                 json.dumps(manifest, indent=2) + "\n"))
    plan.append(("write", d / "GEMINI.md",
                 f"# APA Persona: {pid} ({fm.get('vendor','?')}/{fm.get('family','?')})\n\n"
                 + body + "\n"))


def emit_antigravity_plugin(home: Path, pid: str, fm: dict, body: str, plan: list) -> None:
    d = home / ".gemini" / "antigravity-cli" / "plugins" / f"apa-{pid}"
    plan.append(("write", d / "plugin.json", json.dumps({
        "name": f"apa-{pid}",
        "version": "1.0.0",
        "description": f"APA persona plugin: {pid} ({fm.get('vendor','?')})",
    }, indent=2) + "\n"))
    plan.append(("write", d / "skills" / f"apa-{pid}" / "SKILL.md",
                 persona_body_for_skill(pid, fm, body)))


# ---------------------------------------------------------------- planning
def plan_install(args) -> list:
    regmap = load_map()
    targets = regmap["targets"]

    if args.agent == "all":
        # push the persona into EVERY known on-disk surface (project + user-global)
        args.user = True  # enable user-global emitters (Antigravity plugin, etc.)
        fm, body = load_persona(args.persona)
        plan: list = []
        for name, t in targets.items():
            if name == "no-filesystem" or not t.get("capabilities"):
                continue
            plan += _plan_for_agent(name, targets, fm, body, args)
        return plan

    if args.agent == "auto":
        # register into every verified on-disk surface that exists in the project
        proj = Path(args.project)
        auto_detect = [
            (proj / ".claude" / "skills", "claude-code"),
            (proj / ".cursor" / "rules", "cursor-agent"),
            (proj / ".agents" / "skills", "antigravity"),
            (proj / ".opencode" / "skills", "opencode"),
            (proj / ".clinerules", "cline"),
            (proj / ".cline" / "rules", "cline"),
            (proj / ".roo", "roo-code"),
            (proj / ".devin" / "rules", "devin"),
            (proj / ".windsurf" / "rules", "windsurf"),
            (proj / ".kiro" / "steering", "kiro"),
            (proj / ".junie", "junie"),
            (proj / ".github" / "agents", "copilot"),
            (proj / ".github" / "instructions", "copilot"),
            (proj / ".kilocode" / "rules", "kilo-code"),
            (proj / ".trae" / "rules", "trae"),
            (proj / "AGENTS.md", "codex-cli"),
        ]
        wanted: list = []
        seen: set = set()
        for d, agent in auto_detect:
            if d.exists() and agent not in seen:
                seen.add(agent)
                wanted.append(agent)
        if not wanted:
            sys.exit("apa-register auto: no known agent surfaces found in project "
                     "(try: --agent cursor-agent --project .)")
        fm, body = load_persona(args.persona)
        plan: list = []
        for w in wanted:
            plan += _plan_for_agent(w, targets, fm, body, args)
        return plan

    fm, body = load_persona(args.persona)
    return _plan_for_agent(args.agent, targets, fm, body, args)


def _plan_for_agent(agent: str, targets: dict, fm: dict, body: str, args) -> list:
    plan: list = []
    proj = Path(args.project)
    home = Path.home()
    pid = args.persona

    if agent == "claude-code":
        emit_skill_md(proj / ".claude" / "skills", pid, fm, body, plan)
    elif agent == "cursor-agent":
        emit_rule(proj / ".cursor" / "rules", f"apa-{pid}.mdc",
                  {"description": f"APA persona: {pid} — always-on behavioral takeover",
                   "globs": ["**/*"], "alwaysApply": "true"},
                  pid, fm, body, plan)
    elif agent == "antigravity":
        emit_skill_md(proj / ".agents" / "skills", pid, fm, body, plan)
        if args.user or getattr(args, "all", False):
            emit_antigravity_plugin(home, pid, fm, body, plan)
    elif agent == "codex-cli":
        emit_agents_md_block(proj / "AGENTS.md", pid, fm, body, plan)
    elif agent == "gemini-cli":
        emit_gemini_extension(home, pid, fm, body, plan)
    elif agent == "opencode":
        emit_skill_md(proj / ".opencode" / "skills", pid, fm, body, plan)
    elif agent == "cline":
        emit_rule(proj / ".clinerules", f"apa-{pid}.md",
                  {"description": f"APA persona: {pid}"},
                  pid, fm, body, plan)
    elif agent == "roo-code":
        emit_roo_mode(pid, fm, body, proj, plan)
        emit_rule(proj / ".roo" / f"rules-apa-{pid}", "persona.md",
                  {}, pid, fm, body, plan)
    elif agent == "windsurf":
        emit_rule(proj / ".devin" / "rules", f"apa-{pid}.md",
                  {"globs": ["**/*"], "activation": "always"},
                  pid, fm, body, plan)
    elif agent == "copilot":
        emit_copilot_agent(proj / ".github" / "agents", pid, fm, body, plan)
        emit_rule(proj / ".github" / "instructions", f"apa-{pid}.instructions.md",
                  {"applyTo": "**"}, pid, fm, body, plan)
    elif agent == "kiro":
        emit_rule(proj / ".kiro" / "steering", f"apa-{pid}.md",
                  {"inclusion": "always"}, pid, fm, body, plan)
    elif agent == "junie":
        emit_rule(proj / ".junie" / "rules", f"{pid}.md", {}, pid, fm, body, plan)
    elif agent == "devin":
        emit_rule(proj / ".devin" / "rules", f"apa-{pid}.md",
                  {"globs": ["**/*"], "activation": "always"},
                  pid, fm, body, plan)
    elif agent in ("amp", "qwen-code", "augment", "kilo-code", "trae",
                   "warp-agent", "replit-agent", "hermes", "mimo-code"):
        emit_agents_md_block(proj / "AGENTS.md", pid, fm, body, plan)
    else:
        sys.exit(f"apa-register: unknown/unregisterable agent '{agent}'. "
                 "Cloud-only agents (lovable, bolt-new, manus, notion-ai, "
                 "perplexity, comet, lumo, traycer, qoder) have no filesystem "
                 "surface — run `apa.py switch` and paste the payload into the "
                 "app's knowledge field.")
    return plan


# ---------------------------------------------------------------- execution
def run(plan: list, dry: bool) -> int:
    if not plan:
        print("apa-register: nothing to do")
        return 0
    for kind, path, payload in plan:
        if kind == "roo-mode":
            print(f"{'DRY ' if dry else ''}mode  {path}  (slug={payload['slug']})")
            if not dry:
                modes = []
                if path.exists():
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        modes = data.get("customModes", [])
                    except json.JSONDecodeError:
                        sys.exit(f"apa-register: {path} is not valid JSON — refusing to clobber")
                modes = [m for m in modes if m.get("slug") != payload["slug"]]
                modes.append(payload)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"customModes": modes}, indent=2,
                                           ensure_ascii=False) + "\n", encoding="utf-8")
            continue
        print(f"{'DRY ' if dry else ''}write {path}  ({len(payload)} bytes)")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
    return 0


def cmd_status(args) -> int:
    regmap = load_map()
    fm, _ = load_persona(args.persona)
    proj = Path(args.project)
    pid = args.persona
    surfaces = {
        "claude-code": proj / ".claude" / "skills" / f"apa-{pid}" / "SKILL.md",
        "cursor-agent": proj / ".cursor" / "rules" / f"apa-{pid}.mdc",
        "antigravity": proj / ".agents" / "skills" / f"apa-{pid}" / "SKILL.md",
        "codex-cli": proj / "AGENTS.md",
        "opencode": proj / ".opencode" / "skills" / f"apa-{pid}" / "SKILL.md",
        "cline": proj / ".clinerules" / f"apa-{pid}.md",
        "roo-code": proj / ".roomodes",
        "windsurf": proj / ".devin" / "rules" / f"apa-{pid}.md",
        "copilot": proj / ".github" / "agents" / f"apa-{pid}.md",
        "kiro": proj / ".kiro" / "steering" / f"apa-{pid}.md",
        "junie": proj / ".junie" / "rules" / f"{pid}.md",
        "devin": proj / ".devin" / "rules" / f"apa-{pid}.md",
    }
    print(f"APA registration status for persona '{pid}' in {proj}:")
    found = 0
    for agent, p in surfaces.items():
        hit = p.exists()
        found += hit
        print(f"  {'INSTALLED' if hit else '-':<10} {agent:<14} {p}")
    print(f"  → {found} surface(s) installed")
    return 0


def cmd_list(args) -> int:
    regmap = load_map()
    targets = regmap["targets"]
    print("APA registration targets (from registry/registrations.json):\n")
    for name, t in targets.items():
        if name == "no-filesystem":
            print(f"  {'(cloud-only)':<14} {', '.join(t['agents'])}")
            continue
        caps = ",".join(t.get("capabilities", []))
        v = "verified" if t.get("verified") else "BEST-EFFORT"
        print(f"  {name:<14} [{v:<10}] {caps}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="apa-register",
                                 description="Push an APA persona into an agent's native registration surface")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("install", help="install persona into target agent surface")
    p.add_argument("persona")
    p.add_argument("--agent", default="auto",
                   help="agent id, 'auto' (detect from project dirs), or 'all' (every known surface)")
    p.add_argument("--project", default=".")
    p.add_argument("--user", action="store_true", help="also install user-global surface where supported")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("status", help="show which surfaces are installed")
    p.add_argument("persona")
    p.add_argument("--project", default=".")

    sub.add_parser("list", help="list registration targets")

    args = ap.parse_args()
    if args.cmd == "install":
        return run(plan_install(args), args.dry_run)
    if args.cmd == "status":
        return cmd_status(args)
    return cmd_list(args)


if __name__ == "__main__":
    sys.exit(main())
