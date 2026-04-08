#!/usr/bin/env python3
"""CLI entry point for running MELTS simulations.

Usage examples:
    python run_simulation.py --config ../cases/case_custom/config.json -o ../cases/case_custom/output
    python run_simulation.py --preset nmorb --mode 1 -o ./output
"""
import sys
import os
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meltsapp.schemas import SimConfig, StepResult
from meltsapp.simulation import run_crystallization
from meltsapp import OX


# ---------------------------------------------------------------------------
# Output writers — replicate the format used by case_custom/run_python.py
# ---------------------------------------------------------------------------

def write_outputs(results: list[StepResult], title: str, outdir: str) -> None:
    """Write CSV and all five _tbl.txt files from a list of StepResults."""
    os.makedirs(outdir, exist_ok=True)
    ox_header = " ".join(f"{ox:>10}" for ox in OX)

    # --- results.csv ---
    csv_path = os.path.join(outdir, "results.csv")
    with open(csv_path, "w") as f_csv:
        f_csv.write(
            "step,T_C,P_bar,mass_liquid_g,mass_solid_g,"
            + ",".join(f"liq_{ox}" for ox in OX)
            + ",logfO2,rho_liq,viscosity,phases\n"
        )
        for r in results:
            liq_csv = ",".join(f"{r.liquid_comp.get(ox, 0.0):.4f}" for ox in OX)
            solids_str = "+".join(r.phases[1:]) if len(r.phases) > 1 else ""
            # Filter to solid phase names only (exclude liquid*)
            solid_names = [p for p in r.phases if not p.startswith("liquid")]
            solids_str = "+".join(solid_names)
            f_csv.write(
                f"{r.step},{r.T:.1f},{r.P:.1f},{r.liquid_mass:.4f},{r.solid_mass:.4f},"
                f"{liq_csv},{r.logfO2:.4f},{r.rho_liq:.4f},{r.viscosity:.3f},{solids_str}\n"
            )

    # --- System_main_tbl.txt ---
    with open(os.path.join(outdir, "System_main_tbl.txt"), "w") as f:
        f.write(f"Title: {title}\n\nSystem Thermodynamic Data:\n")
        f.write(
            f"{'index':>5} {'Pressure':>10} {'Temperature':>12} {'mass':>12} {'F':>10} "
            f"{'H':>14} {'S':>12} {'V':>12} {'Cp':>12} {'fO2(abs)':>14} "
            f"{'rho_liq':>10} {'rho_sol':>10} {'viscosity':>10}\n"
        )
        for r in results:
            total_mass = r.liquid_mass + r.solid_mass
            F = r.liquid_mass / total_mass if total_mass > 0 else 0.0
            f.write(
                f"{r.step + 1:5d} {r.P:10.2f} {r.T:12.2f} {total_mass:12.6f} {F:10.7f} "
                f"{r.H_total:14.3f} {r.S_total:12.6f} {r.V_total:12.6f} {r.Cp_total:12.6f} "
                f"{r.logfO2:14.6f} {r.rho_liq:10.6f} {r.rho_sol:10.6f} {r.viscosity:10.3f}\n"
            )

    # --- Liquid_comp_tbl.txt ---
    with open(os.path.join(outdir, "Liquid_comp_tbl.txt"), "w") as f:
        f.write(f"Title: {title}\n\nLiquid Composition:\n")
        f.write(f"{'index':>5} {'Pressure':>10} {'Temperature':>12} {'mass':>12} {ox_header}\n")
        for r in results:
            liq_vals = " ".join(f"{r.liquid_comp.get(ox, 0.0):10.4f}" for ox in OX)
            f.write(f"{r.step + 1:5d} {r.P:10.2f} {r.T:12.2f} {r.liquid_mass:12.6f} {liq_vals}\n")

    # --- Solid_comp_tbl.txt ---
    with open(os.path.join(outdir, "Solid_comp_tbl.txt"), "w") as f:
        f.write(f"Title: {title}\n\nSolid Composition (bulk):\n")
        f.write(f"{'index':>5} {'Pressure':>10} {'Temperature':>12} {'mass':>12} {ox_header}\n")
        for r in results:
            if r.solid_mass > 0.001:
                sol_vals = " ".join(f"{r.solid_comp.get(ox, 0.0):10.4f}" for ox in OX)
                f.write(f"{r.step + 1:5d} {r.P:10.2f} {r.T:12.2f} {r.solid_mass:12.6f} {sol_vals}\n")
            else:
                f.write(f"{r.step + 1:5d} {r.P:10.2f} {r.T:12.2f} {0:12.6f} ---\n")

    # --- Bulk_comp_tbl.txt ---
    with open(os.path.join(outdir, "Bulk_comp_tbl.txt"), "w") as f:
        f.write(f"Title: {title}\n\nBulk Composition:\n")
        f.write(f"{'index':>5} {'Pressure':>10} {'Temperature':>12} {'mass':>12} {ox_header}\n")
        for r in results:
            total_mass = r.liquid_mass + r.solid_mass
            bulk_vals = " ".join(f"{r.bulk_comp.get(ox, 0.0):10.4f}" for ox in OX)
            f.write(f"{r.step + 1:5d} {r.P:10.2f} {r.T:12.2f} {total_mass:12.6f} {bulk_vals}\n")

    # --- Phase_main_tbl.txt ---
    with open(os.path.join(outdir, "Phase_main_tbl.txt"), "w") as f:
        f.write(f"Title: {title}\n\nPhase Data (mass, G, H, S, V, composition):\n")
        for r in results:
            f.write(f"index {r.step + 1} Pressure {r.P:.2f} Temperature {r.T:.2f}\n")
            for pd_ in r.phase_details:
                comp_str = " ".join(f"{pd_.composition.get(ox, 0.0):8.4f}" for ox in OX)
                f.write(
                    f"  {pd_.phase:20s} {pd_.mass:12.6f} {pd_.G:14.3f} {pd_.H:14.3f} "
                    f"{pd_.S:12.6f} {pd_.V:12.6f} {pd_.rho:8.4f} {comp_str}\n"
                )

    print(f"\nOutput files written to: {outdir}")
    for fn in [
        "results.csv",
        "System_main_tbl.txt",
        "Liquid_comp_tbl.txt",
        "Solid_comp_tbl.txt",
        "Bulk_comp_tbl.txt",
        "Phase_main_tbl.txt",
    ]:
        fp = os.path.join(outdir, fn)
        if os.path.exists(fp):
            sz = os.path.getsize(fp) / 1024
            print(f"  {fn:25s} {sz:6.1f} KB")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(args: argparse.Namespace) -> SimConfig:
    """Build a SimConfig from CLI arguments (--config file or --preset)."""
    if args.config:
        with open(args.config) as f:
            data = json.load(f)

        # Map config.json fields to SimConfig fields
        cfg_kwargs = {
            "melts_mode": data.get("melts_mode", 1),
            "composition": data["composition"],
            "T_start": data.get("T_start", 1400.0),
            "T_end": data.get("T_end", 900.0),
            "dT": data.get("dT", -2.0),
            "P_start": data.get("P_start", 5000.0),
            "P_end": data.get("P_end", 1000.0),
            "fo2_buffer": data.get("fo2_buffer"),
            "crystallization_mode": data.get("crystallization_mode", "fractionate"),
        }

        # Override mode from CLI if provided
        if args.mode is not None:
            cfg_kwargs["melts_mode"] = args.mode

        return SimConfig(**cfg_kwargs)

    elif args.preset:
        from meltsapp.presets import PRESETS

        if args.preset not in PRESETS:
            available = ", ".join(sorted(PRESETS.keys()))
            print(f"Error: unknown preset '{args.preset}'. Available: {available}", file=sys.stderr)
            sys.exit(1)

        preset = PRESETS[args.preset]
        defaults = preset.get("defaults", {})
        cfg_kwargs = {
            "melts_mode": args.mode if args.mode is not None else 1,
            "composition": preset["composition"],
            "T_start": defaults.get("T_start", 1400.0),
            "T_end": defaults.get("T_end", 900.0),
            "dT": defaults.get("dT", -2.0),
            "P_start": defaults.get("P_start", 5000.0),
            "P_end": defaults.get("P_end", 1000.0),
            "crystallization_mode": "fractionate",
        }
        return SimConfig(**cfg_kwargs)

    else:
        print("Error: provide --config or --preset", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run MELTS crystallization simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --config ../cases/case_custom/config.json -o ../cases/case_custom/output\n"
            "  %(prog)s --preset nmorb --mode 1 -o ./output\n"
            "  %(prog)s --preset high_mg_basalt -o ./output\n"
        ),
    )
    parser.add_argument("--config", help="Path to config.json file")
    parser.add_argument("--mode", type=int, choices=[1, 2, 3, 4], help="MELTS mode override")
    parser.add_argument("--preset", help="Preset name (high_mg_basalt, nmorb, wet_morb, arc_basalt, bishop_tuff_rhyolite)")
    parser.add_argument("--output", "-o", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args)

    title = "MELTS Simulation"
    if args.config:
        with open(args.config) as f:
            data = json.load(f)
        title = data.get("name", title)
    elif args.preset:
        from meltsapp.presets import PRESETS
        title = PRESETS[args.preset].get("name", args.preset)

    print(f"=== {title} ===")
    print(f"Mode: {config.melts_mode}, T: {config.T_start}->{config.T_end} C (step {config.dT})")
    print(f"P: {config.P_start}->{config.P_end} bar")
    print(f"Crystallization: {config.crystallization_mode}")
    if config.fo2_buffer:
        print(f"fO2 buffer: {config.fo2_buffer} (offset {config.fo2_offset})")
    print()

    # Run simulation
    results: list[StepResult] = []
    for step_result in run_crystallization(config):
        results.append(step_result)

        # Console progress every 10 steps
        if step_result.step % 10 == 0 and step_result.liquid_mass > 0:
            lc = step_result.liquid_comp
            solid_names = [p for p in step_result.phases if not p.startswith("liquid")]
            print(
                f"  step {step_result.step:4d}  T={step_result.T:7.0f}  P={step_result.P:7.0f}  "
                f"Liq={step_result.liquid_mass:7.1f}g  SiO2={lc.get('SiO2', 0):6.2f}  "
                f"MgO={lc.get('MgO', 0):6.2f}  {'+'.join(solid_names)}"
            )

    if not results:
        print("No results produced (simulation may have failed at liquidus).", file=sys.stderr)
        sys.exit(1)

    print(f"\nCompleted {len(results)} steps.")

    # Write output files
    write_outputs(results, title, args.output)


if __name__ == "__main__":
    main()
