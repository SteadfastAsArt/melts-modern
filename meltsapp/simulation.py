"""
High-level simulation runner for MELTS crystallization paths.

The main entry point is ``run_crystallization(config)`` which yields one
``StepResult`` per temperature step along a linear P-T path.
"""
from __future__ import annotations

from typing import Generator

from meltsapp.engine import MeltsSession
from meltsapp.schemas import SimConfig, StepResult


def run_crystallization(config: SimConfig) -> Generator[StepResult, None, None]:
    """Run a crystallization path, yielding one StepResult per temperature step.

    The simulation follows a linear P-T path from (T_start, P_start) to
    (T_end, P_end), stepping by *config.dT* (negative for cooling).

    The loop mirrors the exact logic of ``case_custom/run_python.py``
    lines 120-238: the first equilibration is at T_liquidus - 1 with P
    interpolated for that T, then each subsequent step applies dT and dP.
    """
    session = MeltsSession(config.melts_mode)
    session.set_composition(config.composition)
    session.set_system_properties(config)

    # Find liquidus — yield a sentinel with step=-1 so the caller knows
    T_liq = session.find_liquidus(config.T_start, config.P_start)
    yield StepResult(
        step=-1, T=T_liq, P=config.P_start,
        liquid_mass=0, solid_mass=0,
        liquid_comp={}, solid_comp={}, bulk_comp={},
        phases=[], phase_details=[],
        logfO2=0, rho_liq=0, viscosity=0,
        H_total=0, S_total=0, V_total=0, Cp_total=0, rho_sol=0,
    )

    # Compute per-step pressure increment (linear P-T path)
    n_steps = int((config.T_start - config.T_end) / abs(config.dT))
    dP = (config.P_end - config.P_start) / n_steps

    # Initialise T and P — start just below the liquidus
    T = T_liq - 1
    # Interpolate P for this starting T along the (T_start, P_start)->(T_end, P_end) line
    P = config.P_start + (T - config.T_start) * (config.P_end - config.P_start) / (config.T_end - config.T_start)
    step = 0

    while T >= config.T_end:
        result = session.equilibrate(T, P, step=step)

        if session.failed:
            break

        yield result

        T += config.dT   # dT is negative for cooling
        P += dP
        step += 1
