#!/bin/bash

echo "检查待push的内容..."
echo ""

echo "=== 待push的提交数量 ==="
git log --oneline origin/main..HEAD 2>/dev/null | wc -l | xargs echo "提交数:"
echo ""

echo "=== 待push的文件变化 ==="
git diff --stat origin/main..HEAD 2>/dev/null | tail -20
echo ""

echo "=== 大文件检查 (前20个最大的) ==="
git ls-tree -r -l HEAD | sort -k4 -n -r | head -20 | awk '{printf "%8.2f MB  %s\n", $4/1024/1024, $5}'
echo ""

echo "=== .git目录大小 ==="
du -sh .git/
echo ""

echo "=== 建议 ==="
echo "如果.git目录很大（>100MB），可能需要："
echo "  1. 使用 git gc --aggressive 压缩"
echo "  2. 使用 BFG清理历史中的大文件"
echo "  3. 考虑使用Git LFS管理大文件"

