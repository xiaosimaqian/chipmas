# ChipMASRAG 下一步工作计划

生成时间：2025-11-15 09:50

## 📊 已完成工作回顾

### ✅ 里程碑1：基础设施（100%完成）
- 核心模块：knowledge_base, rag_retriever, environment, negotiation, networks
- 工具模块：def_parser, openroad_interface, boundary_analyzer, die_size_config
- 分区模块：baseline_partitioner (hMETIS, spectral, greedy)

### ✅ 里程碑2：层级化改造（100%完成）⭐
- hierarchical_transformation.py (430行)
- formal_verification.py (380行) + Yosys集成
- physical_mapping.py (370行) + 连接性优化
- macro_lef_generator.py (349行)
- 测试通过率：100% (19/19)

### ✅ 里程碑3：Baseline数据收集（100%完成）🎉
- EXP-002: Clean Baseline - 16/16 ISPD 2015设计成功
- 完整的Legalized HPWL数据
- 运行时间：1.2分钟 - 313.3分钟
- 知识库：28个案例（16个ISPD 2015 + 12个ISPD 2005）

### ✅ 里程碑4：K-SpecPart集成（100%完成）⭐⭐
- Julia环境 + 20+依赖包
- hMETIS + CPLEX + ILP编译
- HGR格式转换工具
- 首次成功运行：mgc_fft_1 (Cutsize=219)
- 深度解决ILP段错误问题

## ⚠️ 第一阶段实验未完成工作

### 🔥 核心缺失：K-SpecPart完整流程
**当前状态**：只完成了逻辑分区（Cutsize=219），**后续物理实现全部缺失**

需要完成的步骤：

```
当前状态：
  DEF → HGR → K-SpecPart → partition.part.4 ✅
                                 ↓
缺失步骤：                        ❌ 未实现
  1. 从partition.part.4提取分区方案
  2. 层级化改造（生成分区网表 + 顶层网表）
  3. Formal验证（等价性检查）
  4. 物理位置优化（连接性驱动）
  5. 各分区独立OpenROAD运行
  6. 提取各分区internal HPWL
  7. 生成Macro LEF
  8. 顶层OpenROAD运行（boundary nets）
  9. 提取boundary HPWL
 10. 计算边界代价
```

### 问题分析：层级化改造的适用性

**已实现的方法** (hierarchical_transformation.py)：
- ❌ 基于Verilog网表解析
- ❌ 对ISPD 2015不适用（缺少门级网表）
- ✅ 测试通过（但仅用于小型测试案例）

**需要的方法** (新实现)：
- ✅ 基于DEF + 分区结果
- ✅ 直接操作component-level分区
- ✅ 适用于ISPD 2015所有设计

## 🎯 第一阶段完整实验目标

### 实验A：K-SpecPart完整流程
**目标**：验证K-SpecPart + Partition-based OpenROAD的完整性

**输入**：
- 设计：mgc_fft_1
- 分区数：K=4
- 平衡约束：ε=5%

**输出指标**：
1. **逻辑分区质量**：
   - Cutsize: 219 ✅（已获得）
   - 分区平衡度: 19.79% ✅（已获得）
   
2. **物理布局质量** ❌（待获得）：
   - Internal HPWL (sum of 4 partitions)
   - Boundary HPWL (from top-level run)
   - **Boundary Cost = BC = HPWL_boundary / HPWL_internal_sum × 100%**
   - Total Legalized HPWL
   
3. **对比基准**：
   - Clean Baseline HPWL: 11,425,351.4 um ✅（已获得）
   - K-SpecPart Total HPWL: ??? um ❌（待获得）
   - **HPWL改善率** = (Baseline - KSpecPart) / Baseline × 100%
   
4. **时间开销**：
   - 逻辑分区时间: ~1小时 ✅（已知）
   - 各分区OpenROAD时间: ??? ❌（待测）
   - 顶层OpenROAD时间: ??? ❌（待测）
   - 总运行时间: ??? ❌（待测）

### 实验B：ChipMASRAG完整流程
**状态**：依赖实验A的基础设施

## 📝 下一步工作详细计划

### Phase 1：实现Partition-based Flow基础设施（3-4天）

#### 任务1.1：DEF分区提取器（1天）
**创建**: `src/utils/def_partition_extractor.py`

**功能**：
```python
def extract_partition_def(
    original_def: Path,
    partition_scheme: Dict[int, List[str]],  # {partition_id: [comp_names]}
    output_dir: Path,
    die_config: Dict
) -> Dict[int, Path]:
    """
    从原始DEF提取各分区的独立DEF文件
    
    输入：
      - original_def: floorplan.def
      - partition_scheme: K-SpecPart分区结果（从.part.4解析）
      - die_config: 各分区的die size配置
    
    输出：
      - partition_0.def, partition_1.def, ...
      - 每个DEF包含该分区的components和internal nets
    """
    pass

def identify_boundary_nets(
    original_def: Path,
    partition_scheme: Dict[int, List[str]]
) -> Dict:
    """
    识别跨分区的边界网络
    
    输出：
      - boundary_nets: {net_name: {connected_partitions: [0, 1], ...}}
      - internal_nets: {partition_id: [net_names]}
    """
    pass
```

