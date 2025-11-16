# OpenROAD GUI Script - View mgc_fft_1 Layout
# 用于在本地查看完整的partition-based布局

puts "=========================================="
puts "Loading mgc_fft_1 Partition-based Layout"
puts "=========================================="

# 读取LEF文件
puts "\n1. Reading LEF files..."
read_lef tech.lef
read_lef cells.lef

# 选择要查看的布局：
# 1. 查看某个partition的详细布局（例如partition_0）
# 2. 查看顶层布局（top_layout.def，包含所有partition macros）

puts "\n2. Select which layout to view:"
puts "   [a] Top-level layout (all partitions as macros)"
puts "   [b] Partition 0 detailed layout"
puts "   [c] Partition 1 detailed layout"
puts "   [d] Partition 2 detailed layout"
puts "   [e] Partition 3 detailed layout"

# 默认加载顶层布局
puts "\nLoading TOP-LEVEL layout by default..."
puts "   To view a specific partition, edit this script and uncomment the desired read_def line.\n"

# 顶层布局（显示4个partition macros + boundary nets）
read_def top/top_layout.def

# 或者查看某个partition的详细布局：
# read_def partition_0/partition_0_layout.def
# read_def partition_1/partition_1_layout.def
# read_def partition_2/partition_2_layout.def
# read_def partition_3/partition_3_layout.def

puts "\n=========================================="
puts "Layout loaded successfully!"
puts "=========================================="
puts "\nGUI Commands:"
puts "  - Zoom: Mouse wheel or Z key"
puts "  - Pan: Right-click drag"
puts "  - Fit: F key"
puts "  - Select: Left-click"
puts "  - Measure: M key"
puts "\nLayout Information:"
puts "  - Design: mgc_fft_1"
puts "  - Total instances: 32,281"
puts "  - Partitions: 4"
puts "  - Boundary HPWL: 4.4 um"
puts "  - Internal HPWL: 6.78M um"
puts "  - Boundary Cost: ~0.00%"
puts "\n=========================================="

