# MELTS Modern

Web-based interactive frontend for rhyolite-MELTS thermodynamic modeling.

## Architecture

- **meltsapp/** — Python package wrapping the MELTS C library via meltsdynamic/meltsengine
  - `engine.py` — `MeltsSession` class with fd-redirection (C library stdout → /dev/null)
  - `simulation.py` — `run_crystallization()` generator yielding StepResult per temperature step
  - `schemas.py` — Pydantic `SimConfig` + dataclass `StepResult`/`PhaseDetail`
  - `presets.py` — 5 named compositions with T/P defaults
  - `plotting/bindplotly.py` — 15 Plotly figure builders, all use `_base_layout()`/`_axis_style()`
  - `plotting/common.py` — TAS boundaries, AFM coords, PHASE_COLORS, derived-column calculator
  - `magemin_engine.py` — MAGEMin engine via PetThermoTools/Julia
- **web/** — FastAPI app, one worker subprocess per simulation
  - `app.py` — REST endpoints + WebSocket streaming (both rMELTS and MAGEMin routes)
  - `worker.py` — rMELTS subprocess (C library is a global singleton)
  - `magemin_worker.py` — MAGEMin subprocess (Julia/PetThermoTools)
  - `static/` — vanilla HTML/CSS/JS SPA with Plotly charts
- **Bundled binaries:** `alphamelts-app/`, `alphamelts-py/`, `lib/` (x86-64 Linux ELF, checked into repo)
- **MAGEMin deps (not in repo):** Julia runtime (`~/julia/`), PetThermoTools (pip), Julia depot (`~/.julia/`)

## Key patterns

- `simResults[i].phases` is a `+`-delimited string, not an array. Split on `+`, strip trailing digits for display names.
- Plotly figure width is NOT set in Python — `responsive: true` in JS handles sizing.
- Multi-panel charts (Harker 3x3, Evolution 2x3, etc.) each occupy their own full-width row.
- Filter `df[df["mass_liquid_g"] > 0.01]` in all liquid-composition plots to avoid (0,0) outliers.

## Testing

```bash
pytest tests/                 # Python: 23 smoke tests for all fig_ functions
npx vitest run                # JS: 17 unit tests for scrubber logic
```

## Running

```bash
python -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=9000)"
```

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
