"""
Plotly figure builders for MELTS thermodynamic modelling results.

Every public function accepts a pandas DataFrame (or phase-data DataFrame)
and returns a fully configured ``plotly.graph_objects.Figure``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .common import (
    PHASE_COLORS,
    TAS_BOUNDARIES,
    TAS_LABELS,
    IB_LINE_X,
    IB_LINE_Y,
    calc_derived,
    detect_phase_events,
    afm_ternary_coords,
)

# ------------------------------------------------------------------
# Shared style helpers
# ------------------------------------------------------------------

_FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
_FONT_TITLE = 14
_FONT_AXIS = 10
_MARKER_SIZE = 5
_LINE_WIDTH_DATA = 2
_LINE_WIDTH_BOUNDARY = 1.5
_COLORSCALE_T = "RdYlBu_r"
_COLORSCALE_MELT = "plasma"


def _base_layout(**overrides) -> dict:
    """Return common layout kwargs."""
    defaults = dict(
        plot_bgcolor="#fafbfc",
        paper_bgcolor="#fafbfc",
        font=dict(family=_FONT_FAMILY, size=_FONT_AXIS),
        title_font=dict(family=_FONT_FAMILY, size=_FONT_TITLE),
        margin=dict(l=60, r=30, t=50, b=50),
        hoverlabel=dict(bgcolor="white", bordercolor="#ddd", font_size=12),
    )
    defaults.update(overrides)
    return defaults


def _axis_style() -> dict:
    """Common axis configuration."""
    return dict(
        showgrid=True,
        gridcolor="#e8ecf0",
        zeroline=False,
        showline=True,
        linecolor="black",
        linewidth=1,
        ticks="inside",
        tickfont=dict(size=_FONT_AXIS),
        mirror=True,
    )


def _ensure_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with derived columns, computing them if missing."""
    if "FeOt" not in df.columns:
        df = calc_derived(df.copy())
    return df


# ===================================================================
# P0  --  Core figures
# ===================================================================


def fig_tas(df: pd.DataFrame) -> go.Figure:
    """TAS classification diagram (Le Maitre 2002)."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    fig = go.Figure()

    # -- TAS boundary lines ------------------------------------------
    for seg in TAS_BOUNDARIES:
        xs, ys = zip(*seg)
        fig.add_trace(
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="lines",
                line=dict(color="#888888", width=0.8),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # -- Field labels -------------------------------------------------
    for name, (lx, ly) in TAS_LABELS.items():
        fig.add_annotation(
            x=lx,
            y=ly,
            text=name.replace("\n", "<br>"),
            showarrow=False,
            font=dict(size=8, color="#999999", family=_FONT_FAMILY),
            xanchor="center",
            yanchor="middle",
        )

    # -- Data scatter -------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=df["liq_SiO2"],
            y=df["Na2O_K2O"],
            mode="markers",
            marker=dict(
                size=_MARKER_SIZE + 1,
                color=df["T_C"],
                colorscale=_COLORSCALE_T,
                colorbar=dict(title="T (\u00b0C)", thickness=15),
                showscale=True,
            ),
            text=[
                f"T={t:.0f}\u00b0C  P={p:.0f} bar<br>SiO2={s:.1f}  Alk={a:.1f}"
                for t, p, s, a in zip(
                    df["T_C"], df["P_bar"], df["liq_SiO2"], df["Na2O_K2O"]
                )
            ],
            hoverinfo="text",
            showlegend=False,
        )
    )

    # -- Cooling-direction arrow --------------------------------------
    n = len(df)
    if n > 15:
        x0 = df["liq_SiO2"].iloc[-15]
        y0 = df["Na2O_K2O"].iloc[-15]
    else:
        x0 = df["liq_SiO2"].iloc[0]
        y0 = df["Na2O_K2O"].iloc[0]
    x1 = df["liq_SiO2"].iloc[-1]
    y1 = df["Na2O_K2O"].iloc[-1]
    fig.add_annotation(
        ax=x0,
        ay=y0,
        x=x1,
        y=y1,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=1.5,
        arrowcolor="black",
    )

    # Start / end temperature annotations
    fig.add_annotation(
        x=df["liq_SiO2"].iloc[0] - 1,
        y=df["Na2O_K2O"].iloc[0] - 0.4,
        text=f"{df['T_C'].iloc[0]:.0f} \u00b0C",
        showarrow=False,
        font=dict(size=8, color="darkblue"),
    )
    fig.add_annotation(
        x=df["liq_SiO2"].iloc[-1] + 0.8,
        y=df["Na2O_K2O"].iloc[-1] + 0.15,
        text=f"{df['T_C'].iloc[-1]:.0f} \u00b0C",
        showarrow=False,
        font=dict(size=8, color="darkred"),
    )

    fig.update_layout(
        **_base_layout(title="TAS Classification (Le Maitre 2002) \u2014 Liquid Evolution Path"),
        xaxis=dict(title="SiO\u2082 (wt%)", range=[40, 72], **_axis_style()),
        yaxis=dict(title="Na\u2082O + K\u2082O (wt%)", range=[0, 10], **_axis_style()),
    )
    return fig


# -------------------------------------------------------------------
def fig_harker_mgo(df: pd.DataFrame) -> go.Figure:
    """3x3 MgO variation (Harker-style) diagrams."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    oxides = [
        ("liq_SiO2", "SiO\u2082 (wt%)"),
        ("liq_Al2O3", "Al\u2082O\u2083 (wt%)"),
        ("FeOt", "FeO* (wt%)"),
        ("liq_CaO", "CaO (wt%)"),
        ("liq_Na2O", "Na\u2082O (wt%)"),
        ("liq_K2O", "K\u2082O (wt%)"),
        ("liq_TiO2", "TiO\u2082 (wt%)"),
        ("liq_H2O", "H\u2082O (wt%)"),
        ("liq_P2O5", "P\u2082O\u2085 (wt%)"),
    ]

    fig = make_subplots(
        rows=3,
        cols=3,
        subplot_titles=[label for _, label in oxides],
        horizontal_spacing=0.08,
        vertical_spacing=0.10,
    )

    for idx, (col, label) in enumerate(oxides):
        r = idx // 3 + 1
        c = idx % 3 + 1
        show_cb = idx == len(oxides) - 1
        fig.add_trace(
            go.Scatter(
                x=df["liq_MgO"],
                y=df[col],
                mode="markers",
                marker=dict(
                    size=_MARKER_SIZE,
                    color=df["T_C"],
                    colorscale=_COLORSCALE_T,
                    showscale=show_cb,
                    colorbar=dict(title="T (\u00b0C)", thickness=12, x=1.02)
                    if show_cb
                    else None,
                ),
                text=[
                    f"T={t:.0f}\u00b0C  MgO={m:.2f}  {label.split()[0]}={v:.2f}"
                    for t, m, v in zip(df["T_C"], df["liq_MgO"], df[col])
                ],
                hoverinfo="text",
                showlegend=False,
            ),
            row=r,
            col=c,
        )
        fig.update_xaxes(title_text="MgO (wt%)", row=r, col=c, **_axis_style())
        fig.update_yaxes(title_text=label, row=r, col=c, **_axis_style())

    fig.update_layout(
        **_base_layout(
            title="MgO Variation Diagrams \u2014 Liquid Line of Descent",
            height=800,
        )
    )
    return fig


