/* PULSE console — live wiring for the hospital-impact-defense FastAPI backend.
   Every number renders from /api/* (poll, 1s). Display-only adaptations from the
   PULSE reference mock are marked DISPLAY. Clinical math lives server-side. */
const API = "";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function fetchJSON(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(r.status + " " + path);
  return r.json();
}
function icons() { window.lucide && lucide.createIcons(); }
function toast(title, body, kind) {
  const w = $("toasts");
  if (w.children.length > 4) w.removeChild(w.firstChild);
  const d = document.createElement("div");
  d.className = "toast " + (kind || "");
  d.innerHTML = "<b>" + esc(title) + "</b>" + esc(body);
  w.appendChild(d);
  setTimeout(() => d.remove(), 5200);
  icons();
}

/* DISPLAY: rule metadata for labels only (detection truth is server-side). */
const RULE_TECH = { R1: "T1486", R2: "T1486", R3: "T1490", R5: "T1110", R6: "T1021", R9: "BASELINE", R10: "T0855" };
const RULE_NAME = { R1: "Mass rename/modify burst", R2: "Canary file touched", R3: "Recovery inhibition", R5: "Brute force → success", R6: "New RDP/SMB source", R9: "Device baseline deviation", R10: "Unauthorized device command" };
const TECH_BASE = { R1: 92, R2: 88, R3: 85, R5: 55, R6: 70, R9: 45, R10: 80 };
/* DISPLAY: severity bands fitted to our measured clinical scale (campaign max ≈41). */
function sevOf(score) { return score >= 38 ? "CRITICAL" : score >= 30 ? "HIGH" : score >= 12 ? "ELEVATED" : "LOW"; }
const sevCls = (s) => ({ CRITICAL: "bad", HIGH: "hi", ELEVATED: "el", LOW: "lo" }[s]);
function titleFor(rules) {
  const has = (r) => rules.includes(r);
  if (has("R1") && has("R3")) return "Ransomware — encryption with recovery inhibition";
  if (has("R1")) return "Ransomware — encryption pattern";
  if (has("R10")) return "Unauthorized device command — IoMT";
  if (has("R5") || has("R6")) return "Credential abuse & lateral movement";
  return "Suspicious endpoint activity";
}
function techOf(inc) {
  const rules = inc.rule_ids || [];
  if (!rules.length) return 0;
  const base = Math.max(...rules.map((r) => TECH_BASE[r] || 50));
  return Math.min(100, Math.round(0.6 * base + 40 * (inc.confidence || 0)));
}
const prettySvc = (s) => s.replace(/_/g, " ");
const prettyApp = (s) => s.replace(/_/g, " ").toUpperCase();

/* ---------------- state ---------------- */
const S = { incidents: [], selected: null, dossier: null, stats: null, feed: [],
  graph: null, eclass: {}, code: "NOMINAL", known: new Set(), blastMode: true, showReach: true };
const SC = { running: null, timers: [], captionTimer: null };

/* ---------------- scenarios (console) ---------------- */
const SCEN = {
  D: { id: "D", api: "d_benign_patching", name: "BENIGN PATCHING", desc: "routine change window · should stay quiet", dur: 6,
    caps: ["02:00 — routine patching and the nightly backup job. High volume, low signal.", "No incident. Volume is not a signature — extension changes, canaries and recovery tampering are."] },
  A: { id: "A", api: "a_radiology", name: "RADIOLOGY RANSOMWARE", desc: "rad-ws-02 → PACS · Tier 2", dur: 8,
    caps: ["Phishing payload detonates on the radiology reading station. Watch the queue, not the console.", "R1+R2+R3: encryption pattern with recovery inhibition — imaging reads exposed through PACS."] },
  B: { id: "B", api: "b_pharmacy", name: "PHARMACY RANSOMWARE", desc: "pharm-srv-01 · Tier 1", dur: 8,
    caps: ["Same ransomware pattern as A — different host. Five RDP failures, then success from an unknown source.", "Medication administration is Tier 1 with a 15-minute budget. Paper MAR cannot beat the clock."] },
  C: { id: "C", api: "c_infusion_pump", name: "ROGUE PUMP COMMAND", desc: "infusion pump · passive telemetry", dur: 6,
    caps: ["Passive telemetry only — pumps cannot run agents. A drug-library push from an address that never spoke to it.", "Policy: never touch the device. Approve the segmentation change in the ledger."] },
  E: { id: "E", api: "e_hospital_campaign", name: "AFTER-HOURS CAMPAIGN", desc: "vendor VPN → nurse WS → pharmacy + pump → backup · 64 events", dur: 14,
    caps: ["One vendor password. Watch the feed narrate P1→P6 in purple.", "Pharmacy and pump go Tier-1; backups burn last. Rank follows patients, not malware."] },
};
function setCaption(txt, hot) {
  const b = $("capBadge"), t = $("capTxt");
  if (txt) { b.style.display = ""; b.classList.toggle("hot", !!hot); b.textContent = "SCENARIO " + (SC.running || ""); t.textContent = txt; }
  else { b.style.display = "none"; t.textContent = "System nominal — run a scenario from the demo console to begin the demonstration."; }
}
async function runScenario(key, withReset = true) {
  if (SC.running) { toast("CONSOLE BUSY", "A scenario is already running — reset first.", "warn"); return; }
  const def = SCEN[key];
  SC.running = key;
  if (withReset) await fetch(API + "/api/sim/reset", { method: "POST" });
  S.selected = null; S.dossier = null;
  setCaption(def.caps[0], key !== "D");
  toast("SCENARIO " + key + " — " + def.name, def.desc, key === "D" ? "" : "bad");
  await fetch(API + "/api/sim/start?scenario=" + encodeURIComponent(def.api), { method: "POST" });
  SC.timers.push(setTimeout(() => setCaption(def.caps[1] || def.caps[0], key !== "D"), 5000));
  SC.timers.push(setTimeout(() => { SC.running = null; setCaption(null); renderConsole(); }, def.dur * 1000));
  renderConsole(); refreshAll();
}
async function guidedRun() {
  if (SC.running) { toast("CONSOLE BUSY", "Reset first.", "warn"); return; }
  for (const k of ["D", "A", "B", "C"]) { await runScenario(k, true); await sleep(9000); }
  toast("GUIDED DEMO COMPLETE", "D quiet, A Tier-2, B Tier-1, C passive-only. Try E campaign next.");
}
async function resetConsole() {
  SC.timers.forEach(clearTimeout); SC.timers = []; SC.running = null;
  await fetch(API + "/api/sim/reset", { method: "POST" });
  S.selected = null; S.dossier = null; S.known = new Set();
  setCaption(null); renderConsole(); refreshAll();
  toast("CONSOLE RESET", "State wiped — audit ledger retained (append-only by design).");
}
async function ambient() {
  const r = await fetch(API + "/api/sim/background?minutes=15&seed=" + Math.floor(Math.random() * 1000), { method: "POST" });
  const j = await r.json();
  toast("AMBIENT TRAFFIC", j.events + " normal events — should fire nothing.", "");
  refreshAll();
}
function renderConsole() {
  $("consoleScen").innerHTML = Object.values(SCEN).map((s) =>
    `<button class="scn ${SC.running === s.id ? "running" : ""}" data-s="${s.id}" ${SC.running ? "disabled" : ""}>
     <span class="sl">${s.id}</span><span class="sn">${s.name}</span><span class="sd">${s.desc}</span></button>`).join("");
  $("consoleScen").querySelectorAll(".scn").forEach((b) => (b.onclick = () => runScenario(b.dataset.s, true)));
}

