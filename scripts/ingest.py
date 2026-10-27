#!/usr/bin/env python3
"""APA ingest — harvest ref-repo system prompts into personas/<id>/PERSONA.md
plus registry/agents.json.

Reads vendor directories from ../ref-repo, extracts persona prose, normalizes,
and emits a per-agent persona payload with frontmatter metadata + alias table.
"""
from __future__ import annotations

import json
import re
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "ref-repo"
OUT_PERSONAS = ROOT / "personas"
OUT_REGISTRY = ROOT / "registry" / "agents.json"

# vendor dir -> persona spec (id, vendor, family, aliases, invocations, file priority)
SPEC: list[dict] = [
    {"id": "claude-code",   "vendor": "Anthropic", "family": "claude",
     "aliases": ["claude", "cc", "claudecode", "anthropic"],
     "files": ["Anthropic/Claude Code/Prompt.txt", "Anthropic/Claude Code 2.0.txt"]},
    {"id": "cursor-agent",  "vendor": "Cursor", "family": "cursor",
     "aliases": ["cursor", "cur"],
     "files": ["Cursor Prompts/Agent Prompt 2.0.txt", "Cursor Prompts/Agent Prompt v1.2.txt"]},
    {"id": "antigravity",   "vendor": "Google", "family": "agy",
     "aliases": ["agy", "antigravity", "google-antigravity", "ag"],
     "files": ["Google/Antigravity/Fast Prompt.txt", "Google/Antigravity/planning-mode.txt"]},
    {"id": "codex-cli",     "vendor": "OpenAI", "family": "codex",
     "aliases": ["codex", "openai-codex", "oai"],
     "files": ["Open Source prompts/Codex CLI/openai-codex-cli-system-prompt-20250820.txt",
               "Open Source prompts/Codex CLI/Prompt.txt"]},
    {"id": "gemini-cli",    "vendor": "Google", "family": "gemini",
     "aliases": ["gemini", "gcli", "google-cli"],
     "files": ["Open Source prompts/Gemini CLI/google-gemini-cli-system-prompt.txt"]},
    {"id": "opencode",      "vendor": "OpenCode", "family": "opencode",
     "aliases": ["oc", "opn", "opencode-oc"],
     "files": ["Open Source prompts/OpenCode/Agent Prompt (mimo.v2.5-free) 2026-09-11.txt",
               "Open Source prompts/OpenCode/Agent Prompt (gpt.5.6.sol) 2026-09-11.txt"]},
    {"id": "cline",         "vendor": "Cline", "family": "cline",
     "aliases": ["cl", "clinerobot"],
     "files": ["Open Source prompts/Cline/Prompt.txt"]},
    {"id": "roo-code",      "vendor": "Roo", "family": "roo",
     "aliases": ["roo", "roocode", "roo-code-agent"],
     "files": ["Open Source prompts/RooCode/Prompt.txt"]},
    {"id": "windsurf",      "vendor": "Windsurf", "family": "windsurf",
     "aliases": ["ws", "cascade", "codeium"],
     "files": ["Windsurf/Prompt Wave 11.txt", "Windsurf/Tools Wave 11.txt"]},
    {"id": "qwen-code",     "vendor": "Qwen", "family": "qwen",
     "aliases": ["qwen", "qw", "qcoder"],
     "files": ["Open Source prompts/Qwen Code/Agent Prompt (gpt.5.6.sol) 2026-09-11.txt"]},
    {"id": "copilot",       "vendor": "GitHub", "family": "copilot",
     "aliases": ["gh", "github-copilot", "cp"],
     "files": ["VSCode Agent/Prompt.txt", "VSCode Agent/claude-sonnet-4.txt"]},
    {"id": "amp",           "vendor": "Sourcegraph", "family": "amp",
     "aliases": ["amper", "sg"],
     "files": ["Amp/README.md"]},
    {"id": "warp-agent",    "vendor": "Warp", "family": "warp",
     "aliases": ["warp", "wp"],
     "files": ["Warp.dev/Prompt.txt"]},
    {"id": "trae",          "vendor": "ByteDance", "family": "trae",
     "aliases": ["bytedance", "tr"],
     "files": ["Trae/Builder Prompt.txt"]},
    {"id": "kiro",          "vendor": "AWS", "family": "kiro",
     "aliases": ["aws-kiro", "kr"],
     "files": ["Kiro/Spec_Prompt.txt"]},
    {"id": "junie",         "vendor": "JetBrains", "family": "junie",
     "aliases": ["jb", "jetbrains"],
     "files": ["Junie/Prompt.txt"]},
    {"id": "devin",         "vendor": "Cognition", "family": "devin",
     "aliases": ["cognition", "dv"],
     "files": ["Devin AI/Prompt.txt"]},
    {"id": "replit-agent",  "vendor": "Replit", "family": "replit",
     "aliases": ["replit", "rp"],
     "files": ["Replit/Prompt.txt"]},
    {"id": "lovable",       "vendor": "Lovable", "family": "lovable",
     "aliases": ["lov", "lv"],
     "files": ["Lovable/Agent Prompt.txt"]},
    {"id": "bolt-new",      "vendor": "StackBlitz", "family": "bolt",
     "aliases": ["bolt", "stackblitz"],
     "files": ["Open Source prompts/Bolt/Prompt.txt"]},
    {"id": "augment",       "vendor": "Augment", "family": "augment",
     "aliases": ["aug", "augment-code"],
     "files": ["Augment Code/claude-4-sonnet-agent-prompts.txt"]},
    {"id": "kilo-code",     "vendor": "Kilo", "family": "kilo",
     "aliases": ["kilo", "kl"],
     "files": ["Open Source prompts/Kilo Code/Agent Prompt (kilo.auto-free) 2026-09-11.txt"]},
    {"id": "manus",         "vendor": "Manus", "family": "manus",
     "aliases": ["mn", "manus-agent"],
     "files": ["Manus Agent Tools & Prompt/Prompt.txt"]},
    {"id": "qoder",         "vendor": "Qoder", "family": "qoder",
     "aliases": ["qd", "quest"],
     "files": ["Qoder/prompt.txt"]},
    {"id": "traycer",       "vendor": "Traycer", "family": "traycer",
     "aliases": ["tc", "traycer-ai"],
     "files": ["Traycer AI/phase_mode_prompts.txt"]},
    {"id": "notion-ai",     "vendor": "Notion", "family": "notion",
     "aliases": ["notion", "nt"],
     "files": ["NotionAi/Prompt.txt"]},
    {"id": "perplexity",    "vendor": "Perplexity", "family": "pplx",
     "aliases": ["pplx", "pxy"],
     "files": ["Perplexity/Prompt.txt"]},
    {"id": "comet",         "vendor": "Perplexity", "family": "comet",
     "aliases": ["perplexity-browser", "comet-assistant"],
     "files": ["Comet Assistant/System Prompt.txt"]},
    {"id": "hermes",        "vendor": "Nous", "family": "hermes",
     "aliases": ["nous", "her"],
     "files": ["Open Source prompts/Hermes/Agent Prompt (nemotron.3.5.lightning-free) 2026-09-11.txt"]},
    {"id": "lumo",          "vendor": "Proton", "family": "lumo",
     "aliases": ["proton", "lm"],
     "files": ["Open Source prompts/Lumo/Prompt.txt"]},
    {"id": "mimo-code",     "vendor": "Xiaomi", "family": "mimo",
     "aliases": ["mimo", "xi"],
     "files": ["Open Source prompts/MiMo Code/Agent Prompt (mimo.v2.5) 2026-09-11.txt"]},
    # --- Phase 3: extended vendors ---
    {"id": "cluely",        "vendor": "Cluely", "family": "cluely",
     "aliases": ["cly", "cluely-assistant"],
     "files": ["Cluely/Default Prompt.txt", "Cluely/Enterprise Prompt.txt"]},
    {"id": "codebuddy",     "vendor": "Tencent", "family": "codebuddy",
     "aliases": ["cb", "tencent-codebuddy"],
     "files": ["CodeBuddy Prompts/Craft Prompt.txt", "CodeBuddy Prompts/Chat Prompt.txt"]},
    {"id": "emergent",      "vendor": "Emergent", "family": "emergent",
     "aliases": ["emg", "emergent-sh"],
     "files": ["Emergent/Prompt.txt"]},
    {"id": "leap-new",      "vendor": "Leap.new", "family": "leap",
     "aliases": ["leap", "lp"],
     "files": ["Leap.new/Prompts.txt"]},
    {"id": "orchids",       "vendor": "Orchids", "family": "orchids",
     "aliases": ["orch", "orchids-app"],
     "files": ["Orchids.app/System Prompt.txt", "Orchids.app/Decision-making prompt.txt"]},
    {"id": "poke",          "vendor": "Poke", "family": "poke",
     "aliases": ["pk", "poke-agent"],
     "files": ["Poke/Poke agent.txt"]},
    {"id": "same-dev",      "vendor": "Same.dev", "family": "same",
     "aliases": ["same", "samedev"],
     "files": ["Same.dev/Prompt.txt"]},
    {"id": "v0",            "vendor": "Vercel", "family": "v0",
     "aliases": ["vercel", "v0dev"],
     "files": ["v0 Prompts and Tools/Prompt.txt"]},
    {"id": "xcode",         "vendor": "Apple", "family": "xcode",
     "aliases": ["apple", "xc", "swift-ide"],
     "files": ["Xcode/ExplainAction.txt", "Xcode/DocumentAction.txt"]},
    {"id": "zai-code",      "vendor": "Zhipu", "family": "zai",
     "aliases": ["zai", "zhipu", "glm-code"],
     "files": ["Z.ai Code/prompt.txt"]},
    {"id": "claude-chrome", "vendor": "Anthropic", "family": "claude",
     "aliases": ["chrome", "claude-browser", "ccr"],
     "files": ["Anthropic/Claude for Chrome/Prompt.txt"]},
]

