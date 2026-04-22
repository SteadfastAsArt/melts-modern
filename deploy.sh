#!/usr/bin/env bash
# MELTS Modern 一键部署脚本
# 用法: bash deploy.sh [--skip-magemin]
# --skip-magemin  跳过 Julia/MAGEMin 安装（只部署 rMELTS 后端）
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="melts-modern"
PORT=9000
LOG_FILE="/var/log/${SERVICE_NAME}.log"
JULIA_VERSION="1.11.9"
JULIA_DIR="${HOME}/julia"

SKIP_MAGEMIN=false
[[ "${1:-}" == "--skip-magemin" ]] && SKIP_MAGEMIN=true

echo "=== MELTS Modern 部署 ==="
echo "项目目录: ${APP_DIR}"
echo "MAGEMin:  $( $SKIP_MAGEMIN && echo '跳过' || echo '安装' )"
echo ""

# ---- 1. 检查 rMELTS 二进制依赖 ----
echo "[1/7] 检查 rMELTS 二进制依赖..."
for f in alphamelts-app/alphamelts-app-2.3.1-linux/alphamelts_linux \
         alphamelts-py/alphamelts-py-2.3.1-linux/libalphamelts.so \
         lib/libpng12.so.0; do
    if [ ! -f "${APP_DIR}/${f}" ]; then
        echo "  ✗ 缺少: ${f}"
        exit 1
    fi
    echo "  ✓ ${f}"
done

# ---- 2. 安装系统依赖 ----
echo ""
echo "[2/7] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq libgsl27 libxml2 libz3-dev > /dev/null
echo "  ✓ libgsl libxml2 libz"

# ---- 3. Python 环境 ----
echo ""
echo "[3/7] 检查 Python 环境..."

PYTHON=""
for p in "${APP_DIR}/venv/bin/python3" "${HOME}/miniconda3/bin/python3" "$(which python3 2>/dev/null)"; do
    if [ -n "$p" ] && [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ✗ 未找到 python3，请先安装 Python >= 3.10"
    exit 1
fi

PYVER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: ${PYTHON} (${PYVER})"

echo "  安装 Python 依赖..."
"$PYTHON" -m pip install --quiet fastapi uvicorn pandas plotly pydantic openpyxl
echo "  ✓ rMELTS Python 依赖已就绪"

# ---- 4. Julia + MAGEMin (可选) ----
echo ""
if $SKIP_MAGEMIN; then
    echo "[4/7] 跳过 Julia/MAGEMin 安装"
else
    echo "[4/7] 安装 Julia + MAGEMin..."

    # 4a. Julia
    if [ -x "${JULIA_DIR}/bin/julia" ]; then
        CURRENT_VER=$("${JULIA_DIR}/bin/julia" --version 2>/dev/null | awk '{print $3}')
        echo "  Julia 已安装: ${CURRENT_VER}"
    else
        echo "  下载 Julia ${JULIA_VERSION}..."
        JULIA_MAJOR=$(echo "$JULIA_VERSION" | cut -d. -f1-2)
        JULIA_TAR="julia-${JULIA_VERSION}-linux-x86_64.tar.gz"
        JULIA_URL="https://julialang-s3.julialang.org/bin/linux/x64/${JULIA_MAJOR}/${JULIA_TAR}"
        curl -fsSL "${JULIA_URL}" -o "/tmp/${JULIA_TAR}"
        mkdir -p "${JULIA_DIR}"
        tar xzf "/tmp/${JULIA_TAR}" -C "${HOME}" --transform="s/^julia-${JULIA_VERSION}/julia/"
        rm "/tmp/${JULIA_TAR}"
        echo "  ✓ Julia ${JULIA_VERSION} → ${JULIA_DIR}"
    fi

    # 4b. PetThermoTools
    if "$PYTHON" -c "import PetThermoTools" 2>/dev/null; then
        PTT_VER=$("$PYTHON" -c "import PetThermoTools; print(PetThermoTools.__version__)" 2>/dev/null || echo "?")
        echo "  PetThermoTools 已安装: ${PTT_VER}"
    else
        echo "  安装 PetThermoTools（含 Julia 包编译，首次约 10-20 分钟）..."
        PATH="${JULIA_DIR}/bin:${PATH}" "$PYTHON" -m pip install --quiet petthermotools juliacall
        echo "  预编译 Julia 包..."
        PATH="${JULIA_DIR}/bin:${PATH}" "$PYTHON" -c "
import os
os.environ['JULIA_DEPOT_PATH'] = os.path.expanduser('~/.julia')
from PetThermoTools import Path
print('  ✓ PetThermoTools + Julia 包编译完成')
" 2>&1 | tail -1
    fi
fi

# ---- 5. 创建 systemd service ----
echo ""
echo "[5/7] 配置 systemd 服务..."

EXTRA_ENV=""
if ! $SKIP_MAGEMIN && [ -d "${JULIA_DIR}" ]; then
    EXTRA_ENV="Environment=JULIA_DEPOT_PATH=${HOME}/.julia
Environment=PATH=${JULIA_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
fi

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << SVCEOF
[Unit]
Description=MELTS Modern Web App
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${APP_DIR}
Environment=LD_LIBRARY_PATH=${APP_DIR}/lib
${EXTRA_ENV}
ExecStart=${PYTHON} -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=${PORT})"
Restart=always
RestartSec=3
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

[Install]
WantedBy=multi-user.target
SVCEOF

echo "  ✓ /etc/systemd/system/${SERVICE_NAME}.service"

# ---- 6. 日志轮转 ----
echo ""
echo "[6/7] 配置日志轮转..."
sudo tee /etc/logrotate.d/${SERVICE_NAME} > /dev/null << LOGEOF
${LOG_FILE} {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
LOGEOF
echo "  ✓ /etc/logrotate.d/${SERVICE_NAME}"

# ---- 7. 启动服务 ----
echo ""
echo "[7/7] 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}
sleep 2

if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "  ✓ 服务运行中"
    echo ""
    echo "=== 部署完成 ==="
    IP=$(hostname -I | awk '{print $1}')
    echo "  访问地址: http://${IP}:${PORT}"
    echo ""
    echo "  后端状态:"
    echo "    rMELTS:  ✓ 就绪"
    if $SKIP_MAGEMIN; then
        echo "    MAGEMin: — 未安装（用 bash deploy.sh 安装完整版）"
    elif [ -x "${JULIA_DIR}/bin/julia" ]; then
        echo "    MAGEMin: ✓ 就绪 (Julia + PetThermoTools)"
    else
        echo "    MAGEMin: ✗ Julia 未找到"
    fi
    echo ""
    echo "  管理命令:"
    echo "    sudo systemctl status ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo journalctl -u ${SERVICE_NAME} -f"
else
    echo "  ✗ 服务启动失败"
    sudo systemctl status ${SERVICE_NAME} --no-pager
    exit 1
fi
