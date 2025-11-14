# OpenROAD GUI 加载 titan23 设计布局结果
# 使用方法: openroad -gui scripts/load_titan23_gui.tcl
#
# 环境变量:
#   DESIGN: 设计名称（默认: des90）
#   OUTPUT_DIR: 输出目录（默认: results/${DESIGN}_nangate45）

# ============================================
# 参数设置
# ============================================
if {[info exists ::env(DESIGN)]} {
    set design $::env(DESIGN)
} else {
    set design "des90"
}

if {[info exists ::env(OUTPUT_DIR)]} {
    set output_dir $::env(OUTPUT_DIR)
} else {
    set output_dir "results/${design}_nangate45"
}

puts "正在加载 titan23 设计布局: $design"
puts "输出目录: $output_dir"
puts ""

# ============================================
# 工艺文件路径设置
# ============================================
set openroad_flow_scripts "/Users/keqin/Documents/workspace/openroad/OpenROAD-flow-scripts"
set nangate45_dir "$openroad_flow_scripts/tools/OpenROAD/test/Nangate45"

# 工艺文件
set tech_lef "$nangate45_dir/Nangate45_tech.lef"
set std_cell_lef "$nangate45_dir/Nangate45_stdcell.lef"

# ============================================
# 读取工艺库
# ============================================
puts "1. 读取工艺库文件..."
read_lef $tech_lef
read_lef $std_cell_lef
puts "   ✓ LEF 文件已读取"
puts ""

# ============================================
# 读取布局结果
# ============================================
set def_file "$output_dir/${design}.def"
set verilog_file "$output_dir/${design}.v"

if {![file exists $def_file]} {
    puts "错误: 找不到 DEF 文件: $def_file"
    puts "请先运行: ./scripts/run_titan23_openroad.sh $design"
    exit 1
}

puts "2. 读取布局结果..."
puts "   DEF 文件: $def_file"
read_def $def_file
puts "   ✓ DEF 文件已读取"
puts ""

# 如果存在 Verilog 文件，也可以读取（可选）
if {[file exists $verilog_file]} {
    puts "3. 读取 Verilog 文件（可选）..."
    read_verilog $verilog_file
    puts "   ✓ Verilog 文件已读取"
    puts ""
}

# ============================================
# 显示设计信息
# ============================================
puts "=========================================="
puts "✓ 设计已成功加载到 GUI！"
puts "=========================================="
puts ""
puts "设计信息："
catch {
    set db [::ord::get_db]
    set chip [$db getChip]
    set block [$chip getBlock]
    set design_name [$block getName]
    puts "  设计名称: $design_name"
    
    set die_area [$block getDieArea]
    puts "  Die 面积: $die_area"
    
    set num_insts [llength [$block getInsts]]
    puts "  实例数量: $num_insts"
    
    set num_nets [llength [$block getNets]]
    puts "  网络数量: $num_nets"
}

puts ""
puts "GUI 操作提示："
puts "  - 使用鼠标滚轮缩放视图"
puts "  - 拖拽鼠标平移视图"
puts "  - 右键菜单查看更多选项"
puts "  - 在命令窗口可以执行 OpenROAD 命令"
puts ""
puts "常用命令："
puts "  report_hpwl          # 查看 HPWL（如果可用）"
puts "  fit                  # 调整视图以适应设计"
puts ""

