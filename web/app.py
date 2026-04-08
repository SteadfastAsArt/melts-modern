#!/usr/bin/env python3
"""
FastAPI application for MELTS thermodynamic modeling.

Spawns worker.py subprocesses for each simulation (the C library is a global
singleton, so one process per run), streams results over WebSocket, and
serves Plotly figure JSON from meltsapp.plotting.bindplotly.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from meltsapp import OX
from meltsapp.presets import PRESETS
from meltsapp.schemas import SimConfig

# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------
SIM_TTL_SECONDS = 3600  # 1 hour


@dataclass
class SimState:
    """Track one simulation's lifecycle."""
    sim_id: str
    process: asyncio.subprocess.Process | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)  # all msgs including init
    status: str = "running"  # running | done | error
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    config: dict[str, Any] = field(default_factory=dict)


SIMULATIONS: dict[str, SimState] = {}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="MELTS Modern", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKER_PATH = Path(__file__).resolve().parent / "worker.py"
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cleanup_old_sims() -> None:
    """Remove simulations older than TTL."""
    now = time.time()
    expired = [
        sid for sid, state in SIMULATIONS.items()
        if now - state.created_at > SIM_TTL_SECONDS and state.status != "running"
    ]
    for sid in expired:
        del SIMULATIONS[sid]


def _results_to_df(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert accumulated results dicts to a DataFrame with derived columns."""
    df = pd.DataFrame(results)
    if df.empty:
        return df
    # Drop nested phase_details column (not useful in the flat DataFrame)
    if "phase_details" in df.columns:
        df = df.drop(columns=["phase_details"])
    from meltsapp.plotting.common import calc_derived
    calc_derived(df)
    return df


def _results_to_phase_data(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a long-form phase_data DataFrame from step results.

    Each row represents one phase at one temperature step, with columns:
    step, T_C, phase, mass, SiO2, TiO2, Al2O3, ... (all 19 oxides).
    """
    rows: list[dict[str, Any]] = []
    for res in results:
        phase_details = res.get("phase_details")
        if not phase_details:
            continue
        step = res["step"]
        T_C = res["T_C"]
        for pd_ in phase_details:
            row = {"step": step, "T_C": T_C}
            row["phase"] = pd_["phase"]
            row["mass"] = pd_["mass"]
            for ox in OX:
                row[ox] = pd_.get(ox, 0.0)
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/presets")
async def get_presets():
    """Return all preset compositions and their defaults."""
    return JSONResponse(content=PRESETS)


@app.post("/api/simulate")
async def start_simulation(config: SimConfig):
    """Spawn a worker subprocess for a new simulation. Returns sim_id."""
    _cleanup_old_sims()

    sim_id = uuid.uuid4().hex[:12]
    state = SimState(sim_id=sim_id, config=config.model_dump())
    SIMULATIONS[sim_id] = state

    config_json = config.model_dump_json()

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(WORKER_PATH),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,  # C library noise, don't pipe it
    )
    state.process = proc

    # Send config and close stdin
    proc.stdin.write(config_json.encode())
    proc.stdin.close()

    # Launch background task to read stdout
    asyncio.create_task(_read_worker_output(sim_id))

    return {"sim_id": sim_id}


async def _read_worker_output(sim_id: str) -> None:
    """Background task: read worker stdout line by line, accumulate results."""
    import logging
    logger = logging.getLogger("melts.worker")

    state = SIMULATIONS.get(sim_id)
    if state is None or state.process is None:
        return

    proc = state.process
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                logger.info(f"[{sim_id}] stdout EOF")
                break
            decoded = line.decode().strip()
            if not decoded:
                continue
            try:
                msg = json.loads(decoded)
            except json.JSONDecodeError:
                logger.debug(f"[{sim_id}] non-JSON: {decoded[:60]}")
                continue

            msg_type = msg.get("type")
            logger.info(f"[{sim_id}] msg type={msg_type}, step={msg.get('step','-')}")
            if msg_type == "step":
                state.results.append(msg)
                state.messages.append(msg)
            elif msg_type in ("init", "liquidus"):
                state.messages.append(msg)
            elif msg_type == "done":
                state.status = "done"
                state.messages.append(msg)
            elif msg_type == "error":
                state.status = "error"
                state.error_message = msg.get("message", "Unknown error")
                state.messages.append(msg)
    except Exception as e:
        logger.error(f"[{sim_id}] exception: {e}")
        state.status = "error"
        state.error_message = str(e)

    # Wait for process exit
    await proc.wait()
    if state.status == "running":
        if proc.returncode != 0:
            state.status = "error"
            state.error_message = f"Worker exited with code {proc.returncode}"
        else:
            state.status = "done"