# -------------------------------------------------------------------
def fig_harker_sio2(df: pd.DataFrame) -> go.Figure:
    """3x3 SiO2 Harker diagrams."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    oxides = [
        ("liq_Al2O3", "Al\u2082O\u2083 (wt%)"),
        ("FeOt", "FeO* (wt%)"),
        ("liq_MgO", "MgO (wt%)"),
        ("liq_CaO", "CaO (wt%)"),
        ("liq_Na2O", "Na\u2082O (wt%)"),
        ("liq_K2O", "K\u2082O (wt%)"),
        ("liq_TiO2", "TiO\u2082 (wt%)"),
        ("liq_H2O", "H\u2082O (wt%)"),
        ("liq_P2O5", "P\u2082O\u2085 (wt%)"),
    ]

    fig = make_subplots(
        rows=3,
        cols=3,
        subplot_titles=[label for _, label in oxides],
        horizontal_spacing=0.08,
        vertical_spacing=0.10,
    )

    for idx, (col, label) in enumerate(oxides):
        r = idx // 3 + 1
        c = idx % 3 + 1
        show_cb = idx == len(oxides) - 1
        fig.add_trace(
            go.Scatter(
                x=df["liq_SiO2"],
                y=df[col],
                mode="markers",
                marker=dict(
                    size=_MARKER_SIZE,
                    color=df["T_C"],
                    colorscale=_COLORSCALE_T,
                    showscale=show_cb,
                    colorbar=dict(title="T (\u00b0C)", thickness=12, x=1.02)
                    if show_cb
                    else None,
                ),
                text=[
                    f"T={t:.0f}\u00b0C  SiO2={s:.2f}  {label.split()[0]}={v:.2f}"
                    for t, s, v in zip(df["T_C"], df["liq_SiO2"], df[col])
                ],
                hoverinfo="text",
                showlegend=False,
            ),
            row=r,
            col=c,
        )
        fig.update_xaxes(title_text="SiO\u2082 (wt%)", row=r, col=c, **_axis_style())
        fig.update_yaxes(title_text=label, row=r, col=c, **_axis_style())

    fig.update_layout(
        **_base_layout(
            title="Harker Diagrams \u2014 Liquid Composition vs SiO\u2082",
            height=800,
        )
    )
    return fig


# -------------------------------------------------------------------
def fig_pt_path(df: pd.DataFrame) -> go.Figure:
    """P-T path coloured by liquid fraction, with phase-appearance markers."""
    df = _ensure_derived(df)
    phase_events = detect_phase_events(df)

    fig = go.Figure()

    # Main P-T scatter
    fig.add_trace(
        go.Scatter(
            x=df["T_C"],
            y=df["P_bar"] / 1000,
            mode="markers",
            marker=dict(
                size=_MARKER_SIZE + 1,
                color=df["liquid_frac"],
                colorscale=_COLORSCALE_MELT,
                colorbar=dict(title="Liquid (%)", thickness=15),
                showscale=True,
            ),
            text=[
                f"T={t:.0f}\u00b0C  P={p:.0f} bar<br>Liq={lf:.1f}%"
                for t, p, lf in zip(df["T_C"], df["P_bar"], df["liquid_frac"])
            ],
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Phase-appearance diamonds
    for phase, T_app in phase_events.items():
        rows = df[df["T_C"] <= T_app]
        if rows.empty:
            continue
        row = rows.iloc[0]
        color = PHASE_COLORS.get(phase, "black")
        fig.add_trace(
            go.Scatter(
                x=[T_app],
                y=[row["P_bar"] / 1000],
                mode="markers+text",
                marker=dict(
                    symbol="diamond",
                    size=10,
                    color=color,
                    line=dict(color="black", width=0.5),
                ),
                text=[phase],
                textposition="top right",
                textfont=dict(size=8, color=color, family=_FONT_FAMILY),
                hoverinfo="text",
                hovertext=f"{phase} appears at {T_app:.0f}\u00b0C",
                showlegend=False,
            )
        )

    fig.update_layout(
        **_base_layout(title="P\u2013T Path with Phase Appearances"),
        xaxis=dict(title="Temperature (\u00b0C)", **_axis_style()),
        yaxis=dict(title="Pressure (kbar)", autorange="reversed", **_axis_style()),
    )
    return fig


# -------------------------------------------------------------------
def fig_afm(df: pd.DataFrame) -> go.Figure:
    """AFM ternary diagram with Irvine-Baragar dividing line."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    A = df["liq_Na2O"] + df["liq_K2O"]
    F = df["FeOt"]
    M = df["liq_MgO"]
    x_data, y_data = afm_ternary_coords(A.values, F.values, M.values)

    sqrt3_2 = np.sqrt(3) / 2

    fig = go.Figure()

    # Triangle boundary
    fig.add_trace(
        go.Scatter(
            x=[0, 1, 0.5, 0],
            y=[0, 0, sqrt3_2, 0],
            mode="lines",
            line=dict(color="black", width=_LINE_WIDTH_BOUNDARY),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Vertex labels
    for lbl, lx, ly, anchor in [
        ("MgO", 0, -0.04, "center"),
        ("FeO*", 1, -0.04, "center"),
        ("Na\u2082O+K\u2082O", 0.5, sqrt3_2 + 0.03, "center"),
    ]:
        fig.add_annotation(
            x=lx,
            y=ly,
            text=lbl,
            showarrow=False,
            font=dict(size=11, family=_FONT_FAMILY),
            xanchor=anchor,
        )

    # Irvine-Baragar dividing line
    fig.add_trace(
        go.Scatter(
            x=IB_LINE_X.tolist(),
            y=IB_LINE_Y.tolist(),
            mode="lines",
            line=dict(color="black", width=1, dash="dash"),
            opacity=0.6,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        x=0.65, y=0.15, text="Tholeiitic", showarrow=False,
        font=dict(size=9, color="grey", family=_FONT_FAMILY),
    )
    fig.add_annotation(
        x=0.40, y=0.30, text="Calc-alkaline", showarrow=False,
        font=dict(size=9, color="grey", family=_FONT_FAMILY),
    )

    # Data scatter
    fig.add_trace(
        go.Scatter(
            x=x_data.tolist(),
            y=y_data.tolist(),
            mode="markers",
            marker=dict(
                size=_MARKER_SIZE,
                color=df["T_C"],
                colorscale=_COLORSCALE_T,
                colorbar=dict(title="T (\u00b0C)", thickness=12),
                showscale=True,
            ),
            text=[
                f"T={t:.0f}\u00b0C<br>A={a:.1f} F={f:.1f} M={m:.1f}"
                for t, a, f, m in zip(df["T_C"], A, F, M)
            ],
            hoverinfo="text",
            showlegend=False,
        )
    )

    fig.update_layout(
        **_base_layout(title="AFM Diagram \u2014 Differentiation Trend"),
        xaxis=dict(
            range=[-0.05, 1.05],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,
            scaleanchor="y",
            scaleratio=1,
        ),
        yaxis=dict(
            range=[-0.08, sqrt3_2 + 0.08],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            showline=False,
        ),
        height=600,
    )
    return fig


# -------------------------------------------------------------------
def fig_evolution(df: pd.DataFrame) -> go.Figure:
    """2x3 multi-panel magma evolution vs temperature."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()
    phase_events = detect_phase_events(df)

    fig = make_subplots(
        rows=2,
        cols=3,
        subplot_titles=[
            "Liquid Remaining",
            "SiO\u2082",
            "Mg#",
            "FeO* & MgO",
            "Al\u2082O\u2083, CaO, Na\u2082O",
            "H\u2082O & log fO\u2082",
        ],
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
        specs=[
            [{}, {}, {}],
            [{}, {}, {"secondary_y": True}],
        ],
    )

    T = df["T_C"]

    # Panel (1,1): liquid fraction
    fig.add_trace(
        go.Scatter(
            x=T, y=df["liquid_frac"], mode="lines",
            line=dict(color="black", width=_LINE_WIDTH_DATA),
            fill="tozeroy", fillcolor="rgba(70,130,180,0.15)",
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>Liq=%{y:.1f}%<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.update_yaxes(title_text="Liquid (%)", range=[0, 105], row=1, col=1)

    # Panel (1,2): SiO2 with rock-type bands
    fig.add_trace(
        go.Scatter(
            x=T, y=df["liq_SiO2"], mode="lines",
            line=dict(color="#d62728", width=_LINE_WIDTH_DATA),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>SiO2=%{y:.1f}%<extra></extra>",
        ),
        row=1, col=2,
    )
    for yval, label in [(52, "Basalt"), (57, "Bas. And."), (63, "Andesite"), (69, "Dacite")]:
        fig.add_hline(
            y=yval, line_dash="dot", line_color="grey", line_width=0.5,
            row=1, col=2,
        )
        fig.add_annotation(
            x=T.iloc[0] - 5, y=yval + 0.5, text=label,
            showarrow=False, font=dict(size=7, color="grey"),
            xref="x2", yref="y2",
        )
    fig.update_yaxes(title_text="SiO\u2082 (wt%)", row=1, col=2)

    # Panel (1,3): Mg#
    fig.add_trace(
        go.Scatter(
            x=T, y=df["Mg_number"], mode="lines",
            line=dict(color="#2ca02c", width=_LINE_WIDTH_DATA),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>Mg#=%{y:.1f}<extra></extra>",
        ),
        row=1, col=3,
    )
    fig.update_yaxes(title_text="Mg# [molar, Fe\u00b2\u207a only]", row=1, col=3)

    # Panel (2,1): FeOt and MgO
    for col_name, label, color in [
        ("liq_MgO", "MgO", "#2ca02c"),
        ("FeOt", "FeO*", "#d62728"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=T, y=df[col_name], mode="lines", name=label,
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=True,
                legendgroup="panel4",
                hovertemplate="T=%{x:.0f}\u00b0C<br>" + label + "=%{y:.2f}%<extra></extra>",
            ),
            row=2, col=1,
        )
    fig.update_yaxes(title_text="wt%", row=2, col=1)

    # Panel (2,2): Al2O3, CaO, Na2O
    for col_name, label, color in [
        ("liq_Al2O3", "Al\u2082O\u2083", "#1f77b4"),
        ("liq_CaO", "CaO", "orange"),
        ("liq_Na2O", "Na\u2082O", "#9467bd"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=T, y=df[col_name], mode="lines", name=label,
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=True,
                legendgroup="panel5",
                hovertemplate="T=%{x:.0f}\u00b0C<br>" + label + "=%{y:.2f}%<extra></extra>",
            ),
            row=2, col=2,
        )
    fig.update_yaxes(title_text="wt%", row=2, col=2)

    # Panel (2,3): H2O (primary y) and logfO2 (secondary y)
    fig.add_trace(
        go.Scatter(
            x=T, y=df["liq_H2O"], mode="lines", name="H\u2082O",
            line=dict(color="#1f77b4", width=_LINE_WIDTH_DATA),
            showlegend=True,
            legendgroup="panel6",
            hovertemplate="T=%{x:.0f}\u00b0C<br>H2O=%{y:.2f}%<extra></extra>",
        ),
        row=2, col=3, secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=T, y=df["logfO2"], mode="lines", name="log fO\u2082",
            line=dict(color="grey", width=1, dash="dash"),
            showlegend=True,
            legendgroup="panel6",
            hovertemplate="T=%{x:.0f}\u00b0C<br>logfO2=%{y:.2f}<extra></extra>",
        ),
        row=2, col=3, secondary_y=True,
    )
    fig.update_yaxes(title_text="H\u2082O (wt%)", row=2, col=3, secondary_y=False)
    fig.update_yaxes(title_text="log fO\u2082", row=2, col=3, secondary_y=True)

    # Reverse x-axes and add phase-appearance vertical lines
    for r in range(1, 3):
        for c in range(1, 4):
            fig.update_xaxes(
                title_text="Temperature (\u00b0C)", autorange="reversed",
                row=r, col=c, **_axis_style(),
            )

    # Phase appearance dashed verticals across all panels
    for phase, T_app in phase_events.items():
        color = PHASE_COLORS.get(phase, "black")
        for r in range(1, 3):
            for c in range(1, 4):
                fig.add_vline(
                    x=T_app, line_dash="dot", line_color=color,
                    line_width=0.6, opacity=0.5, row=r, col=c,
                )
        # Label on first panel only
        fig.add_annotation(
            x=T_app, y=1.0, text=phase, showarrow=False,
            font=dict(size=6, color=color), textangle=-90,
            xref="x", yref="y domain", yanchor="top",
        )

    fig.update_layout(
        **_base_layout(
            title="Magma Evolution During Decompression Crystallization",
            height=650,
        ),
        legend=dict(font=dict(size=8)),
    )
    return fig


# ===================================================================
# P1  --  Extended figures
# ===================================================================


def fig_phase_masses(df: pd.DataFrame, phase_data: pd.DataFrame) -> go.Figure:
    """Stacked area chart of phase masses vs temperature.

    Parameters
    ----------
    df : DataFrame
        Main simulation results (needs T_C, mass_liquid_g).
    phase_data : DataFrame
        Long-form table with columns: step, T_C, phase, mass.
    """
    df = _ensure_derived(df)

    # Pivot phase_data to wide form
    phase_data = phase_data.copy()
    phase_data["phase_base"] = phase_data["phase"].str.rstrip("0123456789")
    wide = (
        phase_data.groupby(["T_C", "phase_base"])["mass"]
        .sum()
        .unstack(fill_value=0)
        .sort_index(ascending=False)
    )

    # Order by appearance temperature (hottest first)
    phase_events = detect_phase_events(df)
    ordered = sorted(phase_events.keys(), key=lambda p: -phase_events.get(p, 0))
    # Add any phases not in events
    for col in wide.columns:
        if col not in ordered:
            ordered.append(col)

    fig = go.Figure()

    for phase in ordered:
        if phase not in wide.columns:
            continue
        color = PHASE_COLORS.get(phase, "#aaaaaa")
        fig.add_trace(
            go.Scatter(
                x=wide.index,
                y=wide[phase],
                mode="lines",
                name=phase,
                stackgroup="one",
                line=dict(width=0.5, color=color),
                fillcolor=color.replace(")", ",0.7)").replace("rgb", "rgba")
                if color.startswith("rgb")
                else color,
                hovertemplate=f"{phase}<br>T=%{{x:.0f}}\u00b0C<br>Mass=%{{y:.2f}} g<extra></extra>",
            )
        )

    # Liquid mass overlay
    fig.add_trace(
        go.Scatter(
            x=df["T_C"],
            y=df["mass_liquid_g"],
            mode="lines",
            name="liquid",
            line=dict(color="black", width=2.5),
            hovertemplate="Liquid<br>T=%{x:.0f}\u00b0C<br>Mass=%{y:.2f} g<extra></extra>",
        )
    )

    fig.update_layout(
        **_base_layout(title="Phase Masses During Crystallization"),
        xaxis=dict(title="Temperature (\u00b0C)", autorange="reversed", **_axis_style()),
        yaxis=dict(title="Mass (g)", **_axis_style()),
        legend=dict(x=0.01, y=0.99, font=dict(size=8)),
    )
    return fig


# -------------------------------------------------------------------
def fig_liquid_vs_temp(df: pd.DataFrame) -> go.Figure:
    """2x4 liquid composition vs temperature."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    oxides = [
        ("liq_SiO2", "SiO\u2082", "#d62728"),
        ("liq_Al2O3", "Al\u2082O\u2083", "#1f77b4"),
        ("FeOt", "FeO*", "#ff7f0e"),
        ("liq_MgO", "MgO", "#2ca02c"),
        ("liq_CaO", "CaO", "#9467bd"),
        ("liq_Na2O", "Na\u2082O", "#e377c2"),
        ("liq_H2O", "H\u2082O", "#17becf"),
        ("liq_TiO2", "TiO\u2082", "#8c564b"),
    ]

    fig = make_subplots(
        rows=2,
        cols=4,
        subplot_titles=[label for _, label, _ in oxides],
        horizontal_spacing=0.06,
        vertical_spacing=0.12,
    )

    phase_events = detect_phase_events(df)

    for idx, (col, label, color) in enumerate(oxides):
        r = idx // 4 + 1
        c = idx % 4 + 1
        fig.add_trace(
            go.Scatter(
                x=df["T_C"],
                y=df[col],
                mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=False,
                hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>{label}=%{{y:.2f}} wt%<extra></extra>",
            ),
            row=r,
            col=c,
        )
        fig.update_xaxes(
            title_text="T (\u00b0C)", autorange="reversed", row=r, col=c, **_axis_style(),
        )
        fig.update_yaxes(title_text=f"{label} (wt%)", row=r, col=c, **_axis_style())

        # Phase vlines
        for phase, T_app in phase_events.items():
            fig.add_vline(
                x=T_app, line_dash="dot", line_color="grey",
                line_width=0.4, opacity=0.5, row=r, col=c,
            )

    fig.update_layout(
        **_base_layout(
            title="Liquid Composition vs Temperature",
            height=600,
        )
    )
    return fig


# -------------------------------------------------------------------
def fig_system_thermo(df_sys: pd.DataFrame) -> go.Figure:
    """2x3 system thermodynamic properties vs temperature.

    Parameters
    ----------
    df_sys : DataFrame
        System-level data with columns: Temperature, H, S, V, Cp,
        fO2(abs) or logfO2, viscosity.
    """
    # Determine column names -- handle both naming conventions
    T_col = "Temperature" if "Temperature" in df_sys.columns else "T_C"
    fo2_col = "fO2(abs)" if "fO2(abs)" in df_sys.columns else "logfO2"
    H_col = "H" if "H" in df_sys.columns else "H_total"
    S_col = "S" if "S" in df_sys.columns else "S_total"
    V_col = "V" if "V" in df_sys.columns else "V_total"
    Cp_col = "Cp" if "Cp" in df_sys.columns else "Cp_total"

    panels = [
        (H_col, "Enthalpy", "J"),
        (S_col, "Entropy", "J/K"),
        (V_col, "Volume", "cc"),
        (Cp_col, "Heat Capacity", "J/K"),
        (fo2_col, "log fO\u2082", ""),
        ("viscosity", "Melt Viscosity", "log\u2081\u2080 Poise"),
    ]

    fig = make_subplots(
        rows=2,
        cols=3,
        subplot_titles=[label for _, label, _ in panels],
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
    )

    for idx, (col, label, unit) in enumerate(panels):
        r = idx // 3 + 1
        c = idx % 3 + 1
        if col not in df_sys.columns:
            continue
        y_title = f"{label} ({unit})" if unit else label
        fig.add_trace(
            go.Scatter(
                x=df_sys[T_col],
                y=df_sys[col],
                mode="lines",
                line=dict(color="black", width=1.2),
                showlegend=False,
                hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>{label}=%{{y:.4g}}<extra></extra>",
            ),
            row=r,
            col=c,
        )
        fig.update_xaxes(
            title_text="Temperature (\u00b0C)", autorange="reversed",
            row=r, col=c, **_axis_style(),
        )
        fig.update_yaxes(title_text=y_title, row=r, col=c, **_axis_style())

    fig.update_layout(
        **_base_layout(
            title="System Thermodynamic Properties",
            height=650,
        )
    )
    return fig


# -------------------------------------------------------------------
def fig_density(df_sys: pd.DataFrame) -> go.Figure:
    """Liquid and solid density vs temperature.

    Parameters
    ----------
    df_sys : DataFrame
        Must contain columns for temperature, rho_liq, and rho_sol.
    """
    T_col = "Temperature" if "Temperature" in df_sys.columns else "T_C"
    rho_liq_col = "rho_liq"
    rho_sol_col = "rho_sol"

    fig = go.Figure()

    # Liquid density
    if rho_liq_col in df_sys.columns:
        fig.add_trace(
            go.Scatter(
                x=df_sys[T_col],
                y=df_sys[rho_liq_col],
                mode="lines",
                name="Liquid",
                line=dict(color="#d62728", width=_LINE_WIDTH_DATA),
                hovertemplate="T=%{x:.0f}\u00b0C<br>\u03c1_liq=%{y:.4f} g/cm\u00b3<extra></extra>",
            )
        )

    # Solid density (filter near-zero values)
    if rho_sol_col in df_sys.columns:
        mask = df_sys[rho_sol_col] > 0.1
        fig.add_trace(
            go.Scatter(
                x=df_sys.loc[mask, T_col],
                y=df_sys.loc[mask, rho_sol_col],
                mode="lines",
                name="Solid (bulk)",
                line=dict(color="#2ca02c", width=_LINE_WIDTH_DATA),
                hovertemplate="T=%{x:.0f}\u00b0C<br>\u03c1_sol=%{y:.4f} g/cm\u00b3<extra></extra>",
            )
        )

    fig.update_layout(
        **_base_layout(title="Melt and Solid Density"),
        xaxis=dict(title="Temperature (\u00b0C)", autorange="reversed", **_axis_style()),
        yaxis=dict(title="Density (g/cm\u00b3)", **_axis_style()),
        legend=dict(x=0.02, y=0.98),
    )
    return fig


# ===================================================================
# P2  --  Mineral detail figures
# ===================================================================


def _filter_phase(phase_data: pd.DataFrame, phase_name: str) -> pd.DataFrame:
    """Select rows for a mineral phase from the long-form phase table."""
    # Accept both 'olivine1' and 'olivine'
    mask = phase_data["phase"].str.rstrip("0123456789") == phase_name
    df = phase_data.loc[mask].copy()
    # Preserve original phase name as instance identifier
    if not df.empty:
        df["_instance"] = df["phase"]
    return df


def fig_olivine(phase_data: pd.DataFrame) -> go.Figure:
    """Olivine Fo content and mass vs temperature.

    Parameters
    ----------
    phase_data : DataFrame
        Long-form phase table with columns including T (or T_C),
        phase, mass, MgO, FeO.
    """
    ol = _filter_phase(phase_data, "olivine")
    T_col = "T" if "T" in ol.columns else "T_C"

    if ol.empty:
        fig = go.Figure()
        fig.add_annotation(text="No olivine data", x=0.5, y=0.5, showarrow=False,
                           xref="paper", yref="paper")
        fig.update_layout(**_base_layout(title="Olivine Properties"))
        return fig

    # Forsterite content: Fo = 100 * (MgO/40.3) / (MgO/40.3 + FeO/71.85)
    ol["Fo"] = 100.0 * (ol["MgO"] / 40.3) / (ol["MgO"] / 40.3 + ol["FeO"] / 71.85)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Forsterite Content", "Mass per Step"],
        horizontal_spacing=0.12,
    )

    fig.add_trace(
        go.Scatter(
            x=ol[T_col], y=ol["Fo"], mode="lines+markers",
            line=dict(color="#2ca02c", width=_LINE_WIDTH_DATA),
            marker=dict(size=4, color="#2ca02c"),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>Fo=%{y:.1f}%<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=1, **_axis_style())
    fig.update_yaxes(title_text="Fo (mol%)", row=1, col=1, **_axis_style())

    fig.add_trace(
        go.Scatter(
            x=ol[T_col], y=ol["mass"], mode="lines",
            line=dict(color="#2ca02c", width=_LINE_WIDTH_DATA),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>Mass=%{y:.3f} g<extra></extra>",
        ),
        row=1, col=2,
    )
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=2, **_axis_style())
    fig.update_yaxes(title_text="Mass (g)", row=1, col=2, **_axis_style())

    fig.update_layout(
        **_base_layout(title="Olivine Properties", height=400)
    )
    return fig


# -------------------------------------------------------------------
def fig_cpx(phase_data: pd.DataFrame) -> go.Figure:
    """Clinopyroxene composition and Mg# vs temperature."""
    cpx = _filter_phase(phase_data, "clinopyroxene")
    T_col = "T" if "T" in cpx.columns else "T_C"

    if cpx.empty:
        fig = go.Figure()
        fig.add_annotation(text="No clinopyroxene data", x=0.5, y=0.5, showarrow=False,
                           xref="paper", yref="paper")
        fig.update_layout(**_base_layout(title="Clinopyroxene Properties"))
        return fig

    cpx["Mg_no"] = 100.0 * (cpx["MgO"] / 40.3) / (cpx["MgO"] / 40.3 + cpx["FeO"] / 71.85)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Composition", "Mg#"],
        horizontal_spacing=0.12,
    )

    instances = sorted(cpx["_instance"].unique())

    ox_colors = [
        ("MgO", "MgO", "#2ca02c"),
        ("CaO", "CaO", "#9467bd"),
        ("FeO", "FeO", "#ff7f0e"),
        ("Al2O3", "Al\u2082O\u2083", "#1f77b4"),
    ]

    for idx, inst in enumerate(instances):
        sub = cpx[cpx["_instance"] == inst].sort_values(T_col)
        suffix = f" ({inst})" if len(instances) > 1 else ""
        dash = "solid" if idx == 0 else "dash"
        show_legend_done = set()

        for col_name, label, color in ox_colors:
            if col_name not in sub.columns:
                continue
            fig.add_trace(
                go.Scatter(
                    x=sub[T_col], y=sub[col_name], mode="lines",
                    name=label + suffix,
                    line=dict(color=color, width=_LINE_WIDTH_DATA, dash=dash),
                    showlegend=(col_name not in show_legend_done),
                    hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>{label}=%{{y:.2f}} wt%<extra>{inst}</extra>",
                ),
                row=1, col=1,
            )
            show_legend_done.add(col_name)

        fig.add_trace(
            go.Scatter(
                x=sub[T_col], y=sub["Mg_no"], mode="lines",
                name="Mg#" + suffix if len(instances) > 1 else None,
                line=dict(color="#1f77b4", width=_LINE_WIDTH_DATA, dash=dash),
                showlegend=(len(instances) > 1),
                hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>Mg#=%{{y:.1f}}<extra>{inst}</extra>",
            ),
            row=1, col=2,
        )

    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=1, **_axis_style())
    fig.update_yaxes(title_text="wt%", row=1, col=1, **_axis_style())
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=2, **_axis_style())
    fig.update_yaxes(title_text="Mg# [molar, Fe\u00b2\u207a only]", row=1, col=2, **_axis_style())

    fig.update_layout(
        **_base_layout(title="Clinopyroxene Properties", height=400),
        legend=dict(x=0.01, y=0.99, font=dict(size=8)),
    )
    return fig


