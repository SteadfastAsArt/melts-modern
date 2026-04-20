# Multi-Sample Batch Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Excel/CSV import for multi-sample batch simulation alongside the existing parameter sweep mode.

**Architecture:** Frontend uses SheetJS (CDN) to parse uploaded files client-side. Parsed samples are displayed in a preview table with checkboxes. On submit, the frontend constructs one SimConfig per selected sample and sends them via the existing `POST /api/batch` endpoint, which is extended to accept a `samples` array as an alternative to `sweep`. Backend execution and comparison plots are entirely reused.

**Tech Stack:** SheetJS (xlsx.mini.js CDN), vanilla JS, FastAPI/Pydantic, existing Plotly comparison infrastructure.

---

### Task 1: Extend Backend Schema — SampleEntry + BatchConfig

**Files:**
- Modify: `meltsapp/schemas.py:107-128`

This task adds the `SampleEntry` model and makes `BatchConfig` accept either `sweep` or `samples`.

- [ ] **Step 1: Add SampleEntry and update BatchConfig in schemas.py**

Open `meltsapp/schemas.py`. After `SweepParam` (line 118) and before `BatchConfig` (line 120), add the `SampleEntry` class. Then modify `BatchConfig` to make `sweep` optional and add `samples`:

```python
class SampleEntry(BaseModel):
    """A single sample with name and composition for multi-sample batch."""

    name: str
    """Sample name (e.g. 'DH-01')."""

    composition: dict[str, float]
    """Oxide name -> wt% (e.g. {'SiO2': 48.68, 'MgO': 9.10, ...})."""


class BatchConfig(BaseModel):
    """Configuration for a batch of simulations.

    Exactly one of `sweep` or `samples` must be provided.
    - sweep: parameter sweep across a single base composition
    - samples: multiple samples each with their own composition
    """

    base_config: SimConfig
    """The base simulation configuration (all shared parameters)."""

    sweep: SweepParam | None = None
    """Parameter sweep configuration (mutually exclusive with samples)."""

    samples: list[SampleEntry] | None = None
    """Multi-sample batch (mutually exclusive with sweep)."""

    @model_validator(mode="after")
    def check_sweep_or_samples(self):
        if self.sweep is None and self.samples is None:
            raise ValueError("Either 'sweep' or 'samples' must be provided")
        if self.sweep is not None and self.samples is not None:
            raise ValueError("Cannot provide both 'sweep' and 'samples'")
        return self
```

The import for `model_validator` needs to be added to the top of the file. Add to the pydantic import line:

```python
from pydantic import BaseModel, model_validator
```

- [ ] **Step 2: Verify import doesn't break**

Run: `cd /home/laz/proj/melts-modern && python -c "from meltsapp.schemas import BatchConfig, SampleEntry; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add meltsapp/schemas.py
git commit -m "feat: extend BatchConfig to accept multi-sample batch via SampleEntry"
```

---

### Task 2: Extend Backend Batch Endpoint

**Files:**
- Modify: `web/app.py:493-541`

The `start_batch()` endpoint needs to handle the new `samples` mode in addition to `sweep`.

- [ ] **Step 1: Update start_batch to handle samples mode**

In `web/app.py`, replace the `start_batch` function (lines 493-541) with:

