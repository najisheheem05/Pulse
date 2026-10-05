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
    elements: data.nodes.map(n=>({data:{id:n.id,label:n.id,kind:n.kind,tier:n.tier,hot:n.hot}}))
      .concat(data.edges.map(e=>({data:{source:e.source,target:e.target,hot:e.hot}}))),
    style: [
      {selector:"node", style:{"label":"data(id)","font-size":9,"text-valign":"bottom","text-halign":"center","background-color":"#1f2a36","border-width":1,"border-color":"#2d3d4a","width":28,"height":28}},
      {selector:"node[kind='service']", style:{"background-color":"#0f2a1e","border-color":"#4ade80","shape":"rectangle","width":40,"height":22}},
      {selector:"node[hot]", style:{"background-color":"#ff5c5c","border-color":"#ff9999","border-width":2,"z-index":10}},
      {selector:"edge", style:{"width":1,"line-color":"#2d3d4a","target-arrow-shape":"triangle","target-arrow-color":"#2d3d4a","curve-style":"bezier"}},
      {selector:"edge[hot]", style:{"line-color":"#ff5c5c","target-arrow-color":"#ff5c5c","width":2}}
    ],
    layout: {name:"breadthfirst", directed:true, padding:12, spacingFactor:1.15,
             circle:false, grid:false, avoidOverlap:true, animate:false},
    minZoom:0.3, maxZoom:2, zoomingEnabled:true, userZoomingEnabled:true, panningEnabled:true
  });
  cy.on("tap", "node", e => {
    // only incident endpoints are selectable — map node -> incident by endpoint_id
    const nodeId = e.target.data("id");
    const inc = (lastIncidents||[]).find(i => i.endpoint_id === nodeId);
    if (inc && inc.id !== selectedInc) selectInc(inc.id);
  });
}

function applyGraphStyle(data) {
  cy.nodes().forEach(n => {
    const match = data.nodes.find(d => d.id === n.id());
    if (match) {
      n.data("hot", match.hot);
      n.style("background-color", match.hot ? "#ff5c5c" : (match.kind==="service"?"#0f2a1e":"#1f2a36"));
      n.style("border-color", match.hot ? "#ff9999" : (match.kind==="service"?"#4ade80":"#2d3d4a"));
    }
  });
  cy.edges().forEach(e => {
    const match = data.edges.find(d => d.source === e.source().id() && d.target === e.target().id());
    if (match) {
      e.data("hot", match.hot);
      e.style("line-color", match.hot ? "#ff5c5c" : "#2d3d4a");
      e.style("target-arrow-color", match.hot ? "#ff5c5c" : "#2d3d4a");
      e.style("width", match.hot ? 2 : 1);
    }
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