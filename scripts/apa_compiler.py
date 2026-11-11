#!/usr/bin/env python3
"""APA persona compiler — vendor system prompt  ->  portable Persona Spec (IR).

Why: injecting a raw vendor prompt makes the host model *simulate* that agent —
it reads tool schemas it cannot call (e.g. Cursor's `codebase_search`) and
role-plays them. The compiler instead extracts what is actually portable:

  identity    — the persona's role statement ("You are X, ...")
  tools       — the persona's tool inventory, each mapped to an abstract
                CAPABILITY (shell, grep, edit_file, web_search, ...)
  directives  — behavioral rules (MUST/NEVER/ALWAYS/imperatives), classified
                into voice / workflow / code_change / tool_policy / safety /
                general, scored, and traced to source file:line

The IR (`personas/<id>/spec.json`) is deterministic (no timestamps) so it can be
diffed and versioned. Rendering for a concrete host + model lives in
apa_render.py. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

COMPILER_VERSION = "apa-compiler/1.0"

# ---------------------------------------------------------------------------
# Capability ontology. `names` are exact tool ids seen across vendor prompts
# (normalized: lowercase, alnum only). `kw` are fallback substrings.
# ---------------------------------------------------------------------------
CAPABILITIES: dict[str, dict] = {
    "read_file":       {"desc": "read file contents",
                        "names": ["readfile", "read", "viewfile", "openfile", "readmanyfiles", "view",
                                  "readfiles", "fsread", "viewcodeitem", "viewfileoutline", "cat"],
                        "kw": ["read_file", "view_file", "open_file", "readfile"]},
    "edit_file":       {"desc": "modify part of an existing file",
                        "names": ["editfile", "edit", "multiedit", "replaceinfile", "strreplace",
                                  "strreplaceeditor", "strreplacebasedtool", "searchreplace", "applypatch",
                                  "replace", "replacefilecontent", "multireplacefilecontent", "patch",
                                  "insertedit", "lovreplace", "editcode", "applydiff", "insertcontent",
                                  "searchandreplace", "fsedit", "findandreplacecode", "reapply"],
                        "kw": ["edit", "replace", "patch", "diff"]},
    "write_file":      {"desc": "create or overwrite a file",
                        "names": ["writefile", "write", "writetofile", "createfile", "writetofs",
                                  "lovwrite", "fswrite", "newfile", "createfolder"],
                        "kw": ["write", "create_file", "createfile"]},
    "delete_file":     {"desc": "delete a file",
                        "names": ["deletefile", "removefile", "lovdelete", "rm", "deletefiles"],
                        "kw": ["delete", "remove_file"]},
    "list_dir":        {"desc": "list a directory",
                        "names": ["listdir", "listfiles", "ls", "listdirectory", "list"],
                        "kw": ["list_dir", "list_files", "listdir"]},
    "glob":            {"desc": "find files by name/pattern",
                        "names": ["glob", "globfilesearch", "filesearch", "findbyname", "findfiles",
                                  "findfilebyname", "fileglob"],
                        "kw": ["glob", "find_by_name", "file_search"]},
    "grep":            {"desc": "exact/regex text search in files",
                        "names": ["grep", "grepsearch", "searchfiles", "searchfilecontent", "ripgrep",
                                  "lovsearchfiles", "findinfiles", "codesearch"],
                        "kw": ["grep", "search_files", "ripgrep"]},
    "semantic_search": {"desc": "meaning-based codebase search",
                        "names": ["codebasesearch", "semanticsearch", "searchcodebase", "codebaseretrieval",
                                  "codebase", "searchcode", "findcode"],
                        "kw": ["codebase", "semantic"]},
    "shell":           {"desc": "run a shell command",
                        "names": ["bash", "runterminalcmd", "executecommand", "runcommand", "shell",
                                  "runshellcommand", "exec", "terminal", "localshell", "shellexec",
                                  "executebash", "runinterminal", "bashtool", "command"],
                        "kw": ["shell", "bash", "terminal", "command", "exec"]},
    "shell_output":    {"desc": "inspect/kill background commands",
                        "names": ["bashoutput", "killshell", "commandstatus", "readterminal",
                                  "getterminaloutput", "shellview", "shellwait", "shellkill", "killbash"],
                        "kw": ["command_status", "terminal_output", "shell_view", "kill"]},
    "web_search":      {"desc": "search the web",
                        "names": ["websearch", "searchweb", "googlewebsearch", "infosearchweb", "search",
                                  "googlesearch", "bravesearch"],
                        "kw": ["web_search", "search_web", "websearch", "google"]},
    "web_fetch":       {"desc": "fetch a URL",
                        "names": ["webfetch", "fetch", "readurlcontent", "fetchurl", "fetchwebpage",
                                  "readurl", "urlfetch", "openurl", "fetchdocument"],
                        "kw": ["fetch", "url"]},
    "browser":         {"desc": "drive a real browser (click/type/screenshot)",
                        "names": ["browseraction", "computer", "browsernavigate", "browserclick",
                                  "navigate", "browserpreview", "openbrowserurl", "browsersubagent",
                                  "screenshot", "takescreenshot", "click", "browserview"],
                        "kw": ["browser", "navigate", "click", "screenshot", "computer"]},
    "todo":            {"desc": "maintain a task/todo list",
                        "names": ["todowrite", "todoread", "updateplan", "addtasks", "updatetasks",
                                  "managetodolist", "todo", "taskmanager", "updatetodolist", "taskboundary"],
                        "kw": ["todo", "plan", "tasks"]},
    "memory":          {"desc": "persist long-term memory",
                        "names": ["updatememory", "creatememory", "savememory", "remember", "memory"],
                        "kw": ["memory", "remember"]},
    "ask_user":        {"desc": "ask the user a question",
                        "names": ["askfollowupquestion", "askuserquestion", "messageaskuser", "askquestion",
                                  "askuser", "question", "notifyuser", "messagenotifyuser", "sendmessage"],
                        "kw": ["ask", "question", "notify_user", "message_user"]},
    "subagent":        {"desc": "delegate to a sub-agent",
                        "names": ["task", "dispatchagent", "invokesubagent", "spawnagent", "newtask",
                                  "agent", "subagent", "runsubagent"],
                        "kw": ["subagent", "sub_agent", "dispatch", "new_task"]},
    "diagnostics":     {"desc": "read linter/compiler diagnostics",
                        "names": ["readlints", "geterrors", "diagnostics", "getdiagnostics", "lint",
                                  "readlinterrors", "getproblems"],
                        "kw": ["lint", "diagnostic", "errors", "problems"]},
    "notebook":        {"desc": "edit Jupyter notebooks",
                        "names": ["editnotebook", "notebookedit", "notebookread", "editnotebookfile"],
                        "kw": ["notebook"]},
    "plan_mode":       {"desc": "plan-mode handoff / approval gate",
                        "names": ["exitplanmode", "planmoderespond", "enterplanmode", "proposeplan"],
                        "kw": ["plan_mode", "planmode"]},
    "mcp":             {"desc": "call MCP server tools",
                        "names": ["usemcptool", "accessmcpresource", "callmcptool", "mcp"],
                        "kw": ["mcp"]},
    "deploy":          {"desc": "deploy the app",
                        "names": ["deploy", "suggestdeploy", "deployapp", "deployment"],
                        "kw": ["deploy"]},
    "image_gen":       {"desc": "generate images",
                        "names": ["generateimage", "imagegen", "createimage"],
                        "kw": ["image_gen", "generate_image"]},
    "reply":           {"desc": "plain chat reply / completion message",
                        "names": ["attemptcompletion", "messageuser", "finalanswer", "respond", "idle",
                                  "planmodereply", "reply"],
                        "kw": ["completion", "final_answer", "respond"]},
}

_NAME_INDEX: dict[str, str] = {}
for _cap, _d in CAPABILITIES.items():
    for _n in _d["names"]:
        _NAME_INDEX.setdefault(_n, _cap)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def classify_tool(name: str) -> str:
    """Map a vendor tool id to an abstract capability ('other' if unknown)."""
    n = _norm(name)
    if n in _NAME_INDEX:
        return _NAME_INDEX[n]
    low = name.lower()
    tokens = set(re.split(r"[_\-\s]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()))

    def kw_hit(k: str) -> bool:
        return k in low if ("_" in k or len(k) >= 6) else k in tokens
    # ordered: most specific first
    for cap in ("semantic_search", "web_search", "web_fetch", "browser", "shell_output", "notebook",
                "diagnostics", "plan_mode", "mcp", "todo", "memory", "ask_user", "subagent", "deploy",
                "image_gen", "grep", "glob", "list_dir", "delete_file", "write_file", "edit_file",
                "read_file", "shell", "reply"):
        if any(kw_hit(k) for k in CAPABILITIES[cap]["kw"]):
            return cap
    return "other"


# ---------------------------------------------------------------------------
# Source loading / normalization
# ---------------------------------------------------------------------------
_CHAT_TOKENS = re.compile(r"<\|[a-z_]+\|>(system|user|assistant)?")


def _yaml_text_blocks(raw: str) -> str:
    """Pull `text: >` / `text: |` scalar blocks out of a YAML prompt dump (Amp)."""
    out: list[str] = []
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?text:\s*[>|][-+]?\s*$", lines[i])
        if not m:
            i += 1
            continue
        base = len(m.group(1))
        i += 1
        block: list[str] = []
        while i < len(lines):
            ln = lines[i]
            if ln.strip() and (len(ln) - len(ln.lstrip())) <= base:
                break
            block.append(ln)
            i += 1
        ind = min((len(b) - len(b.lstrip()) for b in block if b.strip()), default=0)
        out.append("\n".join(b[ind:] for b in block))
    return "\n\n".join(out) if out else raw


_BLOCK_TAGS = re.compile(r"^<(functions|tools)>\s*$")


def blank_tool_blocks(text: str) -> str:
    """Blank tool-schema blocks (keeps line numbers so provenance stays exact).

    Handles `namespace X { ... }` (OpenAI/Cursor TS schemas, brace-counted) and
    `<functions>...</functions>` / `<tools>...</tools>` XML tool lists.
    """
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        ns = re.match(r"^namespace\s+(\w+)\s*\{", ln)
        if ns:
            closer = re.compile(rf"^\}}\s*//\s*namespace\s+{ns.group(1)}\b")
            end = next((k for k in range(i + 1, len(lines)) if closer.match(lines[k])), None)
            if end is None:  # no named closer: brace-count, ignoring // comments
                depth, end = 0, i
                for k in range(i, len(lines)):
                    code = lines[k].split("//", 1)[0]
                    depth += code.count("{") - code.count("}")
                    end = k
                    if depth <= 0:
                        break
            for k in range(i, end + 1):
                lines[k] = ""
            i = end + 1
            continue
        m = _BLOCK_TAGS.match(ln)
        if m:
            close = f"</{m.group(1)}>"
            j = i
            while j < len(lines) and lines[j].strip() != close:
                j += 1
            if j < len(lines):
                for k in range(i, j + 1):
                    lines[k] = ""
                i = j + 1
                continue
        i += 1
    return "\n".join(lines)


def load_source(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    if path.suffix.lower() in (".yaml", ".yml"):
        raw = _yaml_text_blocks(raw)
    return _CHAT_TOKENS.sub("", raw)


def _raw_source(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return _CHAT_TOKENS.sub("", raw)


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Tool inventory extraction
# ---------------------------------------------------------------------------
_STRUCTURAL_TAGS = {
    "example", "examples", "reasoning", "think", "thinking", "communication", "tool_calling",
    "user_information", "env", "identity", "system", "user", "assistant", "context", "rules",
    "instructions", "output", "response", "answer", "code", "path", "content", "command", "diff",
    "query", "url", "result", "summary", "plan", "task", "tasks", "note", "notes", "important",
    "functions", "function", "parameters", "description", "name", "args", "arguments", "text",
    "old_str", "new_str", "file", "files", "commit", "message", "title", "body", "error",
    "multi_tool_use", "parallel", "format", "tools", "tool", "usage", "notes",
}

_OPEN_TAG = re.compile(r"^<([a-z_][\w-]*)>\s*$")

_TOOL_PATTERNS = [
    ("ts_type",  re.compile(r"^\s*type\s+([A-Za-z_][\w-]*)\s*=\s*\(", re.M)),
    ("json",     re.compile(r'"name"\s*:\s*"([A-Za-z_][\w-]*)"')),
    ("yaml",     re.compile(r"^\s*-?\s*name:\s*([A-Za-z_][\w-]*)\s*$", re.M)),
]


def extract_tools(text: str, src: str) -> list[dict]:
    """Return [{name, capability, via, src}] for tools DEFINED in the source."""
    found: dict[str, dict] = {}

    def add(name: str, via: str, pos: int) -> None:
        if name in found or len(name) < 2:
            return
        line = text.count("\n", 0, pos) + 1
        found[name] = {"name": name, "capability": classify_tool(name), "via": via, "src": f"{src}:{line}"}

    for via, rx in _TOOL_PATTERNS:
        for m in rx.finditer(text):
            name = m.group(1)
            if via == "yaml" and classify_tool(name) == "other":
                continue
            if via == "json" and name.lower() in _STRUCTURAL_TAGS:
                continue
            add(name, via, m.start())

    # Heading-defined tools (Claude Code `## Bash`, Cline `## execute_command`):
    # a heading that is a single identifier and is followed by Description/
    # Parameters/Usage within a few lines, or sits under a `# Tools` heading.
    lines = text.split("\n")
    in_tools = False
    offs = 0
    for i, ln in enumerate(lines):
        if _OPEN_TAG.match(ln):
            in_tools = False
        h = re.match(r"^(#{1,4})\s+(.+?)\s*$", ln)
        if h:
            title = h.group(2).strip()
            if len(h.group(1)) <= 2 and re.fullmatch(r"(available\s+)?tools?(\s+\w+)?", title, re.I):
                in_tools = True
            elif len(h.group(1)) == 1 and not re.search(r"tool", title, re.I):
                in_tools = False
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{1,40}", title):
                window = "\n".join(lines[i + 1:i + 8])
                described = re.search(r"^\s*(Description|Parameters|Usage)\s*:", window, re.M | re.I)
                if (in_tools and len(h.group(1)) == 2) or described:
                    if title.lower() not in _STRUCTURAL_TAGS and title.lower() not in ("tools", "functions"):
                        add(title, "heading", offs)
        offs += len(ln) + 1

    # XML-invocation tools (Devin `<str_replace path=..>`, Cline `<read_file>`):
    # only accepted when they classify to a known capability.
    for m in re.finditer(r"^<([a-z][a-z0-9_]{2,40})(?:\s+[a-z_]+=\"[^\"]*\")*\s*/?>", text, re.M):
        name = m.group(1)
        if name in _STRUCTURAL_TAGS or "_" not in name and _norm(name) not in _NAME_INDEX:
            continue
        if re.search(rf"^<{name}>\s*$", text, re.M) and re.search(rf"^</{name}>\s*$", text, re.M) \
                and not re.search(rf"^<{name}>\s*\n\s*<[a-z_]+>", text, re.M):
            continue  # a prose section wrapper like <task_management>, not an invocation
        if classify_tool(name) != "other":
            add(name, "xml", m.start())
    return list(found.values())


# ---------------------------------------------------------------------------
# Segmentation + classification
# ---------------------------------------------------------------------------
SKIP_SECTION = re.compile(
    r"user_?information|^env$|environment( details)?$|system ?info|knowledge cutoff|current date|"
    r"^examples?$|example[s_ ]|_example|tool use formatting|"
    r"^parameters$|^returns?$|^input schema", re.I)

CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("safety",      re.compile(r"secur|safety|refus|malicious|ethic|privacy|harm|legal|copyright|secret", re.I)),
    ("voice",       re.compile(r"tone|style|communicat|format|citing|citation|markdown|response|output|"
                               r"verbos|concis|language|persona|personality|reply|message", re.I)),
    ("code_change", re.compile(r"code ?change|making_code|edit|convention|coding|code style|implement|"
                               r"test|debug|refactor|lint|comment|commit|git|pull request", re.I)),
    ("workflow",    re.compile(r"task|doing|workflow|plan|process|approach|proactiv|agency|objective|"
                               r"context|research|todo|manage|mode|step|autonom|discover|understand", re.I)),
    ("tool_policy", re.compile(r"tool|command|terminal|shell|search|file", re.I)),
]

_CLOSE_TAG = re.compile(r"^</([a-z_][\w-]*)>\s*$")
_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*,?\s*$")
_CAPS_HEAD = re.compile(r"^([A-Z][A-Z0-9 _&/-]{3,40})$")


def segment(text: str) -> list[dict]:
    """Split into sections at markdown headings, top-level XML tags, CAPS headers."""
    sections: list[dict] = []
    cur = {"title": "(preamble)", "start": 1, "lines": []}
    for i, ln in enumerate(text.split("\n"), start=1):
        title = None
        m = _HEADING.match(ln)
        if m:
            title = m.group(2)
        elif _OPEN_TAG.match(ln):
            title = _OPEN_TAG.match(ln).group(1)
        elif _CAPS_HEAD.match(ln.strip()) and not ln.startswith(" "):
            title = ln.strip()
        if title is not None:
            if cur["lines"]:
                sections.append(cur)
            cur = {"title": title.strip("# *`:"), "start": i + 1, "lines": []}
            continue
        if _CLOSE_TAG.match(ln):
            continue
        cur["lines"].append((i, ln))
    if cur["lines"]:
        sections.append(cur)
    return sections


def _section_category(title: str, tool_names: set[str]) -> str:
    if title in tool_names or title.lower() in {t.lower() for t in tool_names}:
        return "tool_policy"
    for cat, rx in CATEGORY_RULES:
        if rx.search(title):
            return cat
    return "general"


# ---------------------------------------------------------------------------
# Directive extraction
# ---------------------------------------------------------------------------
_STRONG = re.compile(r"\b(MUST|NEVER|ALWAYS|IMPORTANT|CRITICAL|REQUIRED|MANDATORY|DO NOT|DON'T|ONLY)\b")
_MEDIUM = re.compile(r"\b(must|never|always|do not|don't|avoid|should|shouldn't|prefer|ensure|make sure|"
                     r"only|required?|forbidden|unless|instead of|refrain)\b", re.I)
_IMPERATIVE = re.compile(
    r"^(use|keep|prefer|read|run|check|write|avoid|ask|explain|follow|be|do|make|try|answer|respond|"
    r"reply|format|include|add|limit|minimi[sz]e|start|when|if|before|after|first|then|always|never|"
    r"don't|do not|only|verify|test|search|create|call|batch|stop|wait|confirm|summari[sz]e|mention|"
    r"cite|reference|focus|break|plan|think|consider|look|find|fix|implement|update|remember|treat|"
    r"assume|output|provide|state|tell|report|show|list|edit|prioriti[sz]e|default|never|refuse)\b", re.I)

# Sentences describing the vendor's runtime, not the persona's behavior.
_ENV_NOISE = re.compile(
    r"knowledge cutoff|today'?s date|current date is|the user'?s os|operating system is|"
    r"\bversion \d|model (name|id) is|you are powered by|powered by (the )?(model|claude|gpt|gemini)|"
    r"/help|report the issue|feedback|github\.com/anthropics|image input capabilities|"
    r"workspace (path|root) is|absolute path of|cwd is|working directory is", re.I)

_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_EXAMPLE = re.compile(r"<(example|examples|good-example|bad-example)[^>]*>.*?</\1>", re.S | re.I)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"`*(])")


def _strip_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", s)
    s = re.sub(r"<[a-z_/][^>]{0,40}>", "", s)
    return re.sub(r"\s+", " ", s).strip(" -*•")


def _units(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Group section lines into bullets/paragraphs, then sentences. Keeps line refs."""
    body = "\n".join(f"\x00{n}\x00{t}" for n, t in lines)
    body = _FENCE.sub("", body)
    body = _INLINE_EXAMPLE.sub("", body)
    units: list[tuple[int, str]] = []
    buf: list[str] = []
    buf_line = 0

    def flush() -> None:
        nonlocal buf, buf_line
        if buf:
            units.append((buf_line, " ".join(buf)))
        buf, buf_line = [], 0

    for raw in body.split("\n"):
        m = re.match(r"^\x00(\d+)\x00(.*)$", raw)
        if not m:
            continue
        n, t = int(m.group(1)), m.group(2)
        if t.lstrip().startswith("//"):
            continue  # schema comment residue
        if not t.strip():
            flush()
            continue
        if _BULLET.match(t):
            flush()
            buf_line = n
            buf = [_BULLET.sub("", t).strip()]
            continue
        if not buf:
            buf_line = n
        buf.append(t.strip())
    flush()

    out: list[tuple[int, str]] = []
    for n, u in units:
        u = _strip_md(u)
        if len(u) <= 320:
            out.append((n, u))
        else:
            out.extend((n, s) for s in _SENT_SPLIT.split(u))
    return out


