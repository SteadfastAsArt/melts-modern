#!/usr/bin/env bash
# MELTS Modern 一键部署脚本
# 用法: 在目标机器上执行  bash deploy.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="melts-modern"
PORT=9000
LOG_FILE="/var/log/${SERVICE_NAME}.log"

echo "=== MELTS Modern 部署 ==="
echo "项目目录: ${APP_DIR}"
echo ""

# ---- 1. 检查二进制依赖 ----
echo "[1/6] 检查二进制依赖..."
for f in alphamelts-app/alphamelts-app-2.3.1-linux/alphamelts_linux \
         alphamelts-py/alphamelts-py-2.3.1-linux/libalphamelts.so \
         lib/libpng12.so.0; do
    if [ ! -f "${APP_DIR}/${f}" ]; then
        echo "  ✗ 缺少: ${f}"
        echo "  请先用 deploy-pack.sh 在源机器打包，再 scp 到此处。"
        exit 1
    fi
    echo "  ✓ ${f}"
done

# ---- 2. 安装系统依赖 ----
echo ""
echo "[2/6] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq libgsl27 libxml2 libz3-dev > /dev/null
echo "  ✓ libgsl libxml2 libz"

# ---- 3. Python 环境 ----
echo ""
echo "[3/6] 检查 Python 环境..."

# 找 python3
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

# 检查并安装 pip 依赖
echo "  安装 Python 依赖..."
"$PYTHON" -m pip install --quiet fastapi uvicorn pandas plotly pydantic openpyxl
echo "  ✓ Python 依赖已就绪"

# ---- 4. 创建 systemd service ----
echo ""
echo "[4/6] 配置 systemd 服务..."

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << SVCEOF
[Unit]
Description=MELTS Modern Web App
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${APP_DIR}
Environment=LD_LIBRARY_PATH=${APP_DIR}/lib
ExecStart=${PYTHON} -c "import uvicorn; from web.app import app; uvicorn.run(app, host='0.0.0.0', port=${PORT})"
Restart=always
RestartSec=3
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

[Install]
WantedBy=multi-user.target
SVCEOF

echo "  ✓ /etc/systemd/system/${SERVICE_NAME}.service"

# ---- 5. 日志轮转 ----
echo ""
echo "[5/6] 配置日志轮转..."
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

# ---- 6. 启动服务 ----
echo ""
echo "[6/6] 启动服务..."
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
    echo "  管理命令:"
    echo "    sudo systemctl status ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo journalctl -u ${SERVICE_NAME} -f"
else
    echo "  ✗ 服务启动失败"
    sudo systemctl status ${SERVICE_NAME} --no-pager
    exit 1
fi
