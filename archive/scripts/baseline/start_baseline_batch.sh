#!/bin/bash
# 在服务器后台启动基线实验批量运行

cd ~/chipmas

# 创建日志目录
mkdir -p results/baseline_logs

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="results/baseline_logs/baseline_batch_${TIMESTAMP}.log"
PID_FILE="results/baseline_logs/baseline_batch_${TIMESTAMP}.pid"

echo "=========================================="
echo "启动基线实验批量运行"
echo "=========================================="
echo "时间: $(date)"
echo "日志文件: $LOG_FILE"
echo "PID文件: $PID_FILE"
echo "=========================================="

# 使用nohup在后台运行
nohup python3 scripts/run_baseline_batch.py --background > "$LOG_FILE" 2>&1 &
PID=$!

# 保存PID
echo $PID > "$PID_FILE"

echo "进程已启动，PID: $PID"
echo ""
echo "查看日志: tail -f $LOG_FILE"
echo "查看进程: ps -p $PID"
echo "停止进程: kill $PID"
echo ""
echo "使用以下命令检查状态:"
echo "  bash scripts/check_baseline_status.sh"


