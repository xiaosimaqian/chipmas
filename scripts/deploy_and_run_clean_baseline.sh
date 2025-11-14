#!/bin/bash
# 部署并运行Clean Baseline收集实验
# EXP-002: ISPD 2015 Clean Baseline（无分区约束）

SERVER="keqin@172.30.31.98"
REMOTE_DIR="~/chipmas"

echo "======================================================================"
echo "EXP-002: ISPD 2015 Clean Baseline 收集"
echo "======================================================================"
echo ""

# 1. 同步脚本到服务器
echo "📦 同步脚本到服务器..."
rsync -avz --progress \
  scripts/collect_clean_baseline.py \
  scripts/experiment_tracker.py \
  $SERVER:$REMOTE_DIR/scripts/

# 2. 确保die_size_config.py是最新的
echo ""
echo "📦 同步die_size_config.py..."
rsync -avz --progress \
  src/utils/die_size_config.py \
  $SERVER:$REMOTE_DIR/src/utils/

# 3. 在服务器上启动实验
echo ""
echo "🚀 在服务器上启动实验..."
ssh $SERVER << 'ENDSSH'
cd ~/chipmas

# 创建输出目录
mkdir -p results/clean_baseline

# 启动实验并记录PID
echo "启动Clean Baseline收集..."
nohup python3 scripts/collect_clean_baseline.py \
  --output-dir results/clean_baseline \
  > results/clean_baseline/run.log 2>&1 &

PID=$!
echo "进程已启动，PID: $PID"

# 更新实验跟踪
python3 scripts/experiment_tracker.py start EXP-002 --pid $PID

echo ""
echo "✅ 实验已启动"
echo "   PID: $PID"
echo "   日志: results/clean_baseline/run.log"
echo ""
echo "监控命令:"
echo "  tail -f ~/chipmas/results/clean_baseline/run.log"
echo "  python3 ~/chipmas/scripts/experiment_tracker.py show EXP-002"
ENDSSH

echo ""
echo "======================================================================"
echo "部署完成"
echo "======================================================================"
echo ""
echo "📋 本地查看实验状态:"
echo "   python3 scripts/experiment_tracker.py list"
echo ""
echo "📋 SSH到服务器监控:"
echo "   ssh $SERVER"
echo "   tail -f ~/chipmas/results/clean_baseline/run.log"
echo ""


