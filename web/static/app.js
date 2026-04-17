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

// MAGEMin uses a reduced oxide set (FeOt instead of FeO + Fe2O3, no MnO/NiO/CoO etc.)
const OX_MAGEMIN = [
  "SiO2", "TiO2", "Al2O3", "FeOt", "Cr2O3",
  "MgO", "CaO", "Na2O", "K2O", "H2O",
];

// First 14 are "main", last 5 are "minor"
const MAIN_OX_COUNT = 14;

const MODE_NAMES = {
  "1": "rhyolite-MELTS 1.0.2",
  "2": "pMELTS 5.6.1",
  "3": "rhyolite-MELTS 1.1.0",
  "4": "rhyolite-MELTS 1.2.0",
};

const MODE_RANGES = {
  "1": "rhyolite-MELTS 1.0.2: 500\u20132000 \u00b0C, 0\u20134000 bar",
  "2": "pMELTS 5.6.1: 1000\u20132500 \u00b0C, 10000\u201330000 bar",
  "3": "rhyolite-MELTS 1.1.0: 500\u20132000 \u00b0C, 0\u20134000 bar",
  "4": "rhyolite-MELTS 1.2.0: 500\u20132000 \u00b0C, 0\u20133000 bar",
};

const ENGINE_INFO = {
  melts: "rhyolite-MELTS: Established model for crustal magmatic systems (Ghiorso & Sack database)",
  magemin: "MAGEMin: Gibbs energy minimizer using Holland-Powell database \u2014 broader P-T range, seismic velocities",
};

const MAGEMIN_MODELS = {
  Green2025: {
    name: "Green et al. 2025",
    desc: "Igneous database: mantle to granite, H\u2082O + CO\u2082 volatiles",
  },
  Weller2024: {
    name: "Weller et al. 2024",
    desc: "Anhydrous alkaline-silicate magmatic systems",
  },
};

// MAGEMin phase display names (short -> readable)
const MAGEMIN_PHASE_NAMES = {
  liquid1: "Melt",
  olivine1: "Olivine",
  orthopyroxene1: "Orthopyroxene",
  clinopyroxene1: "Clinopyroxene",
  garnet1: "Garnet",
  feldspar1: "Feldspar",
  spinel1: "Spinel",
  fluid1: "Fluid",
  "rhm-oxide1": "Oxide",
  plagioclase1: "Plagioclase",
};

// Phase groups for the phase selection UI
const PHASE_GROUPS = [
  {
    label: "Mafic Minerals",
    phases: [
      { id: "olivine", name: "Olivine", tip: "(Mg,Fe)\u2082SiO\u2084 \u2014 common in basalts" },
      { id: "clinopyroxene", name: "Clinopyroxene", tip: "Ca(Mg,Fe)Si\u2082O\u2086 \u2014 augite, diopside" },
      { id: "orthopyroxene", name: "Orthopyroxene", tip: "(Mg,Fe)SiO\u2083 \u2014 enstatite, hypersthene" },
      { id: "spinel", name: "Spinel", tip: "Mg-Fe-Cr-Al oxide \u2014 chromite, magnetite" },
      { id: "garnet", name: "Garnet", tip: "High-P phase \u2014 pyrope, almandine" },
    ],
  },
  {
    label: "Felsic Minerals",
    phases: [
      { id: "plagioclase", name: "Plagioclase", tip: "Ca-Na feldspar \u2014 anorthite to albite" },
      { id: "alkali-feldspar", name: "Alkali Feldspar", tip: "K-Na feldspar \u2014 sanidine, orthoclase" },
      { id: "quartz", name: "Quartz", tip: "SiO\u2082 \u2014 appears in silicic melts" },
      { id: "nepheline", name: "Nepheline", tip: "NaAlSiO\u2084 \u2014 feldspathoid, silica-undersaturated" },
      { id: "leucite", name: "Leucite", tip: "KAlSi\u2082O\u2086 \u2014 K-rich feldspathoid" },
    ],
  },
  {
    label: "Hydrous Phases",
    phases: [
      { id: "hornblende", name: "Hornblende", tip: "Ca-amphibole \u2014 common in intermediate magmas" },
      { id: "biotite", name: "Biotite", tip: "K(Mg,Fe)\u2083AlSi\u2083O\u2081\u2080(OH)\u2082 \u2014 mica" },
      { id: "muscovite", name: "Muscovite", tip: "KAl\u2082AlSi\u2083O\u2081\u2080(OH)\u2082 \u2014 rare in igneous" },
      { id: "cummingtonite", name: "Cummingtonite", tip: "(Mg,Fe)\u2087Si\u2088O\u2082\u2082(OH)\u2082" },
      { id: "clinoamphibole", name: "Clinoamphibole", tip: "Monoclinic amphibole group" },
      { id: "orthoamphibole", name: "Orthoamphibole", tip: "Orthorhombic amphibole group" },
      { id: "fluid", name: "Fluid", tip: "H\u2082O-CO\u2082 fluid phase" },
    ],
  },
  {
    label: "Accessory Phases",
    phases: [
      { id: "apatite", name: "Apatite", tip: "Ca\u2085(PO\u2084)\u2083(OH,F,Cl) \u2014 P host" },
      { id: "sphene", name: "Sphene", tip: "CaTiSiO\u2085 \u2014 titanite" },
      { id: "rutile", name: "Rutile", tip: "TiO\u2082 \u2014 often suppressed" },
      { id: "perovskite", name: "Perovskite", tip: "CaTiO\u2083" },
      { id: "whitlockite", name: "Whitlockite", tip: "Ca\u2083(PO\u2084)\u2082 \u2014 phosphate" },
      { id: "corundum", name: "Corundum", tip: "Al\u2082O\u2083 \u2014 very rare in natural magmas" },
      { id: "sillimanite", name: "Sillimanite", tip: "Al\u2082SiO\u2085 \u2014 metamorphic phase" },
    ],
  },
  {
    label: "SiO\u2082 Polymorphs",
    phases: [
      { id: "tridymite", name: "Tridymite", tip: "High-T SiO\u2082 \u2014 typically suppressed" },
      { id: "cristobalite", name: "Cristobalite", tip: "SiO\u2082 polymorph \u2014 typically suppressed" },
    ],
  },
  {
    label: "Other",
    phases: [
      { id: "melilite", name: "Melilite", tip: "Ca\u2082(Mg,Fe,Al)(Si,Al)\u2082O\u2087" },
      { id: "aenigmatite", name: "Aenigmatite", tip: "Na\u2082Fe\u2085TiSi\u2086O\u2082\u2080 \u2014 peralkaline" },
      { id: "rhm-oxide", name: "Rhm Oxide", tip: "Rhombohedral oxide \u2014 ilmenite, hematite" },
      { id: "ortho-oxide", name: "Ortho Oxide", tip: "Orthorhombic oxide \u2014 pseudobrookite" },
      { id: "alloy-solid", name: "Alloy (solid)", tip: "Metallic alloy, solid" },
      { id: "alloy-liquid", name: "Alloy (liquid)", tip: "Metallic alloy, liquid" },
    ],
  },
];

