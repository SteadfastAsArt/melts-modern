"""Smoke tests for all 15 Plotly figure builders in bindplotly.py.

Each test creates a minimal mock DataFrame and verifies the function
returns a plotly Figure without crashing.
"""
import sys
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meltsapp.plotting.bindplotly import (
    _base_layout,
    _axis_style,
    fig_tas,
    fig_harker_mgo,
    fig_harker_sio2,
    fig_pt_path,
    fig_afm,
    fig_evolution,
    fig_phase_masses,
    fig_liquid_vs_temp,
    fig_system_thermo,
    fig_density,
    fig_olivine,
    fig_cpx,
    fig_plagioclase,
    fig_spinel,
    fig_mg_vs_sio2,
)
from meltsapp import OX


# ---------------------------------------------------------------------------
# Fixture: mock simulation DataFrame
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_df():
    """Create a minimal DataFrame that mimics worker.py output."""
    n = 20
    t_range = np.linspace(1300, 1100, n)
    df = pd.DataFrame({
        "step": range(n),
        "T_C": t_range,
        "P_bar": np.linspace(2000, 1500, n),
        "mass_liquid_g": np.linspace(100, 50, n),
        "mass_solid_g": np.linspace(0, 50, n),
        "logfO2": np.linspace(-8, -10, n),
        "rho_liq": np.full(n, 2700.0),
        "viscosity": np.linspace(2.0, 4.0, n),
        "phases": ["olivine1+spinel1"] * 5 + ["olivine1+spinel1+clinopyroxene1"] * 10 + ["olivine1+spinel1+clinopyroxene1+plagioclase1"] * 5,
        "H_total": np.linspace(-1e6, -1.2e6, n),
        "S_total": np.linspace(500, 450, n),
        "V_total": np.linspace(40, 38, n),
        "Cp_total": np.linspace(200, 190, n),
        "rho_sol": np.linspace(3200, 3300, n),
    })
    # Add all liquid oxide columns
    for ox in OX:
        col = f"liq_{ox}"
        if ox == "SiO2":
            df[col] = np.linspace(48, 55, n)
        elif ox == "MgO":
            df[col] = np.linspace(10, 5, n)
        elif ox == "FeO":
            df[col] = np.linspace(8, 6, n)
        elif ox == "Fe2O3":
            df[col] = np.linspace(1, 0.8, n)
        elif ox == "Al2O3":
            df[col] = np.linspace(16, 18, n)
        elif ox == "CaO":
            df[col] = np.linspace(12, 8, n)
        elif ox == "Na2O":
            df[col] = np.linspace(2, 3.5, n)
        elif ox == "K2O":
            df[col] = np.linspace(0.1, 0.3, n)
        elif ox == "TiO2":
            df[col] = np.linspace(1, 1.5, n)
        elif ox == "H2O":
            df[col] = np.linspace(0.5, 1.5, n)
        elif ox == "P2O5":
            df[col] = np.linspace(0.1, 0.15, n)
        else:
            df[col] = np.zeros(n)
    return df


