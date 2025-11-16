# 本地查看 mgc_fft_1 布局

## 📁 文件说明

本目录包含从服务器下载的完整OpenROAD布局结果：

```
local_view/mgc_fft_1/
├── tech.lef              # 工艺LEF文件
├── cells.lef             # 标准单元LEF文件
├── view_layout.tcl       # OpenROAD GUI查看脚本
├── top/
│   ├── top_layout.def    # 顶层布局（4个partition macros）
│   └── ...
├── partition_0/
│   ├── partition_0_layout.def  # Partition 0详细布局
│   └── ...
├── partition_1/
│   ├── partition_1_layout.def  # Partition 1详细布局
│   └── ...
├── partition_2/
│   ├── partition_2_layout.def  # Partition 2详细布局
│   └── ...
└── partition_3/
    ├── partition_3_layout.def  # Partition 3详细布局
    └── ...
```

## 🖥️ 使用OpenROAD GUI查看布局

### 方法1：使用提供的TCL脚本（推荐）

```bash
cd /Users/keqin/Documents/workspace/chip-rag/chipmas/local_view/mgc_fft_1
openroad -gui view_layout.tcl
```

**默认查看**：顶层布局（显示4个partition macros + boundary nets）

**查看特定partition**：编辑`view_layout.tcl`，注释掉顶层DEF行，取消注释想查看的partition行：

```tcl
# 注释掉这行：
# read_def top/top_layout.def

# 取消注释想查看的partition：
read_def partition_0/partition_0_layout.def
```

### 方法2：手动命令

```bash
cd /Users/keqin/Documents/workspace/chip-rag/chipmas/local_view/mgc_fft_1
openroad -gui
```

在OpenROAD GUI中执行：

```tcl
# 读取LEF
read_lef tech.lef
read_lef cells.lef

# 读取DEF（选择其中一个）
read_def top/top_layout.def               # 顶层布局
# read_def partition_0/partition_0_layout.def  # Partition 0
# read_def partition_1/partition_1_layout.def  # Partition 1
# read_def partition_2/partition_2_layout.def  # Partition 2
# read_def partition_3/partition_3_layout.def  # Partition 3
```

## 📊 布局信息

### 顶层布局 (top_layout.def)
- **内容**：4个partition macros + boundary nets
- **Boundary HPWL**：4.4 um
- **Boundary Nets**：2,203个
- **Die Area**：50000 × 50000 um²

### Partition详细布局

| Partition | Instances | HPWL (um) | Region (llx, lly, urx, ury) |
|-----------|-----------|-----------|----------------------------|
| 0 | 7,297 (22.6%) | 1,540,203.6 | (25000, 25000, 50000, 50000) |
| 1 | 7,329 (22.7%) | 1,596,688.3 | (25000, 0, 50000, 25000) |
| 2 | 7,988 (24.7%) | 1,734,124.5 | (0, 0, 25000, 25000) |
| 3 | 9,667 (29.9%) | 1,913,437.3 | (0, 25000, 25000, 50000) |

**Internal HPWL总和**：6,784,453.7 um  
**边界代价 (BC)**：0.00006485% ≈ 0.00%

## 🎨 GUI操作提示

### 基本操作
- **缩放**：鼠标滚轮 或 `Z` 键
- **平移**：鼠标右键拖动
- **适应窗口**：`F` 键
- **选择**：鼠标左键点击
- **测量距离**：`M` 键

### 查看选项
- **View → Layers**：显示/隐藏不同层
- **View → Nets**：高亮显示特定网络
- **View → Instances**：选择并查看实例信息
- **Tools → Timing**：查看时序信息（如果有）

### 比较不同布局

可以依次打开不同的布局进行比较：
1. 先查看顶层布局，了解整体partition分布
2. 再查看各个partition的详细布局，了解内部单元放置

## 🔍 观察要点

### 顶层布局
1. **Partition分布**：4个partition在die上的物理位置
2. **Boundary nets**：partition之间的连接线（应该很少）
3. **空间利用**：每个partition是否均匀分布

### Partition详细布局
1. **单元密度**：标准单元的放置密度
2. **布线拥塞**：是否有明显的拥塞区域
3. **HPWL分布**：线长是否合理

## 📝 注意事项

1. 本地LEF文件与服务器相同，确保一致性
2. 如果OpenROAD GUI无法打开，检查OpenROAD是否正确安装
3. 可以使用`openroad -version`检查版本
4. DEF文件较大，加载可能需要几秒钟

## 🚀 下一步

查看完布局后，可以：
1. 截图保存关键视图
2. 分析HPWL分布是否合理
3. 与flat布局（无分区）进行比较
4. 在其他ISPD 2015设计上重复实验