# capability tags per persona — powers `apa.py list --tag` / `apa.py search`
TAGS: dict[str, list[str]] = {
    "claude-code":  ["terminal", "tdd", "git-flow", "refactoring", "general"],
    "cursor-agent": ["ide", "typescript", "react", "refactoring", "multi-file"],
    "antigravity":  ["ide", "planning", "gcp", "vertex", "terminal"],
    "codex-cli":    ["terminal", "git-flow", "sandbox", "general"],
    "gemini-cli":   ["terminal", "gcp", "extensions", "general"],
    "opencode":     ["terminal", "tdd", "free-models", "general"],
    "cline":        ["ide", "planning", "act-mode", "vscode", "checkpoints"],
    "roo-code":     ["ide", "modes", "architect", "tdd", "vscode"],
    "windsurf":     ["ide", "cascade", "memories", "rules"],
    "copilot":      ["ide", "github", "pr-review", "agent-mode", "vscode"],
    "qwen-code":    ["terminal", "alibaba", "general"],
    "amp":          ["terminal", "sourcegraph", "multi-model"],
    "warp-agent":   ["terminal", "workflows", "blocks"],
    "trae":         ["ide", "builder", "bytedance"],
    "kiro":         ["ide", "spec-driven", "aws", "steering", "planning"],
    "junie":        ["ide", "jetbrains", "kotlin", "debugging"],
    "devin":        ["autonomous", "browser", "pr", "planning"],
    "replit-agent": ["cloud", "fullstack", "deploy"],
    "lovable":      ["react", "supabase", "saas", "fullstack"],
    "bolt-new":     ["react", "stackblitz", "fullstack", "browser"],
    "augment":      ["ide", "codebase-context", "vscode"],
    "kilo-code":    ["ide", "modes", "vscode"],
    "manus":        ["autonomous", "browser", "research", "tools"],
    "qoder":        ["ide", "quest", "agentic"],
    "traycer":      ["planning", "phases", "orchestration"],
    "notion-ai":    ["docs", "knowledge", "workspace"],
    "perplexity":   ["research", "search", "citations"],
    "comet":        ["browser", "research", "shopping"],
    "hermes":       ["open-weight", "terminal", "nous"],
    "lumo":         ["privacy", "terminal", "proton"],
    "mimo-code":    ["terminal", "xiaomi", "general"],
    "cluely":       ["realtime", "screen", "stealth"],
    "codebuddy":    ["ide", "craft", "tencent"],
    "emergent":     ["autonomous", "fullstack", "generation"],
    "leap-new":     ["no-code", "saas", "generation"],
    "orchids":      ["planning", "decision-making", "workflows"],
    "poke":         ["realtime", "voice", "agent"],
    "same-dev":     ["clone", "fullstack", "replication"],
    "v0":           ["react", "ui", "vercel", "generation"],
    "xcode":        ["ide", "swift", "ios", "macos"],
    "zai-code":     ["terminal", "zhipu", "glm"],
    "claude-chrome": ["browser", "chrome", "assistant"],
}