@pytest.fixture
def mock_phase_data():
    """Create a minimal long-form phase DataFrame."""
    rows = []
    for i, T in enumerate(np.linspace(1300, 1100, 20)):
        # Olivine present throughout
        rows.append({
            "step": i, "T_C": T, "phase": "olivine1", "mass": 2.0 + i * 0.5,
            "SiO2": 40.0, "MgO": 45.0, "FeO": 12.0, "Al2O3": 0.5, "CaO": 0.3,
            **{ox: 0.0 for ox in OX if ox not in ("SiO2", "MgO", "FeO", "Al2O3", "CaO")},
        })
        # CPX appears after step 5
        if i >= 5:
            rows.append({
                "step": i, "T_C": T, "phase": "clinopyroxene1", "mass": 1.0 + i * 0.3,
                "SiO2": 52.0, "MgO": 16.0, "FeO": 5.0, "Al2O3": 4.0, "CaO": 20.0,
                **{ox: 0.0 for ox in OX if ox not in ("SiO2", "MgO", "FeO", "Al2O3", "CaO")},
            })
        # Plagioclase appears after step 10
        if i >= 10:
            rows.append({
                "step": i, "T_C": T, "phase": "plagioclase1", "mass": 0.5 + i * 0.2,
                "SiO2": 55.0, "MgO": 0.1, "FeO": 0.5, "Al2O3": 28.0, "CaO": 10.0,
                "Na2O": 5.0, "K2O": 0.3,
                **{ox: 0.0 for ox in OX if ox not in ("SiO2", "MgO", "FeO", "Al2O3", "CaO", "Na2O", "K2O")},
            })
        # Spinel
        rows.append({
            "step": i, "T_C": T, "phase": "spinel1", "mass": 0.05,
            "SiO2": 0.0, "MgO": 10.0, "FeO": 30.0, "Al2O3": 50.0, "CaO": 0.0,
            "Cr2O3": 8.0, "TiO2": 2.0,
            **{ox: 0.0 for ox in OX if ox not in ("SiO2", "MgO", "FeO", "Al2O3", "CaO", "Cr2O3", "TiO2")},
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests: styling constants
# ---------------------------------------------------------------------------
class TestStyling:
    def test_base_layout_font(self):
        layout = _base_layout()
        assert "Inter" in layout["font"]["family"]

    def test_base_layout_bgcolor(self):
        layout = _base_layout()
        assert layout["plot_bgcolor"] == "#fafbfc"
        assert layout["paper_bgcolor"] == "#fafbfc"

    def test_base_layout_hoverlabel(self):
        layout = _base_layout()
        assert "hoverlabel" in layout
        assert layout["hoverlabel"]["bgcolor"] == "white"

    def test_axis_style_gridcolor(self):
        style = _axis_style()
        assert style["gridcolor"] == "#e8ecf0"


# ---------------------------------------------------------------------------
# Tests: figure smoke tests (each fig_ returns a Figure)
# ---------------------------------------------------------------------------
class TestFigures:
    def test_fig_tas(self, mock_df):
        fig = fig_tas(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_harker_mgo(self, mock_df):
        fig = fig_harker_mgo(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_harker_sio2(self, mock_df):
        fig = fig_harker_sio2(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_pt_path(self, mock_df):
        fig = fig_pt_path(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_afm(self, mock_df):
        fig = fig_afm(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_evolution(self, mock_df):
        fig = fig_evolution(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_phase_masses(self, mock_df, mock_phase_data):
        fig = fig_phase_masses(mock_df, mock_phase_data)
        assert isinstance(fig, go.Figure)

    def test_fig_liquid_vs_temp(self, mock_df):
        fig = fig_liquid_vs_temp(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_system_thermo(self, mock_df):
        fig = fig_system_thermo(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_density(self, mock_df):
        fig = fig_density(mock_df)
        assert isinstance(fig, go.Figure)

    def test_fig_olivine(self, mock_phase_data):
        fig = fig_olivine(mock_phase_data)
        assert isinstance(fig, go.Figure)

    def test_fig_cpx(self, mock_phase_data):
        fig = fig_cpx(mock_phase_data)
        assert isinstance(fig, go.Figure)

    def test_fig_plagioclase(self, mock_phase_data):
        fig = fig_plagioclase(mock_phase_data)
        assert isinstance(fig, go.Figure)

    def test_fig_spinel(self, mock_phase_data):
        fig = fig_spinel(mock_phase_data)
        assert isinstance(fig, go.Figure)

    def test_fig_mg_vs_sio2(self, mock_df):
        fig = fig_mg_vs_sio2(mock_df)
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# Tests: empty phase data edge case
# ---------------------------------------------------------------------------
class TestEmptyPhaseData:
    def test_fig_olivine_empty(self):
        """Olivine plot with no olivine data should not crash."""
        empty = pd.DataFrame(columns=["step", "T_C", "phase", "mass"] + list(OX))
        fig = fig_olivine(empty)
        assert isinstance(fig, go.Figure)

    def test_fig_cpx_empty(self):
        empty = pd.DataFrame(columns=["step", "T_C", "phase", "mass"] + list(OX))
        fig = fig_cpx(empty)
        assert isinstance(fig, go.Figure)

    def test_fig_plagioclase_empty(self):
        empty = pd.DataFrame(columns=["step", "T_C", "phase", "mass"] + list(OX))
        fig = fig_plagioclase(empty)
        assert isinstance(fig, go.Figure)

    def test_fig_spinel_empty(self):
        empty = pd.DataFrame(columns=["step", "T_C", "phase", "mass"] + list(OX))
        fig = fig_spinel(empty)
        assert isinstance(fig, go.Figure)
