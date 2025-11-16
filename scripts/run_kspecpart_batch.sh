#!/bin/bash

# 批量运行K-SpecPart分区
# 用法: nohup bash scripts/run_kspecpart_batch.sh > /tmp/kspecpart_batch.log 2>&1 &

set -e

# 确保在chipmas目录
cd ~/chipmas

# 所有ISPD 2015设计列表（跳过已完成的mgc_fft_1）
DESIGNS=(
    "mgc_fft_2"
    "mgc_fft_a"
    "mgc_fft_b"
    "mgc_matrix_mult_1"
    "mgc_matrix_mult_a"
    "mgc_matrix_mult_b"
    "mgc_edit_dist_a"
    "mgc_des_perf_1"
    "mgc_des_perf_a"
    "mgc_des_perf_b"
    "mgc_pci_bridge32_a"
    "mgc_pci_bridge32_b"
    "mgc_superblue11_a"
    "mgc_superblue12"
    "mgc_superblue16_a"
)

# 日志目录
LOG_DIR="logs/kspecpart_batch_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "批量运行K-SpecPart分区"
echo "=========================================="
echo "设计数量: ${#DESIGNS[@]}"
echo "日志目录: $LOG_DIR"
echo "开始时间: $(date)"
echo ""

TOTAL=0
SUCCESS=0
FAILED=0

for design in "${DESIGNS[@]}"; do
    TOTAL=$((TOTAL + 1))
    
    echo "=========================================="
    echo "[$TOTAL/${#DESIGNS[@]}] 处理: $design"
    echo "=========================================="
    
    # 检查DEF文件（优先使用floorplan.def）
    DEF_FILE="data/ispd2015/$design/floorplan.def"
    if [ ! -f "$DEF_FILE" ]; then
        # 如果floorplan.def不存在，尝试{design}.def
        DEF_FILE="data/ispd2015/$design/${design}.def"
        if [ ! -f "$DEF_FILE" ]; then
            echo "❌ DEF文件不存在: floorplan.def 或 ${design}.def"
            FAILED=$((FAILED + 1))
            continue
        fi
    fi
    
    LOG_FILE="$LOG_DIR/${design}.log"
    START_TIME=$(date +%s)
    
    echo "  DEF文件: $DEF_FILE"
    echo "  日志文件: $LOG_FILE"
    echo ""
    
    # Step 1: DEF转HGR
    echo "  [1/3] DEF → HGR 转换..."
    HGR_DIR="results/hgr/$design"
    mkdir -p "$HGR_DIR"
    
    if python3 -c "
from src.utils.def_parser import DEFParser
import os

def_file = '$DEF_FILE'
hgr_dir = '$HGR_DIR'
design = '$design'

print(f'解析DEF文件: {def_file}')
parser = DEFParser(def_file)
parser.parse()

print(f'生成HGR文件...')
hgr_file = os.path.join(hgr_dir, f'{design}.hgr')
parser.export_to_hgr(hgr_file)

print(f'✓ HGR文件已生成: {hgr_file}')
print(f'  Nodes: {len(parser.components)}')
print(f'  Nets: {len(parser.nets)}')
" >> "$LOG_FILE" 2>&1; then
        echo "    ✓ HGR文件生成成功"
    else
        echo "    ❌ HGR文件生成失败"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # Step 2: 运行K-SpecPart
    echo "  [2/3] 运行K-SpecPart分区..."
    HGR_FILE="$HGR_DIR/${design}.hgr"
    OUTPUT_DIR="results/kspecpart/$design"
    mkdir -p "$OUTPUT_DIR"
    
    cd ~/K-SpecPart
    if julia --project=. run_kspecpart.jl \
        "$HOME/chipmas/$HGR_FILE" \
        "$HOME/chipmas/$OUTPUT_DIR" \
        4 \
        >> "$HOME/chipmas/$LOG_FILE" 2>&1; then
        echo "    ✓ K-SpecPart分区成功"
    else
        echo "    ❌ K-SpecPart分区失败"
        cd ~/chipmas
        FAILED=$((FAILED + 1))
        continue
    fi
    cd ~/chipmas
    
    # Step 3: 创建映射文件
    echo "  [3/3] 创建映射文件..."
    MAPPING_FILE="$OUTPUT_DIR/${design}.mapping.json"
    
    if python3 -c "
import json
from src.utils.def_parser import DEFParser

def_file = '$DEF_FILE'
mapping_file = '$MAPPING_FILE'

print(f'解析DEF文件: {def_file}')
parser = DEFParser(def_file)
parser.parse()

print(f'创建映射文件...')
mapping = {}
for i, comp in enumerate(parser.components):
    mapping[str(i)] = comp['name']

with open(mapping_file, 'w') as f:
    json.dump(mapping, f, indent=2)

print(f'✓ 映射文件已生成: {mapping_file}')
print(f'  总Instance数: {len(mapping)}')
" >> "$LOG_FILE" 2>&1; then
        echo "    ✓ 映射文件生成成功"
    else
        echo "    ❌ 映射文件生成失败"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    END_TIME=$(date +%s)
    RUNTIME=$((END_TIME - START_TIME))
    SUCCESS=$((SUCCESS + 1))
    
    echo ""
    echo "  ✅ 完成: $design"
    echo "     运行时间: ${RUNTIME}秒 ($(($RUNTIME / 60))分钟)"
    
    # 检查分区文件
    PART_FILE="$OUTPUT_DIR/${design}.hgr.processed.specpart.part.4"
    if [ -f "$PART_FILE" ]; then
        # 统计分区大小
        PART_STATS=$(python3 -c "
from collections import Counter
with open('$PART_FILE') as f:
    parts = [int(line.strip()) for line in f]
counts = Counter(parts)
for p in sorted(counts.keys()):
    print(f'  Partition {p}: {counts[p]} instances ({counts[p]*100.0/len(parts):.1f}%)')
")
        echo "     分区统计:"
        echo "$PART_STATS"
    fi
    
    echo ""
done

echo "=========================================="
echo "批量K-SpecPart分区完成！"
echo "=========================================="
echo "结束时间: $(date)"
echo ""
echo "统计结果:"
echo "  总计: $TOTAL"
echo "  成功: $SUCCESS"
echo "  失败: $FAILED"
echo ""
echo "日志目录: $LOG_DIR"
echo "=========================================="

