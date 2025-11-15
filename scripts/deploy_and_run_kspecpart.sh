#!/bin/bash
# 部署K-SpecPart到服务器并运行实验

# 服务器配置
SERVER="keqin@10.10.10.11"
REMOTE_DIR="~/chipmas"

echo "=========================================="
echo "部署K-SpecPart到服务器"
echo "=========================================="

# 1. 同步代码
echo ""
echo "[1/4] 同步代码到服务器..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='results/' \
    --exclude='data/datasets/' \
    --exclude='.DS_Store' \
    scripts/ ${SERVER}:${REMOTE_DIR}/scripts/

rsync -avz --progress \
    src/ ${SERVER}:${REMOTE_DIR}/src/

rsync -avz --progress \
    configs/ ${SERVER}:${REMOTE_DIR}/configs/

echo "✓ 代码同步完成"

# 2. 检查服务器环境
echo ""
echo "[2/4] 检查服务器环境..."
ssh ${SERVER} "cd ${REMOTE_DIR} && bash scripts/setup_kspecpart_server.sh"

# 3. 部署数据
echo ""
echo "[3/4] 准备实验数据..."
echo "注意：ISPD 2015数据已在服务器上 (~/chipmas/data/ispd2015/)"

# 4. 运行实验
echo ""
echo "[4/4] 启动K-SpecPart实验..."

# 创建实验启动脚本
cat > /tmp/run_kspecpart_batch.sh << 'BATCH_EOF'
#!/bin/bash
cd ~/chipmas

# 小设计列表（按规模排序）
DESIGNS=(
    "mgc_fft_1"
    "mgc_fft_2" 
    "mgc_pci_bridge32_a"
    "mgc_pci_bridge32_b"
)

# 逐个运行
for design in "${DESIGNS[@]}"; do
    echo ""
    echo "=========================================="
    echo "运行 K-SpecPart: $design"
    echo "=========================================="
    
    python3 scripts/run_kspecpart_experiment.py \
        --design "$design" \
        --partitions 4 \
        --balance 0.05 \
        2>&1 | tee "results/kspecpart/${design}/${design}_experiment.log"
    
    if [ $? -eq 0 ]; then
        echo "✓ $design 完成"
    else
        echo "❌ $design 失败"
    fi
done

echo ""
echo "=========================================="
echo "所有K-SpecPart实验完成！"
echo "=========================================="
BATCH_EOF

# 上传并执行
scp /tmp/run_kspecpart_batch.sh ${SERVER}:${REMOTE_DIR}/scripts/
ssh ${SERVER} "cd ${REMOTE_DIR} && nohup bash scripts/run_kspecpart_batch.sh > kspecpart_batch.log 2>&1 &"

echo ""
echo "=========================================="
echo "✓ K-SpecPart实验已在服务器后台启动"
echo "=========================================="
echo ""
echo "查看进度:"
echo "  ssh ${SERVER} 'tail -f ~/chipmas/kspecpart_batch.log'"
echo ""
echo "查看结果:"
echo "  ssh ${SERVER} 'ls -lh ~/chipmas/results/kspecpart/*/'"
echo ""
