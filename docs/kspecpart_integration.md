# K-SpecPart 与 OpenROAD 衔接方案

## 概述

本文档详细说明如何使用 K-SpecPart 公开代码进行分区实验，并与 OpenROAD 衔接获取 legalized HPWL，以及如何与 ChipMASRAG 进行公平对比。

**GitHub 仓库**：https://github.com/TILOS-AI-Institute/HypergraphPartitioning

## 核心思路

```
ISPD 2015 → K-SpecPart 分区 → OpenROAD 约束 → OpenROAD 布局 → Legalized HPWL
    ↓              ↓                ↓               ↓                ↓
  .hgr 格式    .part.K 文件    DEF REGIONS    详细布局 DEF      HPWL 值
```

## 详细流程

### 阶段1：ISPD 2015 转换为超图格式

**K-SpecPart 输入格式**（`.hgr` 文件）：
```
<num_hyperedges> <num_vertices> [fmt]
<vertex_list_for_hyperedge_1>
<vertex_list_for_hyperedge_2>
...
```

**转换脚本**：`scripts/convert_ispd2015_to_hgr.py`

```bash
# 单个设计转换
python scripts/convert_ispd2015_to_hgr.py \
    --def-file data/ispd2015/mgc_fft_1/floorplan.def \
    --output results/kspecpart/mgc_fft_1.hgr \
    --mapping results/kspecpart/mgc_fft_1.mapping.json

# 批量转换所有 ISPD 2015 设计
for design in data/ispd2015/*/; do
    design_name=$(basename $design)
    python scripts/convert_ispd2015_to_hgr.py \
        --def-file data/ispd2015/$design_name/floorplan.def \
        --output results/kspecpart/$design_name.hgr \
        --mapping results/kspecpart/$design_name.mapping.json
done
```

**转换逻辑**：
- 每个 `COMPONENT` → 超图顶点（1-based 编号）
- 每个 `NET` → 超图超边（连接的组件列表）
- 输出 `.hgr` 文件 + `.mapping.json`（保存 component_name ↔ vertex_id 映射）

### 阶段2：运行 K-SpecPart

**安装 K-SpecPart**：

```bash
cd ~/chipmas
git clone https://github.com/TILOS-AI-Institute/HypergraphPartitioning.git
cd HypergraphPartitioning/K_SpecPart

# 按照 README 安装 Julia 依赖
# julia --project -e 'using Pkg; Pkg.instantiate()'
```

**运行分区**：

```bash
# 单个设计（4-way 分区，5% 不平衡）
julia run_kspecpart.jl \
    ../../results/kspecpart/mgc_fft_1.hgr \
    4 \
    0.05 \
    ../../results/kspecpart/mgc_fft_1.part.4

# 批量运行
for hgr_file in ../../results/kspecpart/*.hgr; do
    base_name=$(basename $hgr_file .hgr)
    julia run_kspecpart.jl \
        $hgr_file \
        4 \
        0.05 \
        ../../results/kspecpart/$base_name.part.4
done
```

**K-SpecPart 输出格式**（`.part.K` 文件）：
```
0
1
0
2
1
...
```
- 每行一个数字，表示对应顶点的分区 ID（0-based）
- 第 i 行对应顶点 i（1-based）的分区

### 阶段3：K-SpecPart 分区结果转换为 OpenROAD 约束

**转换脚本**：`scripts/convert_kspecpart_to_openroad.py`

```python
def convert_kspecpart_to_openroad_constraints(
    part_file,      # K-SpecPart 输出的 .part.K 文件
    mapping_file,   # 从阶段1获得的 .mapping.json 文件
    def_file,       # 原始 ISPD 2015 DEF 文件
    output_def      # 输出的带分区约束的 DEF 文件
):
    """
    将 K-SpecPart 分区结果转换为 OpenROAD DEF 约束
    """
    # 1. 读取映射关系
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
    id_to_vertex = mapping['id_to_vertex']  # vertex_id -> component_name
    
    # 2. 读取 K-SpecPart 分区结果
    partition_assignment = {}
    with open(part_file, 'r') as f:
        for vertex_id, line in enumerate(f, start=1):  # K-SpecPart 使用 1-based
            part_id = int(line.strip())
            component_name = id_to_vertex[str(vertex_id)]
            partition_assignment[component_name] = part_id
    
    # 3. 构建分区方案
    partition_scheme = {}
    for comp, part_id in partition_assignment.items():
        part_key = f"partition_{part_id}"
        if part_key not in partition_scheme:
            partition_scheme[part_key] = []
        partition_scheme[part_key].append(comp)
    
    # 4. 调用已有的 DEF 约束转换函数
    from src.utils.openroad_interface import OpenRoadInterface
    openroad_interface = OpenRoadInterface()
    openroad_interface.convert_partition_to_def_constraints(
        partition_scheme,
        def_file,
        output_def
    )
```

