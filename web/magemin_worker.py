#!/usr/bin/env python3
"""MAGEMin simulation worker. Reads JSON config from stdin, writes JSON lines to stdout.

Mirrors web/worker.py but uses the MAGEMin engine (via PetThermoTools / Julia)
instead of the MELTS C library. The first invocation in a fresh process is
slow due to Julia JIT compilation (1-2 minutes).
"""
import sys
import os
import json

# Save stdout before any imports might redirect it (mirrors worker.py pattern).
_OUTPUT_FD = os.dup(1)
_OUTPUT = os.fdopen(_OUTPUT_FD, "w", buffering=1)

# Add project root to path so meltsapp can be imported
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from meltsapp.schemas import MageminConfig
from meltsapp.magemin_engine import run_magemin


def emit(msg):
    """Write a JSON line to the saved output pipe."""
    try:
        _OUTPUT.write(json.dumps(msg) + "\n")
        _OUTPUT.flush()
    except BrokenPipeError:
        pass


def main():
    config_json = sys.stdin.read()
    config = MageminConfig.model_validate_json(config_json)

    emit({
        "type": "init",
        "n_steps": 0,
        "message": "Initializing MAGEMin engine (first run may take 1-2 minutes)...",
    })

    run_magemin(config, emit)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        emit({"type": "error", "message": str(e)})
        sys.exit(1)