/* ---------------- queue ---------------- */
function budgetHTML(inc) {
  const t0 = (inc.services_at_risk || []).find((s) => s.risk > 0);
  if (!t0) return "";
  const openedS = Date.parse(inc.created_at) / 1000;
  const rem = t0.max_downtime_min * 60 - (Date.now() / 1000 - openedS);
  if (rem <= 0) return '<span class="chip cd">BUDGET BREACHED</span>';
  const m = Math.floor(rem / 60), s = Math.floor(rem % 60);
  return `<span>budget ${m}:${String(s).padStart(2, "0")}</span>`;
}
function renderQueue() {
  const list = $("queueList");
  if (!S.incidents.length) {
    list.innerHTML = '<div class="q-empty">NO OPEN INCIDENTS<br><span style="font-size:9px">queue is ranked by clinical impact, not CVSS — run a scenario below</span></div>';
    return;
  }
  const sorted = [...S.incidents].sort((a, b) => b.risk_score - a.risk_score);
  list.innerHTML = sorted.map((inc, i) => {
    const sev = sevOf(inc.risk_score);
    const top = (inc.services_at_risk || []).slice(0, 2);
    return `<div class="inc ${sev} ${inc.id === S.selected ? "sel" : ""}" data-id="${inc.id}">
      <div class="inc-rank" style="color:var(--txt3);font-weight:700">#${i + 1}</div>
      <div class="inc-main">
        <div class="inc-id">${inc.id} · CONF ${Math.round((inc.confidence || 0) * 100)}%</div>
        <div class="inc-title">${esc(titleFor(inc.rule_ids || []))}</div>
        <div class="inc-eps">${esc(inc.endpoint_id)}</div>
        <div class="chiprow">${top.map((s) => `<span class="chip t${s.tier}">T${s.tier} ${esc(prettySvc(s.service).toUpperCase())}</span>`).join("")}${budgetHTML(inc)}</div>
        <div class="inc-meta"><div class="confbar"><i style="width:${Math.round((inc.confidence || 0) * 100)}%"></i></div></div>
      </div>
      <div class="inc-score"><b>${inc.risk_score}</b><span>${sev}</span></div></div>`;
  }).join("");
  list.querySelectorAll(".inc").forEach((el) => (el.onclick = () => { S.selected = el.dataset.id; S.dossier = null; refreshAll(true); }));
}

/* ---------------- graph ---------------- */
let cy = null;
const CLSBG = { workstation: "#12201B", server: "#102027", device: "#1F1A12", iot: "#131820" };
const CLSBC = { workstation: "#3E6B58", server: "#37616E", device: "#7A5A2E", iot: "#45505A" };
const ESTY = { runs: { c: "#3E6E7E", w: 1.6, o: 0.7, cv: "bezier", ar: "triangle" },
  serves: { c: "#4A5C68", w: 1.3, o: 0.6, cv: "bezier", ar: "triangle" },
  reach: { c: "#F5B942", w: 1.4, o: 0.8, cv: "bezier", ar: "triangle" } };
