#!/bin/bash
# 快速升级Bison到3.6或更新版本

set -e

echo "=========================================="
echo "升级Bison到3.6或更新版本"
echo "=========================================="

# 检查当前bison版本
if command -v bison &> /dev/null; then
    CURRENT_VERSION=$(bison --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    BISON_MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
    BISON_MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
    
    echo "当前Bison版本: $CURRENT_VERSION"
    
    if [ "$BISON_MAJOR" -ge 3 ] && [ "$BISON_MINOR" -ge 6 ]; then
        echo "✓ Bison版本已满足要求（≥3.6）"
        exit 0
    else
        echo "⚠️  Bison版本过低，需要升级到≥3.6"
    fi
else
    echo "Bison未安装"
fi

# 检查依赖
echo ""
echo "检查依赖..."
if ! command -v m4 &> /dev/null; then
    echo "安装m4（bison的依赖）..."
    sudo apt-get update
    sudo apt-get install -y m4
fi

if ! command -v wget &> /dev/null; then
    echo "安装wget..."
    sudo apt-get install -y wget
fi

# 下载并编译bison
BISON_BUILD_DIR="$HOME/bison_build"
BISON_VERSION="3.8.2"

if [ -d "$BISON_BUILD_DIR" ]; then
    echo "清理旧的bison编译目录..."
    rm -rf "$BISON_BUILD_DIR"
fi

echo ""
echo "下载bison $BISON_VERSION源码..."
cd ~
wget https://ftp.gnu.org/gnu/bison/bison-${BISON_VERSION}.tar.xz || {
    echo "❌ 无法下载bison源码"
    exit 1
}

echo "解压bison源码..."
tar -xf bison-${BISON_VERSION}.tar.xz
mv bison-${BISON_VERSION} "$BISON_BUILD_DIR"
rm bison-${BISON_VERSION}.tar.xz

cd "$BISON_BUILD_DIR"

echo ""
echo "配置bison编译..."
./configure --prefix="$HOME/.local"

echo ""
echo "编译bison（这可能需要几分钟）..."
make -j$(nproc)

echo ""
echo "安装bison..."
make install

# 添加到PATH
export PATH="$HOME/.local/bin:$PATH"

# 验证安装
echo ""
echo "验证安装..."
if "$HOME/.local/bin/bison" --version &> /dev/null; then
    NEW_VERSION=$("$HOME/.local/bin/bison" --version | head -1)
    echo "✓ Bison升级成功: $NEW_VERSION"
    
    # 显示版本信息
    "$HOME/.local/bin/bison" --version | head -1
    
    echo ""
    echo "=========================================="
    echo "✓ Bison升级完成！"
    echo "=========================================="
    echo ""
    echo "安装位置: $HOME/.local/bin/bison"
    echo ""
    echo "请确保 ~/.local/bin 在PATH中："
    echo "  export PATH=\$PATH:\$HOME/.local/bin"
    echo "  或添加到 ~/.bashrc:"
    echo "  echo 'export PATH=\$PATH:\$HOME/.local/bin' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "然后重新运行Yosys编译："
    echo "  cd ~/chipmas"
    echo "  bash scripts/reinstall_yosys_from_source.sh"
else
    echo "❌ Bison安装失败"
    exit 1
fi

cd -

