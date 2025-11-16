#!/bin/bash
# 在服务器上安装Yosys

set -e

echo "=========================================="
echo "在服务器上安装Yosys"
echo "=========================================="

# 检查Yosys是否已安装
if command -v yosys &> /dev/null; then
    echo "✓ Yosys已安装"
    yosys -V
    exit 0
fi

echo "Yosys未安装，开始安装..."

# 检测Linux发行版
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu
    echo "检测到Debian/Ubuntu系统"
    
    # 检查是否有sudo权限
    if sudo -n true 2>/dev/null; then
        echo "有sudo权限，使用apt安装..."
        # 更新包列表
        sudo apt-get update
        
        # 安装Yosys
        sudo apt-get install -y yosys
    else
        echo "⚠️  需要sudo权限，尝试从源码编译（不需要sudo）..."
        
        # 检查依赖
        if ! command -v git &> /dev/null; then
            echo "❌ git未安装，无法从源码编译"
            echo "请手动安装Yosys："
            echo "  sudo apt-get update && sudo apt-get install -y yosys"
            exit 1
        fi
        
        if ! command -v make &> /dev/null; then
            echo "❌ make未安装，无法从源码编译"
            echo "请手动安装Yosys："
            echo "  sudo apt-get update && sudo apt-get install -y yosys"
            exit 1
        fi
        
        # 从源码编译
        BUILD_DIR="$HOME/yosys_build"
        if [ ! -d "$BUILD_DIR" ]; then
            echo "克隆Yosys源码到 $BUILD_DIR..."
            git clone https://github.com/YosysHQ/yosys.git "$BUILD_DIR"
        fi
        
        cd "$BUILD_DIR"
        
        # 初始化git submodules
        echo "初始化git submodules..."
        git submodule update --init --recursive
        
        # 检查并安装依赖（如果可能）
        echo "检查编译依赖..."
        MISSING_DEPS=""
        if ! pkg-config --exists readline 2>/dev/null; then
            MISSING_DEPS="$MISSING_DEPS libreadline-dev"
        fi
        
        if [ -n "$MISSING_DEPS" ]; then
            echo "⚠️  缺少依赖: $MISSING_DEPS"
            echo "请手动安装（需要sudo权限）："
            echo "  sudo apt-get install -y $MISSING_DEPS"
            echo ""
            echo "或者尝试继续编译（可能会失败）..."
            read -t 5 -p "等待5秒后继续..." || true
        fi
        
        echo "编译Yosys（这可能需要10-20分钟）..."
        make config-gcc
        make -j$(nproc)
        
        # 添加到PATH
        YOSYS_BIN="$BUILD_DIR/yosys"
        if [ -f "$YOSYS_BIN" ]; then
            echo "✓ Yosys编译成功: $YOSYS_BIN"
            # 创建符号链接到 ~/.local/bin（如果存在）
            if [ -d "$HOME/.local/bin" ]; then
                ln -sf "$YOSYS_BIN" "$HOME/.local/bin/yosys"
                echo "✓ 已创建符号链接: ~/.local/bin/yosys"
            else
                echo "⚠️  请将以下路径添加到PATH："
                echo "  export PATH=\$PATH:$BUILD_DIR"
            fi
        else
            echo "❌ Yosys编译失败"
            exit 1
        fi
        
        cd -
    fi
    
elif [ -f /etc/redhat-release ]; then
    # RHEL/CentOS/Fedora
    echo "检测到RHEL/CentOS/Fedora系统"
    
    # 对于Fedora
    if command -v dnf &> /dev/null; then
        sudo dnf install -y yosys
    # 对于CentOS/RHEL
    elif command -v yum &> /dev/null; then
        sudo yum install -y yosys
    fi
    
else
    echo "未识别的Linux发行版，尝试从源码编译..."
    
    # 检查依赖
    if ! command -v git &> /dev/null; then
        echo "安装git..."
        sudo apt-get update && sudo apt-get install -y git || sudo yum install -y git
    fi
    
    if ! command -v make &> /dev/null; then
        echo "安装build-essential..."
        sudo apt-get update && sudo apt-get install -y build-essential || sudo yum groupinstall -y "Development Tools"
    fi
    
    # 克隆Yosys源码
    cd /tmp
    if [ ! -d "yosys" ]; then
        git clone https://github.com/YosysHQ/yosys.git
    fi
    
    cd yosys
    make config-gcc
    make -j$(nproc)
    sudo make install
    
    cd -
fi

# 验证安装
if command -v yosys &> /dev/null; then
    echo ""
    echo "=========================================="
    echo "✓ Yosys安装成功！"
    echo "=========================================="
    yosys -V
else
    echo "❌ Yosys安装失败"
    exit 1
fi

