#!/bin/bash
# 检查基线实验运行状态

ssh -o ServerAliveInterval=10 keqin@172.30.31.98 << 'EOF'
cd ~/chipmas

echo "=========================================="
echo "基线实验运行状态"
echo "=========================================="
echo "时间: $(date)"
echo ""

# 检查screen会话
echo "Screen会话:"
screen -ls | grep baseline_batch || echo "  无运行中的baseline_batch会话"
echo ""

# 检查进程
echo "运行中的进程:"
ps aux | grep -E "run_baseline|openroad" | grep -v grep | head -5 || echo "  无相关进程"
echo ""

# 检查最新日志
LATEST_LOG=$(ls -t results/baseline_logs/baseline_batch_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "最新日志: $LATEST_LOG"
    echo "最后10行:"
    tail -10 "$LATEST_LOG"
    echo ""
else
    echo "未找到日志文件"
    echo ""
fi

# 检查已完成的结果
echo "已完成的设计:"
if [ -d "results/baseline" ]; then
    find results/baseline -name "result.json" -type f | wc -l | xargs echo "  已完成:"
    echo ""
    echo "设计列表:"
    find results/baseline -name "result.json" -type f | sed 's|results/baseline/||; s|/result.json||' | sort
else
    echo "  结果目录不存在"
fi
echo ""

# 检查OpenROAD进程
echo "OpenROAD进程（如果正在运行）:"
ps aux | grep openroad | grep -v grep | head -3 || echo "  无OpenROAD进程"
echo ""

EOF


