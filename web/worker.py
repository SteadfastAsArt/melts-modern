#!/usr/bin/env python3
"""MELTS simulation worker. Reads JSON config from stdin, writes JSON lines to stdout."""
import sys
import os
import json

# CRITICAL: Save the real stdout pipe fd BEFORE anything can redirect fd 1.
# MeltsSession.__init__ will redirect fd 1 to /dev/null for the C library.
# We keep a direct handle to the original pipe so emit() always works.
_OUTPUT_FD = os.dup(1)
_OUTPUT = os.fdopen(_OUTPUT_FD, "w", buffering=1)  # line-buffered

# Add project root to path so meltsapp can be imported
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from meltsapp.schemas import SimConfig
from meltsapp.simulation import run_crystallization
from meltsapp import OX


def emit(msg):
    """Write a JSON line to the saved output pipe."""
    try:
        _OUTPUT.write(json.dumps(msg) + "\n")
        _OUTPUT.flush()
    except BrokenPipeError:
        pass


def main():
    config_json = sys.stdin.read()
    config = SimConfig.model_validate_json(config_json)

    if config.path_mode in ("isothermal", "isentropic"):
        n_steps = int(abs(config.P_start - config.P_end) / abs(config.dP)) if config.dP != 0 else 1
    else:
        n_steps = int(abs(config.T_start - config.T_end) / abs(config.dT)) if config.dT != 0 else 1
    emit({"type": "init", "n_steps": n_steps, "message": "Initializing MELTS engine..."})

    for result in run_crystallization(config):
        if result.step == -1:
            emit({"type": "liquidus", "T_liquidus": result.T})
            continue
        # Flatten phase_details into serialisable dicts
        phase_details = []
        for pd_ in result.phase_details:
            row = {"phase": pd_.phase, "mass": pd_.mass}
            for ox in OX:
                row[ox] = pd_.composition.get(ox, 0.0)
            phase_details.append(row)

        emit({
            "type": "step",
            "step": result.step,
            "T_C": result.T,
            "P_bar": result.P,
            "mass_liquid_g": result.liquid_mass,
            "mass_solid_g": result.solid_mass,
            **{f"liq_{ox}": result.liquid_comp.get(ox, 0.0) for ox in OX},
            "logfO2": result.logfO2,
            "rho_liq": result.rho_liq,
            "viscosity": result.viscosity,
            "phases": "+".join(result.phases) if result.phases else "",
            "phase_details": phase_details,
            "H_total": result.H_total,
            "S_total": result.S_total,
            "V_total": result.V_total,
            "Cp_total": result.Cp_total,
            "rho_sol": result.rho_sol,
        })

    emit({"type": "done"})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        emit({"type": "error", "message": str(e)})
        sys.exit(1)
