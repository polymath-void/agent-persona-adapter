/* APA Cockpit — vanilla JS SPA. Zero deps, zero build.
 *
 * Dual-mode (docs/WEBUI.md §8): feature-detects /api/state.
 *   LIVE mode      — thin client over server/serve.py (real fs mutations)
 *   SNAPSHOT mode  — file:// or any static host; data from window.APA_DATA
 *                    (public/snapshot.js) or a dropped snapshot.json;
 *                    mutations become downloadable artifacts + clipboard.
 */
"use strict";

/* ================= store ================= */
const Store = {
  mode: null,           // "live" | "snapshot"
  data: null,           // snapshot payload (both modes keep one for grid render)
  state: null,          // {session, active, prev, activated_at, entry, suppressed}
  overlay: null,        // snapshot-mode virtual state (IndexedDB-backed)

  async boot() {
    // 1) embedded snapshot (script tag) or nothing
    if (window.APA_DATA && window.APA_DATA.format === "apa-snapshot/1") {
      this.data = window.APA_DATA;
    }
    // 2) live detection
    try {
      const r = await fetch("/api/state", { cache: "no-store" });
      if (r.ok) {
        this.mode = "live";
        this.state = await r.json();
        await this.pullLive();
        return;
      }
    } catch (_) { /* static host or file:// */ }
    this.mode = "snapshot";
    if (!this.data) {
      try {
        const r = await fetch("public/snapshot.json", { cache: "no-store" });
        if (r.ok) this.data = await r.json();
      } catch (_) { /* file:// without js variant */ }
    }
    this.overlay = await IDB.get("virtual-state") || { active: null, prev: null, activated_at: null };
    this.state = {
      session: "snapshot", active: this.overlay.active, prev: this.overlay.prev,
      activated_at: this.overlay.activated_at,
      entry: this._meta(this.overlay.active), suppressed: !!this.overlay.active,
    };
  },

  async pullLive() {
    const [pr, sr] = await Promise.all([
      fetch("/api/personas", { cache: "no-store" }),
      fetch("/api/sessions", { cache: "no-store" }),
    ]);
    const idx = await pr.json();
    // hydrate payloads lazily per-persona; index is enough for grid
    this.data = this.data || { format: "apa-snapshot/1", personas: {}, registrations: null };
    this.data.personas = {};
    for (const e of idx.personas) this.data.personas[e.id] = { meta: e, payload: null };
    this.data.registrations = this.data.registrations ||
      await (await fetch("/api/registrations")).json().catch(() => null);
    this.sessions = sr.ok ? await sr.json() : null;
  },

  _meta(id) {
    if (!id || !this.data || !this.data.personas[id]) return null;
    return this.data.personas[id].meta;
  },

  async payloadOf(id) {
    const p = this.data.personas[id];
    if (!p) return null;
    if (p.payload != null) return p.payload;
    if (this.mode === "live") {
      const d = await (await fetch(`/api/personas/${id}`)).json();
      p.payload = d.payload;
      p.source = d.source; p.versions = d.versions;
      return p.payload;
    }
    return null;
  },

  async switchTo(id) {
    if (this.mode === "live") {
      const r = await fetch("/api/switch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: id }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "switch failed");
      this.state = j.state;
      return { payload: j.payload, cli: j.cli };
    }
    const meta = this._meta(id);
    if (!meta) throw new Error(`unknown persona '${id}'`);
    const payload = await this.payloadOf(id);
    this.overlay = { active: id, prev: this.overlay.active, activated_at: now() };
    await IDB.set("virtual-state", this.overlay);
    this.state = { session: "snapshot", active: id, prev: this.overlay.prev,
                   activated_at: this.overlay.activated_at, entry: meta, suppressed: true };
    await copy(payload || "");
    return { payload, cli: `apa.py switch ${id}`, note: "payload copied to clipboard" };
  },

  async clear() {
    if (this.mode === "live") {
      const j = await (await fetch("/api/clear", { method: "POST" })).json();
      this.state = j.state;
      return j.cli;
    }
    this.overlay = { active: null, prev: this.overlay.active, activated_at: now() };
    await IDB.set("virtual-state", this.overlay);
    this.state = { session: "snapshot", active: null, suppressed: false, entry: null };
    return "apa.py clear";
  },

  async stats() {
    if (this.mode === "live") return (await fetch("/api/stats")).json().catch(() => null);
    return null; // computed client-side from audit_tail if present
  },

  async audit(limit = 100) {
    if (this.mode === "live")
      return (await fetch(`/api/audit?limit=${limit}`)).json().catch(() => ({ events: [] }));
    const tail = (this.data && this.data.audit_tail) || [];
    return { events: tail.slice(-limit) };
  },
};

/* IndexedDB micro-wrapper (snapshot-mode persistence; LMK-safe, browser-local) */
const IDB = {
  _db: null,
  async open() {
    if (this._db) return this._db;
    this._db = await new Promise((res, rej) => {
      const rq = indexedDB.open("apa-cockpit", 1);
      rq.onupgradeneeded = () => rq.result.createObjectStore("kv");
      rq.onsuccess = () => res(rq.result);
      rq.onerror = () => rej(rq.error);
    });
    return this._db;
  },
  async get(k) {
    const db = await this.open();
    return new Promise(res => {
      const rq = db.transaction("kv").objectStore("kv").get(k);
      rq.onsuccess = () => res(rq.result); rq.onerror = () => res(null);
    });
  },
  async set(k, v) {
    const db = await this.open();
    return new Promise(res => {
      const rq = db.transaction("kv", "readwrite").objectStore("kv").put(v, k);
      rq.onsuccess = () => res(); rq.onerror = () => res();
    });
  },
};

/* ================= utils ================= */
const $ = s => document.querySelector(s);
const el = (t, cls, txt) => { const n = document.createElement(t); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const now = () => new Date().toISOString().slice(0, 19) + String(-new Date().getTimezoneOffset() / 60).padStart(2, "0") + "00";
const kb = n => n > 1024 ? (n / 1024).toFixed(1) + " KB" : n + " B";

async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (_) {
    const ta = el("textarea"); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand("copy"); ta.remove();
  }
}

function toast(msg, err = false) {
  const t = el("div", "toast" + (err ? " err" : ""), msg);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3800);
}

