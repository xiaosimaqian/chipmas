#!/bin/bash

# 完整批量运行：从K-SpecPart到Step 1-8
# 用法: nohup bash scripts/run_all_ispd2015_complete.sh > /tmp/ispd2015_batch.log 2>&1 &

set -e

# 确保在chipmas目录
cd ~/chipmas

# 设置环境变量
export PATH="$HOME/.local/bin:$PATH"

# 所有ISPD 2015设计列表
DESIGNS=(
    "mgc_fft_1"           # 已完成，跳过
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
LOG_DIR="logs/step1_8_batch_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

# 汇总结果文件
SUMMARY_FILE="$LOG_DIR/summary.json"

echo "=========================================="
echo "ISPD 2015设计批量处理"
echo "从K-SpecPart分区到Step 1-8完整流程"
echo "=========================================="
echo "总设计数: ${#DESIGNS[@]}"
echo "日志目录: $LOG_DIR"
echo "开始时间: $(date)"
echo ""

# 统计变量
TOTAL=0
SUCCESS=0
FAILED=0
SKIPPED=0

# 创建汇总文件
cat > "$SUMMARY_FILE" <<EOF
{
  "start_time": "$(date -Iseconds)",
  "designs": [
EOF

FIRST=true

# 遍历所有设计
for design in "${DESIGNS[@]}"; do
    TOTAL=$((TOTAL + 1))
    
    echo "=========================================="
    echo "[$TOTAL/${#DESIGNS[@]}] 处理设计: $design"
    echo "=========================================="
    echo "时间: $(date)"
    
    # 检查是否已完成
    if [ "$design" = "mgc_fft_1" ]; then
        echo "✅ $design 已完成，跳过"
        SKIPPED=$((SKIPPED + 1))
        
        # 添加到汇总
        if [ "$FIRST" = false ]; then
            echo "," >> "$SUMMARY_FILE"
        fi
        FIRST=false
        cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "skipped",
      "reason": "已完成"
    }
EOF
        echo ""
        continue
    fi
    
    # 检查设计目录
    if [ ! -d "data/ispd2015/$design" ]; then
        echo "⚠️  设计目录不存在，跳过: $design"
        SKIPPED=$((SKIPPED + 1))
        
        if [ "$FIRST" = false ]; then
            echo "," >> "$SUMMARY_FILE"
        fi
        FIRST=false
        cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "skipped",
      "reason": "目录不存在"
    }
EOF
        echo ""
        continue
    fi
    
    # 设置日志文件
    LOG_FILE="$LOG_DIR/${design}.log"
    START_TIME=$(date +%s)
    
    echo "  日志文件: $LOG_FILE"
    echo ""
    
    # Step 0: 检查并运行K-SpecPart（如果需要）
    echo "  [Step 0] 检查K-SpecPart分区..."
    PART_FILE="results/kspecpart/$design/${design}.hgr.processed.specpart.part.4"
    
    if [ ! -f "$PART_FILE" ]; then
        echo "    K-SpecPart分区文件不存在，需要先运行K-SpecPart"
        echo "    ⚠️  跳过此设计（需要手动运行K-SpecPart）"
        SKIPPED=$((SKIPPED + 1))
        
        if [ "$FIRST" = false ]; then
            echo "," >> "$SUMMARY_FILE"
        fi
        FIRST=false
        cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "skipped",
      "reason": "缺少K-SpecPart分区文件"
    }
EOF
        echo ""
        continue
    fi
    
    echo "    ✓ K-SpecPart分区文件存在: $PART_FILE"
    
    # Step 1-8: 运行完整流程
    echo "  [Step 1-8] 运行完整Partition-based OpenROAD Flow..."
    
    if python3 scripts/run_partition_based_flow.py \
        --design "$design" \
        --verilog "data/ispd2015/$design/design.v" \
        --num-partitions 4 \
        --output-dir "tests/results/partition_flow/${design}_step1_8" \
        >> "$LOG_FILE" 2>&1; then
        
        END_TIME=$(date +%s)
        RUNTIME=$((END_TIME - START_TIME))
        SUCCESS=$((SUCCESS + 1))
        
        echo ""
        echo "  ✅ 成功完成: $design"
        echo "     运行时间: ${RUNTIME}秒 ($(($RUNTIME / 60))分钟)"
        
        # 提取关键结果
        RESULT_FILE="tests/results/partition_flow/${design}_step1_8/openroad/flow_summary.json"
        if [ -f "$RESULT_FILE" ]; then
            RESULTS=$(python3 -c "
import json
try:
    with open('$RESULT_FILE') as f:
        data = json.load(f)
    
    # 提取边界代价
    bc_percent = 'N/A'
    internal_hpwl = 'N/A'
    boundary_hpwl = 'N/A'
    
    if 'steps' in data and 'boundary_cost' in data['steps']:
        bc = data['steps']['boundary_cost']
        bc_percent = bc.get('boundary_cost_percent', 'N/A')
        internal_hpwl = bc.get('internal_hpwl_total', 'N/A')
        boundary_hpwl = bc.get('boundary_hpwl', 'N/A')
    
    print(f'{bc_percent}|{internal_hpwl}|{boundary_hpwl}')
except Exception as e:
    print('N/A|N/A|N/A')
" 2>/dev/null || echo "N/A|N/A|N/A")
            
            IFS='|' read -r BC_PERCENT INTERNAL_HPWL BOUNDARY_HPWL <<< "$RESULTS"
            
            echo "     边界代价: ${BC_PERCENT}%"
            echo "     Internal HPWL: $INTERNAL_HPWL um"
            echo "     Boundary HPWL: $BOUNDARY_HPWL um"
            
            # 添加到汇总
            if [ "$FIRST" = false ]; then
                echo "," >> "$SUMMARY_FILE"
            fi
            FIRST=false
            cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "success",
      "runtime_seconds": $RUNTIME,
      "boundary_cost_percent": $BC_PERCENT,
      "internal_hpwl": $INTERNAL_HPWL,
      "boundary_hpwl": $BOUNDARY_HPWL,
      "log_file": "$LOG_FILE"
    }
