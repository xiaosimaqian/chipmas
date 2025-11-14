#!/bin/bash
# 快速检查基线实验状态

SSH_CMD="ssh -o ServerAliveInterval=10 keqin@172.30.31.98"

echo "=========================================="
echo "基线实验快速检查"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 1. 进程状态
echo ""
echo "1. 进程状态:"
PROCESS_COUNT=$($SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
if [ "$PROCESS_COUNT" -gt "0" ]; then
    echo "   ✅ 基线实验正在运行 (进程数: $PROCESS_COUNT)"
    $SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | head -1 | awk '{print \"   PID: \" \$2 \", CPU: \" \$3 \"%, MEM: \" \$4 \"%, 运行时间: \" \$10}'"
else
    echo "   ⚠️  未找到运行中的基线实验进程"
fi

# 2. OpenROAD进程
OPENROAD_COUNT=$($SSH_CMD "ps aux | grep openroad | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
if [ "$OPENROAD_COUNT" -gt "0" ]; then
    echo "   ✅ OpenROAD正在运行 (进程数: $OPENROAD_COUNT)"
    $SSH_CMD "ps aux | grep openroad | grep -v grep | head -1 | awk '{print \"   PID: \" \$2 \", CPU: \" \$3 \"%, MEM: \" \$4 \"% (\" \$6/1024/1024 \" GB), 运行时间: \" \$10}'"
else
    echo "   ℹ️  当前无OpenROAD进程（可能正在处理其他阶段）"
fi

# 3. 进度
echo ""
echo "2. 进度:"
COMPLETED=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
TOTAL_DESIGNS=16
PROGRESS=$((COMPLETED * 100 / TOTAL_DESIGNS))
echo "   已完成: $COMPLETED / $TOTAL_DESIGNS ($PROGRESS%)"

# 4. 最新完成
LATEST_RESULT=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec ls -lt {} + 2>/dev/null | head -1" 2>/dev/null)
if [ -n "$LATEST_RESULT" ]; then
    LATEST_DESIGN=$(echo "$LATEST_RESULT" | awk '{print $NF}' | xargs basename $(dirname {}))
    LATEST_TIME=$(echo "$LATEST_RESULT" | awk '{print $6, $7, $8}')
    echo "   最新完成: $(basename $(dirname $LATEST_RESULT)) (时间: $LATEST_TIME)"
fi

# 5. 失败检查
echo ""
echo "3. 错误检查:"
FAILED_COUNT=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
if [ "$FAILED_COUNT" -gt "0" ]; then
    echo "   ⚠️  失败的设计数: $FAILED_COUNT"
    FAILED_DESIGNS=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | xargs -I {} basename \$(dirname {})" 2>/dev/null)
    echo "   失败设计: $FAILED_DESIGNS"
else
    echo "   ✅ 无失败设计"
fi

# 6. 最新日志错误
LATEST_LOG=$($SSH_CMD "ls -t ~/chipmas/results/baseline_logs/baseline_batch_*.log 2>/dev/null | head -1" 2>/dev/null)
if [ -n "$LATEST_LOG" ]; then
    ERRORS=$($SSH_CMD "tail -50 '$LATEST_LOG' 2>/dev/null | grep -iE 'error|failed|exception' | tail -3" 2>/dev/null)
    if [ -n "$ERRORS" ]; then
        echo "   ⚠️  最新日志中的错误:"
        echo "$ERRORS" | sed 's/^/      /'
    fi
fi

echo ""
echo "=========================================="
echo "详细状态: bash scripts/check_baseline_status.sh"
echo "自动修复: bash scripts/auto_fix_and_restart.sh"
echo "=========================================="

