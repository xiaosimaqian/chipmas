#!/bin/bash
# 定期检查脚本 - 每30分钟执行一次问题报告

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

CHECK_INTERVAL=1800  # 30分钟
REPORT_DIR="monitoring_reports"
mkdir -p "$REPORT_DIR"

echo "=========================================="
echo "定期问题检查（每30分钟）"
echo "=========================================="
echo "开始时间: $(date)"
echo "检查间隔: ${CHECK_INTERVAL}秒"
echo "报告目录: $REPORT_DIR"
echo "=========================================="
echo ""

while true; do
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REPORT_FILE="$REPORT_DIR/issue_report_${TIMESTAMP}.txt"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 生成问题报告..." | tee -a "$REPORT_DIR/check.log"
    
    # 执行问题报告
    bash "$SCRIPT_DIR/report_issues.sh" > "$REPORT_FILE" 2>&1
    
    # 检查是否有问题
    if grep -qiE "❌|⚠️|问题|失败|error" "$REPORT_FILE"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  发现问题，报告已保存: $REPORT_FILE" | tee -a "$REPORT_DIR/check.log"
        echo "请查看报告文件: $REPORT_FILE" | tee -a "$REPORT_DIR/check.log"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 未发现问题" | tee -a "$REPORT_DIR/check.log"
    fi
    
    echo "" | tee -a "$REPORT_DIR/check.log"
    
    # 等待30分钟
    sleep $CHECK_INTERVAL
done


