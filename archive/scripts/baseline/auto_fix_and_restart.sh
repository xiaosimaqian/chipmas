#!/bin/bash
# 自动修复问题并重新启动基线实验

SSH_CMD="ssh -o ServerAliveInterval=10 keqin@172.30.31.98"

echo "=========================================="
echo "自动修复和重启基线实验"
echo "=========================================="
echo "时间: $(date)"
echo ""

# 1. 检查当前状态
echo "1. 检查当前运行状态..."
PROCESS_COUNT=$($SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
echo "   运行中的进程数: $PROCESS_COUNT"

if [ "$PROCESS_COUNT" -gt "0" ]; then
    echo "   ⚠️  发现运行中的进程，先停止..."
    $SSH_CMD "pkill -f 'run_baseline'" 2>/dev/null
    sleep 5
fi

# 2. 检查失败的设计
echo ""
echo "2. 检查失败的设计..."
FAILED_DESIGNS=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | xargs -I {} basename \$(dirname {})" 2>/dev/null)

if [ -n "$FAILED_DESIGNS" ]; then
    echo "   发现失败的设计:"
    echo "$FAILED_DESIGNS" | while read design; do
        echo "     - $design"
        # 检查错误原因
        ERROR_MSG=$($SSH_CMD "cd ~/chipmas && cat results/baseline/$design/result.json 2>/dev/null | grep -o '\"error\":\"[^\"]*' | head -1" 2>/dev/null)
        echo "       错误: $ERROR_MSG"
    done
else
    echo "   ✅ 无失败的设计"
fi

# 3. 检查最新日志中的错误
echo ""
echo "3. 检查最新日志中的错误..."
LATEST_LOG=$($SSH_CMD "ls -t ~/chipmas/results/baseline_logs/baseline_batch_*.log 2>/dev/null | head -1" 2>/dev/null)
if [ -n "$LATEST_LOG" ]; then
    ERRORS=$($SSH_CMD "tail -200 '$LATEST_LOG' 2>/dev/null | grep -iE 'error|failed|exception|traceback' | tail -10" 2>/dev/null)
    if [ -n "$ERRORS" ]; then
        echo "   发现错误:"
        echo "$ERRORS" | head -5
    else
        echo "   ✅ 日志中无严重错误"
    fi
fi

# 4. 同步最新代码
echo ""
echo "4. 同步最新代码..."
cd /Users/keqin/Documents/workspace/chip-rag
rsync -avz --progress -e "ssh -o ServerAliveInterval=10" \
    chipmas/src/utils/openroad_interface.py \
    chipmas/scripts/run_baseline_experiments.py \
    chipmas/scripts/run_baseline_batch.py \
    keqin@172.30.31.98:~/chipmas/ 2>&1 | grep -E "sent|received|error" || echo "   代码同步完成"

# 5. 重新启动
echo ""
echo "5. 重新启动基线实验..."
$SSH_CMD "cd ~/chipmas && bash scripts/start_baseline_batch.sh" 2>&1 | grep -E "PID|日志|进程" || echo "   启动命令已执行"

# 6. 等待并验证
echo ""
echo "6. 等待5秒后验证..."
sleep 5
NEW_PROCESS_COUNT=$($SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
if [ "$NEW_PROCESS_COUNT" -gt "0" ]; then
    echo "   ✅ 新进程已启动 (进程数: $NEW_PROCESS_COUNT)"
    $SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | head -2"
else
    echo "   ⚠️  未检测到新进程，请手动检查"
fi

echo ""
echo "=========================================="
echo "完成"
echo "=========================================="