def _strength(text: str) -> int:
    if _STRONG.search(text):
        return 3
    if _MEDIUM.search(text):
        return 2
    if _IMPERATIVE.match(text):
        return 1
    return 0


def _tool_mentions(text: str, inventory: dict[str, str]) -> list[str]:
    """Inventory tool names explicitly referenced (backticked, `X tool`, or identifier-shaped)."""
    hits = []
    for name in inventory:
        esc = re.escape(name)
        shaped = "_" in name or re.search(r"[a-z][A-Z]", name)
        if re.search(rf"`{esc}`|\b{esc}\s+tool\b", text) or (shaped and re.search(rf"\b{esc}\b", text)):
            hits.append(name)
    return hits


UNIT_RULES: list[tuple[str, re.Pattern]] = [
    ("safety",      re.compile(r"secur|malicious|harmful|secret|api key|credential|password|refus|exploit", re.I)),
    ("voice",       re.compile(r"\btone\b|concise|verbos|markdown|emoji|preamble|postamble|lines of text|"
                               r"answer (concisely|directly)|respond (in|with)|formatting|explanation", re.I)),
    ("code_change", re.compile(r"\bcode\b|comment|commit|\btests?\b|lint|refactor|import|librar|function|"
                               r"\bedit", re.I)),
    ("workflow",    re.compile(r"\bplan|\btasks?\b|\bsteps?\b|before|after|context|understand|investigat|"
                               r"verify|\bgoal", re.I)),
    ("tool_policy", re.compile(r"\btools?\b|command|shell|terminal|search|browser", re.I)),
]

