# Multi-Sample Batch Import Design

## Problem

Current batch mode only supports parameter sweeps — varying one parameter (H₂O, pressure, fO₂, temperature) across a single fixed composition. Users with multiple rock samples in Excel spreadsheets must run simulations one at a time, manually copying compositions into the UI. This is the most common real-world use case: a researcher has 10-30 whole-rock analyses and wants to simulate all of them under the same T/P conditions.

## Solution

Add an "Import Samples" mode alongside the existing "Parameter Sweep" inside the batch mode toggle. Users upload an Excel file with standard geochemistry table format, preview and select samples, then run batch simulation with shared T/P conditions.

## Excel Format

Standard whole-rock geochemistry table:

| (sample name) | SiO2 | TiO2 | Al2O3 | Fe2O3 | FeO | MgO | CaO | Na2O | K2O | H2O | ... |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DH-01 | 48.68 | 1.01 | 17.64 | 1.87 | 6.87 | 9.10 | 11.44 | 2.66 | 0.06 | 0.20 | ... |
| DH-02 | 51.20 | 0.89 | 15.32 | ... | ... | ... | ... | ... | ... | ... | ... |

Rules:
- First column: sample name (string)
- First row: oxide column headers
- Remaining cells: wt% values (float)
- Column header matching against the MELTS 19-oxide list (`OX` from `meltsapp/__init__.py`) is case-insensitive (e.g., "sio2", "SIO2", "SiO2" all match). Non-matching columns are silently ignored with a warning message listing them
- Empty cells default to 0.0
- Supported file formats: .xlsx, .xls, .csv

A downloadable template Excel file is provided containing the 19 MELTS oxide column headers and two example rows.

## UI Flow

### 1. Batch Mode Selection

Inside the existing batch mode fieldset (`#batch-config`), replace the current sweep-only content with a segmented toggle:

```
[Parameter Sweep] [Import Samples]
```

- "Parameter Sweep" shows the existing sweep UI (unchanged)
- "Import Samples" shows:
  - Drag-and-drop upload area (also clickable for file picker)
  - "Download template" link below the drop zone
  - Accepted formats: .xlsx, .xls, .csv

### 2. Sample Preview Table

After successful file parse, the upload area is replaced by:

- **Summary bar**: "✅ Identified N samples, M oxides" with a "Clear" button to reset
- **Warning bar** (conditional): "⚠️ Ignored columns: LOI, Total, Mg#" — lists non-MELTS columns that were skipped
- **Preview table**: Scrollable table with columns:
  - Checkbox (select/deselect per sample)
  - Sample name
  - Key oxides (SiO₂, MgO, and a "..." indicator — full data visible on hover or via horizontal scroll)
- **Footer**: "Selected X / N samples"
- **Select all / Deselect all** via the header checkbox

### 3. Execution

Clicking "Run Batch" with imported samples:

1. Constructs one `SimConfig` per selected sample, using:
   - `composition`: from the Excel row
   - All other fields (T_start, T_end, P_start, P_end, dT, dP, path_mode, fo2_buffer, fo2_offset, crystallization_mode, suppress_phases, melts_mode): from the sidebar form (shared)
2. Sends to a new endpoint `POST /api/batch` with an extended `BatchConfig` that accepts a `samples` field instead of `sweep`
3. Backend executes sequentially (same as current sweep batch — C library singleton constraint)

Progress display shows per-sample status:
- ✅ Completed (with step count)
- ⏳ Running (with current step and temperature)
- ⏸ Pending

### 4. Results Display

Two tabs in the results area:

**Tab: Summary Comparison**
- Reuses existing comparison plot infrastructure (`fig_tas_compare`, `fig_harker_compare`, etc.)
- Sub-tabs for plot types: TAS, Harker, P-T Path, Evolution
- Each sample is a separate trace with its sample name as legend label
- Color-coded per sample

**Tab: Individual Sample**
- Dropdown selector to pick a sample by name
- Shows the full single-run result view: all evolution plots, phase diagrams, temperature scrubber
- Reuses existing single-simulation plot functions and scrubber logic
- CSV download per individual sample

## Architecture

### Frontend (`web/static/app.js`)

**New dependency**: SheetJS (xlsx) via CDN `<script>` tag in `index.html` (~90KB). Parses Excel/CSV entirely client-side.

**New functions**:
- `parseSamplesFile(file)` → `{samples: [{name, composition}], skippedColumns: [string]}` — uses SheetJS to read file, extract first row as headers, map to MELTS oxide names, return parsed samples
- `renderSamplePreview(parsed)` — builds the preview table HTML in the batch config area
- `getSelectedSamples()` → `[{name, composition}]` — reads checkbox state from preview table
- `buildMultiSampleBatch()` → constructs the batch request payload from selected samples + sidebar config

**Modified functions**:
- `collectConfig()` — when in "Import Samples" mode, returns array of SimConfigs rather than single config
- `startBatch()` — accepts both sweep and multi-sample batch payloads
- `onBatchComplete()` — handles sample-name labels in comparison plots
- `showResultsForSample(sampleName)` — switches individual detail tab to show one sample's full results

**New HTML elements** in `index.html`:
- Batch mode segmented toggle (two radio-style buttons)
- Upload drop zone container
- Sample preview table container
- Results tab bar (Summary / Individual)
- Sample selector dropdown in individual tab

### Backend (`web/app.py`)

**Schema changes** (`meltsapp/schemas.py`):
- `BatchConfig` gains a new optional field: `samples: list[SampleEntry] | None`
- New schema: `SampleEntry(name: str, composition: dict[str, float])`
- Validation: either `sweep` or `samples` must be provided, not both

**Endpoint changes**:
- `POST /api/batch` — extended to handle `samples` mode:
  - When `samples` is provided: generates one `SimConfig` per sample using the sample's composition + shared `base_config` fields
  - Labels are the sample names from Excel
  - Execution via existing `_run_batch_sequence()` — no change to execution model
- Comparison endpoints (`/api/batch/{id}/compare/{type}`) — unchanged, already work with arbitrary labels

**No new endpoints needed.** The existing batch infrastructure handles multi-sample naturally once configs are generated.

### Template Excel File

A static file `web/static/melts_template.xlsx` containing:
- Row 1: 19 MELTS oxide headers (SiO2, TiO2, Al2O3, ...)
- Row 2-3: Two example compositions (N-MORB and Arc Basalt from presets)
- Served as static file download

## Error Handling

- **Parse errors**: If SheetJS can't read the file → "Unable to read file. Please use .xlsx, .xls, or .csv format."
- **No valid oxides**: If no column headers match MELTS oxides → "No recognized oxide columns found. Headers must use standard names: SiO2, TiO2, ..."
- **Empty rows**: Rows with all-zero or all-empty oxide values are silently excluded from the preview
- **NaN/non-numeric cells**: Treated as 0.0 with a per-cell warning highlight in the preview table

## Scope Boundaries

**In scope**:
- Excel/CSV upload and client-side parsing
- Sample preview with select/deselect
- Batch execution with per-sample progress
- Summary comparison plots (reuse existing)
- Individual sample detail view with dropdown switching
- Template Excel download
- CSV export per individual sample

**Out of scope**:
- Editing compositions in the preview table (read-only; user fixes in Excel and re-uploads)
- Per-sample T/P overrides (all samples share sidebar settings)
- Saving/loading batch configurations
- Batch result export as single combined CSV
