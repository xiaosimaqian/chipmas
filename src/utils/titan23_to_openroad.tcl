# OpenROAD 综合和布局脚本 - 用于 titan23 设计
# 使用 nangate45 工艺
#
# 使用方法:
#   openroad -exit scripts/titan23_to_openroad.tcl \
#     -design <设计名称> \
#     -verilog <verilog文件路径> \
#     -output_dir <输出目录>

# ============================================
# 参数设置
# ============================================
# 从命令行参数获取
if {[info exists ::env(DESIGN)]} {
    set design $::env(DESIGN)
} else {
    puts "错误: 请设置环境变量 DESIGN"
    exit 1
}

if {[info exists ::env(VERILOG_FILE)]} {
    set synth_verilog $::env(VERILOG_FILE)
} else {
    puts "错误: 请设置环境变量 VERILOG_FILE"
    exit 1
}

if {[info exists ::env(OUTPUT_DIR)]} {
    set output_dir $::env(OUTPUT_DIR)
} else {
    set output_dir "results/${design}_nangate45"
}

# 创建输出目录
file mkdir $output_dir

# ============================================
# 工艺文件路径设置
# ============================================
# 假设 OpenROAD-flow-scripts 在标准位置
# 如果不在，请修改这些路径
set openroad_flow_scripts "/Users/keqin/Documents/workspace/openroad/OpenROAD-flow-scripts"
set nangate45_dir "$openroad_flow_scripts/tools/OpenROAD/test/Nangate45"

# 检查路径是否存在
if {![file exists $nangate45_dir]} {
    puts "错误: 找不到 nangate45 工艺文件目录: $nangate45_dir"
    puts "请修改脚本中的 openroad_flow_scripts 路径"
    exit 1
}

# 工艺文件
set tech_lef "$nangate45_dir/Nangate45_tech.lef"
set std_cell_lef "$nangate45_dir/Nangate45_stdcell.lef"
set liberty_file "$nangate45_dir/Nangate45_typ.lib"
set site "FreePDK45_38x28_10R_NP_162NW_34O"
set pdn_cfg "$nangate45_dir/Nangate45.pdn.tcl"
set tracks_file "$nangate45_dir/Nangate45.tracks"
set layer_rc_file "$nangate45_dir/Nangate45.rc"
set rcx_rules_file "$nangate45_dir/Nangate45.rcx_rules"

# ============================================
# 设计参数（可以根据设计调整）
# ============================================
# 从 Verilog 文件中提取顶层模块名
# 读取 Verilog 文件的第一行 module 声明
set top_module ""
if {[file exists $synth_verilog]} {
    set fp [open $synth_verilog r]
    while {[gets $fp line] >= 0} {
        if {[regexp {^\s*module\s+(\w+)} $line match module_name]} {
            set top_module $module_name
            break
        }
    }
    close $fp
}

# 如果无法提取，使用设计名称作为后备
if {$top_module == ""} {
    puts "警告: 无法从 Verilog 文件中提取顶层模块名，使用设计名称: $design"
    set top_module $design
} else {
    puts "检测到顶层模块名: $top_module"
}

# Die area 和 core area（需要根据设计规模调整）
# 这里使用默认值，实际应该根据设计规模计算
set die_area {0 0 1000 1000}
set core_area {50 50 950 950}

# ============================================
# 读取工艺库
# ============================================
puts "读取工艺库文件..."
read_lef $tech_lef
read_lef $std_cell_lef
read_liberty $liberty_file

# ============================================
# 读取设计
# ============================================
puts "读取 Verilog 文件: $synth_verilog"
read_verilog $synth_verilog
link_design $top_module

# ============================================
# 创建 SDC 文件（如果没有提供）
# ============================================
set sdc_file "$output_dir/${design}.sdc"
if {![file exists $sdc_file]} {
    # 创建基本的 SDC 文件
    set sdc_fp [open $sdc_file w]
    puts $sdc_fp "create_clock -period 10.0 -name clk \[get_ports clk\]"
    puts $sdc_fp "set_propagated_clock \[get_clocks clk\]"
    close $sdc_fp
    puts "创建默认 SDC 文件: $sdc_file"
}
read_sdc $sdc_file

# ============================================
# Floorplan
# ============================================
puts "初始化 Floorplan..."
initialize_floorplan -site $site \
    -die_area $die_area \
    -core_area $core_area

source $tracks_file

# ============================================
# Tapcell 插入
# ============================================
puts "插入 Tapcell..."
tapcell -distance 120 \
    -tapcell_master TAPCELL_X1 \
    -endcap_master TAPCELL_X1

# ============================================
# Power Distribution Network
# ============================================
puts "生成电源网络..."
source $pdn_cfg
pdngen

# ============================================
# Placement
# ============================================
puts "执行全局布局..."
set_routing_layers -signal metal2-metal10 -clock metal6-metal10
global_placement -density 0.3 -pad_left 2 -pad_right 2 -skip_io

puts "放置 IO..."
place_pins -hor_layers metal3 -ver_layers metal2

puts "执行可路由性驱动的全局布局..."
global_placement -routability_driven -density 0.3 \
    -pad_left 2 -pad_right 2

puts "执行详细布局..."
detailed_placement

# ============================================
# 输出结果
# ============================================
puts "写入结果文件..."
write_def "$output_dir/${design}.def"
write_verilog "$output_dir/${design}.v"
write_sdc "$output_dir/${design}.sdc"

# HPWL 信息已在 detailed placement 过程中输出
# 如果需要计算 HPWL，可以从 DEF 文件中解析或使用其他方法

puts ""
puts "=========================================="
puts "✓ 综合和布局完成！"
puts "输出目录: $output_dir"
puts "=========================================="