```python
@app.post("/api/batch")
async def start_batch(batch: BatchConfig):
    """Start a batch of simulations with parameter sweep or multi-sample."""
    _cleanup_old_sims()

    batch_id = uuid.uuid4().hex[:12]

    if batch.samples is not None:
        # Multi-sample mode: one SimConfig per sample, composition from Excel
        configs = []
        labels = []
        for sample in batch.samples:
            cfg = batch.base_config.model_copy(deep=True)
            cfg.composition = sample.composition
            configs.append(cfg)
            labels.append(sample.name)
    else:
        # Parameter sweep mode (existing behavior)
        configs = []
        for val in batch.sweep.values:
            cfg = batch.base_config.model_copy(deep=True)
            if batch.sweep.param == "H2O":
                cfg.composition["H2O"] = val
            elif batch.sweep.param == "pressure":
                cfg.P_start = val
                cfg.P_end = val  # isobaric at swept pressure
            elif batch.sweep.param == "fo2_offset":
                cfg.fo2_offset = val
            elif batch.sweep.param == "temperature":
                cfg.T_start = val
            configs.append(cfg)

        # Auto-generate labels if not provided
        LABEL_TEMPLATES = {
            "H2O": "H\u2082O = {v:.1f} wt%",
            "pressure": "P = {v:.0f} bar",
            "fo2_offset": "fO\u2082 offset = {v:+.1f}",
            "temperature": "T\u2080 = {v:.0f} \u00b0C",
        }
        if batch.sweep.labels and len(batch.sweep.labels) == len(batch.sweep.values):
            labels = batch.sweep.labels
        else:
            tpl = LABEL_TEMPLATES.get(batch.sweep.param, "{v}")
            labels = [tpl.format(v=v) for v in batch.sweep.values]

    batch_state = BatchState(
        batch_id=batch_id,
        configs=configs,
        labels=labels,
        current_run=0,
        total_runs=len(configs),
        status="running",
    )
    BATCHES[batch_id] = batch_state

    # Launch the sequential runner
    asyncio.create_task(_run_batch_sequence(batch_id))

    return {"batch_id": batch_id, "total_runs": len(configs)}
```

- [ ] **Step 2: Update the import in app.py**

At the top of `web/app.py`, line 37, update the import to include `SampleEntry`:

```python
from meltsapp.schemas import BatchConfig, MageminConfig, SampleEntry, SimConfig
```

