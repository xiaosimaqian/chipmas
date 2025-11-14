#!/bin/bash

echo "检查Git仓库状态..."
echo ""

echo "=== 暂存区文件列表（前30个）==="
git diff --cached --name-only | head -30
echo ""

echo "=== 暂存区大小统计 ==="
git diff --cached --stat | tail -1
echo ""

echo "=== 大文件检查 (>10MB) ==="
git diff --cached --name-only | while read file; do
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        echo "$size  $file"
    fi
done | grep -E "^[0-9]+M|^[0-9]+G" | sort -hr | head -20
echo ""

echo "=== data/和results/目录状态 ==="
git ls-files data/ 2>/dev/null | wc -l | xargs echo "data/目录文件数:"
git ls-files results/ 2>/dev/null | wc -l | xargs echo "results/目录文件数:"
echo ""

echo "=== 建议操作 ==="
data_count=$(git ls-files data/ 2>/dev/null | wc -l | tr -d ' ')
results_count=$(git ls-files results/ 2>/dev/null | wc -l | tr -d ' ')

if [ "$data_count" -gt 0 ] || [ "$results_count" -gt 0 ]; then
    echo "⚠️  检测到data/或results/目录在Git中！"
    echo ""
    echo "执行以下命令清理："
    echo "  git rm -r --cached data/ results/"
    echo "  git commit -m 'Remove large data and results directories'"
    echo "  git push -u origin main"
else
    echo "✓ data/和results/目录未在Git中"
    echo "可以安全push"
fi

