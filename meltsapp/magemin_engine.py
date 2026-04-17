"""
MAGEMin computation engine using PetThermoTools.

Converts MageminConfig to PetThermoTools API calls and returns results
as step dicts compatible with the existing MELTS frontend format.

PetThermoTools wraps the MAGEMin Gibbs free-energy minimizer (Holland-Powell
database) via Julia/JuliaCall. The first invocation is slow due to Julia JIT
compilation; subsequent calls within the same process are faster.
"""
from __future__ import annotations

import os
import sys
import traceback

import numpy as np
import pandas as pd

from meltsapp import OX
from meltsapp.schemas import MageminConfig


def _setup_julia() -> None:
    """Ensure Julia is properly configured before importing PetThermoTools."""
    os.environ["JULIA_DEPOT_PATH"] = os.path.expanduser("~/.julia")
    julia_bin = os.path.expanduser("~/julia/bin")
    if julia_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = julia_bin + ":" + os.environ.get("PATH", "")


def _config_to_ptt_bulk(config: MageminConfig) -> dict[str, float]:
    """Convert MageminConfig composition to PetThermoTools format.

    PetThermoTools expects a dict with keys like 'SiO2_Liq', 'Al2O3_Liq', etc.
    comp_fix() inside PetThermoTools normalises and handles Fe speciation
    automatically, so we can pass plain oxide names and let it do the work.

    MAGEMin uses FeOt (total iron as FeO) + Fe3+/FeT ratio, not separate
    FeO/Fe2O3. We compute FeOt from any FeO + Fe2O3 in the input composition.
    """
    comp = config.composition

    # Calculate FeOt (total iron as FeO)
    fe2o3 = comp.get("Fe2O3", 0.0)
    feo = comp.get("FeO", 0.0)
    feot = comp.get("FeOt", 0.0)
    if feot == 0.0:
        # Convert Fe2O3 to FeO equivalent: Fe2O3 -> 2*FeO ratio = 0.8998
        feot = feo + fe2o3 * 0.8998

    bulk = {
        "SiO2_Liq": comp.get("SiO2", 0.0),
        "TiO2_Liq": comp.get("TiO2", 0.0),
        "Al2O3_Liq": comp.get("Al2O3", 0.0),
        "CaO_Liq": comp.get("CaO", 0.0),
        "MgO_Liq": comp.get("MgO", 0.0),
        "FeOt_Liq": feot,
        "K2O_Liq": comp.get("K2O", 0.0),
        "Na2O_Liq": comp.get("Na2O", 0.0),
        "Cr2O3_Liq": comp.get("Cr2O3", 0.0),
        "H2O_Liq": comp.get("H2O", 0.0),
        "Fe3Fet_Liq": config.fe3fet,
    }

    return bulk


# Phase name mapping: MAGEMin short names -> MELTS-style long names
_MAGEMIN_PHASE_MAP = {
    "liquid1": "liquid",
    "olivine1": "olivine",
    "orthopyroxene1": "orthopyroxene",
    "clinopyroxene1": "clinopyroxene",
    "garnet1": "garnet",
    "spinel1": "spinel",
    "feldspar1": "feldspar",
    "plagioclase1": "plagioclase",
    "fluid1": "fluid",
    "rhm-oxide1": "rhm-oxide",
}


