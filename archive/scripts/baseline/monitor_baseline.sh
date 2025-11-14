#!/bin/bash
# 基线实验监控脚本 - 每半小时检查一次运行状态
# 只检测和报告问题，不自动修复，由人工判断处理

SSH_CMD="ssh -o ServerAliveInterval=10 keqin@172.30.31.98"
CHECK_INTERVAL=1800  # 30分钟 = 1800秒
LOG_FILE="monitor_baseline_$(date +%Y%m%d_%H%M%S).log"
ALERT_FILE="monitor_alerts_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================="
echo "基线实验监控脚本（只检测，不自动修复）"
echo "=========================================="
echo "开始时间: $(date)"
echo "检查间隔: ${CHECK_INTERVAL}秒 (30分钟)"
echo "日志文件: $LOG_FILE"
echo "告警文件: $ALERT_FILE"
echo "=========================================="
echo ""

# 记录开始时间
START_TIME=$(date +%s)
CHECK_COUNT=0

while true; do
    CHECK_COUNT=$((CHECK_COUNT + 1))
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    ELAPSED_HOURS=$((ELAPSED / 3600))
    ELAPSED_MINS=$(((ELAPSED % 3600) / 60))
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 第 ${CHECK_COUNT} 次检查 (已运行: ${ELAPSED_HOURS}小时${ELAPSED_MINS}分钟)" | tee -a "$LOG_FILE"
    echo "----------------------------------------" | tee -a "$LOG_FILE"
    
    # 检查运行状态
    STATUS_OUTPUT=$($SSH_CMD "cd ~/chipmas && bash scripts/check_baseline_status.sh" 2>&1)
    echo "$STATUS_OUTPUT" | tee -a "$LOG_FILE"
    
    # 问题检测和报告
    echo "" | tee -a "$LOG_FILE"
    echo "=== 问题检测 ===" | tee -a "$LOG_FILE"
    
    ALERTS=()
    
    # 1. 检查进程是否还在运行
    PROCESS_COUNT=$($SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$PROCESS_COUNT" -eq "0" ]; then
        ALERT="⚠️  警告: 未找到运行中的基线实验进程！"
        echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        ALERTS+=("$ALERT")
        
        # 检查是否所有设计都已完成
        TOTAL_DESIGNS=16
        COMPLETED=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
        if [ "$COMPLETED" -lt "$TOTAL_DESIGNS" ]; then
            ALERT="⚠️  实验未完成，但进程已停止。已完成: $COMPLETED / $TOTAL_DESIGNS"
            echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
            ALERTS+=("$ALERT")
        fi
    else
        echo "✅ 基线实验进程正在运行 (进程数: $PROCESS_COUNT)" | tee -a "$LOG_FILE"
    fi
    
    # 2. 检查OpenROAD进程内存使用
    OPENROAD_COUNT=$($SSH_CMD "ps aux | grep openroad | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$OPENROAD_COUNT" -gt "0" ]; then
        OPENROAD_MEM=$($SSH_CMD "ps aux | grep openroad | grep -v grep | awk '{sum+=\$6} END {print sum/1024/1024}'" 2>/dev/null | head -1)
        if [ -n "$OPENROAD_MEM" ]; then
            MEM_GB=$(echo "$OPENROAD_MEM" | awk '{printf "%.1f", $1}')
            if (( $(echo "$MEM_GB > 100" | bc -l 2>/dev/null || echo "0") )); then
                ALERT="⚠️  OpenROAD内存使用过高: ${MEM_GB} GB"
                echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
                ALERTS+=("$ALERT")
            else
                echo "✅ OpenROAD内存使用正常: ${MEM_GB} GB" | tee -a "$LOG_FILE"
            fi
        fi
    fi
    
    # 3. 检查失败的设计
    FAILED_COUNT=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$FAILED_COUNT" -gt "0" ]; then
        ALERT="⚠️  发现 $FAILED_COUNT 个失败的设计"
        echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        ALERTS+=("$ALERT")
        
        FAILED_DESIGNS=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | xargs -I {} basename \$(dirname {})" 2>/dev/null)
        echo "   失败设计列表: $FAILED_DESIGNS" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        
        # 分析失败原因
        for design in $FAILED_DESIGNS; do
            ERROR_MSG=$($SSH_CMD "cd ~/chipmas && cat results/baseline/$design/result.json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(\"error\", \"Unknown error\")[:200])' 2>/dev/null")
            if [ -n "$ERROR_MSG" ]; then
                echo "   $design 错误: $ERROR_MSG" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
                
                # 检测常见错误类型
                if echo "$ERROR_MSG" | grep -qi "out of memory\|OOM\|内存"; then
                    ALERT="🔴 $design: 内存不足错误，需要减少线程数或优化内存使用"
                    echo "   $ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
                    ALERTS+=("$ALERT")
                elif echo "$ERROR_MSG" | grep -qi "timeout\|超时"; then
                    ALERT="🟡 $design: 超时错误，可能需要增加超时时间或优化性能"
                    echo "   $ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
                    ALERTS+=("$ALERT")
                elif echo "$ERROR_MSG" | grep -qi "DEF parser\|解析错误"; then
                    ALERT="🔴 $design: DEF文件解析错误，需要检查DEF文件格式"
                    echo "   $ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
                    ALERTS+=("$ALERT")
                fi
            fi
        done
    else
        echo "✅ 无失败设计" | tee -a "$LOG_FILE"
    fi
    
    # 4. 检查最新日志中的错误
    LATEST_LOG=$($SSH_CMD "ls -t ~/chipmas/results/baseline_logs/baseline_batch_*.log 2>/dev/null | head -1" 2>/dev/null)
    if [ -n "$LATEST_LOG" ]; then
        ERRORS=$($SSH_CMD "tail -100 '$LATEST_LOG' 2>/dev/null | grep -iE 'error|failed|exception|traceback|out of memory|OOM' | tail -5" 2>/dev/null)
        if [ -n "$ERRORS" ]; then
            ALERT="⚠️  最新日志中发现错误"
            echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
            ALERTS+=("$ALERT")
            echo "$ERRORS" | sed 's/^/   /' | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        fi
    fi
    
    # 5. 检查进度停滞
    COMPLETED=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
    TOTAL_DESIGNS=16
    PROGRESS=$((COMPLETED * 100 / TOTAL_DESIGNS))
    echo "📊 进度: $COMPLETED / $TOTAL_DESIGNS ($PROGRESS%)" | tee -a "$LOG_FILE"
    
    # 检查是否有长时间没有新结果（超过2小时）
    LATEST_RESULT_TIME=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec stat -c '%Y' {} \; 2>/dev/null | sort -n | tail -1" 2>/dev/null)
    if [ -n "$LATEST_RESULT_TIME" ]; then
        CURRENT_TIME_UNIX=$(date +%s)
        TIME_SINCE_LAST=$((CURRENT_TIME_UNIX - LATEST_RESULT_TIME))
        if [ "$TIME_SINCE_LAST" -gt 7200 ] && [ "$COMPLETED" -lt "$TOTAL_DESIGNS" ]; then
            ALERT="⚠️  超过2小时没有新结果产生，可能进程卡住或处理大设计"
            echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
            ALERTS+=("$ALERT")
        fi
    fi
    
    # 6. 检查磁盘空间
    DISK_USAGE=$($SSH_CMD "df -h ~/chipmas/results 2>/dev/null | tail -1 | awk '{print \$5}' | sed 's/%//'" 2>/dev/null)
    if [ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -gt 90 ]; then
        ALERT="⚠️  磁盘使用率过高: ${DISK_USAGE}%，可能需要清理"
        echo "$ALERT" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        ALERTS+=("$ALERT")
    fi
    
    # 汇总告警
    echo "" | tee -a "$LOG_FILE"
    if [ ${#ALERTS[@]} -gt 0 ]; then
        echo "========================================" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        echo "⚠️  发现 ${#ALERTS[@]} 个问题，需要人工处理：" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        for alert in "${ALERTS[@]}"; do
            echo "  - $alert" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        done
        echo "========================================" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        echo "" | tee -a "$LOG_FILE" | tee -a "$ALERT_FILE"
        echo "请检查告警文件: $ALERT_FILE" | tee -a "$LOG_FILE"
    else
        echo "✅ 未发现异常问题" | tee -a "$LOG_FILE"
    fi
    
    echo "" | tee -a "$LOG_FILE"
    echo "下次检查时间: $(date -d '+30 minutes' '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -v+30M '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo '30分钟后')" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    
    # 等待30分钟
    sleep $CHECK_INTERVAL
done
