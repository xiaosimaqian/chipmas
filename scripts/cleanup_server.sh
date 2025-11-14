#!/bin/bash
# 整理服务器 ~/chipmas 目录结构

cd ~/chipmas || exit 1

echo "=== 开始整理 ~/chipmas 目录 ==="

# 1. 创建必要的目录结构
mkdir -p archive/old_logs
mkdir -p archive/old_results
mkdir -p archive/temp_files

# 2. 移动旧的日志文件
if [ -d "logs" ] && [ "$(ls -A logs 2>/dev/null)" ]; then
    echo "移动旧日志文件..."
    mv logs/* archive/old_logs/ 2>/dev/null
fi

# 3. 整理 data 目录
# 合并 dataset 和 datasets（如果 datasets 存在且不为空）
if [ -d "data/datasets" ] && [ "$(ls -A data/datasets 2>/dev/null)" ]; then
    echo "检查 data/datasets 目录..."
    # 如果 dataset 目录已存在，datasets 中的内容应该已经在 dataset 中
    # 这里只做检查，不移动
fi

# 4. 清理临时文件
echo "清理临时文件..."
find . -name "*.pyc" -delete 2>/dev/null
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name ".DS_Store" -delete 2>/dev/null
find . -name "._*" -delete 2>/dev/null

# 5. 整理 results 目录
if [ -d "results" ]; then
    echo "整理 results 目录..."
    # 创建子目录用于分类
    mkdir -p results/baseline_experiments
    mkdir -p results/reference_runs
    mkdir -p results/test_runs
    
    # 移动测试结果到 test_runs
    if [ -d "results/test_original" ]; then
        mv results/test_original results/test_runs/ 2>/dev/null
    fi
    if [ -d "results/test_original_no_partition" ]; then
        mv results/test_original_no_partition results/test_runs/ 2>/dev/null
    fi
    if [ -d "results/test_path_fix" ]; then
        mv results/test_path_fix results/test_runs/ 2>/dev/null
    fi
fi

# 6. 清理空的 nohup.out 文件
if [ -f "nohup.out" ] && [ ! -s "nohup.out" ]; then
    rm -f nohup.out
fi

echo "=== 整理完成 ==="
echo "当前目录结构："
ls -lah | head -20

