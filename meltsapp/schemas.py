"""
Data models for MELTS simulation configuration and results.

SimConfig — Pydantic model for validated input configuration.
PhaseDetail / StepResult — Dataclasses for output-only result data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


class SimConfig(BaseModel):
    """Validated simulation configuration for a MELTS crystallization run."""

    melts_mode: Literal[1, 2, 3, 4]
    """Calculation mode: 1=rMELTS 1.0.2, 2=pMELTS, 3=rMELTS 1.1.0, 4=rMELTS 1.2.0."""

    composition: dict[str, float]
    """Oxide name -> wt% (e.g. {'SiO2': 48.68, 'MgO': 9.10, ...})."""

    T_start: float = 1400.0
    """Starting temperature for liquidus search (°C)."""

    T_end: float = 900.0
    """Final temperature (°C)."""

    dT: float = -2.0
    """Temperature step (°C, negative for cooling)."""

    P_start: float = 5000.0
    """Starting pressure (bar)."""

    P_end: float = 1000.0
    """Final pressure (bar)."""

    fo2_buffer: str | None = None
    """Oxygen fugacity buffer name: 'FMQ', 'NNO', 'IW', 'HM', etc."""

    fo2_offset: float = 0.0
    """Log-unit offset from the fO2 buffer."""

    crystallization_mode: Literal["fractionate", "equilibrium"] = "fractionate"
    """'fractionate' removes solids each step; 'equilibrium' retains them."""

    suppress_phases: list[str] = []
    """List of phase names to suppress during the calculation."""


@dataclass
class PhaseDetail:
    """Thermodynamic and compositional data for a single phase at one step."""

    phase: str
    mass: float
    G: float
    H: float
    S: float
    V: float
    rho: float
    composition: dict[str, float]


@dataclass
class StepResult:
    """Complete output for a single equilibration step."""

    step: int
    T: float
    P: float

    liquid_mass: float
    solid_mass: float

    liquid_comp: dict[str, float]
    solid_comp: dict[str, float]
    bulk_comp: dict[str, float]

    phases: list[str]
    phase_details: list[PhaseDetail]

    logfO2: float
    rho_liq: float
    viscosity: float

    # System thermodynamic totals
    H_total: float
    S_total: float
    V_total: float
    Cp_total: float
    rho_sol: float
