# OpenROAD TCL脚本 - Top Level (Boundary Nets Only)
# mgc_fft_1

# 读取所有LEF文件
read_lef /home/keqin/chipmas/data/ispd2015/mgc_fft_1/tech.lef
read_lef /home/keqin/chipmas/data/ispd2015/mgc_fft_1/cells.lef

# 读取顶层DEF（包含partition macros和boundary nets）
read_def /home/keqin/chipmas/tests/results/partition_flow/mgc_fft_1_step1_8/openroad/top_layout.def

# 注意：顶层DEF已经包含了所有必要信息（partition macros和boundary nets）
# 但DEF中没有定义rows，需要初始化floorplan来添加rows

# 初始化floorplan（添加placement rows）
# Die area: 0 0 5000 5000
# Core area: 250 250 4750 4750
initialize_floorplan -site core -die_area "0 0 5000 5000" -core_area "250 250 4750 4750"

# 全局布局（只优化boundary nets）
global_placement -skip_initial_place

# 详细布局
detailed_placement

# 写入DEF
write_def /home/keqin/chipmas/tests/results/partition_flow/mgc_fft_1_step1_8/openroad/top/top_layout.def

# HPWL信息会在detailed_placement的输出中自动报告