function cliLine(cmd) {
  const n = el("div", "cli-line", "exec: " + cmd);
  n.onclick = () => copy(cmd).then(() => toast("copied: " + cmd));
  return n;
}

function download(name, data, type = "application/octet-stream") {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const a = el("a"); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

/* SHA-256 → first 12 hex, byte-identical to Python's sha256_12 */
async function sha12(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

/* difflib-parity SequenceMatcher.ratio() — faithful port of
 * _find_longest_match + recursive chaining (no autojunk: both strings
 * are < 200 chars in resolver use, matching Python's behavior). */
function _longestBlock(a, b, alo, ahi, blo, bhi) {
  const b2j = new Map();
  for (let j = blo; j < bhi; j++) {
    const ch = b[j];
    if (!b2j.has(ch)) b2j.set(ch, []);
    b2j.get(ch).push(j);
  }
  let bi = alo, bj = blo, bs = 0, j2len = new Map();
  for (let i = alo; i < ahi; i++) {
    const nj = new Map();
    const js = b2j.get(a[i]);
    if (js) {
      for (const j of js) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) || 0) + 1;  // chain from PREVIOUS i
        nj.set(j, k);
        if (k > bs) { bi = i - k + 1; bj = j - k + 1; bs = k; }
      }
    }
    j2len = nj;
  }
  while (bi > alo && bj > blo && a[bi - 1] === b[bj - 1]) { bi--; bj--; bs++; }
  while (bi + bs < ahi && bj + bs < bhi && a[bi + bs] === b[bj + bs]) bs++;
  return [bi, bj, bs];
}
function _matchLen(a, b, alo, ahi, blo, bhi) {
  if (alo >= ahi || blo >= bhi) return 0;
  const [bi, bj, bs] = _longestBlock(a, b, alo, ahi, blo, bhi);
  if (!bs) return 0;
  return bs + _matchLen(a, b, alo, bi, blo, bj)
            + _matchLen(a, b, bi + bs, ahi, bj + bs, bhi);
}
function seqRatio(a, b) {
  if (a === b) return 1;
  if (!a.length || !b.length) return 0;
  return 2 * _matchLen(a, b, 0, a.length, 0, b.length) / (a.length + b.length);
}