function svcLabel(n) { return "T" + n.tier + " · " + prettySvc(n.id).toUpperCase(); }
function buildGraph(g) {
  if (!window.cytoscape) { $("cy").innerHTML = '<div class="d-empty">Cytoscape failed to load (vendored bundle missing).</div>'; return; }
  const eps = g.nodes.filter((n) => n.kind === "endpoint");
  const apps = g.nodes.filter((n) => n.kind === "application");
  const svcs = g.nodes.filter((n) => n.kind === "service");
  const pos = {};
  eps.forEach((n, i) => (pos[n.id] = { x: 110, y: 56 + i * 40 }));
  apps.forEach((n, i) => (pos[n.id] = { x: 600, y: 66 + i * 40 }));
  svcs.forEach((n, i) => (pos[n.id] = { x: 860, y: 120 + i * 110 }));
  const els = [];
  g.nodes.forEach((n) => {
    let label = n.id, w = 104, h = 26, bg = "#141B22", bc = "#55636E", cls = "ep";
    if (n.kind === "endpoint") { bg = CLSBG[n.eclass] || bg; bc = CLSBC[n.eclass] || bc; }
    else if (n.kind === "application") { label = prettyApp(n.id); w = 112; h = 30; bg = "#102027"; bc = "#3E6E7E"; cls = "app"; }
    else if (n.kind === "service") { label = svcLabel(n); w = 168; h = 34; bc = n.tier === 1 ? "#C9485B" : n.tier === 2 ? "#C79A3A" : "#55636E"; cls = "svc t" + n.tier; }
    els.push({ group: "nodes", position: pos[n.id] || { x: 400, y: 300 },
      data: { id: n.id, label, w, h, bg, bc, kind: n.kind }, classes: cls });
  });
  g.edges.forEach((e, i) => {
    const st = ESTY[e.rel] || ESTY.serves;
    els.push({ group: "edges", data: { id: "e" + i + "-" + e.source + "-" + e.target, source: e.source, target: e.target, color: st.c, w: st.w, op: st.o, curve: st.cv, arrow: st.ar }, classes: "k-" + (e.rel || "serves") });
  });
  cy = cytoscape({ container: $("cy"), elements: els,
    style: [
      { selector: "node", style: { label: "data(label)", "font-family": "JetBrains Mono, monospace", "font-size": 12, "font-weight": 600,
        color: "#D8E4EC", "text-wrap": "wrap", "text-valign": "center", "text-halign": "center", shape: "round-rectangle",
        width: "data(w)", height: "data(h)", "background-color": "data(bg)", "border-width": 1.5, "border-color": "data(bc)" } },
      { selector: "edge", style: { width: "data(w)", "curve-style": "data(curve)", "line-color": "data(color)", opacity: "data(op)",
        "target-arrow-shape": "data(arrow)", "target-arrow-color": "data(color)", "arrow-scale": 0.6 } },
      { selector: "edge.k-reach", style: { "line-style": "dashed", "line-dash-pattern": [3, 4] } },
      { selector: "node.dim, edge.dim", opacity: 0.13 },
      { selector: "edge.hidden", display: "none" },
      { selector: "node.compromised", "border-color": "#FF4D5E", "border-width": 2.5, "background-color": "#1E1216" },
      { selector: "node.pulse", "border-width": 4.5, "overlay-color": "rgba(255,77,94,0.28)", "overlay-opacity": 0.8 },
      { selector: "node.contained", "border-color": "#54B9C9", "border-width": 2.5, "background-color": "#0F1B20" },
      { selector: "node.onpath", "border-color": "#57C7A8", "border-width": 2.5 },
      { selector: "node.atrisk", "border-width": 3.2 },
      { selector: "edge.attack", "line-color": "#FF4D5E", "target-arrow-color": "#FF4D5E", width: 2.3, opacity: 1,
        "line-style": "dashed", "line-dash-pattern": [7, 5] },
      { selector: "edge.reachrisk", "line-color": "#F5B942", "target-arrow-color": "#F5B942", width: 1.8, opacity: 0.95,
        "line-style": "dashed", "line-dash-pattern": [4, 4] },
      { selector: "edge.cut", "line-color": "#3A4A55", width: 1, opacity: 0.25, "line-dash-pattern": [2, 5] },
      { selector: "node[ghost]", style: { shape: "ellipse", width: 6, height: 6, "background-color": "data(gc)", "border-width": 0, opacity: 0.95, events: "no" } },
    ],
    layout: { name: "preset" }, wheelSensitivity: 0.2, minZoom: 0.35, maxZoom: 2.6 });
  cy.ready(() => cy.fit(30));
  const tip = $("tooltip");
  cy.on("mouseover tap", "node", (e) => {
    const n = e.target, id = n.id();
    const st = S.stats?.endpoint_status?.[id];
    let h = "<b>" + esc(n.data("label")) + "</b><br>" + esc(id);
    if (st) h += "<br>status: " + st.toUpperCase();
    tip.innerHTML = h; tip.style.display = "block";
    const p = n.renderedPosition();
    tip.style.left = Math.min(p.x + 14, $("graphPanel").clientWidth - 240) + "px";
    tip.style.top = p.y + 14 + "px";
  });
  cy.on("mouseout", "node", () => (tip.style.display = "none"));
  cy.on("tap", (e) => { tip.style.display = "none"; if (e.target === cy) { S.dossier = null; renderDetail(); } });
  cy.on("tap", "node", (e) => { S.dossier = e.target.id(); S.selected = null; renderAll(); });
  let off = 0;
  (function flow() { off -= 0.55;
    if (cy) { cy.edges(".attack").style("line-dash-offset", off); cy.edges(".reachrisk").style("line-dash-offset", off * 0.6); }
    requestAnimationFrame(flow); })();
  setInterval(() => { if (cy) cy.nodes(".compromised").toggleClass("pulse"); }, 650);
}
function selInc() { return S.incidents.find((i) => i.id === S.selected); }
function paintGraph() {
  if (!cy) return;
  cy.batch(() => {
    cy.elements().removeClass("dim compromised contained atrisk onpath attack reachrisk cut");
    cy.edges(".k-reach").toggleClass("hidden", !S.showReach);
    const inc = selInc();
    if (!inc) return;
    const epStatus = S.stats?.endpoint_status || {};
    (inc.paths || []).flat().forEach((nid) => {
      const n = cy.getElementById(nid);
      if (!n.length) return;
      if (n.data("kind") === "endpoint") n.addClass(epStatus[nid] === "contained" ? "contained" : "compromised");
      else if (n.data("kind") === "service") n.addClass("atrisk");
      else n.addClass("onpath");
    });
    // attack edges: consecutive path hops + reach edges into at-risk services
    const pathPairs = new Set();
    (inc.paths || []).forEach((p) => { for (let i = 0; i + 1 < p.length; i++) pathPairs.add(p[i] + ">" + p[i + 1]); });
    const atRisk = new Set((inc.services_at_risk || []).map((s) => s.service));
    cy.edges().forEach((e) => {
      const a = e.source().id(), b = e.target().id();
      if (pathPairs.has(a + ">" + b)) e.addClass("attack");
      else if (e.hasClass("k-reach") && atRisk.has(b)) e.addClass("reachrisk");
    });
    if (S.blastMode) {
      const keep = new Set((inc.paths || []).flat());
      atRisk.forEach((s) => keep.add(s));
      cy.edges(".attack,.reachrisk").forEach((e) => { keep.add(e.source().id()); keep.add(e.target().id()); });
      cy.elements().filter((el) => !keep.has(el.id())).addClass("dim");
    }
  });
}

