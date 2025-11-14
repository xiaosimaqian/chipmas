#!/bin/bash
# 批量启动所有benchmark类型的DREAMPlace处理

REMOTE_SERVER="172.30.31.98"
REMOTE_USER="keqin"
CONFIG="configs/default.yaml"

# Benchmark类型列表（按优先级排序）
BENCHMARKS=(
    "ispd2005free:8:小规模"
    "iccad2014:7:中等规模"
    "dac2012:10:中等规模"
    "iccad2015.ot:8:中等规模"
    "ispd2019:10:中等规模"
    "ispd2005:24:大规模"
    "mms:16:大规模"
)

echo "============================================================"
echo "批量扩展知识库 - 处理所有benchmark类型"
echo "============================================================"
echo ""

# 检查当前知识库状态
echo "当前知识库状态:"
python3 -c "
import json
from pathlib import Path
kb_file = Path('data/knowledge_base/kb_cases.json')
if kb_file.exists():
    with open(kb_file, 'r') as f:
        data = json.load(f)
    cases = data if isinstance(data, list) else data.get('cases', [])
    print(f'  总案例数: {len(cases)}')
else:
    print('  知识库文件不存在')
"

echo ""
echo "计划处理的benchmark类型:"
TOTAL=0
for i in "${!BENCHMARKS[@]}"; do
    IFS=':' read -r TYPE COUNT DESC <<< "${BENCHMARKS[$i]}"
    echo "  $((i+1)). $TYPE: $COUNT个设计 - $DESC"
    TOTAL=$((TOTAL + COUNT))
done
echo ""
echo "总计: $TOTAL个设计"
echo ""

# 检查是否有正在运行的进程
RUNNING=$(ps aux | grep -E "Placer.py|run_dreamplace_batch" | grep -v grep | wc -l)
if [ $RUNNING -gt 0 ]; then
    echo "⚠️  检测到有 $RUNNING 个DREAMPlace进程正在运行"
    read -p "是否继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 1
    fi
fi

# 启动每个benchmark类型
for BENCH in "${BENCHMARKS[@]}"; do
    IFS=':' read -r TYPE COUNT DESC <<< "$BENCH"
    LOG_FILE="/tmp/dreamplace_${TYPE}.log"
    
    echo ""
    echo "============================================================"
    echo "处理: $TYPE ($COUNT个设计) - $DESC"
    echo "============================================================"
    
    # 启动后台进程
    nohup python3 scripts/run_dreamplace_batch.py \
        --remote-server "$REMOTE_SERVER" \
        --remote-user "$REMOTE_USER" \
        --benchmark-type "$TYPE" \
        --config "$CONFIG" \
        > "$LOG_FILE" 2>&1 &
    
    PID=$!
    echo "已启动 (PID: $PID)"
    echo "日志文件: $LOG_FILE"
    echo "监控命令: tail -f $LOG_FILE"
    
    # 如果不是最后一个，等待一段时间
    if [ "$BENCH" != "${BENCHMARKS[-1]}" ]; then
        echo "等待5分钟后处理下一个批次..."
        sleep 300
    fi
done

echo ""
echo "============================================================"
echo "所有批次已启动！"
echo "============================================================"
echo ""
echo "监控所有进程:"
echo "  ps aux | grep Placer.py | grep -v grep"
echo ""
echo "查看所有日志:"
for BENCH in "${BENCHMARKS[@]}"; do
    IFS=':' read -r TYPE COUNT DESC <<< "$BENCH"
    echo "  tail -f /tmp/dreamplace_${TYPE}.log"
done



