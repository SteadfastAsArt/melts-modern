/**
 * MELTS Modern — Frontend logic
 *
 * Handles form population, simulation execution via REST + WebSocket,
 * Plotly plot fetching / rendering, tab switching, and data table display.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const OX = [
  "SiO2", "TiO2", "Al2O3", "Fe2O3", "Cr2O3",
  "FeO", "MnO", "MgO", "NiO", "CoO",
  "CaO", "Na2O", "K2O", "P2O5", "H2O",
  "CO2", "SO3", "Cl2O-1", "F2O-1",
];

// First 14 are "main", last 5 are "minor"
const MAIN_OX_COUNT = 14;

const MODE_NAMES = {
  "1": "rhyolite-MELTS 1.0.2",
  "2": "pMELTS 5.6.1",
  "3": "rhyolite-MELTS 1.1.0",
  "4": "rhyolite-MELTS 1.2.0",
};

// Which plots each tab needs: { tabName: [{divId, plotType}] }
const TAB_PLOTS = {
  classification: [
    { divId: "plot-tas", plotType: "tas" },
    { divId: "plot-afm", plotType: "afm" },
  ],
  harker: [
    { divId: "plot-harker-mgo", plotType: "harker_mgo" },
    { divId: "plot-harker-sio2", plotType: "harker_sio2" },
    { divId: "plot-mg-vs-sio2", plotType: "mg_vs_sio2" },
  ],
  "pt-path": [
    { divId: "plot-pt-path", plotType: "pt_path" },
  ],
  evolution: [
    { divId: "plot-evolution", plotType: "evolution" },
    { divId: "plot-liquid-vs-temp", plotType: "liquid_vs_temp" },
  ],
  phases: [
    { divId: "plot-phase-masses", plotType: "phase_masses" },
    { divId: "plot-olivine", plotType: "olivine" },
    { divId: "plot-cpx", plotType: "cpx" },
    { divId: "plot-plagioclase", plotType: "plagioclase" },
    { divId: "plot-spinel", plotType: "spinel" },
  ],
  system: [
    { divId: "plot-system-thermo", plotType: "system_thermo" },
    { divId: "plot-density", plotType: "density" },
  ],
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentSimId = null;
let presets = {};
let plotCache = {};       // { "simId:plotType": true } — tracks fetched plots
let simResults = [];      // accumulated results for data table
let minorOxVisible = false;
let simRunning = false;

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const $form = document.getElementById("sim-form");
const $presetSelect = document.getElementById("preset-select");
const $meltsMode = document.getElementById("melts-mode");
const $modeBadge = document.getElementById("mode-badge");
const $pmeltsWarning = document.getElementById("pmelts-warning");
const $compBody = document.getElementById("comp-body");
const $toggleMinor = document.getElementById("toggle-minor");
const $btnRun = document.getElementById("btn-run");
const $progressSection = document.getElementById("progress-section");
const $progressBar = document.getElementById("progress-bar");
const $progressInfo = document.getElementById("progress-info");
const $errorDisplay = document.getElementById("error-display");
const $tabs = document.getElementById("tabs");
const $tabContent = document.getElementById("tab-content");
const $emptyState = document.getElementById("empty-state");
const $btnCsv = document.getElementById("btn-csv");
const $rowCount = document.getElementById("row-count");
const $tableWrapper = document.getElementById("table-wrapper");
const $sidebarToggle = document.getElementById("sidebar-toggle");
const $sidebar = document.getElementById("sidebar");
const $dpDtDisplay = document.getElementById("dp-dt-display");

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  buildCompTable();
  loadPresets();
  bindEvents();
  updateDpDt();
});

function buildCompTable() {
  $compBody.innerHTML = "";
  OX.forEach((ox, i) => {
    const tr = document.createElement("tr");
    const isMinor = i >= MAIN_OX_COUNT;
    if (isMinor) tr.classList.add("minor-ox");
    tr.innerHTML = `
      <td class="ox-label">${formatOxide(ox)}</td>
      <td><input type="number" step="0.001" min="0" max="100"
                 id="ox-${ox}" data-oxide="${ox}" value="0" class="ox-input"></td>
    `;
    $compBody.appendChild(tr);
  });
  updateMinorVisibility();
}

function formatOxide(ox) {
  // Pretty-print oxide names with subscripts for HTML display
  return ox
    .replace(/(\d+)/g, "<sub>$1</sub>")
    .replace("-1", "<sup>-1</sup>");
}

async function loadPresets() {
  try {
    const resp = await fetch("/api/presets");
    presets = await resp.json();
    $presetSelect.innerHTML = '<option value="">-- Custom --</option>';
    for (const [key, preset] of Object.entries(presets)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = preset.name;
      $presetSelect.appendChild(opt);
    }
  } catch (e) {
    console.error("Failed to load presets:", e);
  }
}

// ---------------------------------------------------------------------------
// Event binding
// ---------------------------------------------------------------------------
function bindEvents() {
  $presetSelect.addEventListener("change", onPresetChange);
  $meltsMode.addEventListener("change", onModeChange);
  $toggleMinor.addEventListener("click", onToggleMinor);
  $form.addEventListener("submit", onFormSubmit);
  $btnCsv.addEventListener("click", onCsvDownload);
  $sidebarToggle.addEventListener("click", () => {
    $sidebar.classList.toggle("open");
  });

  // Tab switching
  $tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });

  // Update dp/dt when T or P fields change
  ["T-start", "T-end", "P-start", "P-end"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateDpDt);
  });
}

// ---------------------------------------------------------------------------
// Preset / mode handlers
// ---------------------------------------------------------------------------
function onPresetChange() {
  const key = $presetSelect.value;
  if (!key || !presets[key]) return;
  const preset = presets[key];

  // Fill composition
  OX.forEach((ox) => {
    const input = document.getElementById(`ox-${ox}`);
    input.value = preset.composition[ox] || 0;
  });

  // Fill defaults
  if (preset.defaults) {
    const d = preset.defaults;
    if (d.T_start != null) document.getElementById("T-start").value = d.T_start;
    if (d.T_end != null) document.getElementById("T-end").value = d.T_end;
    if (d.P_start != null) document.getElementById("P-start").value = d.P_start;
    if (d.P_end != null) document.getElementById("P-end").value = d.P_end;
  }
  updateDpDt();
}

function onModeChange() {
  const mode = $meltsMode.value;
  $modeBadge.textContent = MODE_NAMES[mode] || "";
  $pmeltsWarning.classList.toggle("hidden", mode !== "2");
}

function onToggleMinor() {
  minorOxVisible = !minorOxVisible;
  updateMinorVisibility();
}

function updateMinorVisibility() {
  const rows = $compBody.querySelectorAll(".minor-ox");
  rows.forEach((r) => (r.style.display = minorOxVisible ? "" : "none"));
  $toggleMinor.textContent = minorOxVisible ? "Hide minor oxides" : "Show more oxides...";
}

function updateDpDt() {
  const tStart = parseFloat(document.getElementById("T-start").value) || 0;
  const tEnd = parseFloat(document.getElementById("T-end").value) || 0;
  const pStart = parseFloat(document.getElementById("P-start").value) || 0;
  const pEnd = parseFloat(document.getElementById("P-end").value) || 0;
  const dT = tEnd - tStart;
  if (Math.abs(dT) < 0.01) {
    $dpDtDisplay.textContent = "dP/dT = -- (isobaric if P constant)";
    return;
  }
  const dpdt = (pEnd - pStart) / dT;
  $dpDtDisplay.textContent = `dP/dT = ${dpdt.toFixed(1)} bar/\u00b0C`;
}

// ---------------------------------------------------------------------------
// Form submission
// ---------------------------------------------------------------------------
function onFormSubmit(e) {
  e.preventDefault();
  if (simRunning) return;

  // Build config object
  const composition = {};
  OX.forEach((ox) => {
    const val = parseFloat(document.getElementById(`ox-${ox}`).value);
    if (val > 0) composition[ox] = val;
  });

  // Validate: need at least SiO2
  if (!composition.SiO2 || composition.SiO2 < 1) {
    showError("Composition must include at least SiO2 > 0 wt%.");
    return;
  }

  const config = {
    melts_mode: parseInt($meltsMode.value),
    composition,
    T_start: parseFloat(document.getElementById("T-start").value),
    T_end: parseFloat(document.getElementById("T-end").value),
    dT: parseFloat(document.getElementById("dT").value),
    P_start: parseFloat(document.getElementById("P-start").value),
    P_end: parseFloat(document.getElementById("P-end").value),
    crystallization_mode: document.getElementById("cryst-mode").value,
  };

  const fo2 = document.getElementById("fo2-buffer").value;
  if (fo2) {
    config.fo2_buffer = fo2;
    config.fo2_offset = parseFloat(document.getElementById("fo2-offset").value) || 0;
  }

  // Validate T range
  if (config.dT >= 0 && config.T_start > config.T_end) {
    showError("dT must be negative when T_start > T_end (cooling).");
    return;
  }

  startSimulation(config);
}

// ---------------------------------------------------------------------------
// Simulation lifecycle
// ---------------------------------------------------------------------------
async function startSimulation(config) {
  simRunning = true;
  simResults = [];
  plotCache = {};
  currentSimId = null;
  $btnRun.disabled = true;
  $btnRun.textContent = "Running...";
  $emptyState.classList.add("hidden");
  $errorDisplay.classList.add("hidden");
  $progressSection.classList.remove("hidden");
  $progressBar.style.width = "0%";
  $progressInfo.textContent = "Starting simulation...";

  // Clear previous plots
  clearAllPlots();

  try {
    const resp = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    currentSimId = data.sim_id;

    // Poll for results
    pollSimulation(data.sim_id, config);
  } catch (err) {
    showError(`Failed to start simulation: ${err.message}`);
    resetRunButton();
  }
}

function pollSimulation(simId, config) {
  const nSteps = Math.abs((config.T_start - config.T_end) / Math.abs(config.dT));
  $progressInfo.textContent = "Initializing MELTS engine...";
  $progressBar.style.width = "2%";

  const pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/simulate/${simId}/results`);
      if (!resp.ok) { clearInterval(pollInterval); return; }
      const data = await resp.json();

      // Update progress from results
      if (data.results && data.results.length > 0) {
        const latest = data.results[data.results.length - 1];
        const pct = Math.min(99, (data.results.length / nSteps) * 100);
        $progressBar.style.width = pct.toFixed(1) + "%";
        $progressInfo.textContent =
          `Step ${data.results.length} / ~${Math.round(nSteps)} | T = ${latest.T_C.toFixed(0)}\u00b0C | P = ${latest.P_bar.toFixed(0)} bar`;
        // Keep simResults in sync
        simResults = data.results;
      }

      if (data.status === "done") {
        clearInterval(pollInterval);
        simResults = data.results;
        onSimulationComplete(simId);
      } else if (data.status === "error") {
        clearInterval(pollInterval);
        showError(`Simulation error: ${data.error}`);
        resetRunButton();
      }
    } catch (e) {
      // Network error, keep trying
      console.warn("Poll error:", e);
    }
  }, 1000); // poll every 1 second
}

async function checkSimStatus(simId) {
  try {
    const resp = await fetch(`/api/simulate/${simId}/results`);
    const data = await resp.json();
    if (data.status === "done") {
      simResults = data.results;
      onSimulationComplete(simId);
    } else if (data.status === "error") {
      showError(`Simulation error: ${data.error}`);
      resetRunButton();
    }
  } catch (e) {
    // Ignore — we already showed the WebSocket error
  }
}

function onSimulationComplete(simId) {
  simRunning = false;
  $progressBar.style.width = "100%";
  $progressInfo.textContent = `Done. ${simResults.length} steps computed.`;
  resetRunButton();

  // Fetch plots for the currently active tab
  const activeTab = document.querySelector(".tab.active");
  if (activeTab) {
    fetchPlotsForTab(activeTab.dataset.tab, simId);
  }
}

function resetRunButton() {
  simRunning = false;
  $btnRun.disabled = false;
  $btnRun.textContent = "Run Simulation";
}

// ---------------------------------------------------------------------------
// Error display
// ---------------------------------------------------------------------------
function showError(msg) {
  $errorDisplay.textContent = msg;
  $errorDisplay.classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === tabName);
  });

  // Update panes
  document.querySelectorAll(".tab-pane").forEach((p) => {
    p.classList.toggle("active", p.dataset.pane === tabName);
  });

  // If data tab, render table
  if (tabName === "data" && simResults.length > 0) {
    renderDataTable();
  }

  // Fetch plots for this tab if we have a sim
  if (currentSimId && simResults.length > 0) {
    fetchPlotsForTab(tabName, currentSimId);
  }
}

// ---------------------------------------------------------------------------
// Plot fetching & rendering
// ---------------------------------------------------------------------------
async function fetchPlotsForTab(tabName, simId) {
  const plots = TAB_PLOTS[tabName];
  if (!plots) return;

  for (const { divId, plotType } of plots) {
    const cacheKey = `${simId}:${plotType}`;
    if (plotCache[cacheKey]) continue;

    const container = document.getElementById(divId);
    if (!container) continue;

    // Show loading state
    container.innerHTML = '<div class="plot-loading">Loading plot...</div>';

    try {
      const resp = await fetch(`/api/plots/${simId}/${plotType}`);
      if (!resp.ok) {
        const errText = await resp.text();
        container.innerHTML = `<div class="plot-error">Plot unavailable: ${errText}</div>`;
        continue;
      }
      const figJson = await resp.json();
      container.innerHTML = "";

      // Apply responsive layout defaults
      const layout = figJson.layout || {};
      layout.autosize = true;
      layout.margin = layout.margin || { l: 60, r: 30, t: 50, b: 50 };

      Plotly.newPlot(container, figJson.data, layout, {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
      });

      plotCache[cacheKey] = true;
    } catch (err) {
      container.innerHTML = `<div class="plot-error">Failed to load plot: ${err.message}</div>`;
    }
  }
}

function clearAllPlots() {
  const plotDivs = document.querySelectorAll(".plot-container");
  plotDivs.forEach((div) => {
    Plotly.purge(div);
    div.innerHTML = "";
  });
}

// ---------------------------------------------------------------------------
// Data table
// ---------------------------------------------------------------------------
function renderDataTable() {
  if (simResults.length === 0) {
    $tableWrapper.innerHTML = '<p class="placeholder-text">No data yet.</p>';
    $rowCount.textContent = "";
    return;
  }

  // Columns to display (skip 'type')
  const cols = Object.keys(simResults[0]).filter((k) => k !== "type");

  // Short column labels
  const shortLabel = (col) => {
    return col
      .replace("mass_liquid_g", "Liq (g)")
      .replace("mass_solid_g", "Sol (g)")
      .replace("liq_", "")
      .replace("_", " ");
  };

  let html = '<table class="data-table"><thead><tr>';
  cols.forEach((c) => {
    html += `<th data-col="${c}">${shortLabel(c)}</th>`;
  });
  html += "</tr></thead><tbody>";

  simResults.forEach((row) => {
    html += "<tr>";
    cols.forEach((c) => {
      let val = row[c];
      if (c === "phase_details" && Array.isArray(val)) {
        // Summarize: "olivine1 (2.31g), spinel1 (0.05g), ..."
        val = val.map((p) => `${p.phase} (${p.mass.toFixed(2)}g)`).join(", ");
      } else if (typeof val === "number") {
        val = Math.abs(val) < 0.01 && val !== 0 ? val.toExponential(3) : val.toFixed(4);
      }
      html += `<td>${val}</td>`;
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  $tableWrapper.innerHTML = html;
  $rowCount.textContent = `${simResults.length} rows`;

  // Sortable headers
  $tableWrapper.querySelectorAll("th").forEach((th) => {
    th.style.cursor = "pointer";
    th.addEventListener("click", () => sortTable(th.dataset.col));
  });
}

let sortCol = null;
let sortAsc = true;

function sortTable(col) {
  if (sortCol === col) {
    sortAsc = !sortAsc;
  } else {
    sortCol = col;
    sortAsc = true;
  }

  simResults.sort((a, b) => {
    const va = a[col];
    const vb = b[col];
    if (typeof va === "number" && typeof vb === "number") {
      return sortAsc ? va - vb : vb - va;
    }
    return sortAsc
      ? String(va).localeCompare(String(vb))
      : String(vb).localeCompare(String(va));
  });

  renderDataTable();
}

// ---------------------------------------------------------------------------
// CSV download
// ---------------------------------------------------------------------------
function onCsvDownload() {
  if (!currentSimId) return;
  window.open(`/api/simulate/${currentSimId}/csv`, "_blank");
}