/* ---------------- detail ledger ---------------- */
function alertSummary(a) {
  const d = a.details || {};
  const bits = [];
  if (d.count) bits.push(d.count + " events/" + d.window_sec + "s");
  if (d.touched) bits.push("touched " + d.touched);
  if (d.commandline) bits.push(d.commandline.slice(0, 70));
  if (d.src_ip) bits.push("from " + d.src_ip);
  if (d.user || d.fails) bits.push((d.fails ? d.fails + " fails → " : "") + (d.user || ""));
  if (d.reason) bits.push(d.reason);
  if (d.dst) bits.push(d.dst + ":" + d.port + "/" + d.proto);
  if (d.command) bits.push(d.command + " " + (d.param || ""));
  return bits.join(" · ").slice(0, 110) || a.title;
}
async function renderDetail() {
  const d = $("detail");
  if (S.dossier) { renderDossier(); return; }
  const inc = selInc();
  if (!inc) {
    $("detailHead").textContent = "IMPACT LEDGER"; $("detailSub").textContent = "SELECT AN INCIDENT";
    d.innerHTML = '<div class="d-empty">No incident selected.<br>Run a scenario in the console below,<br>or tap an incident / graph node.</div>';
    return;
  }
  let full = inc;
  try { full = await fetchJSON("/api/incidents/" + inc.id); } catch (e) { /* fall back to list row */ }
  const rules = full.rule_ids || [];
  const sev = sevOf(full.risk_score || 0);
  const tacs = [["Credential Access", "T1110"], ["Lateral Movement", "T1021"], ["Command & Control", "T0855"], ["Impact", "T1486 / T1490"]];
  const tacHtml = tacs.map(([t, tech], i) => {
    const on = (t === "Credential Access" && rules.includes("R5")) || (t === "Lateral Movement" && rules.includes("R6")) ||
      (t === "Command & Control" && rules.includes("R10")) || (t === "Impact" && (rules.includes("R1") || rules.includes("R3")));
    return (i ? '<span class="tac-arrow">›</span>' : "") + `<span class="tac ${on ? "on" : ""}">${t} · ${tech}</span>`;
  }).join("");
  const top = (full.services_at_risk || [])[0];
  const chain = (full.paths || [])[0] || [full.endpoint_id];
  const steps = chain.map((nid, i) => {
    const rel = i === 0 ? "ORIGIN · COMPROMISED" : (i === chain.length - 1 ? "SUPPORTS · CLINICAL SERVICE" : "RUNS · HOSTS APPLICATION");
    const nm = nid.includes("_") && !nid.includes("-") ? prettySvc(nid).toUpperCase() : (/^(ehr|pacs|lis|pharmacy|directory|fileshare|remote_access|backup|infusion_mgmt|monitoring|ventilation|imaging_modality|surveillance|printing|pacs_viewer|ehr_client)$/.test(nid) ? prettyApp(nid) : nid);
    return `<div class="step"><div class="rail"><div class="dot"></div><div class="ln"></div></div>
      <div class="st"><div class="nm">${esc(nm)}</div><div class="why">${rel}</div></div></div>`;
  }).join("");
  const openedS = Date.parse(full.created_at) / 1000;
  const svcHtml = (full.services_at_risk || []).map((s) => {
    const rem = s.max_downtime_min * 60 - (Date.now() / 1000 - openedS);
    const pct = Math.max(0, Math.min(100, (rem / (s.max_downtime_min * 60)) * 100));
    const infeas = (s.activate_min || 0) > s.max_downtime_min;
    return `<div class="svc-card t${s.tier}">
      <div class="r1"><span class="nm">${esc(prettySvc(s.service))}</span><span class="risk">${Math.round(s.risk * 100)}</span></div>
      <div class="fb">TIER ${s.tier} · ${s.potential ? "POTENTIAL LATERAL · EXPOSURE ×" + s.exposure : s.exposure >= 0.99 ? "DIRECT EXPOSURE" : "EXPOSURE ×" + s.exposure}<br>
      fallback <b>${esc(s.fallback || "—")}</b> · readiness ${Math.round((s.fallback_readiness ?? 0.5) * 100)}% · activation ${s.activate_min ?? "?"} min
      ${infeas ? '<span class="tag-infeas">INFEASIBLE IN BUDGET</span>' : '<span class="tag-ok">FEASIBLE</span>'}</div>
      <div class="cdb ${rem <= 0 ? "breach" : pct < 40 ? "warn" : ""}" data-dead="${openedS + s.max_downtime_min * 60}" data-max="${s.max_downtime_min * 60}"><i style="width:${pct}%"></i><span>${rem <= 0 ? "BUDGET BREACHED" : ""}</span></div></div>`;
  }).join("");
  const sigHtml = (full.alerts || []).map((a) =>
    `<div class="sig"><span class="rid">${a.rule_id}</span><span class="tech">${RULE_TECH[a.rule_id] || ""}</span><span class="det">${esc(alertSummary(a))}</span><span class="tm">${(a.ts || "").slice(11, 19)}</span></div>`).join("");
  const rec = full.recommendation;
  const autoHtml = rec ? `<div class="act done"><div class="lab">${esc(rec.text)}</div>
    <span class="done-tag">${rec.auto ? "EXECUTED AUTOMATICALLY · LOW RISK" : "NEEDS HUMAN APPROVAL · " + esc(rec.approval || "").toUpperCase()}${rec.needs_clinical ? " · CLINICAL NOTIFIED" : ""}</span></div>` : "";
  const acts = full.actions || [];
  const actHtml = acts.filter((a) => a.status === "pending").map((a) =>
    `<div class="act"><div class="lab">${esc(a.action.replace(/_/g, " "))}<span class="riskchip ${a.risk_tier.includes("1") ? "high" : "med"}">${esc(a.risk_tier.toUpperCase())} · ANALYST</span></div>
     <div class="note">${esc(a.reason || "Disruptive containment — a human must sign.")}</div>
     <button class="btn pri" data-act="${esc(a.action)}">OPEN APPROVAL</button></div>`).join("") +
    acts.filter((a) => a.status !== "pending").map((a) =>
      `<div class="act done"><div class="lab">${esc(a.action.replace(/_/g, " "))}</div>
       <span class="done-tag" style="color:${a.status === "approved" ? "var(--ok)" : "var(--bad)"}">${a.status.toUpperCase()} · ${esc(a.approver || "")}</span></div>`).join("");
  const tech = techOf(full);
  d.innerHTML = `<div class="body">
    <div class="d-id">${full.id} · OPENED ${(full.created_at || "").slice(11, 19)} · CONFIDENCE ${Math.round((full.confidence || 0) * 100)}%</div>
    <div class="d-title">${esc(titleFor(rules))}</div>
    <div class="d-sub">endpoint: <span style="color:var(--teal)">${esc(full.endpoint_id)}</span> · status ${esc(full.status || "open").toUpperCase()}</div>
    ${full.status === "contained" ? `<div class="ban-contained">CONTAINMENT ACTIVE — endpoint isolated/segmented on human approval. New events here open a fresh incident.</div>` : ""}
    <div class="explain">${esc(full.explanation || "")}</div>
    <div class="scorebox">
      <div><div class="k">CLINICAL IMPACT</div><div class="v ${sevCls(sev)}">${full.risk_score}</div><div class="n">TIER × FALLBACK × EXPOSURE × CONF</div></div>
      <div><div class="k">TECHNICAL SEVERITY</div><div class="v lo">${tech}</div><div class="n">CVSS-STYLE BASE × CONFIDENCE</div></div>
      <div><div class="k">DIVERGENCE</div><div class="v ${full.risk_score - tech >= 0 ? "cr" : "el"}">${full.risk_score >= tech ? "+" : ""}${Math.round(full.risk_score - tech)}</div><div class="n">WHY WE DON'T RANK BY CVSS</div></div>
    </div>
    <div class="dsec">ATT&CK PROGRESSION</div><div class="tactics">${tacHtml}</div>
    <div class="dsec">PROPAGATION PATH — ${top ? esc(prettySvc(top.service).toUpperCase()) : "—"}</div>${steps}
    <div class="dsec">SERVICES AT RISK</div>${svcHtml || '<div class="d-sub">none reachable</div>'}
    <div class="dsec">DETECTED SIGNALS (${(full.alerts || []).length})</div>${sigHtml || '<div class="d-sub">none</div>'}
    <div class="dsec">RESPONSE</div>${autoHtml}${actHtml}
   </div>`;
  $("detailHead").textContent = "IMPACT LEDGER"; $("detailSub").textContent = full.id;
  d.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => openModal(full, b.dataset.act)));
}
function renderDossier() {
  const id = S.dossier;
  const n = (S.graph?.nodes || []).find((x) => x.id === id);
  const st = S.stats?.endpoint_status?.[id];
  const rel = S.incidents.find((i) => i.endpoint_id === id);
  const deps = (S.graph?.edges || []).filter((e) => e.source === id || e.target === id);
  $("detailHead").textContent = "ENDPOINT DOSSIER"; $("detailSub").textContent = id;
  $("detail").innerHTML = `<div class="body">
    <div class="d-id">${(n?.kind || "?").toUpperCase()} · ${n?.eclass ? n.eclass.toUpperCase() + " · " : ""}${n?.eclass === "device" || n?.eclass === "iot" ? "PASSIVE FLOW TELEMETRY" : "AGENT TELEMETRY"}</div>
    <div class="d-title">${esc(id)}</div>
    <div class="kv"><span class="k">STATUS</span><span class="v" style="color:${st === "compromised" ? "var(--bad)" : st === "contained" ? "var(--cyan)" : "var(--ok)"}">${esc((st || "operational").toUpperCase())}</span>
    <span class="k">INCIDENT</span><span class="v" style="color:var(--teal)">${rel ? rel.id + " · click in queue to open" : "—"}</span></div>
    <div class="dsec">DEPENDENCIES</div>
    ${deps.map((x) => `<div class="sig"><span class="tech" style="width:70px">${esc((x.rel || "").toUpperCase())}</span><span class="det">${esc(x.source === id ? x.target : x.source)}</span></div>`).join("") || '<div class="d-sub">none</div>'}
    <div class="explain" style="margin-top:12px">${n?.eclass === "device" || n?.eclass === "iot" ? "Unagentable device — detection is passive (baselines, command allow-lists). Containment is always a segmentation change, never a host action." : "Agent-bearing host — process, file and logon visibility; isolation via VLAN quarantine (human approval required)."}</div>
   </div>`;
}

