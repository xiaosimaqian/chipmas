#!/bin/bash
###############################################################################
# K-SpecPart环境安装脚本
# 
# 功能：
#   1. 克隆K-SpecPart仓库
#   2. 安装Julia环境
#   3. 安装Julia依赖包
#
# 使用方法：
#   bash scripts/setup_kspecpart.sh
###############################################################################

set -e  # 遇到错误立即退出

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KSPECPART_DIR="$PROJECT_ROOT/external/HypergraphPartitioning"

echo "=========================================="
echo "K-SpecPart环境安装"
echo "=========================================="
echo ""

# 步骤1: 检查Julia是否已安装
echo "[1/4] 检查Julia环境..."
if command -v julia &> /dev/null; then
    JULIA_VERSION=$(julia --version)
    echo "  ✓ Julia已安装: $JULIA_VERSION"
else
    echo "  ✗ Julia未安装"
    echo ""
    echo "请先安装Julia (>= 1.6):"
    echo "  macOS:   brew install julia"
    echo "  Linux:   https://julialang.org/downloads/"
    echo ""
    exit 1
fi

# 步骤2: 克隆K-SpecPart仓库
echo ""
echo "[2/4] 克隆K-SpecPart仓库..."
if [ -d "$KSPECPART_DIR" ]; then
    echo "  ⚠️  目录已存在: $KSPECPART_DIR"
    read -p "  是否重新克隆? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$KSPECPART_DIR"
    else
        echo "  跳过克隆步骤"
    fi
fi

if [ ! -d "$KSPECPART_DIR" ]; then
    mkdir -p "$(dirname "$KSPECPART_DIR")"
    echo "  正在克隆..."
    git clone https://github.com/TILOS-AI-Institute/HypergraphPartitioning.git "$KSPECPART_DIR"
    echo "  ✓ 克隆完成: $KSPECPART_DIR"
else
    echo "  ✓ 使用现有仓库"
fi

# 步骤3: 安装Julia依赖
echo ""
echo "[3/4] 安装Julia依赖..."
cd "$KSPECPART_DIR/K_SpecPart"

if [ -f "Project.toml" ]; then
    echo "  正在安装Julia包..."
    julia --project=. -e 'using Pkg; Pkg.instantiate()'
    echo "  ✓ Julia依赖安装完成"
else
    echo "  ⚠️  未找到Project.toml，跳过依赖安装"
fi

# 步骤4: 测试K-SpecPart
echo ""
echo "[4/4] 测试K-SpecPart..."
cd "$KSPECPART_DIR/K_SpecPart"

# 检查是否有示例文件
if [ -d "../benchmark" ]; then
    SAMPLE_HGR=$(find ../benchmark -name "*.hgr" | head -1)
    if [ -n "$SAMPLE_HGR" ]; then
        echo "  使用示例文件测试: $(basename $SAMPLE_HGR)"
        echo "  运行命令: julia run_kspecpart.jl $SAMPLE_HGR 2 0.05 /tmp/test.part.2"
        
        # 测试运行（如果失败不退出脚本）
        julia run_kspecpart.jl "$SAMPLE_HGR" 2 0.05 /tmp/test.part.2 || true
        
        if [ -f "/tmp/test.part.2" ]; then
            echo "  ✓ K-SpecPart测试成功！"
            rm /tmp/test.part.2
        else
            echo "  ⚠️  测试运行但未生成输出文件"
        fi
    else
        echo "  ⚠️  未找到示例.hgr文件，跳过测试"
    fi
else
    echo "  ⚠️  未找到benchmark目录，跳过测试"
fi

echo ""
echo "=========================================="
echo "✓ K-SpecPart环境安装完成！"
echo "=========================================="
echo ""
echo "K-SpecPart位置: $KSPECPART_DIR/K_SpecPart"
echo ""
echo "使用方法:"
echo "  1. 转换ISPD 2015为HGR格式:"
echo "     python scripts/convert_ispd2015_to_hgr.py \\"
echo "       --def-file data/ispd2015/mgc_fft_1/floorplan.def \\"
echo "       --output results/kspecpart/mgc_fft_1.hgr \\"
echo "       --mapping results/kspecpart/mgc_fft_1.mapping.json"
echo ""
echo "  2. 运行K-SpecPart分区:"
echo "     cd $KSPECPART_DIR/K_SpecPart"
echo "     julia run_kspecpart.jl \\"
echo "       ../../results/kspecpart/mgc_fft_1.hgr \\"
echo "       4 0.05 \\"
echo "       ../../results/kspecpart/mgc_fft_1.part.4"
echo ""