**使用方法**：

```bash
python scripts/convert_kspecpart_to_openroad.py \
    --part-file results/kspecpart/mgc_fft_1.part.4 \
    --mapping-file results/kspecpart/mgc_fft_1.mapping.json \
    --def-file data/ispd2015/mgc_fft_1/floorplan.def \
    --output results/kspecpart/mgc_fft_1_with_partition.def
```

### 阶段4：OpenROAD 生成布局并提取 HPWL

**与 ChipMASRAG 完全相同的流程**：

```bash
# 运行 OpenROAD
openroad -no_init -exit <<EOF
# 读取工艺文件
read_lef data/ispd2015/mgc_fft_1/tech.lef
read_lef data/ispd2015/mgc_fft_1/cells.lef

# 读取带分区约束的 DEF
read_def results/kspecpart/mgc_fft_1_with_partition.def

# 读取网表
read_verilog data/ispd2015/mgc_fft_1/design.v
link_design mgc_fft_1

# 全局布局
global_placement

# 详细布局
detailed_placement

# 输出布局 DEF
write_def results/kspecpart/mgc_fft_1_final_layout.def
EOF
```

**HPWL 提取**：使用相同的 OpenROAD API
- 实现：`src/utils/openroad_interface.py::calculate_hpwl()`
- 方法：使用 OpenROAD Python API 或从 DEF 文件计算

## 与 ChipMASRAG 的对比

### 对比流程表

| 步骤 | K-SpecPart | ChipMASRAG |
|------|-----------|-----------|
| **1. 输入格式** | 超图（.hgr） | DEF/Verilog |
| **2. 分区算法** | 监督式谱框架 | RAG + 多智能体协商 |
| **3. 是否需要 hint** | 是（通常用 hMETIS） | 否（RAG 检索历史案例） |
| **4. 输出格式** | `.part.K` 文件 | JSON（分区方案 + 协商历史） |
| **5. 转换为 OpenROAD 约束** | 相同（DEF REGIONS/GROUPS） | 相同（DEF REGIONS/GROUPS） |
| **6. OpenROAD 布局** | 相同（使用相同参数） | 相同（使用相同参数） |
| **7. HPWL 提取** | 相同（OpenROAD API） | 相同（OpenROAD API） |

### 对比指标

**1. 分区质量（K-SpecPart 原生指标）**：
- **Cut size**：K-SpecPart 优化的主要目标
- **Balance**：分区平衡度
- **运行时间**：分区算法运行时间

**2. 最终布局质量（通过 OpenROAD 获得）**：
- **Legalized HPWL**（主要对比指标）：
  - K-SpecPart：通过 OpenROAD 获得
  - ChipMASRAG：通过 OpenROAD 获得
  - 公平对比：使用相同的 OpenROAD 版本和参数
- **边界代价**：
  - 计算方法：`(完整 HPWL - 各分区内部 HPWL 之和) / 各分区内部 HPWL 之和`
  - ChipMASRAG 专门优化边界代价
- **布局合法性**：OpenROAD 是否能生成合法布局

**3. 方法特点对比**：

| 特点 | K-SpecPart | ChipMASRAG |
|------|-----------|-----------|
| **需要 hint** | 是（hMETIS） | 否（RAG 检索） |
| **知识复用** | 否 | 是（加速 >60倍） |
| **边界代价优化** | 次要（主要优化 cut size） | 主要（专门的协商机制） |
| **可扩展性** | 需为不同规模训练 | 1.2M+，训练时间与规模无关 |
| **预训练需求** | 需要（训练监督模型） | 不需要（动态 RAG 检索） |

