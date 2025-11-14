#!/bin/bash
# 问题报告脚本 - 检测并详细报告所有问题，不自动修复

SSH_CMD="ssh -o ServerAliveInterval=10 keqin@172.30.31.98"
REPORT_FILE="issue_report_$(date +%Y%m%d_%H%M%S).txt"

echo "=========================================="
echo "基线实验问题检测报告"
echo "=========================================="
echo "生成时间: $(date)"
echo "报告文件: $REPORT_FILE"
echo "=========================================="
echo ""

{
    echo "=========================================="
    echo "基线实验问题检测报告"
    echo "生成时间: $(date)"
    echo "=========================================="
    echo ""
    
    # 1. 进程状态
    echo "1. 进程状态检查"
    echo "----------------------------------------"
    PROCESS_COUNT=$($SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$PROCESS_COUNT" -eq "0" ]; then
        echo "❌ 问题: 未找到运行中的基线实验进程"
        echo "   需要检查进程是否异常退出"
    else
        echo "✅ 基线实验进程正在运行 (进程数: $PROCESS_COUNT)"
        $SSH_CMD "ps aux | grep -E 'run_baseline|run_baseline_batch' | grep -v grep | head -2"
    fi
    echo ""
    
    # 2. OpenROAD进程
    echo "2. OpenROAD进程检查"
    echo "----------------------------------------"
    OPENROAD_COUNT=$($SSH_CMD "ps aux | grep openroad | grep -v grep | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$OPENROAD_COUNT" -gt "0" ]; then
        echo "✅ OpenROAD进程正在运行 (进程数: $OPENROAD_COUNT)"
        $SSH_CMD "ps aux | grep openroad | grep -v grep | head -2 | awk '{print \"   PID: \" \$2 \", CPU: \" \$3 \"%, MEM: \" \$6/1024/1024 \" GB, 运行时间: \" \$10}'"
        
        # 检查内存使用
        OPENROAD_MEM=$($SSH_CMD "ps aux | grep openroad | grep -v grep | awk '{sum+=\$6} END {print sum/1024/1024}'" 2>/dev/null | head -1)
        if [ -n "$OPENROAD_MEM" ]; then
            MEM_GB=$(echo "$OPENROAD_MEM" | awk '{printf "%.1f", $1}')
            if (( $(echo "$MEM_GB > 100" | bc -l 2>/dev/null || echo "0") )); then
                echo "⚠️  警告: OpenROAD内存使用较高: ${MEM_GB} GB"
            else
                echo "✅ OpenROAD内存使用正常: ${MEM_GB} GB"
            fi
        fi
    else
        echo "ℹ️  当前无OpenROAD进程（可能正在处理其他阶段）"
    fi
    echo ""
    
    # 3. 进度检查
    echo "3. 进度检查"
    echo "----------------------------------------"
    COMPLETED=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
    TOTAL_DESIGNS=16
    PROGRESS=$((COMPLETED * 100 / TOTAL_DESIGNS))
    echo "已完成: $COMPLETED / $TOTAL_DESIGNS ($PROGRESS%)"
    
    # 检查最新完成时间
    LATEST_RESULT=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec ls -lt {} + 2>/dev/null | head -1" 2>/dev/null)
    if [ -n "$LATEST_RESULT" ]; then
        LATEST_TIME=$(echo "$LATEST_RESULT" | awk '{print $6, $7, $8}')
        LATEST_DESIGN=$(echo "$LATEST_RESULT" | awk '{print $NF}' | xargs -I {} basename $(dirname {}))
        echo "最新完成: $LATEST_DESIGN (时间: $LATEST_TIME)"
        
        # 检查是否长时间没有新结果
        LATEST_RESULT_TIME=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec stat -c '%Y' {} \; 2>/dev/null | sort -n | tail -1" 2>/dev/null)
        if [ -n "$LATEST_RESULT_TIME" ]; then
            CURRENT_TIME_UNIX=$(date +%s)
            TIME_SINCE_LAST=$((CURRENT_TIME_UNIX - LATEST_RESULT_TIME))
            HOURS_SINCE_LAST=$((TIME_SINCE_LAST / 3600))
            if [ "$TIME_SINCE_LAST" -gt 7200 ] && [ "$COMPLETED" -lt "$TOTAL_DESIGNS" ]; then
                echo "⚠️  警告: 超过 ${HOURS_SINCE_LAST} 小时没有新结果产生"
            fi
        fi
    fi
    echo ""
    
    # 4. 失败设计详细分析
    echo "4. 失败设计详细分析"
    echo "----------------------------------------"
    FAILED_COUNT=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ')
    if [ "$FAILED_COUNT" -gt "0" ]; then
        echo "❌ 发现 $FAILED_COUNT 个失败的设计:"
        echo ""
        
        FAILED_DESIGNS=$($SSH_CMD "cd ~/chipmas && find results/baseline -name 'result.json' -type f -exec grep -l '\"status\":\"error\"' {} \; 2>/dev/null | xargs -I {} basename \$(dirname {})" 2>/dev/null)
        
        for design in $FAILED_DESIGNS; do
            echo "设计: $design"
            echo "  ────────────────────────────────"
            
            # 提取错误信息
            ERROR_INFO=$($SSH_CMD "cd ~/chipmas && cat results/baseline/$design/result.json 2>/dev/null | python3 -c \"
import json, sys
try:
    data = json.load(sys.stdin)
    print(f'状态: {data.get(\"status\", \"unknown\")}')
    error = data.get('error', 'Unknown error')
    print(f'错误: {error[:300]}')
    if 'layout_info' in data:
        runtime = data['layout_info'].get('runtime', 0)
        print(f'运行时间: {runtime:.2f}秒')
        returncode = data['layout_info'].get('returncode', 'N/A')
        print(f'返回码: {returncode}')
except Exception as e:
    print(f'解析错误: {e}')
\" 2>/dev/null")
            
            echo "$ERROR_INFO" | sed 's/^/  /'
            
            # 错误分类
            ERROR_MSG=$($SSH_CMD "cd ~/chipmas && cat results/baseline/$design/result.json 2>/dev/null | grep -o '\"error\":\"[^\"]*' | head -1 | cut -d'\"' -f4" 2>/dev/null)
            if echo "$ERROR_MSG" | grep -qi "out of memory\|OOM\|内存"; then
                echo "  问题类型: 🔴 内存不足"
                echo "  建议: 减少OpenROAD线程数或优化内存使用"
            elif echo "$ERROR_MSG" | grep -qi "timeout\|超时"; then
                echo "  问题类型: 🟡 超时"
                echo "  建议: 增加超时时间或优化性能"
            elif echo "$ERROR_MSG" | grep -qi "DEF parser\|解析错误"; then
                echo "  问题类型: 🔴 DEF文件解析错误"
                echo "  建议: 检查DEF文件格式和GROUPS/REGIONS定义"
            elif echo "$ERROR_MSG" | grep -qi "SIGKILL\|-9"; then
                echo "  问题类型: 🔴 进程被强制终止"
                echo "  建议: 检查系统资源（内存、OOM Killer）"
            else
                echo "  问题类型: ⚠️  其他错误"
            fi
            
            echo ""
        done
    else
        echo "✅ 无失败设计"
    fi
    echo ""
    
    # 5. 最新日志错误
    echo "5. 最新日志错误检查"
    echo "----------------------------------------"
    LATEST_LOG=$($SSH_CMD "ls -t ~/chipmas/results/baseline_logs/baseline_batch_*.log 2>/dev/null | head -1" 2>/dev/null)
    if [ -n "$LATEST_LOG" ]; then
        echo "日志文件: $LATEST_LOG"
        ERRORS=$($SSH_CMD "tail -200 '$LATEST_LOG' 2>/dev/null | grep -iE 'error|failed|exception|traceback|out of memory|OOM|SIGKILL' | tail -10" 2>/dev/null)
        if [ -n "$ERRORS" ]; then
            echo "⚠️  发现错误:"
            echo "$ERRORS" | sed 's/^/  /'
        else
            echo "✅ 日志中无严重错误"
        fi
    else
        echo "ℹ️  未找到日志文件"
    fi
    echo ""
    
    # 6. 系统资源
    echo "6. 系统资源检查"
    echo "----------------------------------------"
    MEMORY_INFO=$($SSH_CMD "free -h 2>/dev/null | grep Mem" 2>/dev/null)
    echo "内存: $MEMORY_INFO"
    
    DISK_USAGE=$($SSH_CMD "df -h ~/chipmas/results 2>/dev/null | tail -1" 2>/dev/null)
    echo "磁盘: $DISK_USAGE"
    echo ""
    
    # 7. 建议操作
    echo "7. 建议操作"
    echo "----------------------------------------"
    if [ "$FAILED_COUNT" -gt "0" ]; then
        echo "❌ 发现失败设计，建议："
        echo "  1. 查看失败设计的详细错误信息（见上方）"
        echo "  2. 根据错误类型采取相应措施："
        echo "     - 内存不足: 减少线程数或优化内存"
        echo "     - DEF解析错误: 检查DEF文件格式"
        echo "     - 超时: 增加超时时间"
        echo "  3. 修复后删除失败结果，重新运行"
    fi
    
    if [ "$PROCESS_COUNT" -eq "0" ] && [ "$COMPLETED" -lt "$TOTAL_DESIGNS" ]; then
        echo "❌ 进程已停止但未完成，建议："
        echo "  1. 检查日志文件找出停止原因"
        echo "  2. 修复问题后重新启动"
    fi
    
    if [ ${#ALERTS[@]} -eq 0 ] && [ "$PROCESS_COUNT" -gt "0" ]; then
        echo "✅ 当前运行正常，继续监控即可"
    fi
    echo ""
    
    echo "=========================================="
    echo "报告生成完成"
    echo "=========================================="
    
} | tee "$REPORT_FILE"

echo ""
echo "详细报告已保存到: $REPORT_FILE"


