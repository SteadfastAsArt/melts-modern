"""
meltsapp — Python package for MELTS thermodynamic modeling.

Sets up the vendor alphamelts-py path and exports core constants and classes.
"""
import sys
import os

# Project root (directory containing this package) and vendor library path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR_PATH = os.path.join(PROJECT_ROOT, "alphamelts-py", "alphamelts-py-2.3.1-linux")

if _VENDOR_PATH not in sys.path:
    sys.path.insert(0, _VENDOR_PATH)

# 19 standard MELTS oxide names
OX: list[str] = [
    "SiO2", "TiO2", "Al2O3", "Fe2O3", "Cr2O3",
    "FeO", "MnO", "MgO", "NiO", "CoO",
    "CaO", "Na2O", "K2O", "P2O5", "H2O",
    "CO2", "SO3", "Cl2O-1", "F2O-1",
]

from meltsapp.schemas import MageminConfig, SimConfig, StepResult  # noqa: E402

__all__ = ["OX", "MageminConfig", "SimConfig", "StepResult", "PROJECT_ROOT"]
