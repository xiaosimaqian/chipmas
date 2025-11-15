#!/bin/bash
# 重新运行失败的设计（在服务器上）

SERVER="keqin@172.30.31.98"
REMOTE_DIR="~/chipmas"

# 失败的设计列表
FAILED_DESIGNS=(
    "mgc_fft_2"
    "mgc_fft_a"
    "mgc_fft_b"
    "mgc_matrix_mult_1"
    "mgc_matrix_mult_a"
    "mgc_matrix_mult_b"
    "mgc_pci_bridge32_a"
    "mgc_pci_bridge32_b"
    "mgc_superblue11_a"
    "mgc_superblue12"
    "mgc_superblue16_a"
)

echo "======================================"
echo "重新运行失败的设计"
echo "======================================"
echo ""
echo "失败设计数量: ${#FAILED_DESIGNS[@]}"
echo ""

# 1. 同步最新脚本到服务器
echo "📤 同步最新脚本到服务器..."
rsync -avz scripts/collect_clean_baseline.py $SERVER:$REMOTE_DIR/scripts/
if [ $? -ne 0 ]; then
    echo "❌ 同步失败"
    exit 1
fi
echo "✅ 同步完成"
echo ""

# 2. 在服务器上清理这些设计的旧结果
echo "🧹 清理旧结果..."
for design in "${FAILED_DESIGNS[@]}"; do
    echo "  清理: $design"
    ssh $SERVER "rm -rf $REMOTE_DIR/results/clean_baseline/$design" 2>/dev/null
done
echo "✅ 清理完成"
echo ""

# 3. 生成运行脚本
RUN_SCRIPT=$(cat <<'EOF'
#!/bin/bash
cd ~/chipmas

# 失败的设计列表
DESIGNS=(
    "mgc_fft_2"
    "mgc_fft_a"
    "mgc_fft_b"
    "mgc_matrix_mult_1"
    "mgc_matrix_mult_a"
    "mgc_matrix_mult_b"
    "mgc_pci_bridge32_a"
    "mgc_pci_bridge32_b"
    "mgc_superblue11_a"
    "mgc_superblue12"
    "mgc_superblue16_a"
)

echo "开始重新运行失败的设计..."
echo "时间: $(date)"
echo ""

# 逐个运行
for design in "${DESIGNS[@]}"; do
    echo "[$design] 开始运行..."
    python3 scripts/collect_clean_baseline.py --design $design --output-dir results/clean_baseline
    
    if [ $? -eq 0 ]; then
        echo "[$design] ✅ 完成"
    else
        echo "[$design] ❌ 失败"
    fi
    echo ""
done

echo "所有设计运行完成"
echo "时间: $(date)"
EOF
)

# 4. 上传并执行
echo "🚀 启动重新运行..."
ssh $SERVER "cat > $REMOTE_DIR/rerun_failed.sh << 'EOFSCRIPT'
$RUN_SCRIPT
EOFSCRIPT
chmod +x $REMOTE_DIR/rerun_failed.sh
nohup $REMOTE_DIR/rerun_failed.sh > $REMOTE_DIR/results/rerun_failed.log 2>&1 &
echo \$!"

echo ""
echo "======================================"
echo "✅ 重新运行已启动"
echo "======================================"
echo ""
echo "监控命令:"
echo "  tail -f $REMOTE_DIR/results/rerun_failed.log"
echo "  或者在本地运行:"
echo "  ssh $SERVER 'tail -f $REMOTE_DIR/results/rerun_failed.log'"