# generic behavior floor injected into every persona (safety + anti-hallucination)
FLOOR = """
---
## ADAPTER FLOOR (non-negotiable, overrides persona below when conflicting)
The persona above governs tone, workflow, tools, and heuristics ONLY.
The following remain in force regardless of persona:
1. Never fabricate: file paths, APIs, versions, test results, URLs, or commit SHAs.
   If unverified, label as "UNVERIFIED" or state uncertainty explicitly.
2. Never claim a build/test passed without observed terminal output.
3. No `/bin` or `/usr/bin` paths on Android Termux — resolve via `$PREFIX/bin`.
4. Destructive ops (git push --force, rm -rf, package publish) require explicit
   human confirmation first.
5. Bounded searches only (fd/rg scoped); never unbounded `find /` or `grep -r /`.
6. Session-scoped persona: this persona ends when the APA session ends or
   `/APA clear` is issued. No persistence outside the session.
---
"""


def normalize(text: str, max_bytes: int = 24000) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    if len(text.encode()) > max_bytes:
        # keep the head — behavioral directives live early in system prompts
        cut = text[:max_bytes].rsplit("\n", 1)[0]
        text = cut + "\n\n[...truncated by APA ingest: full source in ref-repo/...]"
    return text.strip()


def first_existing(files: list[str]) -> tuple[Path | None, str | None]:
    for rel in files:
        p = REF / rel
        if p.exists():
            return p, rel
    # fallback: scan vendor top-level dir for any .txt/.md
    if files:
        top = (REF / files[0]).parent
        if top.exists():
            for cand in sorted(top.rglob("*")):
                if cand.suffix.lower() in (".txt", ".md"):
                    return cand, str(cand.relative_to(REF))
    return None, None