// Phase preset templates
const PHASE_PRESETS = {
  default: {
    label: "Standard",
    description: "Suppress tridymite and cristobalite (kinetically unlikely SiO\u2082 polymorphs)",
    suppress: ["tridymite", "cristobalite"],
  },
  shallow: {
    label: "Shallow Crustal",
    description: "Standard + suppress garnet (unstable at < 30 km depth)",
    suppress: ["tridymite", "cristobalite", "garnet"],
  },
  deep: {
    label: "Deep/Mantle",
    description: "All phases enabled for high-pressure modeling",
    suppress: [],
  },
  all: {
    label: "All Phases",
    description: "No phases suppressed \u2014 all are considered by the solver",
    suppress: [],
  },
};

// Path mode descriptions
const PATH_MODE_DESC = {
  isobaric: "Cool at constant pressure. Most common mode for magma chamber crystallization.",
  isothermal: "Decompress at constant temperature. Models volatile exsolution and degassing during ascent.",
  polybaric: "Follow a linear P-T path. Models simultaneous cooling and decompression.",
  isentropic: "Adiabatic (constant entropy) decompression. Models mantle upwelling and decompression melting.",
};

// Which plots each tab needs: { tabName: [{divId, plotType, highlightMode}] }
const TAB_PLOTS = {
  classification: [
    { divId: "plot-tas", plotType: "tas", highlightMode: "marker" },
    { divId: "plot-afm", plotType: "afm", highlightMode: "marker" },
  ],
  harker: [
    { divId: "plot-harker-mgo", plotType: "harker_mgo", highlightMode: "marker" },
    { divId: "plot-harker-sio2", plotType: "harker_sio2", highlightMode: "marker" },
    { divId: "plot-mg-vs-sio2", plotType: "mg_vs_sio2", highlightMode: "marker" },
  ],
  "pt-path": [
    { divId: "plot-pt-path", plotType: "pt_path", highlightMode: "marker" },
  ],
  evolution: [
    { divId: "plot-evolution", plotType: "evolution", highlightMode: "vline" },
    { divId: "plot-liquid-vs-temp", plotType: "liquid_vs_temp", highlightMode: "vline" },
  ],
  phases: [
    { divId: "plot-phase-masses", plotType: "phase_masses", highlightMode: "vline" },
    { divId: "plot-olivine", plotType: "olivine", highlightMode: "vline" },
    { divId: "plot-cpx", plotType: "cpx", highlightMode: "vline" },
    { divId: "plot-plagioclase", plotType: "plagioclase", highlightMode: "vline" },
    { divId: "plot-spinel", plotType: "spinel", highlightMode: "vline" },
  ],
  system: [
    { divId: "plot-system-thermo", plotType: "system_thermo", highlightMode: "vline" },
    { divId: "plot-density", plotType: "density", highlightMode: "vline" },
  ],
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentSimId = null;
let currentBatchId = null;
let currentEngine = "melts"; // "melts" or "magemin"
let batchMode = false;
let presets = {};
let plotCache = {};       // { "simId:plotType": true } — tracks fetched plots
let simResults = [];      // accumulated results for data table
let minorOxVisible = false;
let simRunning = false;
let currentScrubberIndex = -1;
let animationInterval = null;
let highlightTraces = new Map(); // divId -> trace index
let currentSpeed = 100;
let phasePanelVisible = false;
let activePhasePreset = "default";

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const $form = document.getElementById("sim-form");
const $presetSelect = document.getElementById("preset-select");
const $meltsMode = document.getElementById("melts-mode");
const $modeBadge = document.getElementById("mode-badge");
const $modeInfo = document.getElementById("mode-info");
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
const $pathMode = document.getElementById("path-mode");
const $pathModeDesc = document.getElementById("path-mode-desc");
const $labelTStart = document.getElementById("label-T-start");
const $labelTEnd = document.getElementById("label-T-end");
const $labelDT = document.getElementById("label-dT");
const $labelPStart = document.getElementById("label-P-start");
const $labelPEnd = document.getElementById("label-P-end");
const $labelDP = document.getElementById("label-dP");
const $scrubberSection = document.getElementById("scrubber-section");
const $tempScrubber = document.getElementById("temp-scrubber");
const $scrubberInfo = document.getElementById("scrubber-info");
const $btnPlay = document.getElementById("btn-play");
const $btnPause = document.getElementById("btn-pause");
const $speedSelect = document.getElementById("speed-select");
const $toastContainer = document.getElementById("toast-container");
const $engineSelector = document.getElementById("engine-selector");
const $engineInfo = document.getElementById("engine-info");
const $meltsModeFieldset = document.getElementById("melts-mode-fieldset");
const $mageminModelFieldset = document.getElementById("magemin-model-fieldset");
const $mageminPathFieldset = document.getElementById("magemin-path-fieldset");
const $mageminFe3fetFieldset = document.getElementById("magemin-fe3fet-fieldset");
const $mageminModel = document.getElementById("magemin-model");
const $mageminModelInfo = document.getElementById("magemin-model-info");
const $mageminPathMode = document.getElementById("magemin-path-mode");
const $phaseGroups = document.getElementById("phase-groups");
const $phaseInfo = document.getElementById("phase-info");
const $togglePhases = document.getElementById("toggle-phases");
const $phasePresets = document.getElementById("phase-presets");
const $batchToggle = document.getElementById("batch-toggle");
const $batchConfig = document.getElementById("batch-config");
const $sweepParam = document.getElementById("sweep-param");
const $sweepFrom = document.getElementById("sweep-from");
const $sweepTo = document.getElementById("sweep-to");
const $sweepSteps = document.getElementById("sweep-steps");
const $sweepPreview = document.getElementById("sweep-preview");

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  buildCompTable();
  buildPhaseSelection();
  loadPresets();
  bindEvents();
  onPathModeChange();  // set initial field visibility for default mode
});