(This import isn't strictly needed since FastAPI resolves via `BatchConfig`, but keeps it explicit for readability.)

- [ ] **Step 3: Verify the server starts**

Run: `cd /home/laz/proj/melts-modern && python -c "from web.app import app; print('App loaded OK')"`

Expected: `App loaded OK`

- [ ] **Step 4: Commit**

```bash
git add web/app.py
git commit -m "feat: handle multi-sample batch mode in /api/batch endpoint"
```

---

### Task 3: Add SheetJS CDN and Batch Mode Toggle HTML

**Files:**
- Modify: `web/static/index.html:11` (add script tag)
- Modify: `web/static/index.html:189-217` (batch fieldset)

- [ ] **Step 1: Add SheetJS CDN script tag**

In `web/static/index.html`, after the Plotly script tag (line 11), add:

```html
  <script src="https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.mini.min.js"></script>
```

- [ ] **Step 2: Replace the batch fieldset HTML**

Replace the batch fieldset (lines 189-217) with:

```html
        <!-- Batch mode -->
        <fieldset id="batch-fieldset">
          <legend>Batch Mode</legend>
          <div class="batch-toggle-row">
            <label class="toggle-label">
              <input type="checkbox" id="batch-toggle"> Enable batch mode
            </label>
          </div>
          <div class="batch-config hidden" id="batch-config">
            <!-- Batch type selector -->
            <div class="batch-type-toggle" id="batch-type-toggle">
              <button type="button" class="batch-type-btn active" data-batch-type="sweep">Parameter Sweep</button>
              <button type="button" class="batch-type-btn" data-batch-type="samples">Import Samples</button>
            </div>

            <!-- Sweep config (existing) -->
            <div class="batch-sweep-config" id="batch-sweep-config">
              <div class="input-row">
                <label>Sweep Parameter
                  <select id="sweep-param">
                    <option value="H2O">H&#8322;O (wt%)</option>
                    <option value="pressure">Pressure (bar)</option>
                    <option value="fo2_offset">fO&#8322; Offset</option>
                    <option value="temperature">T Start (&deg;C)</option>
                  </select>
                </label>
              </div>
              <div class="input-row" style="margin-top: 8px;">
                <label>From<input type="number" id="sweep-from" value="0" step="0.5"></label>
                <label>To<input type="number" id="sweep-to" value="4" step="0.5"></label>
                <label>Steps<input type="number" id="sweep-steps" value="5" min="2" max="10" step="1"></label>
              </div>
              <div class="sweep-preview" id="sweep-preview">
                Values: 0.0, 1.0, 2.0, 3.0, 4.0
              </div>
            </div>

            <!-- Import samples config -->
            <div class="batch-samples-config hidden" id="batch-samples-config">
              <div class="sample-upload-zone" id="sample-upload-zone">
                <div class="upload-icon">&#128196;</div>
                <div class="upload-text">Drop Excel/CSV file here</div>
                <div class="upload-hint">or click to select file</div>
                <div class="upload-formats">.xlsx / .xls / .csv</div>
                <input type="file" id="sample-file-input" accept=".xlsx,.xls,.csv" hidden>
              </div>
              <div class="upload-template-link">
                <a href="/static/melts_template.xlsx" download>Download template Excel</a>
              </div>
              <div class="sample-preview hidden" id="sample-preview">
                <div class="sample-summary" id="sample-summary"></div>
                <div class="sample-warnings" id="sample-warnings"></div>
                <div class="sample-table-wrapper" id="sample-table-wrapper"></div>
                <div class="sample-footer" id="sample-footer"></div>
              </div>
            </div>
          </div>
        </fieldset>
```

- [ ] **Step 3: Verify HTML is valid**

Open browser to confirm page loads without errors. Or run:

```bash
python -c "from web.app import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add SheetJS CDN and batch mode toggle HTML with import samples UI"
```

---

### Task 4: Add CSS for Batch Type Toggle and Upload Zone

**Files:**
- Modify: `web/static/style.css` (append new rules)

- [ ] **Step 1: Read current end of style.css to find append point**

Read the last 20 lines of `web/static/style.css` to confirm where to append.

- [ ] **Step 2: Append batch-related CSS**

Append to the end of `web/static/style.css`:

```css
/* ---------------------------------------------------------------------------
   Batch type toggle (sweep / import samples)
   --------------------------------------------------------------------------- */
.batch-type-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 12px;
}

.batch-type-btn {
  flex: 1;
  padding: 7px 10px;
  font-size: 0.8rem;
  font-weight: 500;
  text-align: center;
  background: var(--surface);
  color: var(--text-secondary);
  border: none;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.batch-type-btn.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

/* ---------------------------------------------------------------------------
   Sample upload zone
   --------------------------------------------------------------------------- */
.sample-upload-zone {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.sample-upload-zone:hover,
.sample-upload-zone.drag-over {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 5%, transparent);
}

.upload-icon { font-size: 1.5rem; margin-bottom: 4px; }
.upload-text { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
.upload-hint { font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px; }
.upload-formats { font-size: 0.7rem; color: var(--text-muted); margin-top: 6px; }

.upload-template-link {
  text-align: center;
  margin-top: 8px;
}

.upload-template-link a {
  font-size: 0.75rem;
  color: var(--primary);
  text-decoration: underline;
}

/* ---------------------------------------------------------------------------
   Sample preview table
   --------------------------------------------------------------------------- */
.sample-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--primary) 8%, transparent);
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 6px;
}

.sample-summary .clear-btn {
  font-size: 0.72rem;
  color: var(--danger, #ef4444);
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
}

.sample-warnings {
  font-size: 0.72rem;
  color: var(--warning, #d97706);
  background: color-mix(in srgb, var(--warning, #d97706) 8%, transparent);
  padding: 5px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
}

.sample-warnings:empty { display: none; }

.sample-table-wrapper {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.sample-table-wrapper table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.72rem;
}

.sample-table-wrapper th {
  position: sticky;
  top: 0;
  background: var(--surface);
  padding: 5px 8px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
  font-weight: 600;
}

.sample-table-wrapper th:first-child,
.sample-table-wrapper td:first-child {
  width: 28px;
  text-align: center;
}

.sample-table-wrapper td {
  padding: 4px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
  color: var(--text-primary);
}

.sample-table-wrapper tr.deselected {
  opacity: 0.4;
  text-decoration: line-through;
}

.sample-footer {
  font-size: 0.72rem;
  color: var(--text-secondary);
  text-align: right;
  margin-top: 4px;
}

/* ---------------------------------------------------------------------------
   Batch results tab bar (Summary / Individual)
   --------------------------------------------------------------------------- */
.batch-result-tabs {
  display: flex;
  border-bottom: 2px solid var(--border);
  margin-bottom: 12px;
}

.batch-result-tab {
  padding: 8px 20px;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}

.batch-result-tab.active {
  color: var(--primary);
  font-weight: 600;
  border-bottom-color: var(--primary);
}

.sample-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.sample-selector label {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.sample-selector select {
  flex: 1;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/static/style.css
git commit -m "feat: add CSS for batch type toggle, upload zone, sample preview, and result tabs"
```

---

### Task 5: Implement Frontend — File Parsing and Preview

**Files:**
- Modify: `web/static/app.js`

This is the core frontend logic: batch type switching, file upload/drag-drop, SheetJS parsing, and preview table rendering.

- [ ] **Step 1: Add new DOM references and state variables**

In `app.js`, after the existing batch DOM references (line 277, after `const $sweepPreview`), add:

```javascript
const $batchTypeToggle = document.getElementById("batch-type-toggle");
const $batchSweepConfig = document.getElementById("batch-sweep-config");
const $batchSamplesConfig = document.getElementById("batch-samples-config");
const $sampleUploadZone = document.getElementById("sample-upload-zone");
const $sampleFileInput = document.getElementById("sample-file-input");
const $samplePreview = document.getElementById("sample-preview");
const $sampleSummary = document.getElementById("sample-summary");
const $sampleWarnings = document.getElementById("sample-warnings");
const $sampleTableWrapper = document.getElementById("sample-table-wrapper");
const $sampleFooter = document.getElementById("sample-footer");
```

In the state variables section (around line 219, near `let batchMode = false;`), add:

```javascript
let batchType = "sweep"; // "sweep" or "samples"
let importedSamples = null; // {samples: [{name, composition}], skippedColumns: []}
```

- [ ] **Step 2: Add batch type toggle and file upload event binding**

In the `bindEvents()` function, after the existing sweep event bindings (around line 419, after `$sweepParam.addEventListener("change", updateSweepPreview);`), add:

```javascript
  // Batch type toggle (sweep / import samples)
  $batchTypeToggle.addEventListener("click", (e) => {
    const btn = e.target.closest(".batch-type-btn");
    if (!btn) return;
    batchType = btn.dataset.batchType;
    $batchTypeToggle.querySelectorAll(".batch-type-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.batchType === batchType);
    });
    $batchSweepConfig.classList.toggle("hidden", batchType !== "sweep");
    $batchSamplesConfig.classList.toggle("hidden", batchType !== "samples");
  });

  // File upload: click and drag-drop
  $sampleUploadZone.addEventListener("click", () => $sampleFileInput.click());
  $sampleFileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) handleSampleFile(e.target.files[0]);
  });
  $sampleUploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    $sampleUploadZone.classList.add("drag-over");
  });
  $sampleUploadZone.addEventListener("dragleave", () => {
    $sampleUploadZone.classList.remove("drag-over");
  });
  $sampleUploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    $sampleUploadZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) handleSampleFile(e.dataTransfer.files[0]);
  });
```

- [ ] **Step 3: Add the file parsing function**

After the `updateSweepPreview()` function (around line 621), add:

```javascript
// ---------------------------------------------------------------------------
// Multi-sample import
// ---------------------------------------------------------------------------

/** Map of lowercase oxide names to canonical MELTS oxide names. */
const OX_LOWER_MAP = {};
OX.forEach((ox) => { OX_LOWER_MAP[ox.toLowerCase()] = ox; });

function handleSampleFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: "array" });
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" });

      if (rows.length < 2) {
        showError("File has no data rows. Need at least a header row and one sample.");
        return;
      }

      const headers = rows[0].map(String);
      const skippedColumns = [];
      const oxideMap = []; // [{colIdx, oxName}]

      for (let c = 1; c < headers.length; c++) {
        const raw = headers[c].trim();
        const canonical = OX_LOWER_MAP[raw.toLowerCase()];
        if (canonical) {
          oxideMap.push({ colIdx: c, oxName: canonical });
        } else if (raw !== "") {
          skippedColumns.push(raw);
        }
      }

      if (oxideMap.length === 0) {
        showError("No recognized oxide columns. Headers must use standard names: " + OX.slice(0, 10).join(", ") + ", ...");
        return;
      }

      const samples = [];
      for (let r = 1; r < rows.length; r++) {
        const row = rows[r];
        const name = String(row[0] || "").trim();
        if (!name) continue;

        const composition = {};
        let hasValue = false;
        for (const { colIdx, oxName } of oxideMap) {
          const val = parseFloat(row[colIdx]);
          if (!isNaN(val) && val > 0) {
            composition[oxName] = val;
            hasValue = true;
          }
        }
        if (hasValue) {
          samples.push({ name, composition });
        }
      }

      if (samples.length === 0) {
        showError("No valid samples found. Each row needs a name and at least one oxide value > 0.");
        return;
      }

      importedSamples = { samples, skippedColumns, oxideNames: oxideMap.map((m) => m.oxName) };
      renderSamplePreview();
    } catch (err) {
      showError("Unable to read file: " + err.message);
    }
  };
  reader.readAsArrayBuffer(file);
}

function renderSamplePreview() {
  if (!importedSamples) return;
  const { samples, skippedColumns, oxideNames } = importedSamples;

  // Summary bar
  $sampleSummary.innerHTML =
    `<span>Identified ${samples.length} samples, ${oxideNames.length} oxides</span>` +
    `<button type="button" class="clear-btn" id="clear-samples-btn">Clear</button>`;
  document.getElementById("clear-samples-btn").addEventListener("click", clearImportedSamples);

  // Warnings
  if (skippedColumns.length > 0) {
    $sampleWarnings.textContent = "Ignored columns: " + skippedColumns.join(", ");
  } else {
    $sampleWarnings.textContent = "";
  }

  // Preview columns: show SiO2, MgO, CaO, Na2O, K2O, H2O if present
  const previewOx = ["SiO2", "MgO", "CaO", "Na2O", "K2O", "H2O"].filter((ox) => oxideNames.includes(ox));

  // Table
  let html = "<table><thead><tr>";
  html += '<th><input type="checkbox" id="sample-select-all" checked></th>';
  html += "<th>Sample</th>";
  previewOx.forEach((ox) => { html += `<th style="text-align:right">${formatOxide(ox)}</th>`; });
  if (oxideNames.length > previewOx.length) html += '<th style="text-align:center;color:var(--text-muted)">...</th>';
  html += "</tr></thead><tbody>";

  samples.forEach((s, i) => {
    html += `<tr data-sample-idx="${i}">`;
    html += `<td><input type="checkbox" class="sample-cb" data-idx="${i}" checked></td>`;
    html += `<td style="font-weight:600">${s.name}</td>`;
    previewOx.forEach((ox) => {
      const val = s.composition[ox];
      html += `<td style="text-align:right">${val !== undefined ? val.toFixed(2) : "-"}</td>`;
    });
    if (oxideNames.length > previewOx.length) html += '<td style="text-align:center;color:var(--text-muted)">...</td>';
    html += "</tr>";
  });

  html += "</tbody></table>";
  $sampleTableWrapper.innerHTML = html;

  updateSampleFooter();
  $samplePreview.classList.remove("hidden");
  $sampleUploadZone.classList.add("hidden");

  // Checkbox events
  document.getElementById("sample-select-all").addEventListener("change", (e) => {
    const checked = e.target.checked;
    $sampleTableWrapper.querySelectorAll(".sample-cb").forEach((cb) => {
      cb.checked = checked;
      cb.closest("tr").classList.toggle("deselected", !checked);
    });
    updateSampleFooter();
  });

  $sampleTableWrapper.querySelectorAll(".sample-cb").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      e.target.closest("tr").classList.toggle("deselected", !e.target.checked);
      updateSampleFooter();
    });
  });
}

function updateSampleFooter() {
  if (!importedSamples) return;
  const total = importedSamples.samples.length;
  const selected = $sampleTableWrapper.querySelectorAll(".sample-cb:checked").length;
  $sampleFooter.textContent = `Selected ${selected} / ${total} samples`;
}

function getSelectedSamples() {
  if (!importedSamples) return [];
  const selected = [];
  $sampleTableWrapper.querySelectorAll(".sample-cb:checked").forEach((cb) => {
    const idx = parseInt(cb.dataset.idx);
    selected.push(importedSamples.samples[idx]);
  });
  return selected;
}

function clearImportedSamples() {
  importedSamples = null;
  $samplePreview.classList.add("hidden");
  $sampleUploadZone.classList.remove("hidden");
  $sampleFileInput.value = "";
}
```

- [ ] **Step 4: Verify the page loads and the toggle works**

Open the app in the browser, enable batch mode, and confirm the "Parameter Sweep" / "Import Samples" toggle appears and switches views. Upload is not wired to submit yet — that's next task.

- [ ] **Step 5: Commit**

```bash
git add web/static/app.js
git commit -m "feat: add SheetJS file parsing, sample preview table, and batch type toggle"
```

---

### Task 6: Wire Up Multi-Sample Batch Submission

**Files:**
- Modify: `web/static/app.js` (the `onFormSubmit` function and `onBatchComplete`)

- [ ] **Step 1: Update onFormSubmit to handle multi-sample batch**

In `app.js`, find the batch submission block inside `onFormSubmit()` (around line 717-739). Replace the batch branch:

```javascript
  if (batchMode) {
    if (batchType === "samples") {
      // Multi-sample batch
      const selected = getSelectedSamples();
      if (selected.length === 0) {
        showError("No samples selected. Import an Excel file and select at least one sample.");
        return;
      }
      const batchConfig = {
        base_config: config,
        samples: selected,
      };
      startBatch(batchConfig);
    } else {
      // Parameter sweep (existing)
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
    }
  } else {
    startSimulation(config);
  }
```

- [ ] **Step 2: Update the batch toggle label**

In the `bindEvents()` function, find the batch toggle handler (around line 408-413). Update it to also consider the batch type:

```javascript
  $batchToggle.addEventListener("change", (e) => {
    batchMode = e.target.checked;
    $batchConfig.classList.toggle("hidden", !batchMode);
    updateRunButtonLabel();
  });
```

Add the helper function near the batch-related code:

```javascript
function updateRunButtonLabel() {
  if (!batchMode) {
    $btnRun.querySelector(".btn-run-label").textContent = "Run Simulation";
  } else if (batchType === "samples") {
    const count = importedSamples ? getSelectedSamples().length : 0;
    $btnRun.querySelector(".btn-run-label").textContent =
      count > 0 ? `Run Batch (${count} samples)` : "Run Batch";
  } else {
    $btnRun.querySelector(".btn-run-label").textContent = "Run Batch";
  }
}
```

Also call `updateRunButtonLabel()` at the end of `updateSampleFooter()` and in the batch type toggle click handler.

In the batch type toggle handler (the one added in Task 5 Step 2), append `updateRunButtonLabel();` after the visibility toggles.

In `updateSampleFooter()`, append `updateRunButtonLabel();` at the end.

In `clearImportedSamples()`, append `updateRunButtonLabel();` at the end.

- [ ] **Step 3: Verify sweep mode still works**

Enable batch mode with "Parameter Sweep" selected. Confirm sweep preview still works and the Run Batch button shows correctly.

- [ ] **Step 4: Commit**

```bash
git add web/static/app.js
git commit -m "feat: wire multi-sample batch submission to existing batch endpoint"
```

---

### Task 7: Add Individual Sample Detail View

**Files:**
- Modify: `web/static/index.html` (add batch result tabs HTML)
- Modify: `web/static/app.js` (add individual sample switching logic)

- [ ] **Step 1: Add batch result tabs to HTML**

In `web/static/index.html`, inside the main content area, immediately after the `<!-- Tab bar -->` div (line 261, before the opening `<div class="tabs" id="tabs">`), add:

```html
      <!-- Batch result mode tabs (hidden until batch completes) -->
      <div class="batch-result-tabs hidden" id="batch-result-tabs">
        <button class="batch-result-tab active" data-result-mode="compare">Summary Comparison</button>
        <button class="batch-result-tab" data-result-mode="individual">Individual Sample</button>
      </div>
      <div class="sample-selector hidden" id="sample-selector">
        <label>Sample:</label>
        <select id="individual-sample-select"></select>
        <button class="btn-download" id="btn-csv-individual" style="font-size:0.75rem;padding:4px 10px">Download CSV</button>
      </div>
```

- [ ] **Step 2: Add DOM refs and result mode switching in app.js**

After the existing DOM refs for batch (after `$sampleFooter`), add:

```javascript
const $batchResultTabs = document.getElementById("batch-result-tabs");
const $sampleSelector = document.getElementById("sample-selector");
const $individualSampleSelect = document.getElementById("individual-sample-select");
const $btnCsvIndividual = document.getElementById("btn-csv-individual");
```

Add a state variable near the other batch state:

```javascript
let batchResultMode = "compare"; // "compare" or "individual"
let batchRunsData = null; // {batchId, runs: [{sim_id, label}]}
```

In `bindEvents()`, add:

```javascript
  // Batch result mode toggle
  $batchResultTabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".batch-result-tab");
    if (!btn) return;
    batchResultMode = btn.dataset.resultMode;
    $batchResultTabs.querySelectorAll(".batch-result-tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.resultMode === batchResultMode);
    });
    $sampleSelector.classList.toggle("hidden", batchResultMode !== "individual");
    if (batchResultMode === "compare") {
      const activeTab = document.querySelector(".tab.active");
      if (activeTab && currentBatchId) fetchComparisonPlotsForTab(activeTab.dataset.tab, currentBatchId);
    } else if (batchResultMode === "individual") {
      showIndividualSample();
    }
  });

  // Individual sample selector
  $individualSampleSelect.addEventListener("change", () => {
    showIndividualSample();
  });

  // CSV download for individual sample
  $btnCsvIndividual.addEventListener("click", () => {
    const simId = $individualSampleSelect.value;
    if (simId) window.location.href = `/api/simulate/${simId}/csv`;
  });
```

- [ ] **Step 3: Add showIndividualSample and update onBatchComplete**

Add the `showIndividualSample` function:

```javascript
function showIndividualSample() {
  const simId = $individualSampleSelect.value;
  if (!simId) return;

  // Switch to single-sim view mode
  currentSimId = simId;
  plotCache = {}; // clear to re-fetch for this sample

  // Fetch results for this sample to populate scrubber
  fetch(`/api/simulate/${simId}/results`)
    .then((r) => r.json())
    .then((data) => {
      if (data.results && data.results.length > 0) {
        simResults = data.results;
        initScrubber(simResults);
        $scrubberSection.classList.remove("hidden");
      }
      // Fetch plots for current tab
      const activeTab = document.querySelector(".tab.active");
      if (activeTab) fetchPlotsForTab(activeTab.dataset.tab, simId);
    })
    .catch((err) => console.warn("Failed to load sample results:", err));
}
```

Update `onBatchComplete()` to populate the batch result tabs and sample dropdown:

```javascript
function onBatchComplete(batchId, batchData) {
  simRunning = false;
  resetRunButton();
  $progressBar.style.width = "100%";
  $progressInfo.textContent =
    `Batch complete. ${batchData.total_runs} runs finished.`;

  currentBatchId = batchId;
  currentSimId = null;
  batchResultMode = "compare";

  // Store runs data for individual view
  batchRunsData = {
    batchId,
    runs: batchData.runs.filter((r) => r.status === "done"),
  };

  // Show batch result tabs
  $batchResultTabs.classList.remove("hidden");
  $batchResultTabs.querySelectorAll(".batch-result-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.resultMode === "compare");
  });
  $sampleSelector.classList.add("hidden");

  // Populate individual sample dropdown
  $individualSampleSelect.innerHTML = "";
  for (const run of batchRunsData.runs) {
    const opt = document.createElement("option");
    opt.value = run.sim_id;
    opt.textContent = run.label;
    $individualSampleSelect.appendChild(opt);
  }

  // Hide scrubber for comparison mode
  $scrubberSection.classList.add("hidden");

  // Fetch comparison plots for active tab
  const activeTab = document.querySelector(".tab.active");
  if (activeTab) {
    fetchComparisonPlotsForTab(activeTab.dataset.tab, batchId);
  }
}
```

- [ ] **Step 4: Update switchTab to respect batchResultMode**

Find the `switchTab()` function (around line 1092). Update the batch branch:

```javascript
  // Fetch plots for this tab if we have a sim or batch
  if (currentBatchId) {
    if (batchResultMode === "individual" && currentSimId) {
      fetchPlotsForTab(tabName, currentSimId);
    } else {
      fetchComparisonPlotsForTab(tabName, currentBatchId);
    }
  } else if (currentSimId && simResults.length > 0) {
    fetchPlotsForTab(tabName, currentSimId);
  }
```

- [ ] **Step 5: Hide batch result tabs when starting a new run**

In `startBatch()`, add at the beginning (after `clearAllPlots()`):

```javascript
  $batchResultTabs.classList.add("hidden");
  $sampleSelector.classList.add("hidden");
  batchRunsData = null;
```

Also in `startSimulation()` (the single-sim start function), hide them:

```javascript
  $batchResultTabs.classList.add("hidden");
  $sampleSelector.classList.add("hidden");
```

- [ ] **Step 6: Commit**

```bash
git add web/static/index.html web/static/app.js
git commit -m "feat: add individual sample detail view with dropdown switching and scrubber"
```

---

### Task 8: Create Template Excel File

**Files:**
- Create: `web/static/melts_template.xlsx` (generated via Python script)

- [ ] **Step 1: Generate the template file using openpyxl**

Run:

```bash
cd /home/laz/proj/melts-modern && python3 -c "
import openpyxl
from meltsapp import OX
from meltsapp.presets import PRESETS

wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Compositions'

# Header row
ws.cell(1, 1, 'Sample')
for i, ox in enumerate(OX):
    ws.cell(1, i + 2, ox)

# Example row 1: N-MORB
comp = PRESETS['nmorb']['composition']
ws.cell(2, 1, 'N-MORB (example)')
for i, ox in enumerate(OX):
    ws.cell(2, i + 2, comp.get(ox, 0.0))

# Example row 2: Arc Basalt
comp2 = PRESETS['arc_basalt']['composition']
ws.cell(3, 1, 'Arc Basalt (example)')
for i, ox in enumerate(OX):
    ws.cell(3, i + 2, comp2.get(ox, 0.0))

# Auto-width for sample column
ws.column_dimensions['A'].width = 22

wb.save('web/static/melts_template.xlsx')
print('Template created: web/static/melts_template.xlsx')
"
```

Expected: `Template created: web/static/melts_template.xlsx`

If openpyxl is not installed, run `pip install openpyxl` first.

- [ ] **Step 2: Verify the file exists and is downloadable**

```bash
ls -la web/static/melts_template.xlsx
```

Expected: File exists, non-zero size (~5-8KB).

- [ ] **Step 3: Commit**

```bash
git add web/static/melts_template.xlsx
git commit -m "feat: add template Excel file with 19 MELTS oxide columns and example compositions"
```

---

### Task 9: Integration Testing — Full Flow Verification

**Files:** No new files. Manual verification.

- [ ] **Step 1: Start the server**

```bash
cd /home/laz/proj/melts-modern && python -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=9000)"
```

(Run in background or separate terminal.)

- [ ] **Step 2: Verify parameter sweep still works**

1. Open browser to the app
2. Select a preset (e.g., N-MORB)
3. Enable batch mode → "Parameter Sweep" should be active by default
4. Set H₂O sweep from 0 to 4, 3 steps
5. Click Run Batch
6. Confirm: progress shows, comparison plots render on completion

- [ ] **Step 3: Verify multi-sample import**

1. Download the template via the "Download template Excel" link
2. Enable batch mode → switch to "Import Samples"
3. Upload the template file (drag-drop or click)
4. Confirm: preview table shows 2 samples with correct oxide values
5. Confirm: "Ignored columns" warning does NOT appear (all columns match)
6. Confirm: sample count shows "Selected 2 / 2 samples"

- [ ] **Step 4: Run multi-sample batch**

1. With 2 samples imported and selected
2. Set T/P conditions in sidebar (e.g., isobaric, 1300→900°C, 1 bar)
3. Click "Run Batch (2 samples)"
4. Confirm: progress shows "Run 1/2: N-MORB (example)" then "Run 2/2: Arc Basalt (example)"
5. Confirm: on completion, "Summary Comparison" tab shows TAS with 2 overlaid traces
6. Switch to "Individual Sample" tab
7. Select "N-MORB (example)" from dropdown
8. Confirm: full plots load, scrubber appears and works
9. Switch to "Arc Basalt (example)"
10. Confirm: plots refresh for second sample

- [ ] **Step 5: Verify edge cases**

1. Upload a file with non-MELTS columns (e.g., add LOI, Total) — confirm warning appears
2. Deselect one sample → confirm count updates, run only includes selected
3. Click "Clear" → confirm returns to upload zone
4. Upload a CSV file with same format → confirm it parses correctly

- [ ] **Step 6: Commit any fixes needed**

If any issues are found during testing, fix and commit each fix separately.
