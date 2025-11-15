#!/bin/bash
# K-SpecPart服务器安装脚本 (Linux)
# 在服务器上运行: bash scripts/setup_kspecpart_server.sh

set -e

echo "=========================================="
echo "K-SpecPart 服务器安装"
echo "=========================================="

# 1. 检查Julia
echo ""
echo "1. 检查Julia..."
if command -v julia &> /dev/null; then
    julia --version
else
    echo "❌ Julia未安装，请先安装Julia 1.6+"
    echo "   wget https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz"
    echo "   tar -xzf julia-1.9.4-linux-x86_64.tar.gz"
    echo "   export PATH=\"\$PWD/julia-1.9.4/bin:\$PATH\""
    exit 1
fi

# 2. 克隆K-SpecPart (如果不存在)
echo ""
echo "2. 准备K-SpecPart..."
if [ ! -d "external/HypergraphPartitioning" ]; then
    mkdir -p external
    cd external
    git clone https://github.com/TILOS-AI-Institute/HypergraphPartitioning.git
    cd ..
fi

# 3. 安装Julia依赖
echo ""
echo "3. 安装Julia依赖包..."
cd external/HypergraphPartitioning/K_SpecPart
julia --project -e 'using Pkg; Pkg.instantiate(); Pkg.build()'

# 4. 安装METIS
echo ""
echo "4. 安装METIS..."
if ! command -v gpmetis &> /dev/null; then
    cd ~/
    wget http://glaros.dtc.umn.edu/gkhome/fetch/sw/metis/metis-5.1.0.tar.gz
    tar -xzf metis-5.1.0.tar.gz
    cd metis-5.1.0
    make config prefix=~/.local
    make install
    export PATH="$HOME/.local/bin:$PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    cd ~/chipmas
else
    echo "✓ METIS已安装: $(which gpmetis)"
fi

# 5. 安装hMETIS
echo ""
echo "5. 安装hMETIS..."
if ! command -v khmetis &> /dev/null; then
    cd ~/
    wget http://glaros.dtc.umn.edu/gkhome/fetch/sw/hmetis/hmetis-1.5-linux.tar.gz
    tar -xzf hmetis-1.5-linux.tar.gz
    mkdir -p ~/.local/bin
    cp hmetis-1.5-linux/khmetis hmetis-1.5-linux/hmetis hmetis-1.5-linux/shmetis ~/.local/bin/
    chmod +x ~/.local/bin/*metis
    export PATH="$HOME/.local/bin:$PATH"
    cd ~/chipmas
else
    echo "✓ hMETIS已安装: $(which khmetis)"
fi

# 6. 测试K-SpecPart
echo ""
echo "6. 测试K-SpecPart..."
cd external/HypergraphPartitioning/K_SpecPart
julia --project -e 'include("specpart.jl"); println("✓ K-SpecPart加载成功")'

echo ""
echo "=========================================="
echo "✓ K-SpecPart安装完成！"
echo "=========================================="
echo ""
echo "下一步:"
echo "1. 转换ISPD设计为HGR格式:"
echo "   python3 scripts/convert_ispd2015_to_hgr.py --def-file data/ispd2015/mgc_fft_1/floorplan.def --output results/kspecpart/mgc_fft_1.hgr"
echo ""
echo "2. 运行K-SpecPart:"
echo "   cd external/HypergraphPartitioning/K_SpecPart"
echo "   julia --project -e 'include(\"specpart.jl\"); main()' -- ../../results/kspecpart/mgc_fft_1.hgr 4 0.05"
echo ""