/* ---------------- approval modal (PULSE style, single-analyst truth) ---------------- */
function openModal(inc, actionName) {
  const w = $("modalWrap"), m = $("modalBox");
  const top = (inc.services_at_risk || [])[0];
  const clinical = !!(inc.recommendation && inc.recommendation.needs_clinical);
  m.innerHTML = `
   <h3>HUMAN APPROVAL REQUIRED</h3>
   <div class="mtx"><b>${esc(actionName.replace(/_/g, " "))}</b><br>Incident <b>${inc.id}</b> · clinical impact <b>${inc.risk_score}</b> · ${sevOf(inc.risk_score || 0)}
   ${top ? `<br>Services at risk: <b>${esc(prettySvc(top.service))}</b> (Tier ${top.tier})` : ""}
   <br><span style="color:var(--high)">Cost of containment: the endpoint is treated as isolated — approve executes the state change.</span></div>
   <div class="appr"><div class="who"><b>A. Reyes</b><span>SOC ANALYST · ON SHIFT</span></div><div class="tog" id="togSoc">APPROVE</div></div>
   ${clinical ? `<div class="appr"><div class="who"><b>Dr. Okafor</b><span>CLINICAL CHAIR · NOTIFIED (INFORMATION ONLY)</span></div><div class="tog on">NOTIFIED ✓</div></div>` : ""}
   <div class="mtx" style="margin-top:8px;color:var(--txt3)">Two-person rule for Tier-1 is satisfied by analyst decision + clinical notification. Devices are never auto-contained.</div>
   <div class="mbtns">
     <button class="btn pri" id="mGo" disabled style="opacity:.4">CONFIRM EXECUTION</button>
     <button class="btn deny" id="mDeny">DENY</button>
     <button class="btn" id="mCancel">CANCEL</button></div>`;
  w.classList.add("open");
  let ok = false;
  $("togSoc").onclick = (e) => { ok = !ok; e.target.classList.toggle("on", ok); e.target.textContent = ok ? "APPROVED ✓" : "APPROVE";
    const go = $("mGo"); go.disabled = !ok; go.style.opacity = ok ? "1" : ".4"; };
  $("mCancel").onclick = () => w.classList.remove("open");
  $("mDeny").onclick = async () => {
    const reason = prompt("Denial reason (recorded in audit log):", "") ?? null;
    if (reason === null) return;
    w.classList.remove("open");
    await fetch(API + `/api/incidents/${inc.id}/actions/${encodeURIComponent(actionName)}/deny`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approver: "analyst", reason }) });
    toast("ACTION DENIED", actionName.replace(/_/g, " "), "warn");
    refreshAll(true);
  };
  $("mGo").onclick = async () => {
    w.classList.remove("open");
    const r = await fetch(API + `/api/incidents/${inc.id}/actions/${encodeURIComponent(actionName)}/approve`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approver: "analyst" }) });
    if (!r.ok) { toast("APPROVAL FAILED", await r.text(), "bad"); return; }
    toast("CONTAINMENT EXECUTED", actionName.replace(/_/g, " ") + " — incident contained", "bad");
    refreshAll(true);
  };
  icons();
}