EOF
        else
            if [ "$FIRST" = false ]; then
                echo "," >> "$SUMMARY_FILE"
            fi
            FIRST=false
            cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "success",
      "runtime_seconds": $RUNTIME,
      "log_file": "$LOG_FILE",
      "note": "结果文件缺失"
    }
EOF
        fi
    else
        END_TIME=$(date +%s)
        RUNTIME=$((END_TIME - START_TIME))
        FAILED=$((FAILED + 1))
        
        echo ""
        echo "  ❌ 失败: $design"
        echo "     运行时间: ${RUNTIME}秒"
        echo "     查看日志: $LOG_FILE"
        
        # 添加到汇总
        if [ "$FIRST" = false ]; then
            echo "," >> "$SUMMARY_FILE"
        fi
        FIRST=false
        cat >> "$SUMMARY_FILE" <<EOF
    {
      "design": "$design",
      "status": "failed",
      "runtime_seconds": $RUNTIME,
      "log_file": "$LOG_FILE"
    }
EOF
    fi
    
    echo ""
done

# 完成汇总文件
cat >> "$SUMMARY_FILE" <<EOF

  ],
  "end_time": "$(date -Iseconds)",
  "statistics": {
    "total": $TOTAL,
    "success": $SUCCESS,
    "failed": $FAILED,
    "skipped": $SKIPPED
  }
}
EOF

echo "=========================================="
echo "批量处理完成！"
echo "=========================================="
echo "结束时间: $(date)"
echo ""
echo "统计结果:"
echo "  总计: $TOTAL"
echo "  成功: $SUCCESS"
echo "  失败: $FAILED"
echo "  跳过: $SKIPPED"
echo ""
echo "汇总文件: $SUMMARY_FILE"
echo "日志目录: $LOG_DIR"
echo "=========================================="

# 生成Markdown报告
REPORT_FILE="$LOG_DIR/REPORT.md"
cat > "$REPORT_FILE" <<'EOFMD'
# ISPD 2015设计批量测试报告

EOFMD

echo "生成时间: $(date)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## 测试统计" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "- 总计: $TOTAL" >> "$REPORT_FILE"
echo "- 成功: $SUCCESS" >> "$REPORT_FILE"
echo "- 失败: $FAILED" >> "$REPORT_FILE"
echo "- 跳过: $SKIPPED" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## 详细结果" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Design | Status | Runtime | Boundary Cost | Internal HPWL | Boundary HPWL |" >> "$REPORT_FILE"
echo "|--------|--------|---------|---------------|---------------|---------------|" >> "$REPORT_FILE"

# 从JSON提取数据生成表格
python3 -c "
import json
with open('$SUMMARY_FILE') as f:
    data = json.load(f)
for d in data['designs']:
    design = d['design']
    status = d['status']
    runtime = d.get('runtime_seconds', 'N/A')
    if runtime != 'N/A':
        runtime_min = f'{runtime // 60}m {runtime % 60}s'
    else:
        runtime_min = 'N/A'
    bc = d.get('boundary_cost_percent', 'N/A')
    if bc != 'N/A':
        bc = f'{bc:.6f}%'
    int_hpwl = d.get('internal_hpwl', 'N/A')
    bnd_hpwl = d.get('boundary_hpwl', 'N/A')
    print(f'| {design} | {status} | {runtime_min} | {bc} | {int_hpwl} | {bnd_hpwl} |')
" >> "$REPORT_FILE" 2>/dev/null || echo "生成报告表格失败"

echo ""
echo "报告文件: $REPORT_FILE"
echo "=========================================="

