#!/usr/bin/env bash
# 从上游目录更新 MELTS 二进制到本项目
# 用法: bash update-melts.sh [上游目录]
#   默认上游: /home/laz/proj/melts
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
UPSTREAM="${1:-/home/laz/proj/melts}"

echo "=== 更新 MELTS 二进制 ==="
echo "上游目录: ${UPSTREAM}"
echo "项目目录: ${APP_DIR}"
echo ""

# 检查上游目录
for d in alphamelts-app alphamelts-py lib; do
    if [ ! -d "${UPSTREAM}/${d}" ]; then
        echo "✗ 上游缺少: ${UPSTREAM}/${d}"
        exit 1
    fi
done

# 记录旧版本
OLD_APP=$(ls "${APP_DIR}/alphamelts-app/" 2>/dev/null | head -1)
OLD_PY=$(ls "${APP_DIR}/alphamelts-py/" 2>/dev/null | head -1)

# 删除旧文件，复制新文件
for d in alphamelts-app alphamelts-py lib; do
    rm -rf "${APP_DIR}/${d}"
    cp -r "${UPSTREAM}/${d}" "${APP_DIR}/${d}"
    # 如果上游是符号链接目标，解引用
    if [ -L "${UPSTREAM}/${d}" ]; then
        rm -rf "${APP_DIR}/${d}"
        cp -rL "${UPSTREAM}/${d}" "${APP_DIR}/${d}"
    fi
done

# 清理不需要的文件
find "${APP_DIR}/alphamelts-app" -name "logfile.txt" -delete 2>/dev/null || true
find "${APP_DIR}/alphamelts-py" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 显示结果
NEW_APP=$(ls "${APP_DIR}/alphamelts-app/" 2>/dev/null | head -1)
NEW_PY=$(ls "${APP_DIR}/alphamelts-py/" 2>/dev/null | head -1)

echo ""
echo "alphamelts-app: ${OLD_APP:-?} → ${NEW_APP}"
echo "alphamelts-py:  ${OLD_PY:-?} → ${NEW_PY}"
echo ""

# 显示 git diff 概览
cd "${APP_DIR}"
if git diff --stat -- alphamelts-app alphamelts-py lib | grep -q '.'; then
    echo "变更文件:"
    git diff --stat -- alphamelts-app alphamelts-py lib
    echo ""
    echo "下一步:"
    echo "  git add alphamelts-app/ alphamelts-py/ lib/"
    echo "  git commit -m 'chore: update MELTS binaries to ${NEW_APP}'"
    echo "  git push"
else
    echo "✓ 二进制无变化，无需提交。"
fi
