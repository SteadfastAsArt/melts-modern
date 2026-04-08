"""
Shared data constants and utility functions for MELTS plotting module.

Contains TAS boundaries, AFM coordinates, phase color mappings,
and derived-column calculators used across multiple figure types.
"""

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# Phase color mapping (base phase name -> hex color)
# ------------------------------------------------------------------
PHASE_COLORS: dict[str, str] = {
    "olivine": "#2ca02c",
    "clinopyroxene": "#1f77b4",
    "plagioclase": "#d62728",
    "spinel": "#9467bd",
    "fluid": "#17becf",
    "rhm-oxide": "#8c564b",
    "orthopyroxene": "#e377c2",
    "garnet": "#bcbd22",
}

# ------------------------------------------------------------------
# TAS boundary line segments  (Le Maitre 2002)
# Each element is a list of (SiO2, Na2O+K2O) coordinate pairs forming
# one polyline segment on the Total Alkali-Silica diagram.
# ------------------------------------------------------------------
TAS_BOUNDARIES: list[list[tuple[float, float]]] = [
    # Vertical / sub-alkaline lower boundary segments
    [(41, 0), (41, 3)],
    [(41, 3), (45, 5)],
    [(45, 0), (45, 5)],
    [(52, 0), (52, 5)],
    [(57, 0), (57, 5.9)],
    [(63, 0), (63, 7)],
    [(69, 0), (69, 8)],
    # Upper alkaline boundary
    [(45, 5), (49.4, 7.3)],
    [(49.4, 7.3), (52, 5)],
    [(49.4, 7.3), (53, 9.3)],
    [(53, 9.3), (57, 5.9)],
    [(53, 9.3), (57.6, 11.7)],
    [(57.6, 11.7), (63, 7)],
    [(63, 7), (69, 8)],
]

# ------------------------------------------------------------------
# TAS field labels  {name: (x, y)}
# ------------------------------------------------------------------
TAS_LABELS: dict[str, tuple[float, float]] = {
    "Picrobasalt": (43, 1.2),
    "Basalt": (48.5, 2.2),
    "Basaltic\nAndesite": (54.5, 2.5),
    "Andesite": (60, 3.2),
    "Dacite": (66, 3.5),
    "Trachybasalt": (48.8, 5.8),
    "Basaltic\nTrachy-\nandesite": (54, 7.0),
    "Trachy-\nandesite": (59, 9.0),
}

# ------------------------------------------------------------------
# Irvine-Baragar (1971) calc-alkaline / tholeiitic dividing line
# Expressed as normalised ternary fractions (a, f, m where a+f+m=1).
# ------------------------------------------------------------------
_IB_A = np.array([0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.55])
_IB_F = np.array([0.52, 0.50, 0.49, 0.48, 0.465, 0.45, 0.43, 0.40, 0.32, 0.25])
_IB_M = 1.0 - _IB_F - _IB_A

# Pre-compute the 2-D ternary projection of the IB line
IB_LINE_X: np.ndarray = 0.5 * (2 * _IB_F + _IB_A)
IB_LINE_Y: np.ndarray = (np.sqrt(3) / 2) * _IB_A

# Also expose the raw normalised fractions for reference
IB_LINE: dict[str, np.ndarray] = {"a": _IB_A, "f": _IB_F, "m": _IB_M}


# ------------------------------------------------------------------
# Derived-column calculator
# ------------------------------------------------------------------
def calc_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns to a simulation results DataFrame.

    Expects columns with the ``liq_`` prefix (e.g. ``liq_SiO2``).
    Modifies *df* in-place and returns it for convenience.
    """
    df["FeOt"] = df["liq_FeO"] + df["liq_Fe2O3"] * 0.8998
    df["Na2O_K2O"] = df["liq_Na2O"] + df["liq_K2O"]
    df["Mg_number"] = 100.0 * (df["liq_MgO"] / 40.3) / (
        df["liq_MgO"] / 40.3 + df["liq_FeO"] / 71.85
    )
    df["liquid_frac"] = df["mass_liquid_g"] / df["mass_liquid_g"].iloc[0] * 100.0
    return df


# ------------------------------------------------------------------
# Phase-appearance detector
# ------------------------------------------------------------------
def detect_phase_events(df: pd.DataFrame) -> dict[str, float]:
    """Scan the ``phases`` column and return {phase_base_name: first T_C}.

    Trailing digits are stripped so that e.g. ``olivine1`` becomes ``olivine``.
    """
    phase_events: dict[str, float] = {}
    for _, row in df.iterrows():
        if pd.isna(row["phases"]) or str(row["phases"]).strip() == "":
            continue
        for p in str(row["phases"]).split("+"):
            base = p.rstrip("0123456789")
            if base and base not in phase_events:
                phase_events[base] = row["T_C"]
    return phase_events


# ------------------------------------------------------------------
# AFM ternary coordinate conversion
# ------------------------------------------------------------------
def afm_ternary_coords(
    A: np.ndarray | float,
    F: np.ndarray | float,
    M: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert A-F-M values to 2-D Cartesian ternary coordinates.

    The triangle has vertices::

        M = (0, 0)        — bottom-left
        F = (1, 0)        — bottom-right
        A = (0.5, sqrt3/2) — top

    Returns ``(x, y)`` arrays suitable for scatter plotting.
    """
    A = np.asarray(A, dtype=float)
    F = np.asarray(F, dtype=float)
    M = np.asarray(M, dtype=float)
    total = A + F + M
    a = A / total
    f = F / total
    # m = M / total  # not needed directly
    x = 0.5 * (2 * f + a)
    y = (np.sqrt(3) / 2) * a
    return x, y
