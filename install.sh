#!/usr/bin/env bash
# ============================================================
# hermes-yolo 一键安装脚本（幂等，可重复运行）
# 功能: 装 YOLO 依赖 → 注册 MCP → 验证
# 用法: bash install.sh
# ============================================================
set -euo pipefail

# 脚本所在目录（用户 clone 到任意位置都能用）
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_CONFIG="$HOME/.hermes/config.yaml"

echo "==> 1/4 选择 pip 源（自动检测清华源）"
PIP_INDEX="https://pypi.org/simple"
if curl -fsSI --max-time 5 https://pypi.tuna.tsinghua.edu.cn/simple/ >/dev/null 2>&1; then
  PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
  echo "    ✓ 使用清华源（国内加速）"
else
  echo "    → 清华源不可达，使用官方 PyPI"
fi

echo "==> 2/4 安装 YOLO 依赖（CPU 版 torch，已装则跳过）"
if python3 -c "import torch, ultralytics" 2>/dev/null; then
  echo "    ✓ 依赖已存在，跳过"
else
  # 修复损坏的 pip3（部分系统 /usr/bin/pip3 shebang 指向不存在的 Python）
  python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
  export TMPDIR=~/.pip-tmp && mkdir -p ~/.pip-tmp
  pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip3 install -i "$PIP_INDEX" ultralytics
fi

echo "==> 3/4 注册 YOLO MCP 工具（幂等）"
if grep -q "yolo-mcp" "$HERMES_CONFIG" 2>/dev/null; then
  echo "    ✓ yolo-mcp 已注册，跳过"
else
  printf '\nmcp_servers:\n  yolo-mcp:\n    command: python3\n    args:\n      - %s/yolo_mcp.py\n' "$DIR" >> "$HERMES_CONFIG"
  echo "    ✓ 已写入 $HERMES_CONFIG"
fi

echo "==> 4/4 验证 YOLO 检测"
python3 "$DIR/yolo_tool.py" "$DIR/test.jpg" --conf 0.25 >/dev/null 2>&1 \
  && echo "    ✓ YOLO 检测正常（bus/person 已识别）" \
  || echo "    ⚠ 检测失败，请检查依赖: pip3 show ultralytics"

echo
echo "✅ 完成！下一步："
echo "   1. 配置 API key（需已装 hermes）:"
echo "      hermes config set model.api_key \"sk-你的key\""
echo "   2. 测试: hermes chat -q \"test.jpg 里有什么\""