function resolve(name, agents) {
  const low = String(name).trim().toLowerCase();
  if (agents[low]) return low;
  for (const [id, e] of Object.entries(agents))
    if ((e.aliases || []).some(a => a.toLowerCase() === low)) return id;
  const pool = [...Object.keys(agents)];
  for (const [id, e] of Object.entries(agents))
    for (const a of (e.aliases || [])) pool.push(a.toLowerCase());
  let best = null, bestR = 0.72;
  for (const c of pool) {
    const r = seqRatio(low, c);
    if (r >= bestR) { bestR = r; best = c; }
  }
  if (!best) return null;
  if (agents[best]) return best;
  for (const [id, e] of Object.entries(agents))
    if ((e.aliases || []).some(a => a.toLowerCase() === best)) return id;
  return null;
}

/* ustar TAR writer (plain tar — apa.py imports with r:*) */
function tarUstar(files) {
  const enc = new TextEncoder();
  const blocks = [];
  const be16 = n => n.toString(2).padStart(16, "0");
  const oct12 = n => n.toString(8).padStart(11, "0") + "\0";
  for (const { name, data } of files) {
    const bytes = typeof data === "string" ? enc.encode(data) : data;
    const h = new Uint8Array(512);
    const put = (off, s, len) => { const b = enc.encode(s); h.set(b.slice(0, len), off); };
    put(0, name, 100);
    put(100, oct12(0o644), 8);
    put(108, oct12(0), 8);          // uid
    put(116, oct12(0), 8);          // gid
    put(124, oct12(bytes.length), 12);
    put(136, oct12(Math.floor(Date.now() / 1000)), 12);
    put(156, "0", 1);               // regular file
    put(257, "ustar\0", 6);
    put(263, "00", 2);
    // checksum: sum of bytes with chksum field as spaces
    h.fill(0x20, 148, 156);
    let sum = 0; for (const b of h) sum += b;
    put(148, sum.toString(8).padStart(6, "0") + "\0 ", 8);
    blocks.push(h, bytes);
    const pad = (512 - (bytes.length % 512)) % 512;
    if (pad) blocks.push(new Uint8Array(pad));
  }
  blocks.push(new Uint8Array(1024)); // EOF
  const total = blocks.reduce((s, b) => s + b.length, 0);
  const out = new Uint8Array(total);
  let off = 0; for (const b of blocks) { out.set(b, off); off += b.length; }
  return out;
}

async function gzip(bytes) {
  if (typeof CompressionStream === "undefined") return null;
  const cs = new CompressionStream("gzip");
  const w = cs.writable.getWriter(); w.write(bytes); w.close();
  return new Uint8Array(await new Response(cs.readable).arrayBuffer());
}

/* ================= router ================= */
const routes = { "/": viewCockpit, "/personas": viewPersonas,
                 "/registrations": viewRegistrations, "/audit": viewAudit,
                 "/editor": viewEditor };

function nav() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const path = hash.split("?")[0];
  const qs = new URLSearchParams(hash.split("?")[1] || "");
  document.querySelectorAll(".nav a").forEach(a =>
    a.classList.toggle("active", a.dataset.route === path));
  (routes[path] || viewCockpit)(qs);
  window.scrollTo(0, 0);
}

function footCli(cmd) { $("#foot-cli").textContent = cmd; }