function buildCompTable() {
  // Save current values before rebuilding
  const savedValues = {};
  document.querySelectorAll(".ox-input").forEach((input) => {
    const ox = input.dataset.oxide;
    const val = parseFloat(input.value);
    if (val > 0) savedValues[ox] = val;
  });

  $compBody.innerHTML = "";
  const oxList = currentEngine === "magemin" ? OX_MAGEMIN : OX;

  oxList.forEach((ox, i) => {
    const tr = document.createElement("tr");
    const isMinor = currentEngine === "melts" && i >= MAIN_OX_COUNT;
    if (isMinor) tr.classList.add("minor-ox");

    // Restore value: for MAGEMin FeOt, compute from saved FeO + Fe2O3
    let defaultVal = 0;
    if (ox === "FeOt" && currentEngine === "magemin") {
      const feo = savedValues["FeO"] || 0;
      const fe2o3 = savedValues["Fe2O3"] || 0;
      defaultVal = feo + fe2o3 * 0.8998;
      if (defaultVal > 0) defaultVal = parseFloat(defaultVal.toFixed(3));
    } else if ((ox === "FeO" || ox === "Fe2O3") && currentEngine === "melts" && savedValues["FeOt"]) {
      // Switching back to MELTS from MAGEMin: put all FeOt into FeO
      if (ox === "FeO") defaultVal = savedValues["FeOt"] || 0;
    } else {
      defaultVal = savedValues[ox] || 0;
    }

    tr.innerHTML = `
      <td class="ox-label">${formatOxide(ox)}</td>
      <td><input type="number" step="0.001" min="0" max="100"
                 id="ox-${ox}" data-oxide="${ox}" value="${defaultVal}" class="ox-input"></td>
    `;
    $compBody.appendChild(tr);
  });

  // Show/hide minor oxide toggle based on engine
  $toggleMinor.style.display = currentEngine === "melts" ? "" : "none";
  if (currentEngine === "melts") updateMinorVisibility();
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
  $pathMode.addEventListener("change", onPathModeChange);
  $toggleMinor.addEventListener("click", onToggleMinor);
  $form.addEventListener("submit", onFormSubmit);
  $btnCsv.addEventListener("click", onCsvDownload);
  $sidebarToggle.addEventListener("click", () => {
    $sidebar.classList.toggle("open");
  });

  // Engine selector
  $engineSelector.addEventListener("click", (e) => {
    const btn = e.target.closest(".engine-btn");
    if (!btn) return;
    switchEngine(btn.dataset.engine);
  });

  // MAGEMin model selector
  $mageminModel.addEventListener("change", onMageminModelChange);

  // Phase selection
  $togglePhases.addEventListener("click", onTogglePhases);
  $phasePresets.addEventListener("click", (e) => {
    const btn = e.target.closest(".phase-preset-btn");
    if (!btn) return;
    onPhasePresetClick(btn.dataset.preset);
  });

  // Tab switching
  $tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    switchTab(btn.dataset.tab);
  });

  // Scrubber events
  $tempScrubber.addEventListener("input", onScrubberInput);
  $btnPlay.addEventListener("click", onPlayClick);
  $btnPause.addEventListener("click", onPauseClick);
  $speedSelect.addEventListener("change", onSpeedChange);

  // Update dp/dt when T or P fields change
  ["T-start", "T-end", "P-start", "P-end", "dP"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateDpDt);
  });

  // Batch mode toggle
  $batchToggle.addEventListener("change", (e) => {
    batchMode = e.target.checked;
    $batchConfig.classList.toggle("hidden", !batchMode);
    $btnRun.querySelector(".btn-run-label").textContent =
      batchMode ? "Run Batch" : "Run Simulation";
  });

  // Update sweep preview when inputs change
  [$sweepFrom, $sweepTo, $sweepSteps].forEach((el) => {
    el.addEventListener("input", updateSweepPreview);
  });
  $sweepParam.addEventListener("change", updateSweepPreview);
}