@app.websocket("/api/simulate/{sim_id}/stream")
async def stream_results(websocket: WebSocket, sim_id: str):
    """WebSocket that streams step results as they arrive from the worker."""
    if sim_id not in SIMULATIONS:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    state = SIMULATIONS[sim_id]
    sent = 0

    try:
        while True:
            # Send any new messages we haven't sent yet (init, step, done, error)
            while sent < len(state.messages):
                await websocket.send_json(state.messages[sent])
                sent += 1

            # Check if done
            if state.status in ("done", "error"):
                # Drain remaining
                while sent < len(state.messages):
                    await websocket.send_json(state.messages[sent])
                    sent += 1
                break

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/api/simulate/{sim_id}/results")
async def get_results(sim_id: str):
    """Return accumulated results as JSON list."""
    if sim_id not in SIMULATIONS:
        raise HTTPException(404, detail="Simulation not found")
    state = SIMULATIONS[sim_id]
    return JSONResponse(content={
        "status": state.status,
        "error": state.error_message,
        "count": len(state.results),
        "results": state.results,
    })


@app.get("/api/plots/{sim_id}/{plot_type}")
async def get_plot(sim_id: str, plot_type: str):
    """Return Plotly figure JSON for a specific plot type."""
    if sim_id not in SIMULATIONS:
        raise HTTPException(404, detail="Simulation not found")

    state = SIMULATIONS[sim_id]
    if not state.results:
        raise HTTPException(400, detail="No results yet")

    df = _results_to_df(state.results)

    # Map plot_type to the corresponding fig_* function
    PLOT_FUNCTIONS = {
        "tas": "fig_tas",
        "harker_mgo": "fig_harker_mgo",
        "harker_sio2": "fig_harker_sio2",
        "pt_path": "fig_pt_path",
        "afm": "fig_afm",
        "evolution": "fig_evolution",
        "phase_masses": "fig_phase_masses",
        "liquid_vs_temp": "fig_liquid_vs_temp",
        "system_thermo": "fig_system_thermo",
        "density": "fig_density",
        "olivine": "fig_olivine",
        "cpx": "fig_cpx",
        "plagioclase": "fig_plagioclase",
        "spinel": "fig_spinel",
        "mg_vs_sio2": "fig_mg_vs_sio2",
    }

    func_name = PLOT_FUNCTIONS.get(plot_type)
    if func_name is None:
        raise HTTPException(400, detail=f"Unknown plot type: {plot_type}")

    # Determine which arguments each plot function needs
    PHASE_DATA_PLOTS = {"olivine", "cpx", "plagioclase", "spinel"}
    PHASE_MASSES_PLOT = "phase_masses"
    SYSTEM_THERMO_PLOTS = {"system_thermo", "density"}

    try:
        import meltsapp.plotting.bindplotly as bp
        fig_func = getattr(bp, func_name)

        if plot_type in PHASE_DATA_PLOTS:
            phase_data = _results_to_phase_data(state.results)
            fig = fig_func(phase_data)
        elif plot_type == PHASE_MASSES_PLOT:
            phase_data = _results_to_phase_data(state.results)
            fig = fig_func(df, phase_data)
        elif plot_type in SYSTEM_THERMO_PLOTS:
            fig = fig_func(df)
        else:
            fig = fig_func(df)

        return JSONResponse(content=json.loads(fig.to_json()))
    except ImportError as e:
        raise HTTPException(501, detail=f"Plotting module not available: {e}")
    except AttributeError as e:
        raise HTTPException(501, detail=f"Plot function {func_name} not found: {e}")
    except Exception as e:
        raise HTTPException(500, detail=f"Plot generation failed: {e}")


@app.get("/api/simulate/{sim_id}/csv")
async def download_csv(sim_id: str):
    """Download simulation results as CSV."""
    if sim_id not in SIMULATIONS:
        raise HTTPException(404, detail="Simulation not found")

    state = SIMULATIONS[sim_id]
    if not state.results:
        raise HTTPException(400, detail="No results yet")

    # Build CSV in memory
    output = io.StringIO()
    # Use all keys from the first result as header (skip 'type')
    fieldnames = [k for k in state.results[0].keys() if k != "type"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in state.results:
        writer.writerow({k: v for k, v in row.items() if k != "type"})

    csv_bytes = output.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=melts_{sim_id}.csv"},
    )


# ---------------------------------------------------------------------------
# Static files & SPA fallback
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve the single-page application."""
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