/* ---------------- feed ---------------- */
function feedRowHTML(e) {
  const tag = e.event_type.replace(/_/g, " ").toUpperCase();
  return `<div class="fr${e.hot ? " hit" : ""}${e.note ? " hit2" : ""}">
    <span class="t">${(e.ts || "").slice(11, 19)}</span><span class="ep">${esc(e.endpoint_id)}</span>
    <span class="tag">${esc(tag)}</span><span class="msg">${esc(e.note || e.summary || "")}</span></div>`;
}

/* ---------------- charts ---------------- */
function renderCharts() {
  const nowMin = (ts) => Math.floor(Date.parse(ts) / 60000);
  const cur = S.stats ? nowMin(new Date().toISOString()) : 0;
  const stamps = (S.stats?.alert_ts || []).map(nowMin);
  // bucket over the data window if synthetic timestamps are old
  const latest = Math.max(cur, ...stamps, 0);
  const buckets = Array.from({ length: 14 }, (_, i) => { const b = latest - 13 + i; return { b, n: stamps.filter((t) => t === b).length }; });
  const mx = Math.max(1, ...buckets.map((x) => x.n));
  const bw = 100 / 14;
  $("chartRate").innerHTML = `<svg viewBox="0 0 100 46" preserveAspectRatio="none">${
    buckets.map((x, i) => { const h = (x.n / mx) * 38;
      return `<rect x="${(i * bw + 0.6).toFixed(2)}" y="${(43 - h).toFixed(2)}" width="${(bw - 1.2).toFixed(2)}" height="${Math.max(h, x.n ? h : 1).toFixed(2)}" fill="${x.n ? "#FF4D5E" : "#1E2830"}"/>`; }).join("")}</svg>`;
  const pts = S.incidents.map((i) => ({ x: techOf(i), y: i.risk_score, l: i.id.slice(-3), s: sevOf(i.risk_score) }));
  const SX = (v) => 8 + v * 0.84, SY = (v) => 52 - v * 0.46;
  $("chartScatter").innerHTML = `<svg viewBox="0 0 100 58">
   <line x1="8" y1="52" x2="94" y2="52" stroke="rgba(255,255,255,.15)"/><line x1="8" y1="4" x2="8" y2="52" stroke="rgba(255,255,255,.15)"/>
   <line x1="${SX(0)}" y1="${SY(0)}" x2="${SX(100)}" y2="${SY(100)}" stroke="rgba(255,255,255,.2)" stroke-dasharray="2 2"/>
   <text x="9" y="7" font-size="3.4" fill="#5D6E7A">EQUAL LINE — severity = impact</text>
   <text x="52" y="57" font-size="3.6" fill="#5D6E7A">TECHNICAL SEVERITY →</text>
   ${pts.map((p) => `<circle cx="${SX(p.x)}" cy="${SY(p.y)}" r="1.9" fill="${{ CRITICAL: "#FF4D5E", HIGH: "#FF7A45", ELEVATED: "#F5B942", LOW: "#8FA0AD" }[p.s]}"/>
     <text x="${SX(p.x) + 2.6}" y="${SY(p.y) + 1.2}" font-size="3.4" fill="#93A3AF">${p.l}</text>`).join("")}</svg>`;
  const cls = [["WORKST", "workstation"], ["SERVER", "server"], ["IoMT", "device"], ["IoT", "iot"]];
  const st = S.stats?.endpoint_status || {};
  $("chartPosture").innerHTML = cls.map(([lbl, c]) => {
    const eps = Object.entries(S.eclass).filter(([, k]) => k === c).map(([id]) => id);
    const n = eps.length || 1;
    const cnt = { operational: 0, watch: 0, compromised: 0, contained: 0 };
    eps.forEach((id) => { cnt[st[id] || "operational"]++; });
    const W = (v) => ((v / n) * 100).toFixed(1) + "%";
    return `<div class="posture-row"><span class="pl">${lbl}</span>
     <div class="pb"><i style="width:${W(cnt.operational)};background:#1F5C45"></i><i style="width:${W(cnt.watch)};background:#8A6A28"></i><i style="width:${W(cnt.compromised)};background:#FF4D5E"></i><i style="width:${W(cnt.contained)};background:#54B9C9"></i></div>
     <span class="pc">${cnt.compromised + cnt.contained}/${eps.length} hit</span></div>`;
  }).join("");
}