# -------------------------------------------------------------------
def fig_plagioclase(phase_data: pd.DataFrame) -> go.Figure:
    """Plagioclase anorthite (An) content vs temperature."""
    plag = _filter_phase(phase_data, "plagioclase")
    T_col = "T" if "T" in plag.columns else "T_C"

    if plag.empty:
        fig = go.Figure()
        fig.add_annotation(text="No plagioclase data", x=0.5, y=0.5, showarrow=False,
                           xref="paper", yref="paper")
        fig.update_layout(**_base_layout(title="Plagioclase Properties"))
        return fig

    # An = Ca / (Ca + Na + K) in molar
    # Molar amounts: CaO/56.08, Na2O/61.98 (gives 2 mol Na per formula),
    # K2O/94.2 (gives 2 mol K per formula)
    ca_mol = plag["CaO"] / 56.08
    na_mol = plag["Na2O"] / 61.98
    k_mol = plag["K2O"] / 94.2
    plag["An"] = 100.0 * ca_mol / (ca_mol + na_mol + k_mol)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Anorthite Content", "Mass per Step"],
        horizontal_spacing=0.12,
    )

    fig.add_trace(
        go.Scatter(
            x=plag[T_col], y=plag["An"], mode="lines+markers",
            line=dict(color="#d62728", width=_LINE_WIDTH_DATA),
            marker=dict(size=4, color="#d62728"),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>An=%{y:.1f}%<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=1, **_axis_style())
    fig.update_yaxes(title_text="An (mol%)", row=1, col=1, **_axis_style())

    fig.add_trace(
        go.Scatter(
            x=plag[T_col], y=plag["mass"], mode="lines",
            line=dict(color="#d62728", width=_LINE_WIDTH_DATA),
            showlegend=False,
            hovertemplate="T=%{x:.0f}\u00b0C<br>Mass=%{y:.3f} g<extra></extra>",
        ),
        row=1, col=2,
    )
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=2, **_axis_style())
    fig.update_yaxes(title_text="Mass (g)", row=1, col=2, **_axis_style())

    fig.update_layout(
        **_base_layout(title="Plagioclase Properties", height=400)
    )
    return fig


