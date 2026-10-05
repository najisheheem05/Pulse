// Hospital Impact Defense — panel dashboard (1s polling, no build step)
const API = "";
let cy = null;
let selectedInc = null;
let lastIncidents = [];

async function fetchJSON(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

function tierClass(t) { return t === 1 ? "t1" : t === 2 ? "t2" : "t3"; }
function tierLabel(t) { return t === 1 ? "T1 ● life-critical" : t === 2 ? "T2 ● urgent" : "T3 ● deferrable"; }
function fmtMins(m) { const h = Math.floor(m/60), mm = m%60; return h? `${h}h ${mm}m` : `${mm}m`; }

function renderIncidents(list) {
  const el = document.getElementById("incList");
  document.getElementById("incCount").textContent = list.length;
  if (!list.length) { el.innerHTML = '<div style="color:var(--muted);padding:1rem;text-align:center">No incidents — run a scenario (A/B/C/D)</div>'; return; }
  el.innerHTML = list.map((inc, i) => {
    const top = inc.services_at_risk?.[0] || {};
    const tier = top.tier || 3;
    const deadline = top.max_downtime_min ? fmtMins(top.max_downtime_min) : "—";
    return `<div class="incident ${selectedInc===inc.id?'selected':''}" data-id="${inc.id}" onclick="selectInc('${inc.id}')">
      <div class="incident-head">
        <span class="incident-id">${inc.id}</span>
        <span class="incident-score ${tierClass(tier)}">${(inc.risk_score||0).toFixed(1)}</span>
      </div>
      <div class="incident-meta">
        <span>${inc.endpoint_id}</span>
        <span>${inc.rule_ids?.join(", ")||"–"}</span>
        <span>conf ${(inc.confidence*100).toFixed(0)}%</span>
      </div>
      <div class="incident-svc">
        <span class="tier tier-${tier}">${tierLabel(tier)}</span>
        <span>${top.service||"no service mapped"}</span>
        <span class="potential">${top.potential?" (potential lateral)":""}</span>
      </div>
      <div class="incident-meta"><span class="clock ${tier===1?'danger':tier===2?'warn':''}">deadline: ${deadline}</span></div>
    </div>`;
  }).join("");
}

function selectInc(id) {
  selectedInc = id;
  document.querySelectorAll(".incident").forEach(d=>d.classList.toggle("selected", d.dataset.id===id));
  loadDetail(id);
  loadGraph(id);
}

async function loadDetail(id) {
  const inc = await fetchJSON(`/api/incidents/${id}`);
  document.getElementById("detailTitle").textContent = `${inc.id} • ${inc.endpoint_id}`;
  const top = inc.services_at_risk?.[0] || {};
  let txt = inc.explanation || "";
  if (top.fallback) txt += `\n\nFallback: ${top.fallback} (readiness ${Math.round((top.fallback_readiness||0.5)*100)}%, activate in ${top.fallback_activate_min||top.activate_min||"?"} min)`;
  if (inc.recommendation) {
    txt += `\n\nRecommendation: ${inc.recommendation.text}`;
    txt += `\nAuto: ${inc.recommendation.auto ? "yes" : "no"} • Approval: ${inc.recommendation.approval}`;
    if (inc.recommendation.needs_clinical) txt += " ⚠ Clinical notification required";
  }
  document.getElementById("explainBox").textContent = txt;
  // actions
  const acts = inc.actions || [];
  const box = document.getElementById("actionsBox");
  if (!acts.length) { box.innerHTML = '<div style="color:var(--muted);font-size:.75rem">No actions requested</div>'; return; }
  box.innerHTML = acts.map(a => `
    <div class="action-row">
      <span style="font-family:var(--mono);font-size:.7rem">${a.id}</span>
      <strong>${a.action}</strong>
      <span class="action-status ${a.status}">${a.status}</span>
      <span style="color:var(--muted);font-size:.7rem">${a.approver||"–"}</span>
      ${a.status==="pending" ? `
        <button class="btn btn-primary" onclick="decide('${a.id}', true)">Approve</button>
        <button class="btn btn-danger" onclick="decide('${a.id}', false)">Deny</button>
      ` : ""}
    </div>`).join("");
}

async function decide(actionId, approve) {
  const inc = selectedInc;
  if (!inc) return;
  const path = `/api/incidents/${inc}/actions/${actionId}/${approve?"approve":"deny"}`;
  await fetch(API + path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({approver:"analyst"})});
  loadDetail(inc);
  loadAudit();
}

async function loadGraph(highlightId) {
  if (!cy) {
    try {
      const data = await fetchJSON("/api/graph");
      initCytoscape(data);
      if (highlightId) {
        const h = await fetchJSON(`/api/graph?highlight_inc=${highlightId}`);
        applyGraphStyle(h);
      }
    } catch(e) {
      console.error("graph init failed:", e);
      document.getElementById("cy").innerHTML =
        '<div style="color:var(--red);padding:1rem">Graph failed to load: ' + e.message + '</div>';
    }
  } else {
    try {
      const data = await fetchJSON(`/api/graph?highlight_inc=${highlightId||""}`);
      applyGraphStyle(data);
    } catch(e) { console.error("graph update failed:", e); }
  }
}

