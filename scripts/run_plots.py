#!/usr/bin/env python3
"""CLI entry point for generating MELTS plots.

Reads a results.csv file (produced by run_simulation.py) and generates
publication-quality figures using matplotlib.

Usage examples:
    python run_plots.py --input ../cases/case_custom/output/results.csv -o ./figures
    python run_plots.py --input results.csv --plot harker -o ./figures
    python run_plots.py --input results.csv --plot all --format png -o ./figures
"""
import sys
import os
import argparse

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meltsapp import OX
from meltsapp.plotting.common import (
    calc_derived,
    detect_phase_events,
    afm_ternary_coords,
    TAS_BOUNDARIES,
    TAS_LABELS,
    IB_LINE_X,
    IB_LINE_Y,
    PHASE_COLORS,
)


# ---------------------------------------------------------------------------
# Matplotlib defaults
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 8,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------

def plot_harker_sio2(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """Harker diagram: major oxides vs SiO2."""
    oxides = ["Al2O3", "FeO", "MgO", "CaO", "Na2O", "K2O", "TiO2", "H2O"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for ax, ox_name in zip(axes.flat, oxides):
        col = f"liq_{ox_name}"
        if col in df.columns:
            ax.scatter(df["liq_SiO2"], df[col], s=8, c=df["T_C"], cmap="coolwarm")
            ax.set_xlabel("SiO2 (wt%)")
            ax.set_ylabel(f"{ox_name} (wt%)")
            ax.set_title(ox_name)
    fig.suptitle("Harker Diagram (vs SiO2)", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(outdir, f"harker_sio2.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_harker_mgo(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """Harker diagram: major oxides vs MgO."""
    oxides = ["SiO2", "Al2O3", "FeO", "CaO", "Na2O", "K2O", "TiO2", "H2O"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for ax, ox_name in zip(axes.flat, oxides):
        col = f"liq_{ox_name}"
        if col in df.columns:
            ax.scatter(df["liq_MgO"], df[col], s=8, c=df["T_C"], cmap="coolwarm")
            ax.set_xlabel("MgO (wt%)")
            ax.set_ylabel(f"{ox_name} (wt%)")
            ax.set_title(ox_name)
    fig.suptitle("Harker Diagram (vs MgO)", fontsize=14, y=1.02)
    plt.tight_layout()
    path = os.path.join(outdir, f"harker_mgo.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_tas(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """Total Alkali-Silica (TAS) classification diagram."""
    fig, ax = plt.subplots(figsize=(10, 7))
    for seg in TAS_BOUNDARIES:
        xs, ys = zip(*seg)
        ax.plot(xs, ys, "k-", linewidth=0.7)
    for name, (x, y) in TAS_LABELS.items():
        ax.text(x, y, name, fontsize=7, ha="center", va="center", color="gray")
    sc = ax.scatter(
        df["liq_SiO2"], df["Na2O_K2O"], c=df["T_C"], cmap="coolwarm", s=15, zorder=5
    )
    fig.colorbar(sc, ax=ax, label="Temperature (C)")
    ax.set_xlabel("SiO2 (wt%)")
    ax.set_ylabel("Na2O + K2O (wt%)")
    ax.set_title("TAS Classification")
    ax.set_xlim(38, 78)
    ax.set_ylim(0, 16)
    path = os.path.join(outdir, f"TAS.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_afm(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """AFM ternary diagram."""
    A = df["liq_Na2O"] + df["liq_K2O"]
    F = df["FeOt"]
    M = df["liq_MgO"]
    x, y = afm_ternary_coords(A, F, M)

    fig, ax = plt.subplots(figsize=(8, 7))
    # Triangle border
    tri_x = [0, 1, 0.5, 0]
    tri_y = [0, 0, np.sqrt(3) / 2, 0]
    ax.plot(tri_x, tri_y, "k-", linewidth=1)
    # IB dividing line
    ax.plot(IB_LINE_X, IB_LINE_Y, "k--", linewidth=0.8, label="Irvine-Baragar")
    # Data
    sc = ax.scatter(x, y, c=df["T_C"], cmap="coolwarm", s=15, zorder=5)
    fig.colorbar(sc, ax=ax, label="Temperature (C)")
    # Vertex labels
    ax.text(0, -0.03, "M (MgO)", ha="center", fontsize=10)
    ax.text(1, -0.03, "F (FeO*)", ha="center", fontsize=10)
    ax.text(0.5, np.sqrt(3) / 2 + 0.03, "A (Na2O+K2O)", ha="center", fontsize=10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("AFM Diagram")
    path = os.path.join(outdir, f"AFM.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_pt_path(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """P-T path with phase appearances."""
    fig, ax = plt.subplots(figsize=(8, 6))
    sc = ax.scatter(df["T_C"], df["P_bar"], c=df["mass_liquid_g"], cmap="viridis", s=10)
    fig.colorbar(sc, ax=ax, label="Liquid mass (g)")
    events = detect_phase_events(df)
    for phase, T_onset in events.items():
        row = df.loc[(df["T_C"] - T_onset).abs().idxmin()]
        color = PHASE_COLORS.get(phase.rstrip("0123456789"), "#333333")
        ax.annotate(
            phase,
            xy=(row["T_C"], row["P_bar"]),
            fontsize=7,
            color=color,
            fontweight="bold",
        )
    ax.set_xlabel("Temperature (C)")
    ax.set_ylabel("Pressure (bar)")
    ax.set_title("P-T Path")
    ax.invert_xaxis()
    path = os.path.join(outdir, f"PT_path.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_evolution(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """Liquid fraction and Mg# vs temperature."""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(df["T_C"], df["liquid_frac"], "b-", linewidth=1.5, label="Liquid fraction (%)")
    ax1.set_xlabel("Temperature (C)")
    ax1.set_ylabel("Liquid fraction (%)", color="b")
    ax1.tick_params(axis="y", labelcolor="b")
    ax1.invert_xaxis()

    ax2 = ax1.twinx()
    ax2.plot(df["T_C"], df["Mg_number"], "r-", linewidth=1.5, label="Mg#")
    ax2.set_ylabel("Mg#", color="r")
    ax2.tick_params(axis="y", labelcolor="r")

    fig.suptitle("Crystallization Evolution", fontsize=13)
    fig.legend(loc="upper right", bbox_to_anchor=(0.88, 0.88))
    path = os.path.join(outdir, f"evolution.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_mg_vs_sio2(df: pd.DataFrame, outdir: str, fmt: str) -> str:
    """Mg# vs SiO2 colored by temperature."""
    fig, ax = plt.subplots(figsize=(8, 6))
    sc = ax.scatter(df["liq_SiO2"], df["Mg_number"], c=df["T_C"], cmap="coolwarm", s=15)
    fig.colorbar(sc, ax=ax, label="Temperature (C)")
    ax.set_xlabel("SiO2 (wt%)")
    ax.set_ylabel("Mg#")
    ax.set_title("Mg# vs SiO2")
    path = os.path.join(outdir, f"Mg_vs_SiO2.{fmt}")
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Registry of available plots
# ---------------------------------------------------------------------------
PLOT_REGISTRY = {
    "harker_sio2": plot_harker_sio2,
    "harker_mgo": plot_harker_mgo,
    "tas": plot_tas,
    "afm": plot_afm,
    "pt_path": plot_pt_path,
    "evolution": plot_evolution,
    "mg_vs_sio2": plot_mg_vs_sio2,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate MELTS simulation plots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Available plot types:\n"
            "  harker_sio2  — Harker diagram (oxides vs SiO2)\n"
            "  harker_mgo   — Harker diagram (oxides vs MgO)\n"
            "  tas          — Total Alkali-Silica classification\n"
            "  afm          — AFM ternary diagram\n"
            "  pt_path      — Pressure-Temperature path\n"
            "  evolution    — Liquid fraction & Mg# vs temperature\n"
            "  mg_vs_sio2   — Mg# vs SiO2\n"
            "  all          — Generate all plots\n"
        ),
    )
    parser.add_argument("--input", "-i", required=True, help="Path to results.csv")
    parser.add_argument("--plot", "-p", default="all", help="Plot type (default: all)")
    parser.add_argument("--format", "-f", default="png", choices=["png", "pdf", "svg"], help="Output format (default: png)")
    parser.add_argument("--output", "-o", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    # Load and prepare data
    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.input)
    df = calc_derived(df)

    os.makedirs(args.output, exist_ok=True)

    # Determine which plots to generate
    if args.plot == "all":
        plot_names = list(PLOT_REGISTRY.keys())
    else:
        plot_names = [p.strip() for p in args.plot.split(",")]
        for name in plot_names:
            if name not in PLOT_REGISTRY:
                available = ", ".join(sorted(PLOT_REGISTRY.keys()))
                print(f"Error: unknown plot '{name}'. Available: {available}", file=sys.stderr)
                sys.exit(1)

    # Generate plots
    print(f"Generating {len(plot_names)} plot(s) from: {args.input}")
    for name in plot_names:
        path = PLOT_REGISTRY[name](df, args.output, args.format)
        print(f"  {name:15s} -> {path}")

    print("Done.")


if __name__ == "__main__":
    main()