/* ---------------- ECG ---------------- */
const ECG = { data: [], beat: null, next: 0 };
function ecgWave(p) {
  if (p < 0.14) return 0.12 * Math.sin((p / 0.14) * Math.PI);
  if (p < 0.17) return -0.1;
  if (p < 0.2) return -0.1 + 1.1 * (p - 0.17) / 0.03;
  if (p < 0.23) return 1.0 - 1.32 * (p - 0.2) / 0.03;
  if (p < 0.3) return -0.32 * (1 - (p - 0.23) / 0.07);
  if (p < 0.45) return 0;
  if (p < 0.72) return 0.24 * Math.sin(((p - 0.45) / 0.27) * Math.PI);
  return 0;
}
function ecgFrame(t) {
  const cv = $("ecg");
  if (!cv) return;
  const dpr = window.devicePixelRatio || 1;
  if (cv.width !== 340 * dpr) { cv.width = 340 * dpr; cv.height = 38 * dpr; cv.getContext("2d").scale(dpr, dpr); }
  const ctx = cv.getContext("2d");
  const dark = S.code === "CODE DARK";
  const bpm = ({ NOMINAL: 72, WATCH: 96, ALERT: 124, "CODE DARK": 150 })[S.code] || 72;
  if (ECG.beat === null && t >= ECG.next) {
    ECG.beat = { p: 0, ugly: dark && Math.random() < 0.35, flat: dark && Math.random() < 0.12 };
    ECG.next = t + (60000 / bpm) * (dark ? 0.65 + Math.random() * 0.7 : 1);
  }
  let y = (Math.random() - 0.5) * 0.028;
  if (ECG.beat !== null) {
    if (ECG.beat.flat) y = 0;
    else { y = ecgWave(ECG.beat.p); if (ECG.beat.ugly) y *= 1 + 0.5 * Math.sin(ECG.beat.p * 44); }
    ECG.beat.p += 0.021;
    if (ECG.beat.p >= 1) { ECG.beat = null; ECG.next = t + (60000 / bpm) * (dark ? 0.65 + Math.random() * 0.7 : 1); }
  }
  ECG.data.push(y);
  if (ECG.data.length > 340) ECG.data.shift();
  ctx.clearRect(0, 0, 340, 38);
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.beginPath();
  for (let x = 0; x < 340; x += 34) { ctx.moveTo(x, 0); ctx.lineTo(x, 38); }
  ctx.moveTo(0, 19); ctx.lineTo(340, 19); ctx.stroke();
  ctx.strokeStyle = dark ? "#FF4D5E" : "#3DDC97";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ECG.data.forEach((v, i) => { const yy = 19 - v * 15; i ? ctx.lineTo(i, yy) : ctx.moveTo(i, yy); });
  ctx.stroke();
  requestAnimationFrame(ecgFrame);
}

/* ---------------- code level + tick ---------------- */
function checkCode() {
  const mx = Math.max(0, ...S.incidents.map((i) => i.risk_score || 0));
  /* DISPLAY: bands fitted to our measured clinical scale (campaign peak ≈41). */
  const want = mx >= 35 ? "CODE DARK" : mx >= 25 ? "ALERT" : mx >= 12 ? "WATCH" : "NOMINAL";
  if (want !== S.code) {
    S.code = want;
    const b = $("codeBadge");
    b.textContent = "CODE · " + want;
    b.className = "c-" + ({ NOMINAL: "nominal", WATCH: "watch", ALERT: "alert", "CODE DARK": "dark" })[want];
    $("topbar").classList.toggle("dark", want === "CODE DARK");
    if (want !== "NOMINAL") toast("FACILITY CODE LEVEL → " + want, "Peak clinical impact " + mx + " — escalation by clinical score, not alert count.", want === "CODE DARK" ? "bad" : "warn");
  }
}
function tick() {
  const now = new Date();
  $("topClock").innerHTML = "<b>" + now.toTimeString().slice(0, 8) + "</b><br>LIVE · <span>×1</span>";
  $("simClock").textContent = now.toTimeString().slice(0, 8);
  $("simRate").textContent = "LIVE";
  $("bpm").textContent = ({ NOMINAL: 72, WATCH: 96, ALERT: 124, "CODE DARK": 150 })[S.code] + " BPM" + (S.code === "CODE DARK" ? " · IRREG" : "");
  if (S.stats) $("capR").textContent = "EVT " + S.stats.events_total + " · ALERTS " + S.stats.alerts_total + " · INCIDENTS " + S.stats.incidents_open;
  const t = Date.now() / 1000;
  document.querySelectorAll("[data-dead]").forEach((el) => {
    const rem = +el.dataset.dead - t, max = +el.dataset.max;
    const pct = Math.max(0, Math.min(100, (rem / max) * 100));
    el.querySelector("i").style.width = pct + "%";
    el.querySelector("span").textContent = rem <= 0 ? "BUDGET BREACHED" : Math.floor(rem / 60) + ":" + String(Math.floor(rem % 60)).padStart(2, "0");
    el.classList.toggle("breach", rem <= 0);
    el.classList.toggle("warn", rem > 0 && pct < 40);
  });
  checkCode();
}

