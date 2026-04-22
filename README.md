# MELTS Modern

Web-based interactive frontend for thermodynamic phase equilibrium modeling. Supports two computation backends:

| Backend | Engine | Method | Database |
|---------|--------|--------|----------|
| **rhyolite-MELTS** | C library (`libalphamelts.so`) | Gibbs-Duhem integration | Ghiorso & Sack |
| **MAGEMin** | Julia via PetThermoTools | Gibbs free energy minimization | Holland-Powell |

Designed for petrologists who want to run crystallization simulations without writing code.

## Features

- **Dual backends** — choose rMELTS (4 modes: v1.0/1.1/1.2, pMELTS) or MAGEMin (Green2025, Weller2024)
- **Interactive simulation** — set composition, T/P range, click Run
- **5 preset compositions** — High-Mg Basalt, N-MORB, Wet MORB, Arc Basalt, Bishop Tuff Rhyolite
- **15 Plotly charts** — TAS, AFM, Harker diagrams (MgO/SiO2), phase evolution, liquid composition vs T, P-T path, mineral chemistry (olivine, cpx, plagioclase, spinel), system thermodynamics, density
- **Temperature scrubber** — drag slider or hit Play to animate through crystallization steps, with phase-change toast notifications
- **Batch mode** — upload Excel with multiple samples, run all at once, view per-sample results
- **Parameter sweep** — vary T, P, or fO2 over a range in a single run

## Quick Start

Full deployment (rMELTS + MAGEMin):

```bash
git clone https://github.com/SteadfastAsArt/melts-modern.git
cd melts-modern
bash deploy.sh
```

rMELTS only (faster, no Julia dependency):

```bash
bash deploy.sh --skip-magemin
```

`deploy.sh` handles everything: system libraries, Python packages, Julia/PetThermoTools (optional), systemd service, log rotation. After it finishes you'll see the URL.

**Requirements:** x86-64 Linux (Ubuntu 20.04+/Debian 11+), Python >= 3.10, sudo access.

## Manual Run (development)

```bash
# rMELTS only
pip install fastapi uvicorn pandas plotly pydantic openpyxl
export LD_LIBRARY_PATH=./lib
python -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=9000)"

# With MAGEMin — also install Julia and PetThermoTools
pip install petthermotools juliacall
```

Open `http://localhost:9000` in your browser.

## Project Structure

```
meltsapp/                    # Python package
├── engine.py                # MeltsSession — wraps MELTS C library via ctypes
├── magemin_engine.py        # MAGEMin engine via PetThermoTools/Julia
├── simulation.py            # run_crystallization() generator (rMELTS)
├── schemas.py               # Pydantic SimConfig, MageminConfig, BatchConfig
├── presets.py               # 5 named compositions with T/P defaults
└── plotting/
    ├── bindplotly.py        # 15 Plotly figure builders
    └── common.py            # TAS boundaries, AFM coords, phase colors

web/                         # FastAPI application
├── app.py                   # REST + WebSocket endpoints (both backends)
├── worker.py                # rMELTS subprocess worker
├── magemin_worker.py        # MAGEMin subprocess worker
└── static/
    ├── index.html           # Single-page app
    ├── app.js               # Vanilla JS + Plotly
    ├── style.css
    └── melts_template.xlsx  # Template for batch upload

alphamelts-app/              # Pre-compiled MELTS binary (x86-64 Linux)
alphamelts-py/               # Python bindings + libalphamelts.so
lib/                         # Bundled shared libraries (libpng12)

deploy.sh                    # One-click deployment (rMELTS + optional MAGEMin)
deploy-pack.sh               # Pack tarball for offline transfer
update-melts.sh              # Sync upstream rMELTS binary updates
requirements-magemin.txt     # MAGEMin deps version pin (for upstream tracking)

.github/workflows/
├── test.yml                 # Push/PR → pytest + vitest
├── deploy.yml               # Test pass → SSH deploy to server
└── check-upstream.yml       # Weekly PyPI check → auto PR

tests/                       # pytest + vitest test suites
```

## Deployment

### What `deploy.sh` does

