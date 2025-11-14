#!/bin/bash
# 运行 titan23 设计在 OpenROAD 上的完整流程
# 使用方法: ./run_titan23_openroad.sh <设计名称> [输出目录]

set -e

# 检查参数
if [ $# -lt 1 ]; then
    echo "使用方法: $0 <设计名称> [输出目录]"
    echo ""
    echo "示例:"
    echo "  $0 des90"
    echo "  $0 des90 results/des90_nangate45"
    echo ""
    echo "可用的 titan23 设计:"
    ls -1 data/titan23/benchmarks/titan23/ | head -10
    exit 1
fi

DESIGN=$1
OUTPUT_DIR=${2:-"results/${DESIGN}_nangate45"}

# 路径设置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查设计是否存在
DESIGN_DIR="data/titan23/benchmarks/titan23/${DESIGN}"
if [ ! -d "$DESIGN_DIR" ]; then
    echo "错误: 找不到设计目录: $DESIGN_DIR"
    exit 1
fi

# 查找 BLIF 文件
BLIF_FILE=$(find "$DESIGN_DIR/netlists" -name "*.blif" | head -1)
if [ -z "$BLIF_FILE" ]; then
    echo "错误: 在 $DESIGN_DIR/netlists 中找不到 BLIF 文件"
    exit 1
fi

echo "=========================================="
echo "Titan23 设计 OpenROAD 流程"
echo "=========================================="
echo "设计名称: $DESIGN"
echo "BLIF 文件: $BLIF_FILE"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 步骤1: 转换 BLIF 到 Verilog（带综合）
VERILOG_FILE="$OUTPUT_DIR/${DESIGN}.v"
echo "步骤 1: 转换 BLIF 到 Verilog（使用 yosys 综合）..."
if [ ! -f "$VERILOG_FILE" ]; then
    # 先尝试不使用 liberty 文件（通用综合）
    # 这样可以避免 liberty 文件中的单元定义问题
    echo "  使用通用综合（将 FPGA 原语转换为通用逻辑门）"
    python3 "$PROJECT_ROOT/src/utils/convert_blif_to_verilog.py" "$BLIF_FILE" -o "$VERILOG_FILE"
    
    if [ $? -ne 0 ]; then
        echo "错误: BLIF 转换失败"
        exit 1
    fi
    
    echo "  注意: 输出是通用逻辑门，OpenROAD 需要能够识别这些门"
else
    echo "  ✓ Verilog 文件已存在，跳过转换"
fi

# 步骤2: 运行 OpenROAD
echo ""
echo "步骤 2: 运行 OpenROAD 综合和布局..."
export DESIGN=$DESIGN
export VERILOG_FILE="$VERILOG_FILE"
export OUTPUT_DIR="$OUTPUT_DIR"

openroad -exit "$PROJECT_ROOT/src/utils/titan23_to_openroad.tcl"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ 完成！"
    echo "=========================================="
    echo "输出文件:"
    echo "  - DEF: $OUTPUT_DIR/${DESIGN}.def"
    echo "  - Verilog: $OUTPUT_DIR/${DESIGN}.v"
    echo "  - SDC: $OUTPUT_DIR/${DESIGN}.sdc"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "✗ 失败"
    echo "=========================================="
    exit 1
fi

