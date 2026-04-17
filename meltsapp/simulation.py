"""
High-level simulation runner for MELTS crystallization paths.

The main entry point is ``run_crystallization(config)`` which yields one
``StepResult`` per step along the selected P-T path mode.

Supported path modes:
  - isobaric: constant P, step T from T_start toward T_end by dT
  - isothermal: constant T, step P from P_start toward P_end by dP
  - polybaric: linear P-T path, step T by dT with P interpolated
  - isentropic: adiabatic (constant entropy) decompression, step P by dP
"""
from __future__ import annotations

from typing import Generator

from meltsapp.engine import MeltsSession
from meltsapp.schemas import SimConfig, StepResult


def run_crystallization(config: SimConfig) -> Generator[StepResult, None, None]:
    """Run a crystallization path, yielding one StepResult per step.

    Dispatches to the appropriate path-mode implementation based on
    ``config.path_mode``.
    """
    session = MeltsSession(config.melts_mode)
    session.set_composition(config.composition)
    session.set_system_properties(config)

    # Determine the output flag from crystallization mode:
    # fractionate -> 1, equilibrium -> 0
    output_flag = 1 if config.crystallization_mode == "fractionate" else 0

    if config.path_mode == "isobaric":
        yield from _run_isobaric(session, config, output_flag)
    elif config.path_mode == "isothermal":
        yield from _run_isothermal(session, config, output_flag)
    elif config.path_mode == "polybaric":
        yield from _run_polybaric(session, config, output_flag)
    elif config.path_mode == "isentropic":
        yield from _run_isentropic(session, config, output_flag)
    else:
        raise ValueError(f"Unknown path_mode: {config.path_mode!r}")


# ---------------------------------------------------------------------------
# Liquidus sentinel helper
# ---------------------------------------------------------------------------

def _liquidus_sentinel(T_liq: float, P: float) -> StepResult:
    """Create a sentinel StepResult (step=-1) carrying the liquidus temperature."""
    return StepResult(
        step=-1, T=T_liq, P=P,
        liquid_mass=0, solid_mass=0,
        liquid_comp={}, solid_comp={}, bulk_comp={},
        phases=[], phase_details=[],
        logfO2=0, rho_liq=0, viscosity=0,
        H_total=0, S_total=0, V_total=0, Cp_total=0, rho_sol=0,
    )


# ---------------------------------------------------------------------------
# Path mode implementations
# ---------------------------------------------------------------------------

def _run_isobaric(
    session: MeltsSession, config: SimConfig, output_flag: int,
) -> Generator[StepResult, None, None]:
    """Constant pressure, varying temperature (standard cooling path)."""
    P = config.P_start  # constant

    T_liq = session.find_liquidus(config.T_start, P)
    yield _liquidus_sentinel(T_liq, P)

    T = T_liq - 1
    step = 0

    while T >= config.T_end:
        result = session.equilibrate(T, P, step=step, run_mode=1,
                                     output_flag=output_flag)
        if session.failed:
            break
        yield result
        T += config.dT  # dT is negative for cooling
        step += 1


def _run_isothermal(
    session: MeltsSession, config: SimConfig, output_flag: int,
) -> Generator[StepResult, None, None]:
    """Constant temperature, varying pressure (decompression / compression)."""
    T = config.T_start  # constant

    T_liq = session.find_liquidus(T, config.P_start)
    yield _liquidus_sentinel(T_liq, config.P_start)

    P = config.P_start
    step = 0

    while (config.dP < 0 and P >= config.P_end) or \
          (config.dP > 0 and P <= config.P_end):
        result = session.equilibrate(T, P, step=step, run_mode=1,
                                     output_flag=output_flag)
        if session.failed:
            break
        yield result
        P += config.dP
        step += 1


def _run_polybaric(
    session: MeltsSession, config: SimConfig, output_flag: int,
) -> Generator[StepResult, None, None]:
    """Linear P-T path — the original behaviour before path modes were added.

    Both T and P change linearly from (T_start, P_start) to (T_end, P_end),
    stepping by dT in temperature and interpolating P accordingly.
    """
    T_liq = session.find_liquidus(config.T_start, config.P_start)
    yield _liquidus_sentinel(T_liq, config.P_start)

    # Compute per-step pressure increment (linear P-T path)
    n_steps = int((config.T_start - config.T_end) / abs(config.dT))
    dP = (config.P_end - config.P_start) / n_steps if n_steps > 0 else 0

    # Initialise T and P — start just below the liquidus
    T = T_liq - 1
    # Interpolate P for this starting T along the line
    if abs(config.T_end - config.T_start) > 0.01:
        P = config.P_start + (T - config.T_start) * (
            config.P_end - config.P_start
        ) / (config.T_end - config.T_start)
    else:
        P = config.P_start
    step = 0

    while T >= config.T_end:
        result = session.equilibrate(T, P, step=step, run_mode=1,
                                     output_flag=output_flag)
        if session.failed:
            break
        yield result
        T += config.dT  # dT is negative for cooling
        P += dP
        step += 1


def _run_isentropic(
    session: MeltsSession, config: SimConfig, output_flag: int,
) -> Generator[StepResult, None, None]:
    """Adiabatic (constant entropy) decompression.

    The first step establishes the reference entropy at (T_start, P_start)
    using standard equilibration (runMode=1).  Subsequent steps change P by
    dP and use isentropic mode (runMode=3) so the engine solves for T.
    """
    T_liq = session.find_liquidus(config.T_start, config.P_start)
    yield _liquidus_sentinel(T_liq, config.P_start)

    # Initial equilibration at just below the liquidus to set reference entropy
    T = T_liq - 1
    result = session.equilibrate(T, config.P_start, step=0, run_mode=1,
                                 output_flag=output_flag)
    if session.failed:
        return
    yield result

    # Now step in P using isentropic mode (runMode=3)
    P = config.P_start + config.dP
    step = 1

    while (config.dP < 0 and P >= config.P_end) or \
          (config.dP > 0 and P <= config.P_end):
        result = session.equilibrate(T, P, step=step, run_mode=3,
                                     output_flag=output_flag)
        if session.failed:
            break
        yield result
        P += config.dP
        step += 1