def build() -> int:
    registry: dict = {"agents": {}}
    built = skipped = 0

    for spec in SPEC:
        pid = spec["id"]
        src, rel = first_existing(spec["files"])
        if src is None:
            skipped += 1
            continue
        raw = src.read_text(encoding="utf-8", errors="replace")
        body = normalize(raw)
        digest = hashlib.sha256(body.encode()).hexdigest()[:12]

        outdir = OUT_PERSONAS / pid
        outdir.mkdir(parents=True, exist_ok=True)
        front = (
            f"---\n"
            f"id: {pid}\n"
            f"vendor: {spec['vendor']}\n"
            f"family: {spec['family']}\n"
            f"source: ref-repo/{rel}\n"
            f"sha256_12: {digest}\n"
            f"invocations: ['{pid}'"
            + "".join(f", '{a}'" for a in spec["aliases"][:3])
            + "]\n"
            f"---\n\n"
        )
        persona_md = (
            front
            + f"# PERSONA: {pid} ({spec['vendor']} / {spec['family']})\n\n"
            + "## IDENTITY\n"
            + f"You are now running the **{pid}** agent persona. Adopt the system "
            + "instructions below verbatim as your operating behavior for this session.\n\n"
            + "## SOURCE SYSTEM INSTRUCTIONS\n\n"
            + body
            + "\n\n"
            + FLOOR
        )
        (outdir / "PERSONA.md").write_text(persona_md, encoding="utf-8")
        (outdir / "SOURCE.json").write_text(
            json.dumps(
                {
                    "id": pid,
                    "source": f"ref-repo/{rel}",
                    "sha256_12": digest,
                    "bytes": len(body),
                    "note": "educational persona extraction — see policy/PERSONA_POLICY.md",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        registry["agents"][pid] = {
            "vendor": spec["vendor"],
            "family": spec["family"],
            "aliases": spec["aliases"],
            "invocations": [f"/APA {pid}", f"@APA {pid}"]
            + [f"@APA {a}" for a in spec["aliases"][:3]],
            "payload": f"personas/{pid}/PERSONA.md",
            "sha256_12": digest,
            "tags": TAGS.get(pid, []),
            "origin": "ref-repo",
        }
        built += 1

    OUT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OUT_REGISTRY.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"apa-ingest: built={built} skipped={skipped} registry={OUT_REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