### 公平对比保证

**1. 相同的 OpenROAD 工具和参数**：
- 使用相同的 OpenROAD 版本
- 使用相同的 `global_placement` 和 `detailed_placement` 参数
- 使用相同的 LEF/DEF 文件（仅分区约束不同）

**2. 相同的评估指标**：
- 使用相同的 HPWL 计算方法（OpenROAD API）
- 使用相同的边界代价计算方法

**3. 相同的数据集**：
- 使用 ISPD 2015（16 个设计）
- 相同的分区数量（K=4）
- 相同的平衡约束（ε=5%）

## 实验脚本组织

```
scripts/
├── convert_ispd2015_to_hgr.py          # ISPD 2015 → .hgr 格式
├── run_kspecpart.sh                    # 批量运行 K-SpecPart
├── convert_kspecpart_to_openroad.py    # K-SpecPart 结果 → OpenROAD 约束
├── run_openroad_with_kspecpart.py      # 运行 OpenROAD 获取 HPWL
├── compare_with_kspecpart.py           # 完整对比实验运行器
└── analyze_kspecpart_results.py        # 结果分析和可视化
```

## 完整实验命令

```bash
# 1. 转换 ISPD 2015 为超图格式
python scripts/convert_ispd2015_to_hgr.py \
    --def-file data/ispd2015/mgc_fft_1/floorplan.def \
    --output results/kspecpart/mgc_fft_1.hgr \
    --mapping results/kspecpart/mgc_fft_1.mapping.json

# 2. 运行 K-SpecPart
cd HypergraphPartitioning/K_SpecPart
julia run_kspecpart.jl \
    ../../results/kspecpart/mgc_fft_1.hgr \
    4 0.05 \
    ../../results/kspecpart/mgc_fft_1.part.4

# 3. 转换为 OpenROAD 约束
cd ~/chipmas
python scripts/convert_kspecpart_to_openroad.py \
    --part-file results/kspecpart/mgc_fft_1.part.4 \
    --mapping-file results/kspecpart/mgc_fft_1.mapping.json \
    --def-file data/ispd2015/mgc_fft_1/floorplan.def \
    --output results/kspecpart/mgc_fft_1_with_partition.def

# 4. 运行 OpenROAD 获取 HPWL
python scripts/run_openroad_with_kspecpart.py \
    --design mgc_fft_1 \
    --def-with-partition results/kspecpart/mgc_fft_1_with_partition.def \
    --output results/kspecpart/mgc_fft_1_final_layout.def

# 5. 对比分析
python scripts/compare_with_kspecpart.py \
    --kspecpart-results results/kspecpart \
    --chipmasrag-results results/chipmasrag_baseline \
    --output results/comparison_report.pdf
```

## 预期结果

**K-SpecPart 优势**：
- Cut size 小（K-SpecPart 优化目标）
- 算法成熟，结果稳定

**ChipMASRAG 预期优势**：
- **边界代价优化**：专门的协商机制 → 边界代价降低 >25-30%
- **知识复用**：RAG 检索 → 知识库命中时加速 >60倍
- **无需预训练**：动态适配，无需为不同设计训练
- **最终布局质量**：动态协商优化边界 → legalized HPWL 提升 >10-15%
- **可扩展性**：多智能体并行 → 1.2M+ 设计，训练时间与规模无关

## 对比目标表

| 指标 | K-SpecPart | ChipMASRAG 目标 |
|------|-----------|----------------|
| Cut size | 基准 | 相近或略优（±5%） |
| Legalized HPWL | 基准 | 提升 >10-15% |
| 边界代价 | 基准 | 降低 >25-30% |
| 运行时间 | 基准 | 知识库命中：加速 >60倍 |
| 可扩展性 | 需调参 | 1.2M+，无需调参 |
| 预训练需求 | 需要 | 不需要 |

## 参考资料

- K-SpecPart GitHub: https://github.com/TILOS-AI-Institute/HypergraphPartitioning
- K-SpecPart 论文: https://arxiv.org/abs/2305.06167
- OpenROAD 文档: https://openroad.readthedocs.io/


