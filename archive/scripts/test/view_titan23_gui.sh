#!/bin/bash
# 在 GUI 中查看 titan23 设计布局结果
# 使用方法: ./scripts/view_titan23_gui.sh [设计名称]

DESIGN=${1:-"des90"}
OUTPUT_DIR="results/${DESIGN}_nangate45"

# 检查输出目录是否存在
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误: 输出目录不存在: $OUTPUT_DIR"
    echo "请先运行: ./scripts/run_titan23_openroad.sh $DESIGN"
    exit 1
fi

# 检查 DEF 文件是否存在
if [ ! -f "$OUTPUT_DIR/${DESIGN}.def" ]; then
    echo "错误: 找不到 DEF 文件: $OUTPUT_DIR/${DESIGN}.def"
    exit 1
fi

echo "=========================================="
echo "在 GUI 中查看 titan23 设计布局"
echo "=========================================="
echo "设计名称: $DESIGN"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 设置环境变量
export DESIGN=$DESIGN
export OUTPUT_DIR=$OUTPUT_DIR

# 尝试使用本地编译的 OpenROAD（如果有 GUI 支持）
LOCAL_OPENROAD="/Users/keqin/Documents/workspace/openroad/OpenROAD/build/src/openroad"
if [ -f "$LOCAL_OPENROAD" ]; then
    echo "✓ 使用本地编译的 OpenROAD: $LOCAL_OPENROAD"
    echo "正在启动 GUI..."
    "$LOCAL_OPENROAD" -gui scripts/load_titan23_gui.tcl
else
    echo "⚠️  未找到本地编译的 OpenROAD"
    echo "使用系统 OpenROAD: $(which openroad)"
    echo ""
    echo "注意：如果系统 OpenROAD 没有 GUI 支持，会显示错误"
    echo "如果需要 GUI，请确保 OpenROAD 已编译并启用 GUI 支持"
    echo ""
    openroad -gui scripts/load_titan23_gui.tcl
fi
