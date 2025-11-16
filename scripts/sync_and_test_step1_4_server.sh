#!/bin/bash
# 同步代码到服务器并运行Step 1-4测试

set -e

# 服务器配置
SERVER="keqin@172.30.31.98"
SERVER_DIR="~/chipmas"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo "同步代码到服务器并运行Step 1-4测试"
echo "=========================================="
echo "服务器: $SERVER"
echo "本地目录: $LOCAL_DIR"
echo "服务器目录: $SERVER_DIR"
echo ""

# 1. 同步代码到服务器
echo "步骤1: 同步代码到服务器..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='tests/results' \
    --exclude='results' \
    --exclude='data' \
    --exclude='*.log' \
    "$LOCAL_DIR/" "$SERVER:$SERVER_DIR/"

echo ""
echo "✓ 代码同步完成"
echo ""

# 2. 在服务器上安装Yosys
echo "步骤2: 在服务器上安装Yosys..."
ssh -o ServerAliveInterval=10 "$SERVER" << 'ENDSSH'
cd ~/chipmas
bash scripts/setup_yosys_server.sh
ENDSSH

echo ""
echo "✓ Yosys安装完成"
echo ""

# 3. 在服务器上运行Step 1-4测试
echo "步骤3: 在服务器上运行Step 1-4测试..."
ssh -o ServerAliveInterval=10 "$SERVER" << 'ENDSSH'
cd ~/chipmas

echo "=========================================="
echo "运行Step 1-4测试（mgc_fft_1）"
echo "=========================================="

# 检查必要文件
DESIGN_NAME="mgc_fft_1"
DESIGN_DIR="data/ispd2015/$DESIGN_NAME"
KSPECPART_DIR="results/kspecpart/$DESIGN_NAME"
OUTPUT_DIR="tests/results/partition_flow/${DESIGN_NAME}_server"

echo "检查输入文件..."
if [ ! -f "$DESIGN_DIR/design.v" ]; then
    echo "❌ 设计文件不存在: $DESIGN_DIR/design.v"
    exit 1
fi

if [ ! -f "$KSPECPART_DIR/mgc_fft_1.hgr.processed.specpart.part.4" ]; then
    echo "❌ K-SpecPart结果文件不存在"
    echo "   需要先运行K-SpecPart实验"
    exit 1
fi

echo "✓ 输入文件检查通过"
echo ""

# 运行测试
python3 scripts/run_partition_based_flow.py \
    --design "$DESIGN_NAME" \
    --design-dir "$DESIGN_DIR" \
    --kspecpart-dir "$KSPECPART_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --partitions 4 \
    --skip-openroad

echo ""
echo "=========================================="
echo "测试完成，检查结果..."
echo "=========================================="

# 检查结果文件
if [ -f "$OUTPUT_DIR/flow_summary.json" ]; then
    echo "✓ flow_summary.json 存在"
    python3 << 'PYEOF'
import json
from pathlib import Path

summary_file = Path("tests/results/partition_flow/mgc_fft_1_server/flow_summary.json")
if summary_file.exists():
    summary = json.load(open(summary_file))
    print("\n=== Step 1-4完成状态 ===")
    for step_name, step_data in summary.get('steps', {}).items():
        if isinstance(step_data, dict):
            status = step_data.get('status', 'unknown')
            print(f"  {step_name}: {status}")
        else:
            print(f"  {step_name}: {type(step_data).__name__}")
PYEOF
else
    echo "❌ flow_summary.json 不存在"
fi

# 检查生成的文件
echo ""
echo "检查生成的文件..."
if [ -d "$OUTPUT_DIR/hierarchical_netlists" ]; then
    echo "✓ hierarchical_netlists目录存在"
    ls -lh "$OUTPUT_DIR/hierarchical_netlists/" | head -10
fi

if [ -d "$OUTPUT_DIR/formal_verification" ]; then
    echo "✓ formal_verification目录存在"
    if [ -f "$OUTPUT_DIR/formal_verification/verification_report.json" ]; then
        echo "✓ verification_report.json存在"
        python3 << 'PYEOF'
import json
from pathlib import Path

report_file = Path("tests/results/partition_flow/mgc_fft_1_server/formal_verification/verification_report.json")
if report_file.exists():
    report = json.load(open(report_file))
    print(f"  Formal验证: success={report.get('success')}, equivalent={report.get('equivalent')}")
PYEOF
    fi
fi

ENDSSH

echo ""
echo "=========================================="
echo "✓ 服务器端测试完成！"
echo "=========================================="