# -------------------------------------------------------------------
def fig_spinel(phase_data: pd.DataFrame) -> go.Figure:
    """Spinel Cr# and composition vs temperature."""
    sp = _filter_phase(phase_data, "spinel")
    T_col = "T" if "T" in sp.columns else "T_C"

    if sp.empty:
        fig = go.Figure()
        fig.add_annotation(text="No spinel data", x=0.5, y=0.5, showarrow=False,
                           xref="paper", yref="paper")
        fig.update_layout(**_base_layout(title="Spinel Properties"))
        return fig

    # Cr# = Cr / (Cr + Al) molar
    sp["Cr_no"] = 100.0 * (sp["Cr2O3"] / 152.0) / (
        sp["Cr2O3"] / 152.0 + sp["Al2O3"] / 101.96
    )

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["Composition", "Cr#"],
        horizontal_spacing=0.12,
    )

    instances = sorted(sp["_instance"].unique())

    ox_colors = [
        ("Cr2O3", "Cr\u2082O\u2083", "brown"),
        ("Fe2O3", "Fe\u2082O\u2083", "orange"),
        ("Al2O3", "Al\u2082O\u2083", "blue"),
        ("FeO", "FeO", "red"),
        ("MgO", "MgO", "green"),
    ]

    for idx, inst in enumerate(instances):
        sub = sp[sp["_instance"] == inst].sort_values(T_col)
        suffix = f" ({inst})" if len(instances) > 1 else ""
        dash = "solid" if idx == 0 else "dash"
        show_legend_done = set()

        for col_name, label, color in ox_colors:
            if col_name not in sub.columns:
                continue
            fig.add_trace(
                go.Scatter(
                    x=sub[T_col], y=sub[col_name], mode="lines",
                    name=label + suffix,
                    line=dict(color=color, width=_LINE_WIDTH_DATA, dash=dash),
                    showlegend=(col_name not in show_legend_done),
                    hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>{label}=%{{y:.2f}} wt%<extra>{inst}</extra>",
                ),
                row=1, col=1,
            )
            show_legend_done.add(col_name)

        fig.add_trace(
            go.Scatter(
                x=sub[T_col], y=sub["Cr_no"], mode="lines",
                name="Cr#" + suffix if len(instances) > 1 else None,
                line=dict(color="brown", width=_LINE_WIDTH_DATA, dash=dash),
                showlegend=(len(instances) > 1),
                hovertemplate=f"T=%{{x:.0f}}\u00b0C<br>Cr#=%{{y:.1f}}<extra>{inst}</extra>",
            ),
            row=1, col=2,
        )

    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=1, **_axis_style())
    fig.update_yaxes(title_text="wt%", row=1, col=1, **_axis_style())
    fig.update_xaxes(title_text="T (\u00b0C)", autorange="reversed", row=1, col=2, **_axis_style())
    fig.update_yaxes(title_text="Cr# [molar]", row=1, col=2, **_axis_style())

    fig.update_layout(
        **_base_layout(title="Spinel Properties", height=400),
        legend=dict(x=0.01, y=0.99, font=dict(size=8)),
    )
    return fig


