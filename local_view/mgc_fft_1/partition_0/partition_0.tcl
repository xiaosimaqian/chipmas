# OpenROAD TCL脚本 - Partition 0
# mgc_fft_1

# 读取LEF文件
read_lef /home/keqin/chipmas/data/ispd2015/mgc_fft_1/tech.lef
read_lef /home/keqin/chipmas/data/ispd2015/mgc_fft_1/cells.lef

# 读取Verilog网表
read_verilog /home/keqin/chipmas/tests/results/partition_flow/mgc_fft_1_step1_8/hierarchical_netlists/partition_0.v

# 链接设计
link_design partition_0

# 初始化Floorplan
initialize_floorplan -die_area "0 0 2500 2500" -core_area "250 250 2250 2250" -site core

# 生成tracks
make_tracks

# 放置引脚（指定水平层和垂直层）
place_pins -random -hor_layers metal3 -ver_layers metal2

# 全局布局
global_placement -skip_initial_place

# 详细布局
detailed_placement

# 写入DEF
write_def /home/keqin/chipmas/tests/results/partition_flow/mgc_fft_1_step1_8/openroad/partition_0/partition_0_layout.def

# HPWL信息会在detailed_placement的输出中自动报告
