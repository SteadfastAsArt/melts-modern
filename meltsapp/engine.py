"""
MeltsSession — clean wrapper around the vendor MELTSdynamic / MELTSengine API.

Handles file-descriptor redirection so the C library's raw stdout writes
go to stderr, while Python's sys.stdout remains usable for normal output.
"""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from meltsapp import OX
from meltsapp.schemas import PhaseDetail, SimConfig, StepResult

if TYPE_CHECKING:
    from meltsengine import MELTSengine


class MeltsSession:
    """Manages a single MELTS calculation session with fd redirection."""

    _eng: MELTSengine

    def __init__(self, calc_mode: int) -> None:
        # --- File-descriptor redirect ---
        # The C shared library (libalphamelts.so) writes directly to Unix fd 1.
        # We save fd 1 (the subprocess pipe) and redirect fd 1 to /dev/null
        # permanently. Python's sys.stdout is then rebuilt from the saved pipe fd.
        # This way: C library -> /dev/null, Python print() -> pipe to parent.
        self._pipe_fd = os.dup(1)           # save the real pipe
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 1)              # fd 1 -> /dev/null (C library goes here)
        os.close(devnull_fd)
        # Give Python a new stdout backed by the saved pipe fd
        sys.stdout = os.fdopen(self._pipe_fd, "w", buffering=1)  # line-buffered

        from meltsdynamic import MELTSdynamic

        self._melts = MELTSdynamic(calc_mode)
        self._eng = self._melts.engine

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def set_composition(self, comp: dict[str, float]) -> None:
        """Set bulk composition from an oxide-name -> wt% dict."""
        for ox, val in comp.items():
            self._eng.setBulkComposition(ox, val)

    def set_system_properties(self, config: SimConfig) -> None:
        """Apply fO2 buffer, crystallization mode, and phase suppression."""
        props: list[str] = []

        # Crystallization mode
        if config.crystallization_mode == "fractionate":
            props.append("Mode: Fractionate Solids")
        # "equilibrium" needs no special property string (default MELTS behaviour)

        # Oxygen-fugacity buffer
        if config.fo2_buffer is not None:
            if config.fo2_offset and config.fo2_offset != 0.0:
                props.append(f"Log fO2 Path: {config.fo2_buffer}")
                props.append(f"Log fO2 Delta: {config.fo2_offset}")
            else:
                props.append(f"Log fO2 Path: {config.fo2_buffer}")

        # Phase suppression
        for phase in config.suppress_phases:
            props.append(f"Suppress: {phase}")

        if props:
            self._eng.setSystemProperties(props)

    # ------------------------------------------------------------------
    # Liquidus
    # ------------------------------------------------------------------

    def find_liquidus(self, T_init: float, P: float) -> float:
        """Find the liquidus temperature at a given pressure.

        Returns the liquidus temperature (°C).
        """
        self._eng.temperature = T_init
        self._eng.pressure = P
        self._eng.calcEquilibriumState(0, 0)
        return float(self._eng.temperature)

    # ------------------------------------------------------------------
    # Single equilibration step
    # ------------------------------------------------------------------

    def equilibrate(self, T: float, P: float, step: int = 0) -> StepResult:
        """Run one equilibration step and return a fully-populated StepResult."""
        self._eng.temperature = T
        self._eng.pressure = P
        self._eng.calcEquilibriumState(1, 1)

        eng = self._eng

        # Gather all phase names
        all_phases: list[str] = []
        if eng.liquidNames:
            all_phases.extend(eng.liquidNames)
        if eng.solidNames:
            all_phases.extend(eng.solidNames)

        # --- Liquid composition ---
        liq_mass = 0.0
        lc: dict[str, float] = {ox: 0.0 for ox in OX}
        if eng.liquidNames and "liquid1" in eng.liquidNames:
            liq_mass = float(eng.mass.get("liquid1", 0)) if eng.mass else 0.0
            lc = self._get_disp("liquid1")

        # --- Solid (mass-weighted bulk) composition ---
        sol_mass = 0.0
        sc: dict[str, float] = {ox: 0.0 for ox in OX}
        if eng.solidNames:
            for sn in eng.solidNames:
                m = float(eng.mass.get(sn, 0)) if eng.mass else 0.0
                sol_mass += m
                sd = self._get_disp(sn)
                for ox in OX:
                    sc[ox] += sd[ox] * m
            if sol_mass > 0:
                for ox in OX:
                    sc[ox] /= sol_mass

        # --- Bulk composition ---
        total_mass = liq_mass + sol_mass
        bc: dict[str, float] = {ox: 0.0 for ox in OX}
        if total_mass > 0:
            for ox in OX:
                bc[ox] = (lc[ox] * liq_mass + sc[ox] * sol_mass) / total_mass

        # --- System thermodynamic properties ---
        logfO2 = float(eng.logfO2) if eng.logfO2 else 0.0

        sys_h = sum(float(eng.h.get(p, 0)) for p in all_phases) if eng.h else 0.0
        sys_s = sum(float(eng.s.get(p, 0)) for p in all_phases) if eng.s else 0.0
        sys_v = sum(float(eng.v.get(p, 0)) for p in all_phases) if eng.v else 0.0
        sys_cp = sum(float(eng.cp.get(p, 0)) for p in all_phases) if eng.cp else 0.0

        rho_liq = (
            float(eng.rho.get("liquid1", 0))
            if eng.rho and "liquid1" in eng.rho
            else 0.0
        )

        # Composite solid density (mass / volume)
        rho_sol = 0.0
        if eng.rho and eng.solidNames:
            sol_vols: list[tuple[float, float]] = []
            for sn in eng.solidNames:
                sm = float(eng.mass.get(sn, 0)) if eng.mass else 0.0
                rho_p = (
                    float(eng.rho.get(sn, 0))
                    if eng.rho and sn in eng.rho
                    else 1.0
                )
                if rho_p > 0:
                    sol_vols.append((sm, sm / rho_p))
            if sol_vols:
                total_sm = sum(x[0] for x in sol_vols)
                total_sv = sum(x[1] for x in sol_vols)
                rho_sol = total_sm / total_sv if total_sv > 0 else 0.0

        viscosity = (
            float(eng.viscosity.get("liquid1", 0))
            if eng.viscosity and "liquid1" in eng.viscosity
            else 0.0
        )

        # --- Per-phase details ---
        phase_details: list[PhaseDetail] = []
        for phase in all_phases:
            m = float(eng.mass.get(phase, 0)) if eng.mass else 0.0
            g, h, s, v = self._get_phase_thermo(phase)
            rho_p = (
                float(eng.rho.get(phase, 0))
                if eng.rho and phase in eng.rho
                else 0.0
            )
            dc = self._get_disp(phase)
            phase_details.append(
                PhaseDetail(
                    phase=phase,
                    mass=m,
                    G=g,
                    H=h,
                    S=s,
                    V=v,
                    rho=rho_p,
                    composition=dc,
                )
            )

        return StepResult(
            step=step,
            T=T,
            P=P,
            liquid_mass=liq_mass,
            solid_mass=sol_mass,
            liquid_comp=lc,
            solid_comp=sc,
            bulk_comp=bc,
            phases=[p for p in all_phases],
            phase_details=phase_details,
            logfO2=logfO2,
            rho_liq=rho_liq,
            viscosity=viscosity,
            H_total=sys_h,
            S_total=sys_s,
            V_total=sys_v,
            Cp_total=sys_cp,
            rho_sol=rho_sol,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def engine(self) -> MELTSengine:
        """Direct access to the underlying MELTSengine instance."""
        return self._eng

    @property
    def failed(self) -> bool:
        """Whether the last calculation failed."""
        return self._eng.status.failed

    # ------------------------------------------------------------------
    # Internal helpers (ported from run_python.py get_disp / get_phase_thermo)
    # ------------------------------------------------------------------

    def _get_disp(self, phase: str) -> dict[str, float]:
        """Get dispComposition for *phase* as an oxide dict, or zeros."""
        eng = self._eng
        d = eng.dispComposition.get(phase) if eng.dispComposition else None
        if d is None:
            return {ox: 0.0 for ox in OX}
        return {OX[i]: float(d[i]) for i in range(len(OX))}

    def _get_phase_thermo(self, phase: str) -> tuple[float, float, float, float]:
        """Return (G, H, S, V) for *phase*."""
        eng = self._eng
        g = float(eng.g.get(phase, 0)) if eng.g else 0.0
        h = float(eng.h.get(phase, 0)) if eng.h else 0.0
        s = float(eng.s.get(phase, 0)) if eng.s else 0.0
        v = float(eng.v.get(phase, 0)) if eng.v else 0.0
        return g, h, s, v