/* ---------------- audit panel ---------------- */
function renderAuditList(list) {
  $("auditList").innerHTML = list.map((r) =>
    `<div class="aud"><div class="ar1"><span>#${r.seq} · <b>${esc(r.actor)}</b></span><span class="dec ${/deny|denied|tamper|alter/i.test(r.action) ? "no" : "ok"}">${esc(r.action.length > 34 ? r.action.slice(0, 34) + "…" : r.action)}</span></div>
     <div>${esc(r.incident_id || "")} · ${(r.ts || "").slice(11, 19)}</div><div class="hsh">${(r.prev_hash || "").slice(0, 8)} → ${(r.hash || "").slice(0, 8)}</div></div>`).join("") ||
    '<div class="d-empty">Ledger empty.</div>';
}
async function refreshAudit() {
  if (!$("auditPanel").classList.contains("open")) return;
  try {
    const list = await fetchJSON("/api/audit?limit=100");
    renderAuditList(list);
  } catch (e) { /* keep old */ }
}

/* ---------------- main poll ---------------- */
let lastDetailJSON = "";
async function refreshAll(force) {
  try {
    const [incs, stats, feed] = await Promise.all([
      fetchJSON("/api/incidents"), fetchJSON("/api/stats"), fetchJSON("/api/events/recent?limit=40")]);
    // new-incident toasts
    incs.forEach((i) => {
      if (!S.known.has(i.id)) {
        S.known.add(i.id);
        if (S.known.size > 1 || S.stats) toast("INCIDENT " + i.id, titleFor(i.rule_ids || []) + " on " + i.endpoint_id + " — impact " + i.risk_score, "bad");
      }
    });
    S.incidents = incs; S.stats = stats; S.feed = feed;
    renderQueue(); renderCharts();
    if (!cy && S.graph) buildGraph(S.graph);
    paintGraph();
    // detail: re-render only on change (preserves scroll otherwise)
    if (S.selected || S.dossier) {
      const sel = selInc();
      const key = sel ? sel.id + ":" + sel.updated_at + ":" + (sel.status || "") : "dossier:" + S.dossier;
      if (force || key !== lastDetailJSON) { lastDetailJSON = key; await renderDetail(); }
    } else if (lastDetailJSON !== "empty") {
      lastDetailJSON = "empty";
      $("detailHead").textContent = "IMPACT LEDGER"; $("detailSub").textContent = "SELECT AN INCIDENT";
      $("detail").innerHTML = '<div class="d-empty">No incident selected.<br>Run a scenario in the console below,<br>or tap an incident / graph node.</div>';
    }
    refreshAudit();
  } catch (e) { console.error(e); }
}
async function boot() {
  try {
    S.graph = await fetchJSON("/api/graph");
    S.eclass = {};
    S.graph.nodes.forEach((n) => { if (n.eclass) S.eclass[n.id] = n.eclass; });
    buildGraph(S.graph);
  } catch (e) { $("cy").innerHTML = '<div class="d-empty">Graph API unreachable — is the server running?</div>'; }
  renderConsole(); refreshAll(true);
  setInterval(() => refreshAll(false), 1000);
  setInterval(tick, 250);
  setInterval(renderCharts, 1500);
  requestAnimationFrame(ecgFrame);
  toast("PULSE CONSOLE LIVE", "Backend connected. Run a scenario — or GUIDED DEMO for the walkthrough.");
  icons();
}
window.addEventListener("resize", () => { if (cy) { cy.resize(); cy.fit(30); } });
$("btnReset").onclick = resetConsole;
$("btnGuided").onclick = guidedRun;
$("btnAmbient").onclick = ambient;
$("auditBtn").onclick = async () => { $("auditPanel").classList.add("open");
  try { renderAuditList(await fetchJSON("/api/audit?limit=100")); } catch (e) {} };
$("auditClose").onclick = () => $("auditPanel").classList.remove("open");
$("btnVerify").onclick = async () => {
  const r = await fetchJSON("/api/audit/verify");
  const b = $("verifyBanner");
  b.style.display = "block";
  if (r.ok) { b.className = ""; b.textContent = "CHAIN VERIFIED — " + r.checked + " ENTRIES · SHA-256 LINKED · INTACT"; }
  else { b.className = "bad"; b.textContent = "CHAIN BROKEN AT ENTRY #" + r.tampered_seq + " — HASH MISMATCH · TAMPERING DETECTED"; }
};
$("btnTamper").onclick = async () => {
  const r = await (await fetch(API + "/api/audit/tamper", { method: "POST" })).json();
  if (r.ok) { toast("TAMPER SIMULATION", "Entry #" + r.tampered_seq + " modified in storage. Run VERIFY CHAIN.", "bad"); refreshAudit(); }
  else toast("LEDGER", r.detail || "Nothing to tamper — run a scenario first.", "warn");
};
$("tglBlast").onclick = (e) => { S.blastMode = !S.blastMode; e.target.classList.toggle("on", S.blastMode); paintGraph(); };
$("tglReach").onclick = (e) => { S.showReach = !S.showReach; e.target.classList.toggle("on", S.showReach); paintGraph(); };
$("tglFit").onclick = () => cy && cy.fit(30);
boot();