/* ================= views ================= */
function viewCockpit() {
  footCli("apa.py status");
  const v = $("#view"); v.innerHTML = "";
  const s = Store.state || {};
  const meta = s.entry;

  const banner = el("div", "active-banner" + (s.active ? "" : " off"));
  if (s.active) {
    banner.appendChild(el("div", "persona-name", s.active));
    if (meta) banner.appendChild(el("span", "vendor", `${meta.vendor} / ${meta.family}`));
    const tag = el("span", "suppress-tag on", "HOST PERSONA: SUPPRESSED");
    banner.appendChild(el("div")).appendChild(tag);
    if (s.activated_at) banner.append(el("div", "vendor", `since ${s.activated_at} · prev: ${s.prev || "—"}`));
    if (meta) {
      const chips = el("div", "chips");
      for (const t of meta.tags || []) chips.appendChild(el("span", "chip tag", t));
      banner.appendChild(chips);
      if (meta.sha256_12) banner.appendChild(el("div", "vendor mono", `sha ${meta.sha256_12}`));
    }
    const row = el("div", "row"); row.style.marginTop = "14px";
    const bClear = el("button", "btn danger", "/APA clear");
    bClear.onclick = async () => {
      const cli = await Store.clear();
      toast("host persona restored · " + cli); render();
    };
    const bCopy = el("button", "btn", "copy payload");
    bCopy.onclick = async () => {
      const p = await Store.payloadOf(s.active);
      if (p) { await copy(p); toast("payload copied — paste into any agent"); }
      else toast("payload not in snapshot — re-run: apa.py snapshot --js", true);
    };
    row.append(bClear, bCopy, cliLine(`apa.py switch ${s.active}`));
    banner.appendChild(row);
  } else {
    banner.appendChild(el("div", "persona-name", "no active persona"));
    banner.appendChild(el("span", "suppress-tag off", "HOST PERSONA: IN EFFECT"));
  }
  v.appendChild(banner);

  // quick switch
  const sw = el("div", "panel");
  sw.appendChild(el("h2", null, "quick switch"));
  const ids = Object.keys(Store.data?.personas || {}).sort();
  const chips = el("div", "chips");
  for (const id of ["claude-code", "antigravity", "cursor-agent", "codex-cli", "gemini-cli", "opencode"].filter(x => ids.includes(x))) {
    const c = el("span", "chip", id);
    c.onclick = () => doSwitch(id);
    chips.appendChild(c);
  }
  const input = el("input"); input.type = "text";
  input.placeholder = "search 42 personas — id, vendor, tag… (enter to activate fuzzy match)";
  input.onkeydown = e => {
    if (e.key !== "Enter") return;
    const q = input.value.trim(); if (!q) return;
    const pid = resolve(q, mapMetas());
    if (pid) doSwitch(pid);
    else { location.hash = "#/personas?q=" + encodeURIComponent(q); }
  };
  sw.append(input, chips);
  v.appendChild(sw);

  // HUD stats
  const grid = el("div", "stat-grid");
  const total = ids.length;
  const custom = ids.filter(i => Store.data.personas[i].meta?.origin && Store.data.personas[i].meta.origin !== "ref-repo").length;
  const sess = Store.sessions;
  grid.append(
    statCard(total, "personas"),
    statCard(s.active ? 1 : 0, "active"),
    statCard(custom, "custom/blend"),
    statCard((Store.data?.registrations?.targets ? Object.keys(Store.data.registrations.targets).length : "—"), "surface targets"),
    statCard(sess ? sess.sessions.length : 1, "sessions"),
  );
  v.appendChild(grid);
  if (sess && sess.sessions.length > 1) {
    const p = el("div", "panel"); p.appendChild(el("h2", null, "sessions"));
    const row = el("div", "row");
    for (const s2 of sess.sessions) {
      const c = el("span", "chip", `${s2.name}${s2.name === sess.current ? " ●" : ""}${s2.active ? " · " + s2.active : ""}`);
      c.onclick = async () => {
        if (Store.mode === "live") {
          await fetch("/api/session/use", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: s2.name }) });
          await Store.pullLive(); toast("session: " + s2.name); render();
        }
      };
      row.appendChild(c);
    }
    p.appendChild(row); v.appendChild(p);
  }
}

function statCard(n, l) {
  const s = el("div", "stat");
  s.append(el("div", "n", String(n)), el("div", "l", l));
  return s;
}

function mapMetas() {
  const m = {};
  for (const [id, p] of Object.entries(Store.data?.personas || {})) m[id] = p.meta || {};
  return m;
}

async function doSwitch(id) {
  try {
    const r = await Store.switchTo(id);
    toast(`active: ${id}` + (r.note ? " · " + r.note : "") + (Store.mode === "snapshot" ? " · payload copied" : ""));
    render();
  } catch (e) { toast(String(e.message || e), true); }
}