// ---------------------------------------------------------------------------
// Preset / mode handlers
// ---------------------------------------------------------------------------
function onPresetChange() {
  const key = $presetSelect.value;
  if (!key || !presets[key]) return;
  const preset = presets[key];

  // Fill composition (using correct oxide set for current engine)
  const oxList = currentEngine === "magemin" ? OX_MAGEMIN : OX;
  oxList.forEach((ox) => {
    const input = document.getElementById(`ox-${ox}`);
    if (!input) return;
    if (ox === "FeOt" && currentEngine === "magemin") {
      // Compute FeOt from FeO + Fe2O3 in preset
      const feo = preset.composition["FeO"] || 0;
      const fe2o3 = preset.composition["Fe2O3"] || 0;
      input.value = parseFloat((feo + fe2o3 * 0.8998).toFixed(3));
    } else {
      input.value = preset.composition[ox] || 0;
    }
  });

  // Fill defaults
  if (preset.defaults) {
    const d = preset.defaults;
    if (d.T_start != null) document.getElementById("T-start").value = d.T_start;
    if (d.T_end != null) document.getElementById("T-end").value = d.T_end;
    if (d.P_start != null) document.getElementById("P-start").value = d.P_start;
    if (d.P_end != null) document.getElementById("P-end").value = d.P_end;

    // Auto-detect appropriate path mode from preset defaults
    const pathMode = $pathMode.value;
    if (pathMode === "isobaric" && d.P_start != null && d.P_end != null && d.P_start !== d.P_end) {
      // Preset has a P range but we're in isobaric mode — switch to polybaric
      $pathMode.value = "polybaric";
      onPathModeChange();
    } else if (pathMode === "polybaric" && d.P_start != null && d.P_end != null && d.P_start === d.P_end) {
      // Preset has constant P but we're in polybaric mode — switch to isobaric
      $pathMode.value = "isobaric";
      onPathModeChange();
    }
  }
  updateDpDt();
}

function onModeChange() {
  const mode = $meltsMode.value;
  $modeBadge.textContent = MODE_NAMES[mode] || "";
  document.getElementById("mode-info").textContent = MODE_RANGES[mode] || "";
}

function onPathModeChange() {
  const mode = $pathMode.value;

  // Update description
  $pathModeDesc.textContent = PATH_MODE_DESC[mode] || "";

  // Field visibility configuration per mode
  // Each mode shows/hides: T_end, dT, P_end, dP
  // and adjusts labels accordingly

  switch (mode) {
    case "isobaric":
      // T_start, T_end, dT visible; P_start visible, P_end hidden, dP hidden
      $labelTEnd.classList.remove("hidden");
      $labelDT.classList.remove("hidden");
      $labelPEnd.classList.add("hidden");
      $labelDP.classList.add("hidden");
      $dpDtDisplay.textContent = "Constant pressure";
      break;

    case "isothermal":
      // T_start visible (constant), T_end hidden, dT hidden
      // P_start, P_end, dP visible
      $labelTEnd.classList.add("hidden");
      $labelDT.classList.add("hidden");
      $labelPEnd.classList.remove("hidden");
      $labelDP.classList.remove("hidden");
      $dpDtDisplay.textContent = "Constant temperature";
      break;

    case "polybaric":
      // All T and P fields visible, dP hidden (interpolated from T range)
      $labelTEnd.classList.remove("hidden");
      $labelDT.classList.remove("hidden");
      $labelPEnd.classList.remove("hidden");
      $labelDP.classList.add("hidden");
      updateDpDt();
      break;

    case "isentropic":
      // T_start visible (initial guess), T_end hidden, dT hidden
      // P_start, P_end, dP visible
      $labelTEnd.classList.add("hidden");
      $labelDT.classList.add("hidden");
      $labelPEnd.classList.remove("hidden");
      $labelDP.classList.remove("hidden");
      $dpDtDisplay.textContent = "Engine solves for temperature";
      break;
  }
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
  const mode = $pathMode.value;

  if (mode === "isobaric") {
    $dpDtDisplay.textContent = "Constant pressure";
    return;
  }
  if (mode === "isothermal") {
    $dpDtDisplay.textContent = "Constant temperature";
    return;
  }
  if (mode === "isentropic") {
    $dpDtDisplay.textContent = "Engine solves for temperature";
    return;
  }

  // polybaric: show dP/dT ratio
  const tStart = parseFloat(document.getElementById("T-start").value) || 0;
  const tEnd = parseFloat(document.getElementById("T-end").value) || 0;
  const pStart = parseFloat(document.getElementById("P-start").value) || 0;
  const pEnd = parseFloat(document.getElementById("P-end").value) || 0;
  const dT = tEnd - tStart;
  if (Math.abs(dT) < 0.01) {
    $dpDtDisplay.textContent = "dP/dT = -- (no temperature range)";
    return;
  }
  const dpdt = (pEnd - pStart) / dT;
  $dpDtDisplay.textContent = `dP/dT = ${dpdt.toFixed(1)} bar/\u00b0C`;
}

// ---------------------------------------------------------------------------
// Engine switching
// ---------------------------------------------------------------------------
function switchEngine(engine) {
  if (engine === currentEngine) return;
  currentEngine = engine;

  // Update button states
  $engineSelector.querySelectorAll(".engine-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.engine === engine);
  });

  // Update info text
  $engineInfo.textContent = ENGINE_INFO[engine] || "";

  // Toggle fieldset visibility
  const isMelts = engine === "melts";
  $meltsModeFieldset.classList.toggle("hidden", !isMelts);
  $mageminModelFieldset.classList.toggle("hidden", isMelts);
  $mageminPathFieldset.classList.toggle("hidden", isMelts);
  $mageminFe3fetFieldset.classList.toggle("hidden", isMelts);

  // Update mode badge
  if (isMelts) {
    $modeBadge.textContent = MODE_NAMES[$meltsMode.value] || "";
  } else {
    const model = $mageminModel.value;
    $modeBadge.textContent = "MAGEMin \u2014 " + (MAGEMIN_MODELS[model]?.name || model);
  }

  // Rebuild composition table for the selected engine
  buildCompTable();
}

function onMageminModelChange() {
  const model = $mageminModel.value;
  $modeBadge.textContent = "MAGEMin \u2014 " + (MAGEMIN_MODELS[model]?.name || model);
  $mageminModelInfo.textContent = MAGEMIN_MODELS[model]?.desc || "";
}

