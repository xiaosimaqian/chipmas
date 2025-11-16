#!/bin/bash
# 在服务器上升级Yosys到0.56或更新版本

set -e

echo "=========================================="
echo "升级服务器Yosys到0.56或更新版本"
echo "=========================================="

# 检查当前Yosys版本
if command -v yosys &> /dev/null; then
    CURRENT_VERSION=$(yosys -V 2>&1 | head -1)
    echo "当前Yosys版本: $CURRENT_VERSION"
    
    # 检查版本号
    if echo "$CURRENT_VERSION" | grep -q "Yosys 0.56\|Yosys 0.57\|Yosys 0.58\|Yosys 0.59\|Yosys 0.6"; then
        echo "✓ Yosys版本已满足要求（≥0.56）"
        exit 0
    else
        echo "⚠️  Yosys版本过低，需要升级"
    fi
else
    echo "Yosys未安装"
fi

echo ""
echo "开始升级Yosys..."

# 检查依赖
echo "检查编译依赖..."
MISSING_DEPS=""
if ! command -v git &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS git"
fi
if ! command -v make &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS build-essential"
fi
if ! pkg-config --exists readline 2>/dev/null; then
    MISSING_DEPS="$MISSING_DEPS libreadline-dev"
fi

if [ -n "$MISSING_DEPS" ]; then
    echo "⚠️  缺少依赖: $MISSING_DEPS"
    echo "请手动安装（需要sudo权限）："
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y $MISSING_DEPS"
    echo ""
    read -p "是否已安装依赖？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "请先安装依赖后重新运行此脚本"
        exit 1
    fi
fi

# 编译Yosys
BUILD_DIR="$HOME/yosys_build"
if [ ! -d "$BUILD_DIR" ]; then
    echo "克隆Yosys源码到 $BUILD_DIR..."
    git clone https://github.com/YosysHQ/yosys.git "$BUILD_DIR"
fi

cd "$BUILD_DIR"

# 更新到最新版本或指定版本
echo "更新Yosys源码..."
git fetch origin
# 尝试使用0.56版本（已验证可工作）
if git tag | grep -q "^0.56"; then
    echo "切换到Yosys 0.56版本..."
    git checkout 0.56
else
    echo "使用最新版本..."
    git pull origin master
fi

# 初始化submodules
echo "初始化git submodules..."
git submodule update --init --recursive

# 编译
echo "编译Yosys（这可能需要10-20分钟）..."
make config-gcc
make -j$(nproc)

# 安装
YOSYS_BIN="$BUILD_DIR/yosys"
if [ -f "$YOSYS_BIN" ]; then
    echo "✓ Yosys编译成功: $YOSYS_BIN"
    
    # 检查版本
    NEW_VERSION=$("$YOSYS_BIN" -V 2>&1 | head -1)
    echo "新版本: $NEW_VERSION"
    
    # 添加到PATH
    if [ -d "$HOME/.local/bin" ]; then
        ln -sf "$YOSYS_BIN" "$HOME/.local/bin/yosys"
        echo "✓ 已创建符号链接: ~/.local/bin/yosys"
        echo ""
        echo "请确保 ~/.local/bin 在PATH中："
        echo "  export PATH=\$PATH:\$HOME/.local/bin"
        echo "  或添加到 ~/.bashrc"
    else
        echo "⚠️  请将以下路径添加到PATH："
        echo "  export PATH=\$PATH:$BUILD_DIR"
    fi
    
    # 验证安装
    echo ""
    echo "验证安装..."
    if "$YOSYS_BIN" -V &> /dev/null; then
        echo "✓ Yosys安装成功！"
        "$YOSYS_BIN" -V | head -1
    else
        echo "❌ Yosys安装失败"
        exit 1
    fi
else
    echo "❌ Yosys编译失败"
    exit 1
fi

cd -

echo ""
echo "=========================================="
echo "✓ Yosys升级完成！"
echo "=========================================="
echo ""
echo "请重新运行Step 1-4测试："
echo "  cd ~/chipmas"
echo "  bash scripts/run_step1_4_server.sh"

