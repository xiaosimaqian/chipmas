#!/bin/bash

echo "================================"
echo "Git历史清理脚本"
echo "================================"
echo ""
echo "⚠️  警告：此操作会重写Git历史！"
echo "⚠️  确保已经备份重要数据！"
echo ""
echo "当前Git仓库大小："
git count-objects -vH | grep "size-pack"
echo ""

read -p "是否继续？(yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "操作已取消"
    exit 0
fi

echo ""
echo "步骤1: 创建备份分支..."
git branch backup-before-cleanup 2>/dev/null || echo "备份分支已存在"

echo ""
echo "步骤2: 从Git历史中移除data/和results/目录..."

# 使用git filter-repo（推荐）或filter-branch
if command -v git-filter-repo &> /dev/null; then
    echo "使用git-filter-repo（推荐方法）..."
    git filter-repo --path data --path results --invert-paths --force
else
    echo "git-filter-repo未安装，使用filter-branch..."
    git filter-branch --force --index-filter \
      "git rm -r --cached --ignore-unmatch data/ results/" \
      --prune-empty --tag-name-filter cat -- --all
fi

echo ""
echo "步骤3: 清理引用和对象..."
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo ""
echo "步骤4: 检查清理后的大小..."
git count-objects -vH

echo ""
echo "================================"
echo "✓ 清理完成！"
echo "================================"
echo ""
echo "下一步："
echo "1. 检查仓库是否正常: git log --oneline | head"
echo "2. 强制推送到远程: git push origin main --force"
echo ""
echo "如果出现问题，可以恢复："
echo "  git reset --hard backup-before-cleanup"