**测试**：
- 输入：mgc_fft_1 + K-SpecPart结果
- 输出：4个partition DEF文件
- 验证：每个DEF的component数量匹配分区统计

#### 任务1.2：顶层DEF生成器（1天）
**创建**: `src/utils/top_def_generator.py`

**功能**：
```python
def generate_top_def(
    partition_lef_files: Dict[int, Path],  # Macro LEF
    boundary_nets: Dict,
    physical_regions: Dict[int, Tuple],  # 物理位置映射
    output_def: Path,
    die_config: Dict
) -> Path:
    """
    生成顶层DEF（只包含boundary nets）
    
    包含：
      1. COMPONENTS: partition macros（固定位置）
      2. NETS: 只包含boundary nets
      3. PINS: 连接到partition macro的引脚
    """
    pass
```

#### 任务1.3：完整流程脚本（1-2天）
**创建**: `scripts/run_partition_based_flow.py`

**流程**：
```python
def run_partition_based_flow(design_name, partition_file, num_partitions):
    # 1. 解析分区结果
    partition_scheme = parse_kspecpart_result(partition_file)
    
    # 2. 识别边界网络
    boundary_info = identify_boundary_nets(def_file, partition_scheme)
    
    # 3. 物理位置优化
    connectivity_matrix = analyze_partition_connectivity(boundary_info)
    physical_regions = optimize_physical_layout(
        num_partitions, connectivity_matrix, die_area
    )
    
    # 4. 提取各分区DEF
    partition_defs = extract_partition_defs(
        original_def, partition_scheme, physical_regions
    )
    
    # 5. 并行运行各分区OpenROAD
    partition_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_partition_openroad, pid, pdef): pid
            for pid, pdef in partition_defs.items()
        }
        for future in as_completed(futures):
            result = future.result()
            partition_results.append(result)
    
    # 6. 生成Macro LEF
    macro_lefs = generate_macro_lefs(partition_results)
    
    # 7. 生成顶层DEF
    top_def = generate_top_def(
        macro_lefs, boundary_info, physical_regions
    )
    
    # 8. 顶层OpenROAD运行
    top_result = run_top_openroad(top_def, macro_lefs)
    
    # 9. 计算边界代价
    internal_hpwl_sum = sum(r['hpwl'] for r in partition_results)
    boundary_hpwl = top_result['hpwl']
    boundary_cost = (boundary_hpwl / internal_hpwl_sum) * 100
    
    # 10. 汇总结果
    return {
        'design': design_name,
        'cutsize': 219,  # from K-SpecPart
        'partition_hpwls': [r['hpwl'] for r in partition_results],
        'internal_hpwl_sum': internal_hpwl_sum,
        'boundary_hpwl': boundary_hpwl,
        'boundary_cost': boundary_cost,
        'total_hpwl': internal_hpwl_sum + boundary_hpwl,
        'runtime': {...}
    }
```

### Phase 2：完成mgc_fft_1实验（1天）

**运行命令**：
```bash
cd ~/chipmas
python3 scripts/run_partition_based_flow.py \
  --design mgc_fft_1 \
  --partition-file results/kspecpart/mgc_fft_1/mgc_fft_1.hgr.processed.specpart.part.4 \
  --num-partitions 4 \
  --output results/kspecpart/mgc_fft_1/partition_based_flow/
```

**预期输出**：
```
results/kspecpart/mgc_fft_1/partition_based_flow/
├── partitions/
│   ├── partition_0.def
│   ├── partition_0_layout.def
│   ├── partition_0.lef (macro)
│   └── partition_0_result.json (HPWL=???)
│   ├── partition_1.def
│   └── ...
├── top/
│   ├── top.def (boundary nets only)
│   ├── top_layout.def
│   └── top_result.json (HPWL=???)
├── visualization/
│   ├── partition_layout.png
│   └── connectivity_matrix.png
└── summary.json
    {
      "design": "mgc_fft_1",
      "method": "K-SpecPart",
      "cutsize": 219,
      "boundary_cost": "??%",
      "total_hpwl": "??? um",
      "baseline_hpwl": "11,425,351.4 um",
      "improvement": "??%"
    }
```

### Phase 3：知识库集成（半天）

#### 需要收集的分区数据

**对于每个设计 × 每个分区方法**：