_CAT_WEIGHT = {"voice": 4, "safety": 3, "workflow": 3, "code_change": 3, "general": 2, "tool_policy": 1}


def compile_text(sources: list[tuple[str, str, str]], meta: dict) -> dict:
    """Compile [(display_path, prose_text, tool_text)] into a Persona Spec dict."""
    inventory: dict[str, dict] = {}
    for src, _, raw in sources:
        for t in extract_tools(raw, src):
            inventory.setdefault(t["name"], t)
    inv_caps = {n: t["capability"] for n, t in inventory.items()}

    identity: dict = {}
    directives: list[dict] = []
    seen: set[str] = set()
    stats = {"sections": 0, "skipped_sections": 0, "units": 0, "dropped_env": 0, "dropped_weak": 0}

    for src, text, _ in sources:
        text = blank_tool_blocks(text)
        total_lines = text.count("\n") + 1
        for sec in segment(text):
            stats["sections"] += 1
            title = sec["title"]
            body = "\n".join(t for _, t in sec["lines"])
            tool_def = bool(re.search(r"^\s*type\s+\w+\s*=\s*\(|\"parameters\"\s*:", body, re.M))
            if SKIP_SECTION.search(title) or (tool_def and title not in inventory):
                stats["skipped_sections"] += 1
                continue
            cat = _section_category(title, set(inventory))
            for line, unit in _units(sec["lines"]):
                stats["units"] += 1
                if not identity and re.match(r"^You are\b", unit) and len(unit) < 600:
                    stmt = re.sub(r",?\s*(powered by|based on|running on)\s+.+?(?=,|\.\s|\.$|$)", "", unit)
                    identity = {"statement": stmt, "src": f"{src}:{line}"}
                    continue
                if not (15 <= len(unit) <= 420) or unit.endswith(":"):
                    continue
                if _ENV_NOISE.search(unit):
                    stats["dropped_env"] += 1
                    continue
                strength = _strength(unit)
                if strength == 0:
                    stats["dropped_weak"] += 1
                    continue
                key = re.sub(r"[^a-z0-9]", "", unit.lower())[:80]
                if key in seen:
                    continue
                seen.add(key)
                tools = _tool_mentions(unit, inv_caps)
                d_cat = cat
                if cat == "general":
                    for c, rx in UNIT_RULES:
                        if rx.search(unit):
                            d_cat = c
                            break
                position = 1.0 - (line / max(total_lines, 1))
                score = strength * 10 + _CAT_WEIGHT.get(d_cat, 2) + round(2 * position, 2)
                if tool_def or title in inventory:
                    score -= 3  # tool-doc prose: useful but secondary
                directives.append({
                    "text": unit, "category": d_cat, "strength": strength,
                    "score": round(score, 2), "tools": tools,
                    "capabilities": sorted({inv_caps[t] for t in tools}),
                    "section": title[:60], "src": f"{src}:{line}",
                })

    for i, d in enumerate(directives, 1):
        d["id"] = f"d{i:03d}"
    caps: dict[str, list[str]] = {}
    for n, c in inv_caps.items():
        caps.setdefault(c, []).append(n)

    m = re.match(r"^You are (?:an? |the )?([A-Z][\w.\-]*(?: [A-Z][\w.\-]*){0,3})"
                 r"(?:,|\.|:| an?\b| the\b| built| created| made| designed| developed)",
                 identity.get("statement", ""))
    identity["name"] = (m.group(1).strip() if m else meta.get("name") or meta.get("id"))
    stats.update({
        "directives": len(directives),
        "strong": sum(1 for d in directives if d["strength"] == 3),
        "tools": len(inventory),
        "unmapped_tools": sorted(n for n, c in inv_caps.items() if c == "other"),
    })
    return {
        "format": "apa-spec/1",
        "compiler": COMPILER_VERSION,
        "id": meta.get("id"),
        "vendor": meta.get("vendor"),
        "family": meta.get("family"),
        "sources": [{"path": s, "sha256_12": _sha12(r), "lines": r.count("\n") + 1} for s, _, r in sources],
        "identity": identity,
        "tools": sorted(inventory.values(), key=lambda t: t["name"].lower()),
        "capabilities": {k: sorted(v) for k, v in sorted(caps.items())},
        "directives": directives,
        "stats": stats,
    }