/* ---- personas grid ---- */
function viewPersonas(qs) {
  footCli("apa.py list [--tag t] · search <q>");
  const v = $("#view"); v.innerHTML = "";
  const metas = mapMetas();
  const ids = Object.keys(metas).sort();

  const bar = el("div", "panel");
  const row = el("div", "row");
  const search = el("input"); search.type = "text"; search.placeholder = "filter…";
  search.value = qs.get("q") || "";
  const tagSel = el("select");
  const allTags = [...new Set(ids.flatMap(i => metas[i].tags || []))].sort();
  tagSel.append(new Option("all tags", ""), ...allTags.map(t => new Option(t, t)));
  row.append(search, tagSel);
  bar.appendChild(row);
  v.appendChild(bar);

  const grid = el("div", "grid");
  const paint = () => {
    grid.innerHTML = "";
    const q = search.value.trim().toLowerCase(), tag = tagSel.value;
    // Fuzzy: if the query isn't a substring of anything, ask the difflib-port
    // resolver for a single best match so typos ("cursr") still surface a card.
    const fuzzyId = q ? resolve(q, metas) : null;
    const shown = ids.filter(id => {
      const m = metas[id];
      if (tag && !(m.tags || []).includes(tag)) return false;
      if (!q) return true;
      if (id === fuzzyId) return true;
      return id.includes(q) || (m.vendor || "").toLowerCase().includes(q)
        || (m.family || "").toLowerCase().includes(q)
        || (m.aliases || []).some(a => a.toLowerCase().includes(q));
    });
    for (const id of shown) {
      const m = metas[id];
      const c = el("div", "card" + (Store.state.active === id ? " active-p" : ""));
      const head = el("div", "row");
      head.append(el("span", "cid", id));
      const org = el("span", "origin " + (m.origin || ""), m.origin === "ref-repo" || !m.origin ? "ref" : m.origin);
      head.appendChild(org);
      c.appendChild(head);
      c.appendChild(el("div", "cvendor", `${m.vendor || "?"} / ${m.family || "?"}`));
      const chips = el("div", "chips");
      for (const t of (m.tags || []).slice(0, 5)) chips.appendChild(el("span", "chip tag", t));
      c.appendChild(chips);
      c.appendChild(el("div", "cbytes", `${m.bytes ? kb(m.bytes) : ""} ${m.sha256_12 ? "· " + m.sha256_12 : ""}`));
      c.onclick = () => openDrawer(id);
      grid.appendChild(c);
    }
    if (!shown.length) grid.appendChild(el("div", "empty", "no personas match"));
  };
  search.oninput = paint; tagSel.onchange = paint;
  paint();
  v.appendChild(grid);
}

async function openDrawer(id) {
  const metas = mapMetas(); const m = metas[id];
  const d = el("div", "drawer");
  const close = el("button", "btn sm", "✕ close");
  close.style.float = "right";
  close.onclick = () => d.remove();
  d.appendChild(close);
  d.appendChild(el("h2", null, id));
  const kv = el("div", "kv");
  const add = (k, val) => { kv.append(el("span", "k", k), el("span", null, String(val ?? "—"))); };
  add("vendor", m.vendor); add("family", m.family);
  add("aliases", (m.aliases || []).join(", ") || "—");
  add("tags", (m.tags || []).join(", ") || "—");
  add("origin", m.origin || "ref-repo");
  add("sha256_12", m.sha256_12 || "—");
  add("bytes", m.bytes ? kb(m.bytes) : "—");
  d.appendChild(kv);

  const row = el("div", "row");
  const bAct = el("button", "btn primary", "activate");
  bAct.onclick = async () => { d.remove(); await doSwitch(id); };
  const bExp = el("button", "btn", "export .apa");
  bExp.onclick = async () => {
    if (Store.mode === "live") { window.open(`/api/export/${id}`, "_blank"); return; }
    const payload = await Store.payloadOf(id);
    if (!payload) { toast("no payload in snapshot — re-snapshot with bodies", true); return; }
    const manifest = JSON.stringify({ format: "apa-bundle/1", id, ...m, exported_at: now() }, null, 2) + "\n";
    const tar = tarUstar([{ name: "manifest.json", data: manifest }, { name: "PERSONA.md", data: payload }]);
    const gz = await gzip(tar);
    if (gz) download(id + ".apa", gz, "application/gzip");
    else download(id + ".tar", tar, "application/x-tar");
    toast(`artifact: ${id}.apa — apply with: apa.py import ${id}.apa`);
  };
  const bClip = el("button", "btn", "copy payload");
  bClip.onclick = async () => { const p = await Store.payloadOf(id); if (p) { await copy(p); toast("payload copied — paste into any agent"); } else toast("payload not in snapshot", true); };
  row.append(bAct, bExp, bClip);
  d.appendChild(row);
  d.appendChild(cliLine(`apa.py switch ${id}`));

  d.appendChild(el("h2", null, "payload"));
  const pre = el("pre", null, "loading…");
  d.appendChild(pre);
  document.body.appendChild(d);
  const p = await Store.payloadOf(id);
  pre.textContent = p || "(payload not available in this snapshot — regenerate: apa.py snapshot --js)";
}

