#!/usr/bin/env bash
# px2pptx.sh — 一键运行 px-image2pptx
#
# 封装了所有需要的环境变量(避免 ~/.cache 权限问题)
#
# 用法:
#   ./px2pptx.sh <input.png> [output.pptx] [lang]
#   ./px2pptx.sh slide.png                 # 默认输出 slide.pptx, lang=ch
#   ./px2pptx.sh slide.png out.pptx en     # 英文
#   ./px2pptx.sh slide.png out.pptx ch --skip-inpaint  # 跳过 LAMA (纯色背景)
#
# 注意:第一次跑会下 ~370MB 模型(PP-OCRv5 + LAMA),后续秒级

set -e

# === 路径 ===
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$WORKSPACE/.venv"
CACHE_BASE="${PPTX_CACHE_BASE:-/tmp}"

# === 检查 venv ===
if [ ! -d "$VENV" ]; then
    echo "❌ venv 不存在: $VENV"
    echo "   请先创建: cd $WORKSPACE && uv venv --python 3.11 .venv"
    exit 1
fi

# === 参数 ===
INPUT="${1:-}"
OUTPUT="${2:-}"
LANG="${3:-ch}"

if [ -z "$INPUT" ]; then
    echo "用法: $0 <input.png> [output.pptx] [lang]"
    echo ""
    echo "示例:"
    echo "  $0 slide.png                # 输出 slide.pptx, lang=ch"
    echo "  $0 slide.png out.pptx en    # 英文"
    echo ""
    echo "额外参数(透传给 px-image2pptx):"
    echo "  --skip-inpaint              # 跳过 LAMA 背景修复(快)"
    echo "  --min-font 10 --max-font 60 # 字号范围"
    echo "  --work-dir ./debug/         # 保留中间产物"
    echo "  --max-inpaint-size 2048     # 缩 LAMA 输入,提速"
    exit 1
fi

# 默认输出名
if [ -z "$OUTPUT" ]; then
    OUTPUT="${INPUT%.*}.pptx"
fi

# === 环境变量(关键!避开 ~/.cache 权限问题) ===
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export PADDLE_PDX_CACHE_HOME="$CACHE_BASE/paddlex"
export TORCH_HOME="$CACHE_BASE/torch-cache"
export MODELSCOPE_CACHE="$CACHE_BASE/ms-cache"

# 激活 venv
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# === 跑 ===
echo "🚀 px-image2pptx"
echo "   in : $INPUT"
echo "   out: $OUTPUT"
echo "   lang: $LANG"
echo ""

px-image2pptx "$INPUT" -o "$OUTPUT" --lang "$LANG" "${@:4}"