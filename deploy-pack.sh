#!/usr/bin/env bash
# 在源机器上执行：打包所有部署所需文件（代码 + 二进制依赖）
# 输出: melts-modern-deploy.tar.gz
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

ARCHIVE="melts-modern-deploy.tar.gz"

echo "=== 打包 MELTS Modern ==="

# 确认二进制存在
for f in alphamelts-app/alphamelts-app-2.3.1-linux/alphamelts_linux \
         alphamelts-py/alphamelts-py-2.3.1-linux/libalphamelts.so \
         lib/libpng12.so.0; do
    if [ ! -f "$f" ]; then
        echo "✗ 缺少: $f"
        exit 1
    fi
done

tar czf "${ARCHIVE}" \
    --exclude='__pycache__' \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='cases/*/output' \
    --exclude='*.log' \
    --exclude='nohup.out' \
    --exclude='.gstack' \
    --exclude='.superpowers' \
    --exclude='.claude' \
    meltsapp/ \
    web/ \
    alphamelts-app/ \
    alphamelts-py/ \
    lib/ \
    tests/ \
    scripts/ \
    deploy.sh \
    pyproject.toml \
    CLAUDE.md

SIZE=$(du -h "${ARCHIVE}" | cut -f1)
echo "✓ 打包完成: ${ARCHIVE} (${SIZE})"
echo ""
echo "部署步骤:"
echo "  1. scp ${ARCHIVE} user@目标机器:/home/user/"
echo "  2. ssh user@目标机器"
echo "  3. mkdir -p ~/proj/melts-modern && cd ~/proj/melts-modern"
echo "  4. tar xzf ~/${ARCHIVE}"
echo "  5. bash deploy.sh"
