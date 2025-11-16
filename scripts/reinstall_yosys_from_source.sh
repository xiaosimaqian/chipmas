#!/bin/bash
# 在服务器上卸载当前Yosys，然后从GitHub源码安装最新版本

set -e

echo "=========================================="
echo "卸载当前Yosys并从GitHub源码安装"
echo "=========================================="

# 1. 检查当前Yosys版本
if command -v yosys &> /dev/null; then
    CURRENT_VERSION=$(yosys -V 2>&1 | head -1)
    echo "当前Yosys版本: $CURRENT_VERSION"
    
    # 查找Yosys的安装位置
    YOSYS_PATH=$(which yosys)
    echo "Yosys路径: $YOSYS_PATH"
    
    # 2. 卸载当前Yosys
    echo ""
    echo "步骤1: 卸载当前Yosys..."
    
    # 检查是否通过apt安装
    if dpkg -l | grep -q "^ii.*yosys"; then
        echo "检测到通过apt安装的Yosys，使用apt卸载..."
        sudo apt-get remove -y yosys || true
        sudo apt-get purge -y yosys || true
    fi
    
    # 删除符号链接
    if [ -L "$YOSYS_PATH" ]; then
        echo "删除符号链接: $YOSYS_PATH"
        rm -f "$YOSYS_PATH"
    fi
    
    # 删除可能的安装目录
    if [ -d "$HOME/.local/bin" ] && [ -f "$HOME/.local/bin/yosys" ]; then
        echo "删除: $HOME/.local/bin/yosys"
        rm -f "$HOME/.local/bin/yosys"
    fi
    
    # 删除之前编译的版本
    if [ -d "$HOME/yosys_build" ]; then
        echo "删除之前的编译目录: $HOME/yosys_build"
        rm -rf "$HOME/yosys_build"
    fi
    
    echo "✓ Yosys卸载完成"
else
    echo "Yosys未安装，跳过卸载步骤"
fi

# 3. 检查依赖
echo ""
echo "步骤2: 检查编译依赖..."
MISSING_DEPS=""

# 检查必需工具
if ! command -v git &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS git"
fi
if ! command -v make &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS build-essential"
fi
if ! command -v g++ &> /dev/null && ! command -v clang++ &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS g++"
fi

