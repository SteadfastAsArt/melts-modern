#!/bin/bash
# Wrapper script for rhyolite-MELTS
MELTS_DIR="$(cd "$(dirname "$0")" && pwd)"
export LD_LIBRARY_PATH="${MELTS_DIR}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "${MELTS_DIR}/Melts-rhyolite-public" "$@"