def run_magemin(config: MageminConfig, emit_fn) -> None:
    """Run a MAGEMin simulation and emit results via emit_fn.

    Args:
        config: MageminConfig instance.
        emit_fn: callback(dict) to emit JSON messages to the parent process.
    """
    _setup_julia()

    try:
        import petthermotools as ptt
    except ImportError as e:
        emit_fn({
            "type": "error",
            "message": (
                f"Failed to import PetThermoTools: {e}. "
                "Make sure PetThermoTools is installed and MAGEMinCalc is set up "
                "(run ptt.install_MAGEMinCalc() in a Python shell)."
            ),
        })
        return

    bulk = _config_to_ptt_bulk(config)

    # Activate the Julia environment for MAGEMin
    emit_fn({
        "type": "init",
        "n_steps": 0,
        "message": "Activating Julia environment (first run may take 1-2 minutes)...",
    })

    try:
        ptt.activate_petthermotools_env()
    except Exception as e:
        emit_fn({
            "type": "error",
            "message": (
                f"Failed to activate Julia/MAGEMin environment: {e}. "
                "Try running ptt.install_MAGEMinCalc() to install or update."
            ),
        })
        return

    # Common kwargs for PetThermoTools
    kwargs = {
        "Model": config.model,
        "bulk": bulk,
        "Frac_solid": config.crystallization_mode == "fractionate",
        "find_liquidus": config.find_liquidus,
        "Fe3Fet_init": config.fe3fet,
        "timeout": 600,
        "multi_processing": False,
    }

    # Phase suppression
    if config.suppress_phases:
        kwargs["Suppress"] = config.suppress_phases
    else:
        kwargs["Suppress"] = ["rutile", "tridymite"]

    if config.h2o_init is not None:
        kwargs["H2O_init"] = config.h2o_init
    if config.co2_init is not None:
        kwargs["CO2_init"] = config.co2_init
    if config.fO2_buffer:
        kwargs["fO2_buffer"] = config.fO2_buffer
        if config.fO2_offset:
            kwargs["fO2_offset"] = config.fO2_offset

    emit_fn({
        "type": "init",
        "n_steps": 0,
        "message": f"Running MAGEMin ({config.model}) crystallization...",
    })

    try:
        if config.path_mode == "isobaric":
            results = ptt.isobaric_crystallisation(
                T_start_C=config.T_start,
                T_end_C=config.T_end,
                dt_C=config.dT,
                P_bar=config.P_start,
                **kwargs,
            )
        elif config.path_mode == "isothermal":
            results = ptt.isothermal_decompression(
                T_C=config.T_start,
                P_start_bar=config.P_start,
                P_end_bar=config.P_end,
                dp_bar=config.dP,
                **kwargs,
            )
        elif config.path_mode == "polybaric":
            results = ptt.polybaric_crystallisation_path(
                T_start_C=config.T_start,
                T_end_C=config.T_end,
                dt_C=config.dT,
                P_start_bar=config.P_start,
                P_end_bar=config.P_end,
                dp_bar=config.dP,
                **kwargs,
            )
        else:
            emit_fn({"type": "error", "message": f"Unknown path mode: {config.path_mode}"})
            return
    except Exception as e:
        emit_fn({
            "type": "error",
            "message": f"MAGEMin calculation failed: {e}\n{traceback.format_exc()}",
        })
        return

    # Convert PetThermoTools results to our step format
    _emit_results(results, emit_fn)