/* ---- registrations matrix ---- */
async function viewRegistrations() {
  footCli("python3 scripts/register.py install <persona> --agent all --project <dir>");
  const v = $("#view"); v.innerHTML = "";
  let regmap = Store.data?.registrations;
  if (!regmap && Store.mode === "live")
    regmap = await (await fetch("/api/registrations")).json().catch(() => null);
  if (!regmap || !regmap.targets) {
    v.appendChild(el("div", "empty", "registrations map missing — regenerate snapshot (apa.py snapshot --js)"));
    return;
  }
  const targets = Object.entries(regmap.targets)
    .filter(([, t]) => t.capabilities && Object.keys(t.capabilities).length);
  const ids = Object.keys(mapMetas()).sort();

  const panel = el("div", "panel");
  panel.appendChild(el("h2", null, `matrix — ${ids.length} personas × ${targets.length} surfaces`));
  const wrap = el("div", "matrix-wrap");
  const tbl = el("table", "matrix");
  const thead = el("thead"); const hr = el("tr");
  hr.appendChild(el("th", null, "persona"));
  for (const [tid, t] of targets) {
    const th = el("th", null, tid);
    th.title = (t.source || "") + (t.verified ? " (verified)" : " (BEST-EFFORT)");
    hr.appendChild(th);
  }
  thead.appendChild(hr); tbl.appendChild(thead);
  const tbody = el("tbody");
  for (const pid of ids) {
    const tr = el("tr");
    const td0 = el("td", "pname", pid);
    td0.onclick = () => location.hash = "#/personas?q=" + pid;
    tr.appendChild(td0);
    for (const [tid, t] of targets) {
      const caps = t.capabilities || {};
      const keys = Object.keys(caps);
      const td = el("td");
      if (!keys.length) { td.className = "na"; td.textContent = "n/a"; }
      else {
        const kind = caps[pid] || keys.find(k => k.endsWith(":default")) ? "avail" : null;
        // capability registry: file emit keyed by persona id or default
        const hit = caps[pid] || caps["*"] || (t.format && (caps.default || caps[":default"]));
        td.className = hit ? "yes" : "no";
        td.textContent = hit ? "●" : "·";
        td.title = hit ? `${tid}: ${typeof hit === "string" ? hit : "emittable"}` : `${tid}: available (not persona-keyed)`;
        td.style.cursor = "pointer";
        td.onclick = async () => {
          if (Store.mode === "live") {
            toast(`cli: register.py install ${pid} --agent ${tid} --project <dir>`);
          } else {
            toast(`artifact mode — run: register.py install ${pid} --agent ${tid} --project <dir>`);
          }
        };
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  tbl.appendChild(tbody); wrap.appendChild(tbl); panel.appendChild(wrap);
  panel.appendChild(cliLine("python3 scripts/register.py install claude-code --agent all --project ~/myrepo"));
  v.appendChild(panel);
}

/* ---- audit ---- */
async function viewAudit() {
  footCli("apa.py stats · tail state/audit.log");
  const v = $("#view"); v.innerHTML = "";
  const stats = await Store.stats();
  const { events } = await Store.audit(150);

  if (stats) {
    const grid = el("div", "stat-grid");
    grid.append(statCard(stats.events_total, "events"), statCard(stats.switches, "switches"),
      statCard(stats.floor_overrides, "floor overrides"));
    v.appendChild(grid);
    const p = el("div", "panel"); p.appendChild(el("h2", null, "most-switched personas"));
    const top = Object.entries(stats.per_persona).slice(0, 8);
    const mx = top.length ? top[0][1] : 1;
    for (const [pid, n] of top) p.appendChild(barRow(pid, n, mx));
    p.appendChild(el("h2", null, "usage by capability tag")).style.marginTop = "14px";
    const tt = Object.entries(stats.per_tag).slice(0, 8);
    const mt = tt.length ? tt[0][1] : 1;
    for (const [t, n] of tt) p.appendChild(barRow(t, n, mt, true));
    v.appendChild(p);
  }

  const p2 = el("div", "panel");
  p2.appendChild(el("h2", null, "timeline (last 150)"));
  const tl = el("div", "timeline");
  if (!events.length) tl.appendChild(el("div", "empty", "no audit events in this snapshot"));
  for (const e of [...events].reverse()) {
    const d = el("div", "tevent " + (e.event || ""));
    d.appendChild(el("div", "ts", `${e.ts || "?"} · ${e.event || "?"}`));
    const what = [e.from != null && `from ${e.from ?? "—"}`, e.to != null && `to ${e.to ?? "—"}`,
      e.id && `id ${e.id}`, e.winner && `winner ${e.winner}`, e.note].filter(Boolean).join("  ");
    d.appendChild(el("div", "what", what));
    tl.appendChild(d);
  }
  p2.appendChild(tl); v.appendChild(p2);
}

function barRow(label, n, mx, dim = false) {
  const r = el("div", "bar-row");
  r.appendChild(el("span", null, label));
  const track = el("div", "bar-track");
  const fill = el("div", "bar-fill" + (dim ? " dim" : ""));
  fill.style.width = Math.max(3, n / mx * 100) + "%";
  track.appendChild(fill);
  r.appendChild(track);
  r.appendChild(el("span", "mono", String(n)));
  return r;
}

/* ---- editor ---- */
function viewEditor() {
  footCli("apa.py new <id> · edit <id> · export <id> -o f.apa");
  const v = $("#view"); v.innerHTML = "";
  const p = el("div", "panel");
  p.appendChild(el("h2", null, "author / edit custom persona"));

  const form = el("div", "row");
  const mkIn = (ph, w) => { const i = el("input"); i.type = "text"; i.placeholder = ph; if (w) i.style.width = w; return i; };
  const inId = mkIn("id (lowercase)", "180px");
  const inVendor = mkIn("vendor", "130px");
  const inAliases = mkIn("aliases a,b,c", "180px");
  const inTags = mkIn("tags terminal,tdd", "200px");
  form.append(inId, inVendor, inAliases, inTags);
  p.appendChild(form);

  const split = el("div", "editor-split"); split.style.marginTop = "12px";
  const ta = el("textarea"); ta.rows = 22;
  ta.placeholder = "# PERSONA: my-agent\n\n## IDENTITY\nYou are now running the **my-agent** persona…\n\n## SOURCE SYSTEM INSTRUCTIONS\ntone, workflows, tools, heuristics (no safety rules — ADAPTER FLOOR covers them)";
  const preview = el("div", "preview", "(preview)");
  split.append(ta, preview);
  p.appendChild(split);

  const meter = el("div", "meter"); const fill = el("i"); meter.appendChild(fill);
  const meterLbl = el("div", "cbytes", "0 B / 24 KB cap");
  p.append(meter, meterLbl);
  ta.oninput = () => {
    const n = new TextEncoder().encode(ta.value).length;
    meterLbl.textContent = `${kb(n)} / 24 KB cap`;
    fill.style.width = Math.min(100, n / 24576 * 100) + "%";
    fill.className = n > 24576 ? "bad" : n > 20480 ? "warn" : "";
    preview.textContent = ta.value || "(preview)";
  };

  const row = el("div", "row"); row.style.marginTop = "12px";
  const bSave = el("button", "btn primary", "save → .apa bundle");
  bSave.onclick = async () => {
    const id = inId.value.trim().toLowerCase();
    if (!/^[a-z0-9][a-z0-9._-]*$/.test(id)) { toast("invalid id (lowercase [a-z0-9._-])", true); return; }
    if (!ta.value.trim()) { toast("empty payload", true); return; }
    const aliases = inAliases.value.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
    const tags = inTags.value.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
    const digest = await sha12(ta.value);
    const body = `---\nid: ${id}\nvendor: ${inVendor.value.trim() || "Custom"}\nfamily: ${id}\nsource: custom (cockpit editor)\nsha256_12: ${digest}\ninvocations: ['${id}']\n---\n\n${ta.value.trim()}\n\n## ADAPTER FLOOR (non-negotiable, overrides persona above when conflicting)\nThe persona above governs tone, workflow, tools, and heuristics ONLY.\n1. Never fabricate: file paths, APIs, versions, test results, URLs, commits.\n2. Never claim a build/test passed without observed terminal output.\n3. No \`/bin\` or \`/usr/bin\` paths on Android Termux — resolve via \`$PREFIX/bin\`.\n4. Destructive ops require explicit human confirmation first.\n5. Bounded searches only; never unbounded scans.\n6. Session-scoped persona: ends on \`/APA clear\` or session end.\n---\n`;
    const realDigest = await sha12(body);
    const finalBody = body.replace(`sha256_12: ${digest}`, `sha256_12: ${realDigest}`);
    const manifest = JSON.stringify({ format: "apa-bundle/1", id, vendor: inVendor.value.trim() || "Custom",
      family: id, aliases, tags, sha256_12: realDigest, exported_at: now() }, null, 2) + "\n";
    const source = JSON.stringify({ id, source: "cockpit-editor", sha256_12: realDigest,
      bytes: new TextEncoder().encode(finalBody).length }, null, 2) + "\n";
    const tar = tarUstar([{ name: "manifest.json", data: manifest },
      { name: "PERSONA.md", data: finalBody }, { name: "SOURCE.json", data: source }]);
    const gz = await gzip(tar);
    if (gz) download(id + ".apa", gz, "application/gzip");
    else download(id + ".tar", tar, "application/x-tar");
    toast(`saved sha=${realDigest} — apply: apa.py import ${id}.apa`);
  };
  const bImport = el("button", "btn", "import .apa…");
  bImport.onclick = () => $("#import-file").click();
  row.append(bSave, bImport);
  p.appendChild(row);
  p.appendChild(cliLine(`python3 scripts/apa.py import <file>.apa --as <id>`));
  v.appendChild(p);
}

/* ================= shell wiring ================= */
function render() { nav(); }

function paintMode() {
  const b = $("#mode-badge");
  b.textContent = Store.mode === "live" ? "LIVE" : "SNAPSHOT";
  b.className = "badge badge-mode " + (Store.mode === "live" ? "live" : "snapshot");
  b.title = Store.mode === "live"
    ? "connected to server/serve.py — mutations hit real state files"
    : "no server — mutations are artifacts (downloads + clipboard)";
  const ids = Object.keys(Store.data?.personas || {});
  $("#hud").textContent = `${ids.length} personas · ${Store.mode} · ${location.host || "file://"}`;
}

async function boot() {
  try { await Store.boot(); } catch (e) { console.error(e); }
  paintMode();
  window.addEventListener("hashchange", nav);
  nav();

  // drag-drop snapshot re-sync
  const dz = $("#foot-drop");
  ["dragover", "dragenter"].forEach(ev => document.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.add("armed");
  }));
  ["dragleave", "drop"].forEach(ev => document.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.remove("armed");
  }));
  document.addEventListener("drop", async e => {
    const f = e.dataTransfer?.files?.[0]; if (!f) return;
    try {
      const snap = JSON.parse(await f.text());
      if (snap.format !== "apa-snapshot/1") throw new Error("not an apa-snapshot/1");
      Store.data = snap;
      if (snap.state) Store.overlay = snap.state;
      paintMode(); toast(`snapshot re-synced — ${Object.keys(snap.personas || {}).length} personas`);
      render();
    } catch (err) { toast("bad snapshot: " + err.message, true);
    } finally { dz.classList.remove("armed"); }
  });

  // .apa import (serverless: decode bundle → prefill editor)
  $("#import-file").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    toast("serverless import: bundle must be applied via CLI — apa.py import " + f.name);
    download(f.name.replace(/\.apa$/, "") + ".apply.sh.txt",
      `python3 scripts/apa.py import ${f.name} --as <id>\n`, "text/plain");
    e.target.value = "";
  };
}

boot();
