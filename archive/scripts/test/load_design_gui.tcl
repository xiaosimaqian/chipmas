# OpenROAD GUI 加载设计脚本
# 使用方法: openroad -gui scripts/load_design_gui.tcl
#
# 功能：
# - 自动检测并加载 LEF、DEF 文件
# - 如果存在 Verilog 文件，也会加载并链接
# - 适用于大多数 OpenROAD 设计

# ============================================
# 配置：设置设计路径（可以根据需要修改）
# ============================================
set design_dir "data/ispd2015/mgc_pci_bridge32_a"

puts "正在加载设计: $design_dir"
puts ""

# ============================================
# 步骤1: 读取 LEF 文件（必需）
# ============================================
puts "1. 读取 LEF 文件..."
read_lef $design_dir/tech.lef
read_lef $design_dir/cells.lef
puts "   ✓ LEF 文件已读取"
puts ""

# ============================================
# 步骤2: 读取设计文件
# ============================================
puts "2. 读取设计文件..."

# 检查是否存在 Verilog 文件
set verilog_file "$design_dir/design.v"
if {[file exists $verilog_file]} {
    # 如果有 Verilog，先读取 Verilog，再读取 DEF，然后链接
    puts "   检测到 Verilog 文件，使用完整流程..."
    read_verilog $verilog_file
    read_def $design_dir/floorplan.def
    # 尝试链接设计（如果失败也不影响，因为 DEF 已包含信息）
    catch {
        link_design [db get topBlock getName]
        puts "   ✓ Verilog + DEF 已读取并链接"
    } {
        puts "   ✓ Verilog + DEF 已读取（链接步骤跳过）"
    }
} else {
    # 如果没有 Verilog，直接读取 DEF
    puts "   仅读取 DEF 文件..."
    read_def $design_dir/floorplan.def
    puts "   ✓ DEF 文件已读取"
}
puts ""

# ============================================
# 步骤3: 显示加载成功信息
# ============================================
puts "=========================================="
puts "✓ 设计已成功加载到 GUI！"
puts "=========================================="
puts ""
puts "GUI 操作提示："
puts "  - 使用鼠标滚轮缩放视图"
puts "  - 拖拽鼠标平移视图"
puts "  - 右键菜单查看更多选项"
puts "  - 在命令窗口可以执行 OpenROAD 命令"
puts ""
puts "常用命令示例："
puts "  report_hpwl          # 查看半周线长"
puts "  global_placement     # 执行全局布局"
puts "  detailed_placement   # 执行详细布局"
puts ""