def persona_body_source(persona_md: str) -> str:
    """Extract the hand-written body of a custom/imported PERSONA.md (no frontmatter/floor)."""
    text = re.sub(r"^---\n.*?\n---\n", "", persona_md, count=1, flags=re.S)
    text = text.split("## ADAPTER FLOOR")[0]
    m = re.search(r"## SOURCE SYSTEM INSTRUCTIONS\s*\n(.*)", text, re.S)
    return (m.group(1) if m else text).strip()


def compile_persona(root: Path, pid: str, entry: dict, write: bool = True) -> dict:
    """Compile one registry entry. Sources: entry['sources'] (ref-repo files) or PERSONA.md body."""
    srcs: list[tuple[str, str]] = []
    for rel in entry.get("sources", []):
        p = root / rel
        if p.exists():
            srcs.append((rel, load_source(p), _raw_source(p)))
    pfile = root / "personas" / pid / "PERSONA.md"
    if not srcs and pfile.exists():
        body = persona_body_source(pfile.read_text(encoding="utf-8"))
        srcs.append((f"personas/{pid}/PERSONA.md", body, body))
    if not srcs:
        raise FileNotFoundError(f"no sources for persona '{pid}'")
    spec = compile_text(srcs, {"id": pid, **entry})
    if write:
        out = root / "personas" / pid / "spec.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name("spec.json.tmp")
        tmp.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(out)
    return spec


def spec_is_stale(root: Path, pid: str, entry: dict) -> bool:
    """True if spec.json is missing, from another compiler version, or sources changed."""
    sp = root / "personas" / pid / "spec.json"
    if not sp.exists():
        return True
    try:
        spec = json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    if spec.get("compiler") != COMPILER_VERSION:
        return True
    for s in spec.get("sources", []):
        p = root / s["path"]
        if not p.exists():
            return True
        text = _raw_source(p)
        if s["path"].endswith("PERSONA.md"):
            text = persona_body_source(p.read_text(encoding="utf-8"))
        if _sha12(text) != s["sha256_12"]:
            return True
    return False