# -------------------------------------------------------------------
def fig_mg_vs_sio2(df: pd.DataFrame) -> go.Figure:
    """Mg# vs SiO2 differentiation index, coloured by temperature."""
    df = _ensure_derived(df)
    df = df[df["mass_liquid_g"] > 0.01].copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["liq_SiO2"],
            y=df["Mg_number"],
            mode="markers",
            marker=dict(
                size=_MARKER_SIZE + 1,
                color=df["T_C"],
                colorscale=_COLORSCALE_T,
                colorbar=dict(title="T (\u00b0C)", thickness=15),
                showscale=True,
            ),
            text=[
                f"T={t:.0f}\u00b0C<br>SiO2={s:.1f}  Mg#={mg:.1f}"
                for t, s, mg in zip(df["T_C"], df["liq_SiO2"], df["Mg_number"])
            ],
            hoverinfo="text",
            showlegend=False,
        )
    )

    fig.update_layout(
        **_base_layout(title="Differentiation Index: Mg# vs SiO\u2082"),
        xaxis=dict(title="SiO\u2082 (wt%)", **_axis_style()),
        yaxis=dict(title="Mg# [molar, Fe\u00b2\u207a only]", **_axis_style()),
    )
    return fig


# ===================================================================
# Batch comparison figures — multi-run overlay
# ===================================================================