def _emit_results(results: dict, emit_fn) -> None:
    """Convert PetThermoTools result dict to JSON step messages.

    Actual PetThermoTools result dict (after ``stich``) structure::

        Conditions — DataFrame: T_C, P_bar, mass_g, H_J, S_J/K, V_cm^3,
                     rho_kg/m^3, log10(fO2), eta_Pa.s, cp_J/kg/K, ...
        liquid1    — DataFrame: SiO2_Liq, TiO2_Liq, Al2O3_Liq, Cr2O3_Liq,
                     FeOt_Liq, MgO_Liq, CaO_Liq, Na2O_Liq, K2O_Liq,
                     H2O_Liq, Fe3Fet_Liq  (NaN when liquid absent)
        liquid1_prop — DataFrame: mass_g, rho_kg/m^3, V_cm^3, ...
        olivine1   — DataFrame: SiO2_Ol, TiO2_Ol, ... (NaN when absent)
        olivine1_prop — mass_g, rho_kg/m^3, ...
        mass_g     — DataFrame with one column per phase (liquid1, olivine1, ...)
        PhaseList  — Series of comma-separated phase labels per step
        All, volume_cm3, rho_kg/m3 — aggregate DataFrames
    """
    if not results:
        emit_fn({"type": "error", "message": "MAGEMin returned no results"})
        return

    if "Conditions" not in results:
        emit_fn({"type": "error", "message": "No 'Conditions' key in MAGEMin results"})
        return

    conditions = results["Conditions"]
    if conditions is None or len(conditions) == 0:
        emit_fn({"type": "error", "message": "Empty Conditions in MAGEMin results"})
        return

    n_steps = len(conditions)
    emit_fn({
        "type": "init",
        "n_steps": n_steps,
        "message": f"MAGEMin calculation complete. Processing {n_steps} steps...",
    })

    # Identify solid-phase keys: everything that has a matching _prop DataFrame,
    # excluding liquid, and is not a meta key.
    meta_keys = {
        "Conditions", "Input", "sys", "All",
        "mass_g", "volume_cm3", "rho_kg/m3", "PhaseList",
    }
    phase_keys = [
        k for k in results
        if k not in meta_keys
        and not k.endswith("_prop")
        and k != "liquid1"
        and (k + "_prop") in results
        and isinstance(results[k], pd.DataFrame)
    ]

    # Mass DataFrame for quick phase-mass look-up
    mass_df = results.get("mass_g", None)

    for i in range(n_steps):
        T_C = float(conditions["T_C"].iloc[i])
        P_bar = float(conditions["P_bar"].iloc[i])

        # ---------------------------------------------------------------
        # System-level properties from Conditions
        # ---------------------------------------------------------------
        mass_total = _safe_float(conditions, "mass_g", i)
        logfO2 = _safe_float(conditions, "log10(fO2)", i)
        H_total = _safe_float(conditions, "H_J", i)
        S_total = _safe_float(conditions, "S_J/K", i)
        V_total = _safe_float(conditions, "V_cm^3", i)
        rho_sys = _safe_float(conditions, "rho_kg/m^3", i)
        Cp_total = _safe_float(conditions, "cp_J/kg/K", i, 0.0)
        viscosity = _safe_float(conditions, "eta_Pa.s", i, 0.0)

        # ---------------------------------------------------------------
        # Liquid composition  (liquid1 DataFrame, columns *_Liq)
        # ---------------------------------------------------------------
        mass_liquid = 0.0
        rho_liq = 0.0
        feot_liq = 0.0
        fe3fet_liq = 0.0

        # We build the full MELTS-style liq_ dict for all 19 standard OX
        liq_out: dict[str, float] = {f"liq_{ox}": 0.0 for ox in OX}

        liq_df = results.get("liquid1")
        liq_prop = results.get("liquid1_prop")

        if liq_prop is not None and i < len(liq_prop):
            mass_liquid = _safe_float(liq_prop, "mass_g", i)
            rho_liq = _safe_float(liq_prop, "rho_kg/m^3", i)

        if liq_df is not None and i < len(liq_df) and mass_liquid > 0.001:
            # Columns are SiO2_Liq, TiO2_Liq, Al2O3_Liq, Cr2O3_Liq,
            # FeOt_Liq, MgO_Liq, CaO_Liq, Na2O_Liq, K2O_Liq, H2O_Liq,
            # Fe3Fet_Liq
            _LIQ_COL_MAP = {
                "SiO2_Liq": "SiO2",
                "TiO2_Liq": "TiO2",
                "Al2O3_Liq": "Al2O3",
                "Cr2O3_Liq": "Cr2O3",
                "MgO_Liq": "MgO",
                "CaO_Liq": "CaO",
                "Na2O_Liq": "Na2O",
                "K2O_Liq": "K2O",
                "H2O_Liq": "H2O",
            }
            for src_col, ox in _LIQ_COL_MAP.items():
                if src_col in liq_df.columns:
                    v = liq_df[src_col].iloc[i]
                    liq_out[f"liq_{ox}"] = float(v) if pd.notna(v) else 0.0

            # Iron speciation: back-calculate FeO and Fe2O3 from FeOt + Fe3Fet
            feot_liq = _safe_float_df(liq_df, "FeOt_Liq", i)
            fe3fet_liq = _safe_float_df(liq_df, "Fe3Fet_Liq", i)

            if feot_liq > 0:
                # Fe3Fet = mass-fraction of total-iron-as-FeO that is Fe3+
                # FeO (as Fe2+) = FeOt * (1 - Fe3Fet)
                # Fe2O3 = FeOt * Fe3Fet / 0.8998
                liq_out["liq_FeO"] = feot_liq * (1.0 - fe3fet_liq)
                liq_out["liq_Fe2O3"] = feot_liq * fe3fet_liq / 0.8998
            else:
                liq_out["liq_FeO"] = 0.0
                liq_out["liq_Fe2O3"] = 0.0

        # Solid mass
        mass_solid = max(0.0, mass_total - mass_liquid) if mass_total > 0 else 0.0

        # ---------------------------------------------------------------
        # Phase details (solid phases) and active-phase list
        # ---------------------------------------------------------------
        phase_details: list[dict] = []
        active_phases: list[str] = []

        for pk in phase_keys:
            # Get mass from the mass_g summary DataFrame (most reliable)
            if mass_df is not None and pk in mass_df.columns:
                phase_mass = _safe_float(mass_df, pk, i)
            else:
                prop_df = results.get(pk + "_prop")
                phase_mass = _safe_float(prop_df, "mass_g", i) if prop_df is not None and i < len(prop_df) else 0.0

            if phase_mass < 0.001:
                continue

            active_phases.append(pk)

            # Build phase-detail entry with OX columns (unsuffixed)
            pd_entry: dict[str, object] = {"phase": pk, "mass": phase_mass}
            phase_comp_df = results.get(pk)
            if phase_comp_df is not None and i < len(phase_comp_df):
                # Columns are like SiO2_Ol, TiO2_Ol, ... — strip suffix
                for col in phase_comp_df.columns:
                    v = phase_comp_df[col].iloc[i]
                    if pd.isna(v):
                        continue
                    # Strip the phase suffix: "SiO2_Ol" -> "SiO2"
                    base_ox = col.rsplit("_", 1)[0]
                    # Map FeOt -> FeO for compatibility
                    if base_ox == "FeOt":
                        base_ox = "FeO"
                    if base_ox in OX or base_ox == "Fe3Fet":
                        pd_entry[base_ox] = float(v)

            # Fill any missing OX with 0.0
            for ox in OX:
                if ox not in pd_entry:
                    pd_entry[ox] = 0.0

            phase_details.append(pd_entry)

        # Build +delimited phase string (liquid first, then solids)
        all_phases: list[str] = []
        if mass_liquid > 0.01:
            all_phases.append("liquid1")
        all_phases.extend(active_phases)

        step_msg = {
            "type": "step",
            "step": i,
            "T_C": T_C,
            "P_bar": P_bar,
            "mass_liquid_g": mass_liquid,
            "mass_solid_g": mass_solid,
            "phases": "+".join(all_phases),
            "phase_details": phase_details,
            "logfO2": logfO2,
            "rho_liq": rho_liq,
            "viscosity": viscosity,
            "H_total": H_total,
            "S_total": S_total,
            "V_total": V_total,
            "Cp_total": Cp_total,
            "rho_sol": rho_sys if mass_liquid < 0.01 else 0.0,
        }

        # Merge liq_ oxide columns at top level for MELTS plot compatibility
        step_msg.update(liq_out)

        emit_fn(step_msg)

    emit_fn({"type": "done"})


def _safe_float(df: pd.DataFrame, col: str, idx: int, default: float = 0.0) -> float:
    """Safely extract a float value from a DataFrame by column name."""
    if df is None or col not in df.columns or idx >= len(df):
        return default
    val = df[col].iloc[idx]
    if pd.isna(val):
        return default
    return float(val)


def _safe_float_df(df: pd.DataFrame, col: str, idx: int, default: float = 0.0) -> float:
    """Alias for _safe_float for use in liquid composition extraction."""
    return _safe_float(df, col, idx, default)
