#!/bin/bash

# 批量运行所有ISPD 2015设计的Step 1-8流程
# 用法: bash scripts/run_all_ispd2015_step1_8.sh

set -e

# 确保在chipmas目录
cd ~/chipmas

# 设置环境变量
export PATH="$HOME/.local/bin:$PATH"

# 所有ISPD 2015设计列表（按大小排序，小的先运行）
DESIGNS=(
    "mgc_fft_1"
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
LOG_DIR="logs/step1_8_batch"
mkdir -p "$LOG_DIR"

# 汇总结果文件
SUMMARY_FILE="$LOG_DIR/summary_$(date +%Y%m%d_%H%M%S).json"
echo "{" > "$SUMMARY_FILE"
echo "  \"start_time\": \"$(date -Iseconds)\"," >> "$SUMMARY_FILE"
echo "  \"designs\": {" >> "$SUMMARY_FILE"

# 统计变量
TOTAL=0
SUCCESS=0
FAILED=0
SKIPPED=0

echo "=========================================="
echo "批量运行ISPD 2015设计的Step 1-8流程"
echo "=========================================="
echo "总设计数: ${#DESIGNS[@]}"
echo "日志目录: $LOG_DIR"
echo "汇总文件: $SUMMARY_FILE"
echo ""

# 遍历所有设计
FIRST=true
for design in "${DESIGNS[@]}"; do
    TOTAL=$((TOTAL + 1))
    echo "=========================================="
    echo "[$TOTAL/${#DESIGNS[@]}] 处理设计: $design"
    echo "=========================================="
    
    # 检查设计目录是否存在
    if [ ! -d "data/ispd2015/$design" ]; then
        echo "⚠️  设计目录不存在，跳过: data/ispd2015/$design"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    # 检查必要文件是否存在
    if [ ! -f "data/ispd2015/$design/design.v" ]; then
        echo "⚠️  design.v不存在，跳过: $design"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    # 设置日志文件
    LOG_FILE="$LOG_DIR/${design}_$(date +%Y%m%d_%H%M%S).log"
    START_TIME=$(date +%s)
    
    echo "  开始时间: $(date)"
    echo "  日志文件: $LOG_FILE"
    echo ""
    
    # 运行Step 1-8流程
    if python3 scripts/run_partition_based_flow.py \
        --design "$design" \
        --verilog "data/ispd2015/$design/design.v" \
        --num-partitions 4 \
        --output-dir "tests/results/partition_flow/${design}_step1_8" \
        > "$LOG_FILE" 2>&1; then
        
        END_TIME=$(date +%s)
        RUNTIME=$((END_TIME - START_TIME))
        SUCCESS=$((SUCCESS + 1))
        
        echo "✅ 成功完成: $design"
        echo "   运行时间: ${RUNTIME}秒 ($(($RUNTIME / 60))分钟)"
        
        # 提取关键结果
        if [ -f "tests/results/partition_flow/${design}_step1_8/flow_summary.json" ]; then
            BC=$(python3 -c "
import json
try:
    with open('tests/results/partition_flow/${design}_step1_8/flow_summary.json') as f:
        data = json.load(f)
    if 'steps' in data and 'openroad' in data['steps']:
        or_data = data['steps']['openroad']
        if 'steps' in or_data and 'boundary_cost' in or_data['steps']:
            bc = or_data['steps']['boundary_cost']
            print(f\"{bc.get('boundary_cost_percent', 'N/A'):.6f}%\")
        else:
            print('N/A')
    else:
        print('N/A')
except:
    print('N/A')
" 2>/dev/null || echo "N/A")
            echo "   边界代价: $BC"
        fi
        
        STATUS="success"
    else
        END_TIME=$(date +%s)
        RUNTIME=$((END_TIME - START_TIME))
        FAILED=$((FAILED + 1))
        
        echo "❌ 失败: $design"
        echo "   运行时间: ${RUNTIME}秒"
        echo "   查看日志: $LOG_FILE"
        
        STATUS="failed"
    fi
    
    # 添加到汇总文件
    if [ "$FIRST" = false ]; then
        echo "," >> "$SUMMARY_FILE"
    fi
    FIRST=false
    
    echo "    \"$design\": {" >> "$SUMMARY_FILE"
    echo "      \"status\": \"$STATUS\"," >> "$SUMMARY_FILE"
    echo "      \"runtime_seconds\": $RUNTIME," >> "$SUMMARY_FILE"
    echo "      \"log_file\": \"$LOG_FILE\"" >> "$SUMMARY_FILE"
    echo -n "    }" >> "$SUMMARY_FILE"
    
    echo ""
done

# 完成汇总文件
echo "" >> "$SUMMARY_FILE"
echo "  }," >> "$SUMMARY_FILE"
echo "  \"end_time\": \"$(date -Iseconds)\"," >> "$SUMMARY_FILE"
echo "  \"statistics\": {" >> "$SUMMARY_FILE"
echo "    \"total\": $TOTAL," >> "$SUMMARY_FILE"
echo "    \"success\": $SUCCESS," >> "$SUMMARY_FILE"
echo "    \"failed\": $FAILED," >> "$SUMMARY_FILE"
echo "    \"skipped\": $SKIPPED" >> "$SUMMARY_FILE"
echo "  }" >> "$SUMMARY_FILE"
echo "}" >> "$SUMMARY_FILE"

echo "=========================================="
echo "批量运行完成！"
echo "=========================================="
echo "总计: $TOTAL"
echo "成功: $SUCCESS"
echo "失败: $FAILED"
echo "跳过: $SKIPPED"
echo ""
echo "汇总文件: $SUMMARY_FILE"
echo "日志目录: $LOG_DIR"
echo "=========================================="