COMPARE_COLORS = [
    "#3b82f6",  # blue
    "#ef4444",  # red
    "#10b981",  # green
    "#f59e0b",  # amber
    "#8b5cf6",  # purple
    "#ec4899",  # pink
    "#06b6d4",  # cyan
    "#f97316",  # orange
]


def _compare_color(index: int) -> str:
    """Return a color for the i-th dataset in a comparison plot."""
    return COMPARE_COLORS[index % len(COMPARE_COLORS)]


# -------------------------------------------------------------------
def fig_tas_compare(datasets: list[dict]) -> go.Figure:
    """TAS classification diagram with multiple runs overlaid.

    Parameters
    ----------
    datasets : list of dict
        Each dict has keys ``"label"`` (str) and ``"df"`` (DataFrame).
    """
    fig = go.Figure()

    # -- TAS boundary lines (same as fig_tas) --
    for seg in TAS_BOUNDARIES:
        xs, ys = zip(*seg)
        fig.add_trace(
            go.Scatter(
                x=list(xs), y=list(ys),
                mode="lines",
                line=dict(color="#888888", width=0.8),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # -- Field labels --
    for name, (lx, ly) in TAS_LABELS.items():
        fig.add_annotation(
            x=lx, y=ly,
            text=name.replace("\n", "<br>"),
            showarrow=False,
            font=dict(size=8, color="#999999", family=_FONT_FAMILY),
            xanchor="center", yanchor="middle",
        )

    # -- One trace per dataset --
    for i, ds in enumerate(datasets):
        df = _ensure_derived(ds["df"])
        df = df[df["mass_liquid_g"] > 0.01].copy()
        color = _compare_color(i)
        fig.add_trace(
            go.Scatter(
                x=df["liq_SiO2"],
                y=df["Na2O_K2O"],
                mode="markers+lines",
                marker=dict(size=_MARKER_SIZE, color=color),
                line=dict(color=color, width=1.5),
                name=ds["label"],
                hovertemplate=(
                    f"{ds['label']}<br>"
                    "SiO2=%{x:.1f}<br>Alk=%{y:.1f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        **_base_layout(title="TAS Classification \u2014 Parameter Sweep Comparison"),
        xaxis=dict(title="SiO\u2082 (wt%)", range=[40, 72], **_axis_style()),
        yaxis=dict(title="Na\u2082O + K\u2082O (wt%)", range=[0, 10], **_axis_style()),
        legend=dict(x=0.01, y=0.99, font=dict(size=9)),
    )
    return fig


# -------------------------------------------------------------------
def fig_harker_mgo_compare(datasets: list[dict]) -> go.Figure:
    """3x3 MgO variation diagrams with multiple runs overlaid."""
    oxides = [
        ("liq_SiO2", "SiO\u2082 (wt%)"),
        ("liq_Al2O3", "Al\u2082O\u2083 (wt%)"),
        ("FeOt", "FeO* (wt%)"),
        ("liq_CaO", "CaO (wt%)"),
        ("liq_Na2O", "Na\u2082O (wt%)"),
        ("liq_K2O", "K\u2082O (wt%)"),
        ("liq_TiO2", "TiO\u2082 (wt%)"),
        ("liq_H2O", "H\u2082O (wt%)"),
        ("liq_P2O5", "P\u2082O\u2085 (wt%)"),
    ]

    fig = make_subplots(
        rows=3, cols=3,
        subplot_titles=[label for _, label in oxides],
        horizontal_spacing=0.08,
        vertical_spacing=0.10,
    )

    for idx, (col, label) in enumerate(oxides):
        r = idx // 3 + 1
        c = idx % 3 + 1
        for i, ds in enumerate(datasets):
            df = _ensure_derived(ds["df"])
            df = df[df["mass_liquid_g"] > 0.01].copy()
            color = _compare_color(i)
            # Only show legend on first subplot to avoid duplicates
            show_legend = (idx == 0)
            fig.add_trace(
                go.Scatter(
                    x=df["liq_MgO"],
                    y=df[col],
                    mode="markers",
                    marker=dict(size=_MARKER_SIZE - 1, color=color, opacity=0.7),
                    name=ds["label"],
                    showlegend=show_legend,
                    legendgroup=ds["label"],
                    hovertemplate=(
                        f"{ds['label']}<br>"
                        f"MgO=%{{x:.2f}}  {label.split()[0]}=%{{y:.2f}}<extra></extra>"
                    ),
                ),
                row=r, col=c,
            )
        fig.update_xaxes(title_text="MgO (wt%)", row=r, col=c, **_axis_style())
        fig.update_yaxes(title_text=label, row=r, col=c, **_axis_style())

    fig.update_layout(
        **_base_layout(
            title="MgO Variation \u2014 Parameter Sweep Comparison",
            height=800,
        ),
        legend=dict(x=0.01, y=1.06, orientation="h", font=dict(size=8)),
    )
    return fig


# -------------------------------------------------------------------
def fig_evolution_compare(datasets: list[dict]) -> go.Figure:
    """2x3 magma evolution panels with multiple runs overlaid."""
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            "Liquid Remaining",
            "SiO\u2082",
            "Mg#",
            "FeO* & MgO",
            "Al\u2082O\u2083, CaO, Na\u2082O",
            "H\u2082O",
        ],
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
    )

    for i, ds in enumerate(datasets):
        df = _ensure_derived(ds["df"])
        df = df[df["mass_liquid_g"] > 0.01].copy()
        color = _compare_color(i)
        T = df["T_C"]
        lbl = ds["label"]
        show = (i == 0)  # only first dataset's traces show in legend at first

        # Panel (1,1): liquid fraction
        fig.add_trace(
            go.Scatter(
                x=T, y=df["liquid_frac"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                name=lbl, showlegend=True,
                legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>Liq=%{{y:.1f}}%<extra></extra>",
            ),
            row=1, col=1,
        )

        # Panel (1,2): SiO2
        fig.add_trace(
            go.Scatter(
                x=T, y=df["liq_SiO2"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=False, legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>SiO2=%{{y:.1f}}%<extra></extra>",
            ),
            row=1, col=2,
        )

        # Panel (1,3): Mg#
        fig.add_trace(
            go.Scatter(
                x=T, y=df["Mg_number"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=False, legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>Mg#=%{{y:.1f}}<extra></extra>",
            ),
            row=1, col=3,
        )

        # Panel (2,1): FeOt (solid) and MgO (dash)
        fig.add_trace(
            go.Scatter(
                x=T, y=df["FeOt"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=False, legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>FeO*=%{{y:.2f}}%<extra></extra>",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=T, y=df["liq_MgO"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA, dash="dash"),
                showlegend=False, legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>MgO=%{{y:.2f}}%<extra></extra>",
            ),
            row=2, col=1,
        )

        # Panel (2,2): Al2O3 (solid), CaO (dash), Na2O (dot)
        for col_name, dash_style in [
            ("liq_Al2O3", "solid"),
            ("liq_CaO", "dash"),
            ("liq_Na2O", "dot"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=T, y=df[col_name], mode="lines",
                    line=dict(color=color, width=_LINE_WIDTH_DATA, dash=dash_style),
                    showlegend=False, legendgroup=lbl,
                    hovertemplate=(
                        f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>"
                        f"{col_name.replace('liq_', '')}=%{{y:.2f}}%<extra></extra>"
                    ),
                ),
                row=2, col=2,
            )

        # Panel (2,3): H2O
        fig.add_trace(
            go.Scatter(
                x=T, y=df["liq_H2O"], mode="lines",
                line=dict(color=color, width=_LINE_WIDTH_DATA),
                showlegend=False, legendgroup=lbl,
                hovertemplate=f"{lbl}<br>T=%{{x:.0f}}\u00b0C<br>H2O=%{{y:.2f}}%<extra></extra>",
            ),
            row=2, col=3,
        )

    # Axis labels and reverse x
    fig.update_yaxes(title_text="Liquid (%)", row=1, col=1)
    fig.update_yaxes(title_text="SiO\u2082 (wt%)", row=1, col=2)
    fig.update_yaxes(title_text="Mg#", row=1, col=3)
    fig.update_yaxes(title_text="wt%", row=2, col=1)
    fig.update_yaxes(title_text="wt%", row=2, col=2)
    fig.update_yaxes(title_text="H\u2082O (wt%)", row=2, col=3)

    for r in range(1, 3):
        for c in range(1, 4):
            fig.update_xaxes(
                title_text="Temperature (\u00b0C)", autorange="reversed",
                row=r, col=c, **_axis_style(),
            )

    fig.update_layout(
        **_base_layout(
            title="Magma Evolution \u2014 Parameter Sweep Comparison",
            height=650,
        ),
        legend=dict(x=0.01, y=1.06, orientation="h", font=dict(size=8)),
    )
    return fig


# -------------------------------------------------------------------
def fig_pt_path_compare(datasets: list[dict]) -> go.Figure:
    """P-T path with multiple runs overlaid."""
    fig = go.Figure()

    for i, ds in enumerate(datasets):
        df = _ensure_derived(ds["df"])
        color = _compare_color(i)
        fig.add_trace(
            go.Scatter(
                x=df["T_C"],
                y=df["P_bar"] / 1000,
                mode="markers+lines",
                marker=dict(size=_MARKER_SIZE - 1, color=color),
                line=dict(color=color, width=1.5),
                name=ds["label"],
                hovertemplate=(
                    f"{ds['label']}<br>"
                    "T=%{x:.0f}\u00b0C<br>P=%{y:.2f} kbar<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        **_base_layout(title="P\u2013T Path \u2014 Parameter Sweep Comparison"),
        xaxis=dict(title="Temperature (\u00b0C)", **_axis_style()),
        yaxis=dict(title="Pressure (kbar)", autorange="reversed", **_axis_style()),
        legend=dict(x=0.01, y=0.99, font=dict(size=9)),
    )
    return fig