function updateSweepPreview() {
  const from = parseFloat($sweepFrom.value);
  const to = parseFloat($sweepTo.value);
  const steps = parseInt($sweepSteps.value);
  if (isNaN(from) || isNaN(to) || isNaN(steps) || steps < 2) {
    $sweepPreview.textContent = "Values: (invalid)";
    return;
  }
  const values = [];
  for (let i = 0; i < steps; i++) {
    values.push(from + (to - from) * i / (steps - 1));
  }
  const paramName = $sweepParam.options[$sweepParam.selectedIndex].textContent;
  $sweepPreview.textContent =
    `Values: ${values.map((v) => v.toFixed(1)).join(", ")} (${paramName})`;
}

// ---------------------------------------------------------------------------
// Form submission
// ---------------------------------------------------------------------------
function onFormSubmit(e) {
  e.preventDefault();
  if (simRunning) return;

  if (currentEngine === "magemin") {
    submitMageminForm();
    return;
  }

  // Build config object
  const composition = {};
  OX.forEach((ox) => {
    const el = document.getElementById(`ox-${ox}`);
    if (!el) return;
    const val = parseFloat(el.value);
    if (val > 0) composition[ox] = val;
  });

  // Validate: need at least SiO2
  if (!composition.SiO2 || composition.SiO2 < 1) {
    showError("Composition must include at least SiO2 > 0 wt%.");
    return;
  }

  const pathMode = $pathMode.value;

  const config = {
    melts_mode: parseInt($meltsMode.value),
    composition,
    path_mode: pathMode,
    T_start: parseFloat(document.getElementById("T-start").value),
    T_end: parseFloat(document.getElementById("T-end").value),
    dT: parseFloat(document.getElementById("dT").value),
    P_start: parseFloat(document.getElementById("P-start").value),
    P_end: parseFloat(document.getElementById("P-end").value),
    dP: parseFloat(document.getElementById("dP").value),
    crystallization_mode: document.getElementById("cryst-mode").value,
    suppress_phases: getSuppressedPhases(),
  };

  const fo2 = document.getElementById("fo2-buffer").value;
  if (fo2) {
    config.fo2_buffer = fo2;
    config.fo2_offset = parseFloat(document.getElementById("fo2-offset").value) || 0;
  }

  // Mode-specific adjustments and validation
  if (pathMode === "isobaric") {
    // Constant P: force P_end = P_start
    config.P_end = config.P_start;
    if (config.dT >= 0 && config.T_start > config.T_end) {
      showError("dT must be negative when T_start > T_end (cooling).");
      return;
    }
  } else if (pathMode === "isothermal") {
    // Constant T: force T_end = T_start
    config.T_end = config.T_start;
    if (config.dP === 0) {
      showError("dP must be non-zero for isothermal mode.");
      return;
    }
    if (config.dP > 0 && config.P_start > config.P_end) {
      showError("dP must be negative when P_start > P_end (decompression).");
      return;
    }
    if (config.dP < 0 && config.P_start < config.P_end) {
      showError("dP must be positive when P_start < P_end (compression).");
      return;
    }
  } else if (pathMode === "polybaric") {
    if (config.dT >= 0 && config.T_start > config.T_end) {
      showError("dT must be negative when T_start > T_end (cooling).");
      return;
    }
  } else if (pathMode === "isentropic") {
    // T_end is not used; set to a safe low value so the backend doesn't choke
    config.T_end = 600;
    if (config.dP === 0) {
      showError("dP must be non-zero for isentropic mode.");
      return;
    }
    if (config.dP > 0 && config.P_start > config.P_end) {
      showError("dP must be negative when P_start > P_end (decompression).");
      return;
    }
    if (config.dP < 0 && config.P_start < config.P_end) {
      showError("dP must be positive when P_start < P_end (compression).");
      return;
    }
  }

  if (batchMode) {
    const from = parseFloat($sweepFrom.value);
    const to = parseFloat($sweepTo.value);
    const steps = parseInt($sweepSteps.value);
    if (isNaN(from) || isNaN(to) || isNaN(steps) || steps < 2) {
      showError("Invalid sweep parameters. Need From, To, and Steps >= 2.");
      return;
    }
    const values = [];
    for (let i = 0; i < steps; i++) {
      values.push(from + (to - from) * i / (steps - 1));
    }
    const batchConfig = {
      base_config: config,
      sweep: {
        param: $sweepParam.value,
        values: values,
      },
    };
    startBatch(batchConfig);
  } else {
    startSimulation(config);
  }
}

function submitMageminForm() {
  // Build composition from MAGEMin oxide set
  const composition = {};
  OX_MAGEMIN.forEach((ox) => {
    const el = document.getElementById(`ox-${ox}`);
    if (!el) return;
    const val = parseFloat(el.value);
    if (val > 0) composition[ox] = val;
  });

  // Validate
  if (!composition.SiO2 || composition.SiO2 < 1) {
    showError("Composition must include at least SiO2 > 0 wt%.");
    return;
  }

  // Convert FeOt to FeO for the backend (the engine will reconvert)
  if (composition.FeOt) {
    composition.FeO = composition.FeOt;
    delete composition.FeOt;
  }

  const config = {
    model: $mageminModel.value,
    path_mode: $mageminPathMode.value,
    composition,
    fe3fet: parseFloat(document.getElementById("fe3fet").value) || 0.1,
    T_start: parseFloat(document.getElementById("T-start").value),
    T_end: parseFloat(document.getElementById("T-end").value),
    dT: Math.abs(parseFloat(document.getElementById("dT").value)) || 2,
    P_start: parseFloat(document.getElementById("P-start").value),
    P_end: parseFloat(document.getElementById("P-end").value),
    dP: 100,
    crystallization_mode: document.getElementById("cryst-mode").value,
    find_liquidus: true,
    suppress_phases: [],
  };

  const fo2 = document.getElementById("fo2-buffer").value;
  if (fo2) {
    config.fO2_buffer = fo2;
    config.fO2_offset = parseFloat(document.getElementById("fo2-offset").value) || 0;
  }

  startSimulation(config, "/api/simulate/magemin");
}