```python
kb_entry = {
    "design_name": "mgc_fft_1",
    "method": "K-SpecPart",
    "partitioning": {
        "num_partitions": 4,
        "balance_constraint": 0.05,
        "cutsize": 219,
        "partition_sizes": [7297, 7329, 7988, 9667],
        "partition_balance": 0.1979,
        "logical_time": 3600  # seconds
    },
    "physical_layout": {
        "physical_regions": {
            0: [0, 0, 2500, 2500],
            1: [2500, 0, 5000, 2500],
            2: [0, 2500, 2500, 5000],
            3: [2500, 2500, 5000, 5000]
        },
        "partition_hpwls": [2800000, 2900000, 3100000, 3500000],
        "internal_hpwl_sum": 12300000,
        "boundary_hpwl": 850000,
        "boundary_cost": 6.91,  # %
        "total_hpwl": 13150000  # um
    },
    "comparison": {
        "baseline_hpwl": 11425351.4,
        "improvement": -15.1,  # % (negative = worse)
        "baseline_runtime": 750,  # seconds
        "partitioned_runtime": 4200  # seconds (including partitioning)
    },
    "metadata": {
        "timestamp": "2025-11-15T10:00:00",
        "experiment_id": "EXP-003"
    }
}
```

**知识库更新策略**：
1. **新增字段**：每个案例添加 `partitioning` 和 `comparison` 字段
2. **RAG检索增强**：基于分区特征检索相似案例
3. **历史分析**：对比不同分区方法的效果

#### 更新脚本
**创建**: `scripts/update_kb_with_partition_results.py`

```python
def update_kb_with_partition_results(
    kb_file: Path,
    partition_result: Dict,
    backup: bool = True
):
    """
    将分区实验结果集成到知识库
    
    流程：
      1. 读取现有知识库
      2. 查找或创建对应设计的条目
      3. 添加/更新分区数据
      4. 备份并保存
    """
    pass
```

### Phase 4：Git代码管理（30分钟）

#### 提交策略
```bash
# 1. 查看当前状态
git status

# 2. 添加新文件（排除大文件）
git add WORK_SUMMARY_AND_PLAN.md
git add NEXT_STEPS_PLAN.md
git add SYNC_STATUS_*.md
git add src/utils/def_partition_extractor.py  # 新文件
git add src/utils/top_def_generator.py  # 新文件
git add scripts/run_partition_based_flow.py  # 新文件
git add scripts/update_kb_with_partition_results.py  # 新文件

# 3. 提交
git commit -m "完成K-SpecPart集成和数据同步

主要更新：
- 完成K-SpecPart环境搭建和首次运行
- 同步服务器实验结果（Clean Baseline + K-SpecPart）
- 更新工作计划（WORK_SUMMARY_AND_PLAN.md）
- 创建下一步工作计划（NEXT_STEPS_PLAN.md）

待实现：
- Partition-based OpenROAD Flow
- DEF分区提取器
- 顶层DEF生成器
"

# 4. 推送
git push origin main
```

#### .gitignore验证
确保以下内容被忽略：
```
data/datasets/          # 大数据集
data/embeddings/        # 嵌入向量
results/                # 实验结果
*.def                   # DEF文件
*.log                   # 日志文件
__pycache__/            # Python缓存
```

## 📊 时间估算总览

| 任务 | 预计时间 | 优先级 |
|------|---------|--------|
| **DEF分区提取器** | 1天 | P0 🔥 |
| **顶层DEF生成器** | 1天 | P0 🔥 |
| **完整流程脚本** | 1-2天 | P0 🔥 |
| **mgc_fft_1实验** | 1天 | P0 🔥 |
| **知识库集成** | 0.5天 | P1 |
| **Git管理** | 0.5天 | P1 |
| **总计** | **5-6天** | |

## 🎯 本周目标（Week of 2025-11-15）

1. **周一-周三**：实现Partition-based Flow基础设施
2. **周四**：完成mgc_fft_1完整实验，获得第一个对比数据点
3. **周五**：知识库集成 + Git管理 + 文档更新

**完成标志**：
- ✅ mgc_fft_1的K-SpecPart完整流程运行成功
- ✅ 获得完整的对比指标（Boundary Cost, HPWL改善率等）
- ✅ 知识库包含分区实验数据
- ✅ 代码和文档已提交到Git

## 📝 关键问题

### Q1: 层级化改造如何处理DEF而非Verilog？
**答案**：新实现`def_partition_extractor.py`，直接从DEF提取分区，不依赖Verilog网表。

### Q2: 如何验证Formal等价性？
**答案**：由于是基于DEF的物理分区（component-level），不改变逻辑连接，**不需要Formal验证**。Formal验证主要用于Verilog网表层级改造。

### Q3: 各分区OpenROAD的die size如何确定？
**答案**：基于物理区域映射结果，die_area = physical_region尺寸。

### Q4: 知识库如何利用分区数据？
**答案**：
1. RAG检索：根据设计特征和分区策略检索相似案例
2. 策略学习：ChipMASRAG学习哪种分区策略对哪类设计有效
3. 协商指导：历史边界代价指导智能体协商

