"""
Data models for MELTS and MAGEMin simulation configuration and results.

SimConfig — Pydantic model for validated MELTS input configuration.
MageminConfig — Pydantic model for validated MAGEMin input configuration.
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

    path_mode: Literal["isobaric", "isothermal", "polybaric", "isentropic"] = "isobaric"
    """Path mode: how to step through T-P space.

    - isobaric: constant P, step T from T_start to T_end by dT
    - isothermal: constant T, step P from P_start to P_end by dP
    - polybaric: linear P-T path, step T by dT with P interpolated
    - isentropic: adiabatic (constant entropy) decompression, step P by dP
    """

    dP: float = -100.0
    """Pressure step (bar, negative for decompression). Used in isothermal/isentropic modes."""

    fo2_buffer: str | None = None
    """Oxygen fugacity buffer name: 'FMQ', 'NNO', 'IW', 'HM', etc."""

    fo2_offset: float = 0.0
    """Log-unit offset from the fO2 buffer."""

    crystallization_mode: Literal["fractionate", "equilibrium"] = "fractionate"
    """'fractionate' removes solids each step; 'equilibrium' retains them."""

    suppress_phases: list[str] = []
    """List of phase names to suppress during the calculation."""


class MageminConfig(BaseModel):
    """Validated simulation configuration for a MAGEMin crystallization run."""

    model: Literal["Green2025", "Weller2024"] = "Green2025"
    """Thermodynamic database: Green et al. 2025 or Weller et al. 2024."""

    path_mode: Literal["isobaric", "isothermal", "polybaric"] = "isobaric"
    """Simulation path mode."""

    composition: dict[str, float]
    """Oxide name -> wt% (e.g. {'SiO2': 48.68, 'Al2O3': 17.64, ...})."""

    fe3fet: float = 0.1
    """Fe3+/FeT ratio (0-1). MAGEMin uses FeOt + Fe3Fet instead of separate FeO/Fe2O3."""

    T_start: float = 1300.0
    T_end: float = 900.0
    dT: float = 2.0
    """Temperature range and step (deg C). dT is positive (step size)."""

    P_start: float = 5000.0
    P_end: float = 5000.0
    dP: float = 100.0
    """Pressure range and step (bar)."""

    crystallization_mode: Literal["fractionate", "equilibrium"] = "fractionate"

    fO2_buffer: str | None = None
    fO2_offset: float = 0.0

    suppress_phases: list[str] = []

    find_liquidus: bool = True
    """Whether to find the liquidus before starting the path."""

    h2o_init: float | None = None
    """Initial H2O content (wt%). If None, uses H2O from composition."""

    co2_init: float | None = None
    """Initial CO2 content (wt%). If None, no CO2."""


class SweepParam(BaseModel):
    """A single parameter sweep configuration."""

    param: Literal["H2O", "pressure", "fo2_offset", "temperature"]
    """Which parameter to vary across runs."""

    values: list[float]
    """Explicit values to use for each run."""

    labels: list[str] = []
    """Optional labels for each value (auto-generated if empty)."""


class BatchConfig(BaseModel):
    """Configuration for a batch of simulations with parameter sweeps."""

    base_config: SimConfig
    """The base simulation configuration (all shared parameters)."""

    sweep: SweepParam
    """The parameter to sweep across runs."""


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
