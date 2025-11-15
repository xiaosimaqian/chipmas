#!/bin/bash
###############################################################################
# K-SpecPart完整依赖安装脚本
# 
# 依赖列表:
#   1. METIS - 图分区器
#   2. hMETIS - 超图分区器（初始hint）
#   3. OR-Tools - ILP求解器（或CPLEX）
#   4. FM refinement - TritonPart
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS_DIR="$PROJECT_ROOT/external/deps"

echo "=========================================="
echo "K-SpecPart依赖安装"
echo "=========================================="
echo ""

mkdir -p "$DEPS_DIR"
cd "$DEPS_DIR"

# 依赖1: METIS
echo "[1/4] 安装METIS..."
if command -v gpmetis &> /dev/null; then
    echo "  ✓ METIS已安装"
    gpmetis --help 2>&1 | head -2 || true
else
    echo "  正在安装METIS..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install metis
        echo "  ✓ METIS安装完成"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux安装
        if [ ! -d "metis-5.1.0" ]; then
            wget http://glaros.dtc.umn.edu/gkhome/fetch/sw/metis/metis-5.1.0.tar.gz
            tar -xzf metis-5.1.0.tar.gz
            cd metis-5.1.0
            make config
            make
            sudo make install
            cd ..
            echo "  ✓ METIS安装完成"
        fi
    fi
fi

# 依赖2: hMETIS
echo ""
echo "[2/4] 安装hMETIS..."
echo "  ⚠️  hMETIS需要从官网手动下载"
echo "  官网: http://glaros.dtc.umn.edu/gkhome/metis/hmetis/download"
echo ""
echo "  下载后请执行:"
echo "    tar -xzf hmetis-1.5-*.tar.gz"
echo "    cd hmetis-1.5-*"
echo "    # 将khmetis复制到PATH中"
echo ""

if command -v khmetis &> /dev/null; then
    echo "  ✓ hMETIS已安装"
    khmetis 2>&1 | head -3 || true
else
    echo "  ⚠️  hMETIS未安装"
    echo "  提示: K-SpecPart可以不使用hMETIS的hint运行（性能可能略差）"
fi

# 依赖3: OR-Tools
echo ""
echo "[3/4] 安装OR-Tools..."
if python3 -c "import ortools" 2>/dev/null; then
    echo "  ✓ OR-Tools (Python)已安装"
else
    echo "  正在安装OR-Tools..."
    pip3 install ortools
    echo "  ✓ OR-Tools安装完成"
fi

# 编译ILP partitioner
echo ""
echo "  编译ILP partitioner..."
ILP_DIR="$PROJECT_ROOT/external/HypergraphPartitioning/K_SpecPart/ilp_partitioner"
if [ -d "$ILP_DIR" ]; then
    cd "$ILP_DIR"
    if [ -d "build" ]; then
        rm -rf build
    fi
    mkdir -p build
    cd build
    
    # 检查CMake
    if command -v cmake &> /dev/null; then
        echo "  正在编译..."
        cmake .. || echo "  ⚠️  CMake配置失败"
        make || echo "  ⚠️  编译失败"
        
        if [ -f "ilp_partition" ]; then
            echo "  ✓ ILP partitioner编译完成"
        else
            echo "  ⚠️  ILP partitioner未生成"
        fi
    else
        echo "  ⚠️  CMake未安装，跳过ILP partitioner编译"
        echo "  安装CMake: brew install cmake (macOS) 或 apt install cmake (Linux)"
    fi
fi

# 依赖4: TritonPart (FM refinement)
echo ""
echo "[4/4] TritonPart (FM refinement)..."
TRITONPART_DIR="$PROJECT_ROOT/external/HypergraphPartitioning/TritonPart-agent"
if [ -d "$TRITONPART_DIR" ]; then
    echo "  ✓ TritonPart代码已包含在仓库中"
else
    echo "  ⚠️  TritonPart目录未找到"
fi

echo ""
echo "=========================================="
echo "依赖安装完成！"
echo "=========================================="
echo ""
echo "已安装依赖:"
command -v gpmetis &> /dev/null && echo "  ✓ METIS" || echo "  ✗ METIS"
command -v khmetis &> /dev/null && echo "  ✓ hMETIS" || echo "  ✗ hMETIS (可选)"
python3 -c "import ortools" 2>/dev/null && echo "  ✓ OR-Tools" || echo "  ✗ OR-Tools"
[ -f "$PROJECT_ROOT/external/HypergraphPartitioning/K_SpecPart/ilp_partitioner/build/ilp_partition" ] && echo "  ✓ ILP partitioner" || echo "  ⚠️  ILP partitioner"
echo ""
echo "K-SpecPart准备就绪！"
echo ""
