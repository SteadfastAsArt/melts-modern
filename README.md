# MELTS Modern

Web-based interactive frontend for [rhyolite-MELTS](https://melts.ofm-research.org/) thermodynamic modeling. Designed for petrologists who want to run crystallization simulations without writing code.

## Features

- **Interactive simulation** — set composition, T/P range, choose from 4 MELTS modes (rhyolite-MELTS v1.0/1.1/1.2, pMELTS), click Run
- **5 preset compositions** — High-Mg Basalt, N-MORB, Wet MORB, Arc Basalt, Bishop Tuff Rhyolite
- **15 Plotly charts** — TAS, AFM, Harker diagrams (MgO/SiO2), phase evolution, liquid composition vs T, P-T path, mineral chemistry (olivine, cpx, plagioclase, spinel), system thermodynamics, density
- **Temperature scrubber** — drag slider or hit Play to animate through crystallization steps, with phase-change toast notifications
- **Batch mode** — upload Excel with multiple samples, run all at once, view per-sample results
- **Parameter sweep** — vary T, P, or fO2 over a range in a single run

## Quick Start

```bash
git clone https://github.com/SteadfastAsArt/melts-modern.git
cd melts-modern
bash deploy.sh
```

`deploy.sh` handles everything: system libraries, Python packages, systemd service, log rotation. After it finishes you'll see the URL.

**Requirements:** x86-64 Linux (Ubuntu 20.04+/Debian 11+), Python >= 3.10, sudo access.

## Manual Run (development)

```bash
pip install fastapi uvicorn pandas plotly pydantic openpyxl
export LD_LIBRARY_PATH=./lib
python -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=9000)"
```

Open `http://localhost:9000` in your browser.

## Project Structure

```
meltsapp/                    # Python package
├── engine.py                # MeltsSession — wraps MELTS C library via ctypes
├── simulation.py            # run_crystallization() generator
├── schemas.py               # Pydantic SimConfig, BatchConfig; dataclass StepResult
├── presets.py               # 5 named compositions with T/P defaults
└── plotting/
    ├── bindplotly.py        # 15 Plotly figure builders
    └── common.py            # TAS boundaries, AFM coords, phase colors

web/                         # FastAPI application
├── app.py                   # REST + WebSocket endpoints
├── worker.py                # Subprocess per simulation (C library is a global singleton)
└── static/
    ├── index.html           # Single-page app
    ├── app.js               # Vanilla JS + Plotly
    ├── style.css
    └── melts_template.xlsx  # Template for batch upload

alphamelts-app/              # Pre-compiled MELTS binary (x86-64 Linux)
alphamelts-py/               # Python bindings + libalphamelts.so
lib/                         # Bundled shared libraries (libpng12)

deploy.sh                    # One-click deployment script
deploy-pack.sh               # Pack tarball for offline transfer
tests/                       # pytest + vitest test suites
```

## Deployment

### What `deploy.sh` does

| Step | Action |
|------|--------|
| 1 | Verify MELTS binaries are present |
| 2 | `apt install` system libraries (libgsl, libxml2) |
| 3 | `pip install` Python dependencies |
| 4 | Create systemd service (`melts-modern.service`) |
| 5 | Configure log rotation (`/var/log/melts-modern.log`) |
| 6 | Enable, start, and verify the service |

### Service Management

```bash
sudo systemctl status melts-modern     # check status
sudo systemctl restart melts-modern    # restart after code changes
sudo journalctl -u melts-modern -f     # live logs
```

### Update (after git push)

```bash
cd /path/to/melts-modern
git pull
sudo systemctl restart melts-modern
```

### CI/CD

The deploy script is idempotent — running it again updates the service in place. A minimal GitHub Actions workflow:

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd ~/proj/melts-modern
            git pull origin master
            bash deploy.sh
```

Set `HOST`, `USER`, `SSH_KEY` in repo Settings → Secrets. Each push to master will SSH in, pull the latest code, and restart the service.

## Testing

```bash
pytest tests/              # Python: smoke tests for all figure builders
npx vitest run             # JS: unit tests for scrubber logic
```

## Architecture Notes

- The MELTS C library is a **global singleton** — only one simulation can run per process. Each simulation spawns `worker.py` as a subprocess that reads `SimConfig` from stdin and emits JSON lines to stdout.
- `libalphamelts.so` writes to stdout internally. `MeltsSession.__init__` redirects fd 1 to `/dev/null`; the worker saves the real stdout fd before import.
- All Plotly figures are built server-side as JSON. The frontend renders with `Plotly.react()` and `responsive: true` (no fixed width in Python).

## License

The MELTS thermodynamic model and binaries are developed by OFM Research. See [melts.ofm-research.org](https://melts.ofm-research.org/) for licensing terms. This web frontend is for research use.