function initCytoscape(data) {
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: data.nodes.map(n=>({data:{id:n.id,label:n.id,kind:n.kind,tier:n.tier,eclass:n.eclass,hot:n.hot?1:0}}))
      .concat(data.edges.map(e=>({data:{source:e.source,target:e.target,hot:e.hot?1:0}}))),
    style: [
      // base: light label with dark halo so text reads on the dark theme
      {selector:"node", style:{"label":"data(label)","font-size":11,"color":"#e8edf2",
        "font-weight":400,"text-valign":"bottom","text-halign":"center","text-margin-y":7,
        "text-outline-width":2,"text-outline-color":"#0b0f14","text-outline-opacity":0.9,
        "background-color":"#1f2a36","border-width":2,"border-color":"#3b4c5e",
        "width":30,"height":30,"z-index":1}},
      // workstations: blue ellipse
      {selector:"node[eclass = 'workstation']", style:{"shape":"ellipse","background-color":"#16283a","border-color":"#60a5fa"}},
      // servers: blue rounded rect, slightly larger
      {selector:"node[eclass = 'server']", style:{"shape":"round-rectangle","background-color":"#1a2440","border-color":"#60a5fa","width":38,"height":28}},
      // medical devices: purple diamond
      {selector:"node[eclass = 'device']", style:{"shape":"diamond","background-color":"#241536","border-color":"#c084fc","width":34,"height":34}},
      // building IoT: teal triangle
      {selector:"node[eclass = 'iot']", style:{"shape":"triangle","background-color":"#0f2b28","border-color":"#2dd4bf","width":32,"height":32}},
      // applications: violet round rect
      {selector:"node[kind = 'application']", style:{"shape":"round-rectangle","background-color":"#1c1830","border-color":"#a78bfa","width":36,"height":24,"font-size":10,"color":"#d8ccff"}},
      // services: tier-colored, bold labels
      {selector:"node[kind = 'service']", style:{"shape":"round-rectangle","width":64,"height":30,"font-size":12,"font-weight":700}},
      {selector:"node[tier = 1]", style:{"background-color":"#2a1215","border-color":"#ff5c5c","color":"#ffc9c9"}},
      {selector:"node[tier = 2]", style:{"background-color":"#2a2111","border-color":"#ffb84d","color":"#ffe1ae"}},
      {selector:"node[tier = 3]", style:{"background-color":"#0f2a1e","border-color":"#4ade80","color":"#b8f4cd"}},
      // attack path: red glow + white bold labels, above everything
      {selector:"node[hot = 1]", style:{"border-color":"#ff5c5c","border-width":3,"color":"#ffffff",
        "font-weight":700,"shadow-blur":14,"shadow-color":"#ff5c5c","shadow-opacity":0.8,"z-index":10}},
      {selector:"edge", style:{"width":1.5,"line-color":"#3b4c5e","target-arrow-shape":"triangle",
        "target-arrow-color":"#3b4c5e","target-arrow-fill":"filled","arrow-scale":1.1,"curve-style":"bezier","opacity":0.85}},
      {selector:"edge[hot = 1]", style:{"line-color":"#ff5c5c","target-arrow-color":"#ff5c5c",
        "width":3,"opacity":1,"shadow-blur":8,"shadow-color":"#ff5c5c","shadow-opacity":0.7}}
    ],
    layout: {name:"breadthfirst", directed:true, padding:14, spacingFactor:1.3,
             circle:false, grid:false, avoidOverlap:true, maximal:true, animate:false},
    minZoom:0.3, maxZoom:2.5, zoomingEnabled:true, userZoomingEnabled:true, panningEnabled:true,
    wheelSensitivity:0.3
  });
  cy.on("tap", "node", e => {
    // only incident endpoints are selectable — map node -> incident by endpoint_id
    const nodeId = e.target.data("id");
    const inc = (lastIncidents||[]).find(i => i.endpoint_id === nodeId);
    if (inc && inc.id !== selectedInc) selectInc(inc.id);
  });
}

function applyGraphStyle(data) {
  // visuals live in the stylesheet (kind/tier/hot selectors) — here we only flip data flags
  cy.nodes().forEach(n => {
    const match = data.nodes.find(d => d.id === n.id());
    if (match) n.data("hot", match.hot ? 1 : 0);
  });
  cy.edges().forEach(e => {
    const match = data.edges.find(d => d.source === e.source().id() && d.target === e.target().id());
    if (match) e.data("hot", match.hot ? 1 : 0);
  });
}

async function loadAudit() {
  const v = await fetchJSON("/api/audit/verify");
  const box = document.getElementById("auditBox");
  box.className = "verification " + (v.ok ? "ok" : "fail");
  box.textContent = v.ok
    ? `✓ Audit chain OK — ${v.checked} entries verified`
    : `✗ TAMPER DETECTED at seq ${v.tampered_seq} (${v.checked} checked)`;
}

async function refreshAll() {
  try {
    const incs = await fetchJSON("/api/incidents");
    lastIncidents = incs;
    renderIncidents(incs);
    if (selectedInc) {
      const still = incs.find(i=>i.id===selectedInc);
      if (!still) { selectedInc=null; document.getElementById("explainBox").textContent="Select an incident"; document.getElementById("actionsBox").innerHTML=""; }
      else { loadDetail(selectedInc); loadGraph(selectedInc); }
    }
    loadAudit();
  } catch(e) {
    console.error(e);
    document.getElementById("statusBadge").textContent = "ERROR";
    document.getElementById("statusBadge").style.background = "rgba(255,92,92,.3)";
    document.getElementById("statusBadge").style.color = "#ff5c5c";
  }
}

function tickClock() {
  const now = new Date();
  document.getElementById("clock").textContent = now.toLocaleTimeString();
}

setInterval(refreshAll, 1000);
setInterval(tickClock, 1000);
tickClock();
refreshAll();