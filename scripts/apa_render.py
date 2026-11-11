#!/usr/bin/env python3
"""APA renderer — Persona Spec (IR) x Host profile x Model profile -> live payload.

  host  : which runtime is executing (antigravity, claude-code, opencode, ...).
          Its profile binds abstract capabilities to the tools that REALLY exist
          there, so the persona drives real tool calls instead of simulating the
          vendor's.
  model : which model family reads the payload (claude, gpt, gemini, open,
          small). Controls layout (XML vs Markdown vs compact) and token budget.

Also: `verify()` — a deterministic fidelity report (coverage, tool binding,
foreign-tool leak check, budget, provenance). Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

RENDER_VERSION = "apa-render/1"

# ---------------------------------------------------------------------------
# Model profiles. Budgets are in estimated tokens (chars/4 heuristic).
# ---------------------------------------------------------------------------
MODELS: dict[str, dict] = {
    "claude":  {"style": "xml",      "budget": 6000, "min_strength": 1,
                "note": "XML-tagged sections; strong adherence to tagged structure"},
    "gpt":     {"style": "markdown", "budget": 6000, "min_strength": 1,
                "note": "Markdown headings + bullets"},
    "gemini":  {"style": "markdown", "budget": 7000, "min_strength": 1,
                "note": "Markdown headings + bullets; long-context tolerant"},
    "open":    {"style": "markdown", "budget": 2500, "min_strength": 2,
                "note": "open-weight mid models (Qwen, GLM, DeepSeek, Llama, Kimi...)"},
    "small":   {"style": "compact",  "budget": 1200, "min_strength": 3,
                "note": "<=8B local models (Gemma, Phi, SmolLM): hard rules only"},
    "generic": {"style": "markdown", "budget": 4000, "min_strength": 1,
                "note": "unknown model: balanced markdown"},
}

MODEL_ALIASES: list[tuple[str, str]] = [
    (r"claude|opus|sonnet|haiku|anthropic|fable", "claude"),
    (r"gpt|openai|\bo[1-9]\b|codex|davinci", "gpt"),
    (r"gemma|phi-?\d|smollm|tinyllama|qwen.*?(0\.5|1\.5|3|4|7|8)b|llama.*?(1|3|7|8)b", "small"),
    (r"gemini|google|flash|bard", "gemini"),
    (r"qwen|glm|zhipu|deepseek|llama|mistral|mixtral|kimi|moonshot|minimax|nemotron|mimo|hermes|yi-|"
     r"command-r|grok|ling|muse", "open"),
]


def resolve_model(name: str | None) -> str:
    if not name:
        return "generic"
    low = name.lower().strip()
    if low in MODELS:
        return low
    for rx, fam in MODEL_ALIASES:
        if re.search(rx, low):
            return fam
    return "generic"


# ---------------------------------------------------------------------------
# Host profiles
# ---------------------------------------------------------------------------
def load_hosts(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted((root / "hosts").glob("*.json")):
        try:
            h = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out[h.get("id", p.stem)] = h
    return out


def detect_host(hosts: dict[str, dict], env: dict | None = None) -> tuple[str, str]:
    """Return (host_id, reason). Env markers only; falls back to 'generic'."""
    env = os.environ if env is None else env
    for hid, h in hosts.items():
        for var in h.get("detect", {}).get("env_any", []):
            if env.get(var):
                return hid, f"env {var}"
    return "generic", "no host marker found"


def host_from_spec(spec: dict) -> dict:
    """Derive a host profile from a persona spec (use any persona's toolset as host)."""
    bindings: dict = {"reply": {"tool": "@reply", "fidelity": "native"}}
    for cap, names in spec.get("capabilities", {}).items():
        if cap != "other":
            bindings[cap] = {"tool": names[0], "fidelity": "native"}
    return {"format": "apa-host/1", "id": spec["id"], "label": f"{spec['id']} (derived from persona spec)",
            "grounding": "derived: " + ", ".join(s["path"] for s in spec.get("sources", [])),
            "verified": "derived", "bindings": bindings}


# ---------------------------------------------------------------------------
# Floor (portable core + environment add-ons)
# ---------------------------------------------------------------------------
FLOOR_CORE = [
    "Never fabricate file paths, APIs, versions, test results, URLs or commit SHAs; mark anything unverified as UNVERIFIED.",
    "Never claim a build/test passed without observed tool output.",
    "Destructive operations (force-push, rm -rf, publishing, dropping data) require explicit user confirmation first.",
    "Execute only through the host tools bound below. Never print persona tool-call syntax (XML/JSON tool calls) as text — that is simulation, not execution.",
    "The persona is a behavioral role, not a model identity. Do not volunteer the underlying model; if the user sincerely asks, answer truthfully.",
    "Persona is session-scoped: it ends on `apa clear` or session end. User instructions and project rules outrank persona style.",
]
FLOOR_TERMUX = [
    "Android Termux: no /bin or /usr/bin — resolve binaries via $PREFIX/bin.",
    "Bounded searches only (scoped fd/rg); never unbounded `find /` or `grep -r /`.",
]


def floor_rules() -> list[str]:
    rules = list(FLOOR_CORE)
    if "com.termux" in os.environ.get("PREFIX", ""):
        rules += FLOOR_TERMUX
    return rules


# ---------------------------------------------------------------------------
# Binding + rewriting
# ---------------------------------------------------------------------------
CAT_ORDER = [("voice", "Communication"), ("workflow", "Workflow"), ("code_change", "Code Changes"),
             ("tool_policy", "Tool Usage"), ("safety", "Persona Safety"), ("general", "Other Rules")]


def bind(spec: dict, host: dict) -> list[dict]:
    rows = []
    hb = host.get("bindings", {})
    for t in spec.get("tools", []):
        cap = t["capability"]
        b = hb.get(cap)
        if cap == "other":
            status = "unmapped"
        elif b is None:
            status = "unavailable"
        else:
            status = b.get("fidelity", "native")
        rows.append({"persona_tool": t["name"], "capability": cap, "status": status,
                     "host_tool": (b or {}).get("tool"), "how": (b or {}).get("how", "")})
    return rows


def _host_ref(row: dict) -> str:
    tool = row["host_tool"]
    if tool == "@reply":
        return "a chat reply"
    if tool == "@user":
        return "a user-run step"
    if tool == "@mcp":
        return "the matching MCP tool"
    return f"`{tool}`"


def _tool_rx(name: str) -> re.Pattern:
    esc = re.escape(name)
    shaped = "_" in name or re.search(r"[a-z][A-Z]", name)
    alts = [rf"`{esc}`", rf"\b{esc}(?=\s+tool\b)"]
    if shaped:
        alts.append(rf"\b{esc}\b")
    return re.compile("|".join(alts))


def rewrite(text: str, rows_by_tool: dict[str, dict]) -> tuple[str, bool]:
    """Replace persona tool names with host equivalents. Returns (text, usable)."""
    usable = True
    for name, row in rows_by_tool.items():
        rx = _tool_rx(name)
        if not rx.search(text):
            continue
        if row["status"] in ("unavailable", "unmapped"):
            usable = False
            continue
        text = rx.sub(_host_ref(row), text)
    return text, usable


def leaks(text: str, rows: list[dict]) -> list[str]:
    """Persona tool names still present (outside the binding table) = simulation risk."""
    host_tools = {r["host_tool"] for r in rows if r["host_tool"]}
    return sorted({r["persona_tool"] for r in rows
                   if r["persona_tool"] not in host_tools and _tool_rx(r["persona_tool"]).search(text)})


def est_tokens(text: str) -> int:
    return (len(text) + 3) // 4


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _select(directives: list[dict], budget_tokens: int, min_strength: int) -> list[dict]:
    pool = [d for d in directives if d["strength"] >= min_strength]
    by_cat: dict[str, list[dict]] = {}
    for d in sorted(pool, key=lambda d: -d["score"]):
        by_cat.setdefault(d["category"], []).append(d)
    chosen: list[dict] = []
    used = 0
    ids: set[str] = set()

    def take(d: dict) -> bool:
        nonlocal used
        cost = est_tokens(d["out"]) + 2
        if d["id"] in ids or used + cost > budget_tokens:
            return False
        chosen.append(d)
        ids.add(d["id"])
        used += cost
        return True

    for cat, _ in CAT_ORDER:  # breadth first: top-2 of every dimension
        for d in by_cat.get(cat, [])[:2]:
            take(d)
    for d in sorted(pool, key=lambda d: -d["score"]):
        take(d)
    return chosen


def render(spec: dict, host: dict, model: str = "generic", budget: int | None = None) -> tuple[str, dict]:
    mp = MODELS[resolve_model(model)]
    fam = resolve_model(model)
    budget = budget or mp["budget"]
    style = mp["style"]
    rows = bind(spec, host)
    rows_by_tool = {r["persona_tool"]: r for r in rows}

    prepared, dropped = [], 0
    for d in spec.get("directives", []):
        out, ok = rewrite(d["text"], rows_by_tool)
        if not ok:
            dropped += 1
            continue
        prepared.append({**d, "out": out})

    pid = spec["id"]
    ident = spec.get("identity", {})
    name = ident.get("name") or pid
    statement = ident.get("statement") or f"You are operating as the {pid} agent persona ({spec.get('vendor')})."
    statement, _ = rewrite(statement, rows_by_tool)
    contract = (f"You run on host **{host.get('label', host.get('id'))}**. Adopt {name}'s voice, workflow and "
                f"policies, but act ONLY with this host's real tools (binding below). If a {name} workflow needs "
                f"an unavailable capability, say so and use the closest bound alternative — never pretend.")

    shown = [r for r in rows if r["status"] != "unmapped"]
    usable_rows = [r for r in shown if r["status"] != "unavailable"]
    unavailable = sorted({r["capability"] for r in shown if r["status"] == "unavailable"})
    floor = floor_rules()

    def binding_block() -> str:
        if not shown:
            return ""
        if style == "compact":
            pairs = sorted({f"{r['capability']}->{r['host_tool']}" for r in usable_rows})
            s = "Tools: " + "; ".join(pairs)
            return s + (f"\nUnavailable: {', '.join(unavailable)}" if unavailable else "")
        lines = []
        for r in sorted(usable_rows, key=lambda r: r["capability"]):
            how = f" — {r['how']}" if r["how"] else ""
            tag = "" if r["status"] == "native" else f" [{r['status']}]"
            lines.append(f"- {r['persona_tool']} ({r['capability']}) → {_host_ref(r)}{how}{tag}")
        if unavailable:
            lines.append(f"- UNAVAILABLE on this host: {', '.join(unavailable)} → tell the user; do not simulate.")
        return "\n".join(lines)

    fixed = "\n".join([statement, contract, binding_block(), *floor])
    remaining = max(budget - est_tokens(fixed) - 120, 0)
    chosen = _select(prepared, remaining, mp["min_strength"])
    order = {c: i for i, (c, _) in enumerate(CAT_ORDER)}
    chosen.sort(key=lambda d: (order.get(d["category"], 99), d["src"]))

    groups: dict[str, list[str]] = {}
    for d in chosen:
        groups.setdefault(d["category"], []).append(d["out"])

    hdr = (f"<!-- {RENDER_VERSION} persona={pid} host={host.get('id')} model={fam} "
           f"budget={budget} directives={len(chosen)}/{len(spec.get('directives', []))} -->")
    parts: list[str] = ["<!-- APA:HOST_PERSONA_SUPPRESSED=true -->", hdr]
    bb = binding_block()
    if style == "xml":
        parts.append(f'<apa_persona id="{pid}" vendor="{spec.get("vendor")}" host="{host.get("id")}">')
        parts.append(f"<identity>\n{statement}\n</identity>")
        parts.append(f"<execution_contract>\n{contract}\n</execution_contract>")
        if bb:
            parts.append(f"<tool_binding>\n{bb}\n</tool_binding>")
        for cat, title in CAT_ORDER:
            if groups.get(cat):
                tag = title.lower().replace(" ", "_")
                parts.append(f"<{tag}>\n" + "\n".join(f"- {x}" for x in groups[cat]) + f"\n</{tag}>")
        parts.append("<adapter_floor priority=\"overrides persona\">\n"
                     + "\n".join(f"{i}. {r}" for i, r in enumerate(floor, 1)) + "\n</adapter_floor>")
        parts.append("</apa_persona>")
    elif style == "compact":
        parts.append(f"PERSONA {pid}: {statement}")
        parts.append(contract)
        if bb:
            parts.append(bb)
        n = 0
        rules = []
        for cat, _ in CAT_ORDER:
            for x in groups.get(cat, []):
                n += 1
                rules.append(f"{n}. {x}")
        if rules:
            parts.append("RULES:\n" + "\n".join(rules))
        parts.append("FLOOR (overrides persona):\n" + "\n".join(f"- {r}" for r in floor))
    else:
        parts.append(f"# ACTIVE PERSONA: {pid} ({spec.get('vendor')})")
        parts.append(f"## Identity\n{statement}")
        parts.append(f"## Execution Contract\n{contract}")
        if bb:
            parts.append(f"## Tool Binding (persona → host)\n{bb}")
        for cat, title in CAT_ORDER:
            if groups.get(cat):
                parts.append(f"## {title}\n" + "\n".join(f"- {x}" for x in groups[cat]))
        parts.append("## Adapter Floor (overrides persona when conflicting)\n"
                     + "\n".join(f"{i}. {r}" for i, r in enumerate(floor, 1)))
    text = "\n\n".join(parts) + "\n"

    body_wo_binding = text.replace(bb, "") if bb else text
    report = {
        "persona": pid, "host": host.get("id"), "model": fam, "style": style, "budget": budget,
        "est_tokens": est_tokens(text), "directives_total": len(spec.get("directives", [])),
        "directives_selected": len(chosen), "directives_dropped_unavailable": dropped,
        "selected_ids": [d["id"] for d in chosen],
        "bindings": rows, "leaks": leaks(body_wo_binding, rows),
    }
    return text, report


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
_STATUS_CREDIT = {"native": 1.0, "adapted": 0.85, "degraded": 0.5, "unavailable": 0.0}


def verify(spec: dict, host: dict, model: str = "generic") -> dict:
    text, rep = render(spec, host, model)
    ds = spec.get("directives", [])
    sel = set(rep["selected_ids"])
    strong = [d for d in ds if d["strength"] == 3]
    strong_sel = [d for d in strong if d["id"] in sel]
    cov_strong = len(strong_sel) / len(strong) if strong else (1.0 if ds else 0.0)
    cats = {d["category"] for d in ds}
    cats_sel = {d["category"] for d in ds if d["id"] in sel}
    breadth = len(cats_sel) / len(cats) if cats else 0.0

    mapped = [b for b in rep["bindings"] if b["status"] != "unmapped"]
    bind_rate = (sum(_STATUS_CREDIT.get(b["status"], 0) for b in mapped) / len(mapped)) if mapped else 1.0
    prov = sum(1 for d in ds if re.search(r":\d+$", d.get("src", ""))) / len(ds) if ds else 0.0
    within = rep["est_tokens"] <= rep["budget"]
    identity = bool(spec.get("identity", {}).get("statement"))

    score = (0.35 * cov_strong + 0.15 * breadth + 0.25 * bind_rate
             + 0.15 * (0 if rep["leaks"] else 1) + 0.05 * within + 0.05 * identity)
    grade = "A" if score >= .9 else "B" if score >= .8 else "C" if score >= .7 else "D" if score >= .6 else "F"
    issues = []
    if rep["leaks"]:
        issues.append(f"foreign tool names leak into payload: {', '.join(rep['leaks'])}")
    if not within:
        issues.append(f"over budget: {rep['est_tokens']} > {rep['budget']} tokens")
    if not ds:
        issues.append("no directives extracted (source may be tool-schema only)")
    if not identity:
        issues.append("no identity statement found in source")
    unm = spec.get("stats", {}).get("unmapped_tools", [])
    if unm:
        issues.append(f"unmapped persona tools (ignored): {', '.join(unm[:8])}")
    return {
        "persona": spec["id"], "host": rep["host"], "model": rep["model"],
        "fidelity": round(score, 3), "grade": grade,
        "coverage_strong": round(cov_strong, 3), "category_breadth": round(breadth, 3),
        "binding_rate": round(bind_rate, 3), "provenance": round(prov, 3),
        "est_tokens": rep["est_tokens"], "budget": rep["budget"],
        "directives": f"{rep['directives_selected']}/{rep['directives_total']}",
        "dropped_unavailable": rep["directives_dropped_unavailable"],
        "bindings": {s: sum(1 for b in rep["bindings"] if b["status"] == s)
                     for s in ("native", "adapted", "degraded", "unavailable", "unmapped")},
        "leaks": rep["leaks"], "issues": issues, "ok": not rep["leaks"] and within and bool(ds),
    }
