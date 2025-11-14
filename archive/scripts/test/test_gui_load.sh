#!/bin/bash
# OpenROAD GUI 加载测试脚本

echo "=========================================="
echo "OpenROAD GUI 加载设计测试"
echo "=========================================="
echo ""

# 检查 openroad 命令
if ! command -v openroad &> /dev/null; then
    echo "❌ 错误: 找不到 openroad 命令"
    echo "   请确保 openroad 在 PATH 中"
    exit 1
fi

echo "✓ OpenROAD 已找到: $(which openroad)"
echo "  版本: $(openroad -version 2>&1 | head -1)"
echo ""

# 检查设计文件
DESIGN_DIR="data/ispd2015/mgc_pci_bridge32_a"
if [ ! -d "$DESIGN_DIR" ]; then
    echo "❌ 错误: 设计目录不存在: $DESIGN_DIR"
    exit 1
fi

if [ ! -f "$DESIGN_DIR/tech.lef" ] || [ ! -f "$DESIGN_DIR/cells.lef" ] || [ ! -f "$DESIGN_DIR/floorplan.def" ]; then
    echo "❌ 错误: 设计文件不完整"
    exit 1
fi

echo "✓ 设计文件检查通过: $DESIGN_DIR"
echo ""

# 测试非GUI模式加载
echo "测试非GUI模式加载..."
if openroad -exit scripts/load_design_gui_verified.tcl 2>&1 | grep -q "设计已成功加载"; then
    echo "✓ 非GUI模式加载成功"
else
    echo "⚠️  非GUI模式加载有警告（可能正常）"
fi
echo ""

echo "=========================================="
echo "准备启动 GUI..."
echo "=========================================="
echo ""
echo "将执行命令: openroad -gui scripts/load_design_gui_verified.tcl"
echo ""
echo "GUI 窗口将自动打开并加载设计"
echo "按 Ctrl+C 可以取消"
echo ""
read -p "按 Enter 继续，或 Ctrl+C 取消..." 

# 启动 GUI
openroad -gui scripts/load_design_gui_verified.tcl
