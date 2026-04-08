"""
Named preset compositions and default simulation parameters.

Each preset is drawn from the demonstration scripts:
  - ``case_custom/run_python.py`` — High-Mg basalt
  - ``run_cases.py`` — N-MORB, Wet MORB, Arc Basalt, Bishop Tuff Rhyolite
"""
from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "high_mg_basalt": {
        "name": "High-Mg Basalt (3% H2O)",
        "composition": {
            "SiO2": 47.869,
            "TiO2": 0.607,
            "Al2O3": 12.044,
            "Cr2O3": 0.066,
            "Fe2O3": 0.603,
            "FeO": 9.418,
            "MnO": 0.166,
            "MgO": 17.593,
            "CaO": 10.073,
            "Na2O": 1.329,
            "K2O": 0.073,
            "NiO": 0.110,
            "P2O5": 0.049,
            "H2O": 3.000,
        },
        "defaults": {
            "T_start": 1400,
            "T_end": 900,
            "P_start": 5000,
            "P_end": 1000,
        },
    },
    "nmorb": {
        "name": "N-MORB (0.2% H2O)",
        "composition": {
            "SiO2": 48.68,
            "TiO2": 1.01,
            "Al2O3": 17.64,
            "Fe2O3": 0.89,
            "Cr2O3": 0.03,
            "FeO": 7.59,
            "MgO": 9.10,
            "CaO": 12.45,
            "Na2O": 2.65,
            "K2O": 0.03,
            "P2O5": 0.08,
            "H2O": 0.20,
        },
        "defaults": {
            "T_start": 1300,
            "T_end": 1000,
            "P_start": 1000,
            "P_end": 1000,
        },
    },
    "wet_morb": {
        "name": "N-MORB (2.0% H2O)",
        "composition": {
            "SiO2": 48.68,
            "TiO2": 1.01,
            "Al2O3": 17.64,
            "Fe2O3": 0.89,
            "Cr2O3": 0.03,
            "FeO": 7.59,
            "MgO": 9.10,
            "CaO": 12.45,
            "Na2O": 2.65,
            "K2O": 0.03,
            "P2O5": 0.08,
            "H2O": 2.00,
        },
        "defaults": {
            "T_start": 1300,
            "T_end": 1000,
            "P_start": 2000,
            "P_end": 2000,
        },
    },
    "arc_basalt": {
        "name": "Arc Basalt (3% H2O)",
        "composition": {
            "SiO2": 51.0,
            "TiO2": 0.80,
            "Al2O3": 16.5,
            "Fe2O3": 1.50,
            "FeO": 6.50,
            "MgO": 8.00,
            "CaO": 10.50,
            "Na2O": 2.80,
            "K2O": 0.50,
            "P2O5": 0.15,
            "H2O": 3.0,
        },
        "defaults": {
            "T_start": 1300,
            "T_end": 800,
            "P_start": 3000,
            "P_end": 3000,
        },
    },
    "bishop_tuff_rhyolite": {
        "name": "Bishop Tuff Rhyolite (5.5% H2O)",
        "composition": {
            "SiO2": 77.5,
            "TiO2": 0.08,
            "Al2O3": 12.5,
            "Fe2O3": 0.21,
            "FeO": 0.47,
            "MgO": 0.03,
            "CaO": 0.43,
            "Na2O": 3.98,
            "K2O": 4.88,
            "H2O": 5.5,
        },
        "defaults": {
            "T_start": 900,
            "T_end": 650,
            "P_start": 2000,
            "P_end": 2000,
        },
    },
}