// ---------------------------------------------------------------------------
// Simulation lifecycle
// ---------------------------------------------------------------------------
async function startSimulation(config, url = "/api/simulate") {
  stopAnimation(); // prevent stale interval from previous sim
  clearAllHighlights();
  simRunning = true;
  simResults = [];
  plotCache = {};
  currentSimId = null;
  currentBatchId = null;
  $btnRun.disabled = true;
  $btnRun.querySelector(".btn-run-label").textContent = "Running...";
  $emptyState.classList.add("hidden");
  $errorDisplay.classList.add("hidden");
  $progressSection.classList.remove("hidden");
  $progressBar.style.width = "0%";
  $progressInfo.textContent = currentEngine === "magemin"
    ? "Starting MAGEMin simulation (first run may take 1-2 minutes)..."
    : "Starting simulation...";

  // Clear previous plots
  clearAllPlots();

  try {
    const resp = await fetch(url, {
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
  let nSteps;
  if (config.path_mode === "isothermal" || config.path_mode === "isentropic") {
    nSteps = Math.abs((config.P_start - config.P_end) / Math.abs(config.dP));
  } else {
    nSteps = Math.abs((config.T_start - config.T_end) / Math.abs(config.dT));
  }
  const engineLabel = currentEngine === "magemin" ? "MAGEMin" : "MELTS";
  $progressInfo.textContent = `Initializing ${engineLabel} engine...`;
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
  // Show scrubber and reset
  stopAnimation(); // clear any stale animation from previous sim
  $scrubberSection.classList.remove("hidden");
  $tempScrubber.max = simResults.length - 1;
  $tempScrubber.value = 0;
  currentScrubberIndex = 0;
  clearAllHighlights();
  $btnPause.classList.add("hidden");
  $btnPlay.classList.remove("hidden");

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
  $btnRun.querySelector(".btn-run-label").textContent =
    batchMode ? "Run Batch" : "Run Simulation";
}

// ---------------------------------------------------------------------------
// Batch simulation lifecycle
// ---------------------------------------------------------------------------
async function startBatch(batchConfig) {
  stopAnimation();
  clearAllHighlights();
  simRunning = true;
  simResults = [];
  plotCache = {};
  currentSimId = null;
  currentBatchId = null;
  $btnRun.disabled = true;
  $btnRun.querySelector(".btn-run-label").textContent = "Running Batch...";
  $emptyState.classList.add("hidden");
  $errorDisplay.classList.add("hidden");
  $progressSection.classList.remove("hidden");
  $progressBar.style.width = "0%";
  $progressInfo.textContent = "Starting batch...";
  $scrubberSection.classList.add("hidden");

  clearAllPlots();

  try {
    const resp = await fetch("/api/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batchConfig),
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    currentBatchId = data.batch_id;

    pollBatch(data.batch_id, data.total_runs);
  } catch (err) {
    showError(`Failed to start batch: ${err.message}`);
    resetRunButton();
  }
}

function pollBatch(batchId, totalRuns) {
  const pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/batch/${batchId}/status`);
      if (!resp.ok) { clearInterval(pollInterval); return; }
      const data = await resp.json();

      // Update progress
      const completedRuns = data.runs.filter((r) => r.status === "done").length;
      const pct = (completedRuns / totalRuns) * 100;
      $progressBar.style.width = pct.toFixed(1) + "%";

      const currentRun = data.runs.find((r) => r.status === "running");
      if (currentRun) {
        $progressInfo.textContent =
          `Run ${completedRuns + 1}/${totalRuns}: ${currentRun.label} (${currentRun.n_results} steps)`;
      } else {
        $progressInfo.textContent = `Completed ${completedRuns}/${totalRuns} runs`;
      }

      if (data.status === "done") {
        clearInterval(pollInterval);
        onBatchComplete(batchId, data);
      } else if (data.status === "error") {
        clearInterval(pollInterval);
        showError("Batch failed.");
        resetRunButton();
      }
    } catch (e) {
      console.warn("Batch poll error:", e);
    }
  }, 1000);
}

function onBatchComplete(batchId, batchData) {
  simRunning = false;
  resetRunButton();
  $progressBar.style.width = "100%";
  $progressInfo.textContent =
    `Batch complete. ${batchData.total_runs} runs finished.`;

  // Hide scrubber for batch mode (not applicable to multi-run comparison)
  $scrubberSection.classList.add("hidden");

  // Store batch info for plot fetching
  currentBatchId = batchId;
  currentSimId = null;

  // Fetch comparison plots for active tab
  const activeTab = document.querySelector(".tab.active");
  if (activeTab) {
    fetchComparisonPlotsForTab(activeTab.dataset.tab, batchId);
  }
}

// Comparison plot types available per tab
const COMPARE_PLOTS = {
  classification: [
    { divId: "plot-tas", plotType: "tas" },
  ],
  harker: [
    { divId: "plot-harker-mgo", plotType: "harker_mgo" },
  ],
  "pt-path": [
    { divId: "plot-pt-path", plotType: "pt_path" },
  ],
  evolution: [
    { divId: "plot-evolution", plotType: "evolution" },
  ],
};

async function fetchComparisonPlotsForTab(tabName, batchId) {
  const plots = COMPARE_PLOTS[tabName];
  if (!plots) return;

  for (const { divId, plotType } of plots) {
    const cacheKey = `batch:${batchId}:${plotType}`;
    if (plotCache[cacheKey]) continue;

    const container = document.getElementById(divId);
    if (!container) continue;
    container.innerHTML = '<div class="plot-loading">Loading comparison...</div>';

    try {
      const resp = await fetch(`/api/batch/${batchId}/compare/${plotType}`);
      if (!resp.ok) {
        const errText = await resp.text();
        container.innerHTML = `<div class="plot-error">Comparison not available: ${errText}</div>`;
        continue;
      }
      const figJson = await resp.json();
      container.innerHTML = "";
      const layout = figJson.layout || {};
      layout.autosize = true;

      Plotly.newPlot(container, figJson.data, layout, {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
      });

      plotCache[cacheKey] = true;
    } catch (err) {
      container.innerHTML = `<div class="plot-error">Failed: ${err.message}</div>`;
    }
  }
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

  // Fetch plots for this tab if we have a sim or batch
  if (currentBatchId) {
    fetchComparisonPlotsForTab(tabName, currentBatchId);
  } else if (currentSimId && simResults.length > 0) {
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

  // Re-apply scrubber highlight after plots are rendered
  if (currentScrubberIndex >= 0 && simResults.length > 0) {
    updateScrubberHighlight(currentScrubberIndex);
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

// ---------------------------------------------------------------------------
// Scrubber
// ---------------------------------------------------------------------------
let scrubberRafId = null;
function onScrubberInput() {
  if (scrubberRafId) return;
  scrubberRafId = requestAnimationFrame(() => {
    scrubberRafId = null;
    if (simResults.length === 0) return;
    const index = parseInt($tempScrubber.value);
    if (index < 0 || index >= simResults.length) return;
    currentScrubberIndex = index;
    updateScrubberHighlight(index);
  });
}

function updateScrubberHighlight(index) {
  if (simResults.length === 0) return;
  const step = simResults[index];
  if (!step) return;

  // Update info card
  const phases = step.phases ? step.phases.split("+").filter(Boolean).map(p => {
    if (currentEngine === "magemin" && MAGEMIN_PHASE_NAMES[p]) return MAGEMIN_PHASE_NAMES[p];
    return p.replace(/\d+$/, "");
  }).join(", ") : "none";
  const liqPct = step.mass_liquid_g && simResults[0].mass_liquid_g
    ? ((step.mass_liquid_g / simResults[0].mass_liquid_g) * 100).toFixed(1)
    : "?";
  $scrubberInfo.textContent = `T = ${step.T_C.toFixed(0)}\u00b0C | P = ${step.P_bar.toFixed(0)} bar | Liquid: ${liqPct}% | Phases: ${phases}`;

  // Highlight on each visible plot
  const activeTab = document.querySelector(".tab.active");
  if (!activeTab) return;
  const tabName = activeTab.dataset.tab;
  const plots = TAB_PLOTS[tabName];
  if (!plots) return;

  for (const { divId, plotType, highlightMode } of plots) {
    const container = document.getElementById(divId);
    if (!container || !container.data) continue; // not rendered yet

    if (highlightMode === "vline") {
      Plotly.relayout(container, {
        shapes: [{
          type: "line",
          x0: step.T_C, x1: step.T_C,
          yref: "paper", y0: 0, y1: 1,
          line: { color: "#3b82f6", width: 1.5, dash: "dash" },
        }],
      });
    } else if (highlightMode === "marker") {
      // Remove previous highlight trace
      const prevTraceIdx = highlightTraces.get(divId);
      if (prevTraceIdx !== undefined && container.data.length > prevTraceIdx) {
        try { Plotly.deleteTraces(container, prevTraceIdx); } catch(e) {}
      }
      // Find the data point at this index from the first data trace
      // For scatter plots, the data arrays correspond 1:1 to simResults indices
      const firstTrace = container.data[0];
      if (!firstTrace || !firstTrace.x || index >= firstTrace.x.length) {
        highlightTraces.delete(divId);
        continue;
      }

      // Determine x and y values for the highlight point
      // Skip boundary line traces (they have hoverinfo: "skip")
      let dataTraceIdx = -1;
      for (let t = 0; t < container.data.length; t++) {
        if (container.data[t].hoverinfo !== "skip" && container.data[t].mode && container.data[t].mode.includes("markers")) {
          dataTraceIdx = t;
          break;
        }
      }
      if (dataTraceIdx === -1) {
        highlightTraces.delete(divId);
        continue;
      }

      const dataTrace = container.data[dataTraceIdx];
      const xVal = dataTrace.x[index];
      const yVal = dataTrace.y[index];

      if (xVal === undefined || yVal === undefined) {
        highlightTraces.delete(divId);
        continue;
      }

      Plotly.addTraces(container, {
        x: [xVal],
        y: [yVal],
        mode: "markers",
        marker: {
          size: 12,
          color: "#3b82f6",
          line: { color: "white", width: 2 },
        },
        showlegend: false,
        hoverinfo: "skip",
      });
      highlightTraces.set(divId, container.data.length - 1);
    }
  }
}

function clearAllHighlights() {
  highlightTraces.clear();
  currentScrubberIndex = -1;
}

// ---------------------------------------------------------------------------
// Play / pause animation
// ---------------------------------------------------------------------------
function onPlayClick() {
  if (simResults.length === 0) return;
  $btnPlay.classList.add("hidden");
  $btnPause.classList.remove("hidden");

  // If at end, reset to beginning
  if (parseInt($tempScrubber.value) >= simResults.length - 1) {
    $tempScrubber.value = 0;
  }

  currentSpeed = parseInt($speedSelect.value);
  startAnimation();
}

function onPauseClick() {
  stopAnimation();
  $btnPause.classList.add("hidden");
  $btnPlay.classList.remove("hidden");
}

function onSpeedChange() {
  currentSpeed = parseInt($speedSelect.value);
  if (animationInterval) {
    stopAnimation();
    startAnimation();
  }
}

function startAnimation() {
  stopAnimation();
  animationInterval = setInterval(() => {
    const t0 = performance.now();
    let idx = parseInt($tempScrubber.value) + 1;
    if (idx >= simResults.length) {
      stopAnimation();
      $btnPause.classList.add("hidden");
      $btnPlay.classList.remove("hidden");
      return;
    }
    $tempScrubber.value = idx;
    currentScrubberIndex = idx;

    requestAnimationFrame(() => {
      updateScrubberHighlight(idx);
      detectAndShowToasts(idx);

      // Adaptive speed: if update took too long, throttle
      const elapsed = performance.now() - t0;
      if (elapsed > currentSpeed * 1.5 && currentSpeed < 200) {
        const speeds = [50, 100, 200];
        const currentIdx = speeds.indexOf(currentSpeed);
        if (currentIdx < speeds.length - 1) {
          currentSpeed = speeds[currentIdx + 1];
          $speedSelect.value = currentSpeed;
          // Show throttle indicator
          $scrubberInfo.textContent += " \u26a1 Slowed for performance";
          stopAnimation();
          startAnimation();
        }
      }
    });
  }, currentSpeed);
}

function stopAnimation() {
  if (animationInterval) {
    clearInterval(animationInterval);
    animationInterval = null;
  }
}

// ---------------------------------------------------------------------------
// Phase-appearance toast notifications
// ---------------------------------------------------------------------------
function detectAndShowToasts(index) {
  if (index <= 0 || index >= simResults.length) return;
  const prev = simResults[index - 1].phases ? simResults[index - 1].phases.split("+").filter(Boolean) : [];
  const curr = simResults[index].phases ? simResults[index].phases.split("+").filter(Boolean) : [];
  const prevSet = new Set(prev);
  const newPhases = curr.filter(p => !prevSet.has(p));

  for (const phase of newPhases) {
    let displayName;
    if (currentEngine === "magemin" && MAGEMIN_PHASE_NAMES[phase]) {
      displayName = MAGEMIN_PHASE_NAMES[phase];
    } else {
      const baseName = phase.replace(/\d+$/, "");
      displayName = baseName.charAt(0).toUpperCase() + baseName.slice(1);
    }
    showToast(`${displayName} crystallizes at ${simResults[index].T_C.toFixed(0)}\u00b0C`);
  }
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  $toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ---------------------------------------------------------------------------
// Phase selection
// ---------------------------------------------------------------------------
function buildPhaseSelection() {
  $phaseGroups.innerHTML = "";
  for (const group of PHASE_GROUPS) {
    const groupDiv = document.createElement("div");
    groupDiv.className = "phase-group";

    const groupLabel = document.createElement("div");
    groupLabel.className = "phase-group-label";
    groupLabel.textContent = group.label;
    groupDiv.appendChild(groupLabel);

    const grid = document.createElement("div");
    grid.className = "phase-checkbox-grid";

    for (const phase of group.phases) {
      const label = document.createElement("label");
      label.className = "phase-checkbox-label";
      label.title = phase.tip;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "phase-checkbox";
      checkbox.id = `phase-${phase.id}`;
      checkbox.dataset.phaseId = phase.id;
      checkbox.checked = true; // default: all included
      checkbox.addEventListener("change", onPhaseCheckboxChange);

      const span = document.createElement("span");
      span.className = "phase-checkbox-name";
      span.textContent = phase.name;

      const tipSpan = document.createElement("span");
      tipSpan.className = "phase-checkbox-tip";
      tipSpan.textContent = phase.tip;

      label.appendChild(checkbox);
      label.appendChild(span);
      label.appendChild(tipSpan);
      grid.appendChild(label);
    }

    groupDiv.appendChild(grid);
    $phaseGroups.appendChild(groupDiv);
  }

  // Apply default preset (suppress tridymite + cristobalite)
  applyPhasePreset("default");
}

function applyPhasePreset(presetKey) {
  const preset = PHASE_PRESETS[presetKey];
  if (!preset) return;

  activePhasePreset = presetKey;
  const suppressSet = new Set(preset.suppress);

  // Update all checkboxes
  const checkboxes = $phaseGroups.querySelectorAll(".phase-checkbox");
  for (const cb of checkboxes) {
    cb.checked = !suppressSet.has(cb.dataset.phaseId);
  }

  // Update preset button highlights
  const buttons = $phasePresets.querySelectorAll(".phase-preset-btn");
  for (const btn of buttons) {
    btn.classList.toggle("active", btn.dataset.preset === presetKey);
  }

  // Update info text
  updatePhaseInfo();
}

function onPhasePresetClick(presetKey) {
  applyPhasePreset(presetKey);
}

function onPhaseCheckboxChange() {
  // User manually changed a checkbox: clear preset highlight
  activePhasePreset = null;
  const buttons = $phasePresets.querySelectorAll(".phase-preset-btn");
  for (const btn of buttons) {
    btn.classList.remove("active");
  }
  updatePhaseInfo();
}

function updatePhaseInfo() {
  const suppressed = getSuppressedPhases();
  if (suppressed.length === 0) {
    $phaseInfo.textContent = "All phases enabled";
  } else {
    // Capitalize first letter for display
    const names = suppressed.map((id) => {
      // Find the display name from PHASE_GROUPS
      for (const group of PHASE_GROUPS) {
        for (const phase of group.phases) {
          if (phase.id === id) return phase.name.toLowerCase();
        }
      }
      return id;
    });
    $phaseInfo.textContent = `Suppressing: ${names.join(", ")}`;
  }
}

function getSuppressedPhases() {
  const suppressed = [];
  const checkboxes = $phaseGroups.querySelectorAll(".phase-checkbox");
  for (const cb of checkboxes) {
    if (!cb.checked) {
      suppressed.push(cb.dataset.phaseId);
    }
  }
  return suppressed;
}

function onTogglePhases() {
  phasePanelVisible = !phasePanelVisible;
  $phaseGroups.classList.toggle("hidden", !phasePanelVisible);
  $togglePhases.textContent = phasePanelVisible
    ? "Hide phase details"
    : "Customize phases...";
}