| Step | Action |
|------|--------|
| 1 | Verify rMELTS binaries are present |
| 2 | `apt install` system libraries (libgsl, libxml2) |
| 3 | `pip install` Python dependencies (fastapi, plotly, etc.) |
| 4 | Install Julia + PetThermoTools for MAGEMin (unless `--skip-magemin`) |
| 5 | Create systemd service (`melts-modern.service`) |
| 6 | Configure log rotation (`/var/log/melts-modern.log`) |
| 7 | Enable, start, and verify the service |

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

### Upstream Dependencies & Update Flow

两个后端的上游更新方式不同：

| 上游 | 分发方式 | 本项目集成 | 更新机制 |
|------|---------|-----------|---------|
| **alphamelts** (rMELTS) | 预编译二进制，手动下载 | 二进制直接提交到 git | `update-melts.sh` 手动同步 |
| **PetThermoTools** (MAGEMin) | PyPI 包 | pip install，版本 pin 在 `requirements-magemin.txt` | GitHub Actions 每周自动检查，有新版开 PR |

**rMELTS 二进制更新：**

```bash
# 在有上游目录的开发机上执行
bash update-melts.sh                    # 默认 /home/laz/proj/melts
bash update-melts.sh /path/to/melts     # 或指定路径

# 检查 diff，提交推送
git add alphamelts-app/ alphamelts-py/ lib/
git commit -m "chore: update MELTS binaries to X.Y.Z"
git push
```

**PetThermoTools 更新：**

`check-upstream.yml` 每周一自动检查 PyPI，发现新版会自动开 PR。合并 PR 后走正常的 test → deploy 流程。也可以手动更新：

```bash
pip install --upgrade petthermotools
# 更新 pin 文件
pip show petthermotools | grep Version  # 查看新版本号
# 编辑 requirements-magemin.txt 中的版本号
git add requirements-magemin.txt && git commit -m "chore(deps): update PetThermoTools" && git push
```

### CI/CD

三个 GitHub Actions workflow 已配置在 `.github/workflows/`：

```
git push master
    │
    ▼
┌─────────┐    pass    ┌──────────┐
│  test   │ ─────────→ │  deploy  │ ─→ SSH 到服务器 git pull + restart
│ pytest  │            │ ssh-action│
│ vitest  │    fail    └──────────┘
└─────────┘ ─→ 阻断，不部署

每周一 16:00 (UTC+8)
    │
    ▼
┌─────────────────┐    有新版    ┌────────────┐
│ check-upstream  │ ──────────→ │ 自动开 PR  │ ─→ 合并后触发 test → deploy
│ 查 PyPI 版本    │            └────────────┘
└─────────────────┘
```

**启用步骤：** 在 GitHub repo → Settings → Secrets and variables → Actions 中添加：

| Secret | 值 |
|--------|----|
| `DEPLOY_HOST` | 目标机器 IP 或域名 |
| `DEPLOY_USER` | SSH 用户名 |
| `DEPLOY_SSH_KEY` | SSH 私钥内容 |

多台机器部署时，在 `deploy.yml` 的 `matrix.server` 中扩展，每台机器配对应的 secrets。

## Testing

```bash
pytest tests/              # Python: smoke tests for all figure builders
npx vitest run             # JS: unit tests for scrubber logic
```

## Architecture Notes

- **rMELTS:** The C library is a global singleton — only one simulation per process. Each simulation spawns `worker.py` as a subprocess (stdin: SimConfig JSON, stdout: JSON lines).
- **MAGEMin:** Uses Julia via PetThermoTools/juliacall. First invocation is slow (Julia JIT, 1-2 min); subsequent calls within the same process are fast. No global singleton — concurrent sessions are possible. Each simulation spawns `magemin_worker.py`.
- `libalphamelts.so` writes to stdout internally. `MeltsSession.__init__` redirects fd 1 to `/dev/null`; the worker saves the real stdout fd before import.
- All Plotly figures are built server-side as JSON. The frontend renders with `Plotly.react()` and `responsive: true` (no fixed width in Python).

## License

The MELTS thermodynamic model and binaries are developed by OFM Research. See [melts.ofm-research.org](https://melts.ofm-research.org/) for licensing terms. MAGEMin is developed by Riel et al. This web frontend is for research use.
