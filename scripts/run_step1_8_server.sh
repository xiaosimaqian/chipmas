#!/bin/bash
# 在服务器上运行完整的Step 1-8测试

set -e

# 设置PATH，确保能找到~/.local/bin中的工具
export PATH="$HOME/.local/bin:$PATH"

echo "=========================================="
echo "在服务器上运行完整Step 1-8测试"
echo "=========================================="

# 检查Yosys
if ! command -v yosys &> /dev/null; then
    echo "❌ Yosys未安装"
    echo "请先安装Yosys：bash scripts/reinstall_yosys_from_source.sh"
    exit 1
fi

echo "✓ Yosys已安装"
yosys -V | head -1
echo ""

# 检查OpenROAD
if ! command -v openroad &> /dev/null; then
    echo "❌ OpenROAD未安装"
    exit 1
fi

echo "✓ OpenROAD已安装"
openroad -version | head -1
echo ""

# 检查必要文件
DESIGN_NAME="mgc_fft_1"
DESIGN_DIR="data/ispd2015/$DESIGN_NAME"
KSPECPART_DIR="results/kspecpart/$DESIGN_NAME"
OUTPUT_DIR="tests/results/partition_flow/${DESIGN_NAME}_step1_8"

echo "检查输入文件..."
if [ ! -f "$DESIGN_DIR/design.v" ]; then
    echo "❌ 设计文件不存在: $DESIGN_DIR/design.v"
    exit 1
fi

if [ ! -f "$DESIGN_DIR/tech.lef" ]; then
    echo "❌ 技术LEF文件不存在: $DESIGN_DIR/tech.lef"
    exit 1
fi

if [ ! -f "$DESIGN_DIR/cells.lef" ]; then
    echo "❌ 标准单元LEF文件不存在: $DESIGN_DIR/cells.lef"
    exit 1
fi

if [ ! -f "$KSPECPART_DIR/mgc_fft_1.hgr.processed.specpart.part.4" ]; then
    echo "❌ K-SpecPart结果文件不存在"
    echo "   需要先运行K-SpecPart实验"
    exit 1
fi

echo "✓ 输入文件检查通过"
echo ""

# 运行完整流程（包含OpenROAD）
echo "=========================================="
echo "运行完整Step 1-8流程（包含OpenROAD）..."
echo "=========================================="
echo ""
echo "注意：这可能需要较长时间（各Partition OpenROAD执行）"
echo ""

python3 scripts/run_partition_based_flow.py \
    --design "$DESIGN_NAME" \
    --design-dir "$DESIGN_DIR" \
    --kspecpart-dir "$KSPECPART_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --partitions 4

echo ""
echo "=========================================="
echo "检查结果..."
echo "=========================================="

# 检查结果文件
if [ -f "$OUTPUT_DIR/flow_summary.json" ]; then
    echo "✓ flow_summary.json 存在"
    python3 << 'PYEOF'
import json
from pathlib import Path

summary_file = Path("tests/results/partition_flow/mgc_fft_1_step1_8/flow_summary.json")
if summary_file.exists():
    summary = json.load(open(summary_file))
    print("\n=== Step 1-8完成状态 ===")
    for step_name, step_data in summary.get('steps', {}).items():
        if isinstance(step_data, dict):
            if 'status' in step_data:
                status = step_data.get('status', 'unknown')
                print(f"  {step_name}: {status}")
            elif 'success' in step_data:
                success = step_data.get('success', False)
                print(f"  {step_name}: {'success' if success else 'failed'}")
            else:
                print(f"  {step_name}: {type(step_data).__name__}")
        else:
            print(f"  {step_name}: {type(step_data).__name__}")
    
    # 检查边界代价
    if 'openroad' in summary.get('steps', {}):
        openroad_data = summary['steps']['openroad']
        if 'boundary_cost' in openroad_data.get('steps', {}):
            bc = openroad_data['steps']['boundary_cost']
            print(f"\n=== 边界代价 ===")
            print(f"  Internal HPWL总和: {bc.get('internal_hpwl_total', 0):.2f} um")
            print(f"  Boundary HPWL: {bc.get('boundary_hpwl', 0):.2f} um")
            print(f"  边界代价 (BC): {bc.get('boundary_cost_percent', 0):.2f}%")
PYEOF
else
    echo "❌ flow_summary.json 不存在"
fi

# 检查生成的文件
echo ""
echo "检查生成的文件..."
if [ -d "$OUTPUT_DIR/openroad" ]; then
    echo "✓ openroad目录存在"
    echo "  文件列表："
    find "$OUTPUT_DIR/openroad" -type f -name "*.def" -o -name "*.lef" -o -name "*.log" | head -20
fi

echo ""
echo "=========================================="
echo "✓ Step 1-8测试完成！"
echo "=========================================="