# 检查bison版本（需要≥3.6）
if command -v bison &> /dev/null; then
    BISON_VERSION=$(bison --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    BISON_MAJOR=$(echo "$BISON_VERSION" | cut -d. -f1)
    BISON_MINOR=$(echo "$BISON_VERSION" | cut -d. -f2)
    
    if [ "$BISON_MAJOR" -lt 3 ] || ([ "$BISON_MAJOR" -eq 3 ] && [ "$BISON_MINOR" -lt 6 ]); then
        echo "⚠️  Bison版本过低: $BISON_VERSION (需要≥3.6)"
        echo "   需要升级bison，请参考脚本中的bison升级步骤"
        MISSING_DEPS="$MISSING_DEPS bison(≥3.6)"
    else
        echo "✓ Bison版本满足要求: $BISON_VERSION"
    fi
else
    MISSING_DEPS="$MISSING_DEPS bison"
fi

# 检查flex（bison的依赖）
if ! command -v flex &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS flex"
fi

# 检查可选但推荐的依赖
if ! pkg-config --exists readline 2>/dev/null; then
    MISSING_DEPS="$MISSING_DEPS libreadline-dev"
fi
if ! pkg-config --exists tcl 2>/dev/null; then
    MISSING_DEPS="$MISSING_DEPS tcl-dev"
fi
if ! pkg-config --exists libffi 2>/dev/null; then
    MISSING_DEPS="$MISSING_DEPS libffi-dev"
fi

# 升级bison的函数
upgrade_bison() {
    echo ""
    echo "升级Bison到3.6或更新版本..."
    
    BISON_BUILD_DIR="$HOME/bison_build"
    if [ -d "$BISON_BUILD_DIR" ]; then
        echo "清理旧的bison编译目录..."
        rm -rf "$BISON_BUILD_DIR"
    fi
    
    # 检查是否需要安装m4（bison的依赖）
    if ! command -v m4 &> /dev/null; then
        echo "安装m4（bison的依赖）..."
        sudo apt-get install -y m4 || {
            echo "❌ 无法安装m4，请手动安装：sudo apt-get install -y m4"
            exit 1
        }
    fi
    
    echo "下载bison源码..."
    cd ~
    wget https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.xz || {
        echo "❌ 无法下载bison源码"
        exit 1
    }
    
    echo "解压bison源码..."
    tar -xf bison-3.8.2.tar.xz
    mv bison-3.8.2 "$BISON_BUILD_DIR"
    rm bison-3.8.2.tar.xz
    
    cd "$BISON_BUILD_DIR"
    
    echo "配置bison编译..."
    ./configure --prefix="$HOME/.local"
    
    echo "编译bison（这可能需要几分钟）..."
    make -j$(nproc)
    
    echo "安装bison..."
    make install
    
    # 添加到PATH
    export PATH="$HOME/.local/bin:$PATH"
    
    # 验证安装
    if "$HOME/.local/bin/bison" --version &> /dev/null; then
        NEW_BISON_VERSION=$("$HOME/.local/bin/bison" --version | head -1)
        echo "✓ Bison升级成功: $NEW_BISON_VERSION"
    else
        echo "❌ Bison安装失败"
        exit 1
    fi
    
    cd -
}

# 处理依赖
if [ -n "$MISSING_DEPS" ]; then
    echo "⚠️  缺少依赖: $MISSING_DEPS"
    
    # 检查是否需要升级bison
    NEED_BISON_UPGRADE=false
    if echo "$MISSING_DEPS" | grep -q "bison(≥3.6)"; then
        NEED_BISON_UPGRADE=true
    fi
    
    if [ "$NEED_BISON_UPGRADE" = true ]; then
        echo ""
        echo "检测到需要升级bison到3.6或更新版本"
        read -p "是否自动升级bison？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            upgrade_bison
            # 重新检查bison版本
            export PATH="$HOME/.local/bin:$PATH"
            BISON_VERSION=$(bison --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            BISON_MAJOR=$(echo "$BISON_VERSION" | cut -d. -f1)
            BISON_MINOR=$(echo "$BISON_VERSION" | cut -d. -f2)
            if [ "$BISON_MAJOR" -lt 3 ] || ([ "$BISON_MAJOR" -eq 3 ] && [ "$BISON_MINOR" -lt 6 ]); then
                echo "❌ Bison升级后版本仍不满足要求"
                exit 1
            fi
            echo "✓ Bison版本已满足要求"
        else
            echo "请手动升级bison后重新运行此脚本"
            echo "参考：https://www.gnu.org/software/bison/"
            exit 1
        fi
    else
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
else
    echo "✓ 所有依赖已安装"
fi

# 4. 从GitHub克隆源码
echo ""
echo "步骤3: 从GitHub克隆Yosys源码..."
BUILD_DIR="$HOME/yosys_build"

if [ -d "$BUILD_DIR" ]; then
    echo "清理旧的源码目录..."
    rm -rf "$BUILD_DIR"
fi

echo "克隆Yosys源码（包含submodules）..."
git clone --recurse-submodules https://github.com/YosysHQ/yosys.git "$BUILD_DIR"

cd "$BUILD_DIR"

# 确保PATH包含~/.local/bin（如果升级了bison）
export PATH="$HOME/.local/bin:$PATH"

# 验证bison版本
if command -v bison &> /dev/null; then
    BISON_VERSION=$(bison --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    BISON_PATH=$(which bison)
    echo "使用Bison: $BISON_PATH (版本: $BISON_VERSION)"
fi

# 5. 配置编译环境
echo ""
echo "步骤4: 配置编译环境..."

# 检测可用的编译器
if command -v clang++ &> /dev/null; then
    echo "使用clang++编译器..."
    make config-clang
elif command -v g++ &> /dev/null; then
    echo "使用g++编译器..."
    make config-gcc
else
    echo "❌ 未找到C++编译器（需要g++或clang++）"
    exit 1
fi

# 6. 编译Yosys
echo ""
echo "步骤5: 编译Yosys（这可能需要10-20分钟）..."
echo "使用 $(nproc) 个并行任务..."

make -j$(nproc)

# 7. 验证编译结果
YOSYS_BIN="$BUILD_DIR/yosys"
if [ ! -f "$YOSYS_BIN" ]; then
    echo "❌ Yosys编译失败：未找到可执行文件"
    exit 1
fi

echo "✓ Yosys编译成功: $YOSYS_BIN"

# 8. 安装Yosys
echo ""
echo "步骤6: 安装Yosys..."

# 创建安装目录
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

# 创建符号链接
ln -sf "$YOSYS_BIN" "$INSTALL_DIR/yosys"
echo "✓ 已创建符号链接: $INSTALL_DIR/yosys"

# 9. 验证安装
echo ""
echo "步骤7: 验证安装..."

# 检查PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "⚠️  $INSTALL_DIR 不在PATH中"
    echo "请将以下内容添加到 ~/.bashrc 或 ~/.zshrc："
    echo "  export PATH=\$PATH:\$HOME/.local/bin"
    echo ""
    echo "然后运行："
    echo "  source ~/.bashrc  # 或 source ~/.zshrc"
    echo ""
    echo "或者临时添加到当前会话："
    echo "  export PATH=\$PATH:\$HOME/.local/bin"
    export PATH="$PATH:$INSTALL_DIR"
fi

# 验证Yosys
if "$INSTALL_DIR/yosys" -V &> /dev/null; then
    NEW_VERSION=$("$INSTALL_DIR/yosys" -V 2>&1 | head -1)
    echo "✓ Yosys安装成功！"
    echo "新版本: $NEW_VERSION"
    
    # 显示版本信息
    "$INSTALL_DIR/yosys" -V
else
    echo "❌ Yosys安装验证失败"
    exit 1
fi

cd -

echo ""
echo "=========================================="
echo "✓ Yosys安装完成！"
echo "=========================================="
echo ""
echo "安装位置: $INSTALL_DIR/yosys"
echo "源码位置: $BUILD_DIR"
echo ""
echo "请确保 $INSTALL_DIR 在PATH中，然后重新运行测试："
echo "  cd ~/chipmas"
echo "  bash scripts/run_step1_4_server.sh"

