# 测试加载设计脚本（非GUI模式）
set design_dir "data/ispd2015/mgc_pci_bridge32_a"

puts "开始加载设计..."
puts "设计目录: $design_dir"

# 读取LEF文件
puts "\n1. 读取 LEF 文件..."
read_lef $design_dir/tech.lef
puts "  ✓ tech.lef 已读取"

read_lef $design_dir/cells.lef
puts "  ✓ cells.lef 已读取"

# 读取DEF文件
puts "\n2. 读取 DEF 文件..."
if {[file exists $design_dir/design.v]} {
    read_verilog $design_dir/design.v
    read_def $design_dir/floorplan.def
    set design_name [get_design]
    link_design $design_name
    puts "  ✓ Verilog + DEF 已读取并链接"
} else {
    read_def $design_dir/floorplan.def
    puts "  ✓ DEF 已读取"
}

# 显示设计信息
puts "\n3. 设计信息："
set design_name [get_design]
puts "  设计名称: $design_name"

catch {
    set die_area [get_die_area]
    puts "  Die 面积: $die_area"
}

catch {
    set num_cells [llength [get_cells -hierarchical]]
    puts "  单元数量: $num_cells"
}

puts "\n=========================================="
puts "✓ 设计加载成功！"
puts "=========================================="
