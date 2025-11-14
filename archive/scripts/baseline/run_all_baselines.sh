#!/bin/bash
# 批量运行所有ISPD 2015设计的基线实验
# 按设计规模从小到大依次运行，充分利用服务器资源

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 配置
DATA_DIR="data/ispd2015"
OUTPUT_DIR="results/baseline"
SEED=42
LOG_DIR="results/baseline_logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建日志目录
mkdir -p "$LOG_DIR"

# 定义设计列表（按规模从小到大排序，根据组件数量估算）
# 注意：实际规模需要根据DEF文件中的组件数量确定
DESIGNS=(
    "mgc_edit_dist_a"           # 较小
    "mgc_fft_1"                 # 较小
    "mgc_fft_2"                 # 较小
    "mgc_matrix_mult_1"         # 较小
    "mgc_des_perf_1"            # 中等
    "mgc_fft_a"                 # 中等
    "mgc_fft_b"                 # 中等
    "mgc_matrix_mult_a"         # 中等
    "mgc_des_perf_a"            # 中等
    "mgc_des_perf_b"            # 中等
    "mgc_matrix_mult_b"         # 中等
    "mgc_pci_bridge32_a"        # 较大
    "mgc_pci_bridge32_b"        # 较大
    "mgc_superblue11_a"         # 大
    "mgc_superblue12"           # 大
    "mgc_superblue16_a"         # 最大
)

echo "=========================================="
echo "ISPD 2015 基线实验批量运行"
echo "=========================================="
echo "开始时间: $(date)"
echo "设计数量: ${#DESIGNS[@]}"
echo "输出目录: $OUTPUT_DIR"
echo "日志目录: $LOG_DIR"
echo "=========================================="

# 运行Python脚本
python3 scripts/run_baseline_experiments.py \
    --designs "${DESIGNS[@]}" \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --seed "$SEED" \
    --skip-existing \
    2>&1 | tee "$LOG_DIR/baseline_run_${TIMESTAMP}.log"

echo ""
echo "=========================================="
echo "实验完成"
echo "结束时间: $(date)"
echo "日志文件: $LOG_DIR/baseline_run_${TIMESTAMP}.log"
echo "=========================================="


