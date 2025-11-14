<!-- 84882d4f-219f-427d-b629-e0bf5b84033c a269a5dd-7279-426e-ab60-8c22e7c29632 -->
# ChipMASRAG代码实现与实验计划（修正版）

## 一、项目结构设计

### 1.1 目录结构

```
chipmas/
├── src/                          # 核心源代码（高度集成）
│   ├── __init__.py
│   ├── framework.py              # 主框架入口（集成所有组件）
│   ├── coordinator.py            # 协调者智能体（RAG检索+全局协调）
│   ├── partition_agent.py        # 分区智能体（GAT+Actor-Critic+协商）
│   ├── knowledge_base.py         # 知识库管理（重新构建）
│   ├── rag_retriever.py          # RAG检索模块（粗/细/语义三级检索）
│   ├── negotiation.py            # 边界协商协议
│   ├── networks.py               # 神经网络（GAT、Actor、Critic、协商网络）
│   ├── training.py               # 训练算法（MADDPG、PPO）
│   ├── environment.py            # 布局环境（状态、奖励、动作）
│   └── utils/                    # 工具函数模块
│       ├── __init__.py
│       ├── boundary_analyzer.py  # 边界代价分析（连接识别、代价分解）
│       ├── def_parser.py          # DEF文件解析器（解析组件位置、网络连接）
│       ├── visualization.py      # 可视化工具（分区、边界代价、布局）
│       ├── openroad_interface.py # OpenRoad接口（HPWL计算）
│       ├── resource_monitor.py  # 资源监控（时间、内存）
│       ├── convert_blif_to_verilog.py  # BLIF到Verilog转换工具（用于titan23）
│       └── titan23_to_openroad.tcl     # Titan23设计OpenROAD综合布局脚本
├── experiments/                  # 实验相关
│   ├── __init__.py
│   ├── runner.py                 # 实验运行器（统一入口）
│   ├── evaluator.py              # 评估器（HPWL、成功率等）
│   └── logger.py                 # 实验日志系统
├── data/                         # 数据目录（统一使用data）
│   ├── ispd2015/                 # ISPD 2015基准测试（16个设计）
│   │   ├── mgc_pci_bridge32_a/   # 每个设计包含：cells.lef, design.v, floorplan.def, tech.lef
│   │   ├── mgc_pci_bridge32_b/
│   │   ├── mgc_fft_1/
│   │   ├── mgc_fft_2/
│   │   ├── mgc_fft_a/
│   │   ├── mgc_fft_b/
│   │   ├── mgc_des_perf_1/
│   │   ├── mgc_des_perf_a/
│   │   ├── mgc_des_perf_b/
│   │   ├── mgc_edit_dist_a/
│   │   ├── mgc_matrix_mult_1/
│   │   ├── mgc_matrix_mult_a/
│   │   ├── mgc_matrix_mult_b/
│   │   ├── mgc_superblue11_a/
│   │   ├── mgc_superblue12/
│   │   └── mgc_superblue16_a/
│   ├── titan23/                  # Titan23基准测试
│   │   ├── benchmarks/titan23/   # Titan23设计文件
│   │   ├── arch/                 # FPGA架构文件
│   │   └── vqm_to_blif/          # 格式转换工具
│   ├── knowledge_base/           # 知识库数据（重新构建）
│   └── results/                  # 实验结果归档
│       ├── {timestamp}/          # 按时间戳归档
│       │   ├── config.json       # 实验配置
│       │   ├── logs/             # 日志文件
│       │   ├── checkpoints/      # 模型检查点
│       │   └── results.json      # 结果汇总
├── configs/                      # 配置文件
│   ├── default.yaml              # 默认配置
│   ├── experiment.yaml          # 实验配置
│   └── knowledge_base.yaml       # 知识库配置
├── scripts/                      # 脚本工具
│   ├── build_kb.py              # 重新构建知识库（满足ChipMASRAG要求）
│   ├── run_experiment.py        # 运行实验
│   ├── analyze_results.py       # 结果分析
│   └── run_titan23_openroad.sh  # Titan23设计OpenROAD流程一键脚本
├── requirements.txt             # 依赖包
├── README.md                    # 项目说明
└── docs/                        # 文档（已有论文）
```

### 1.2 设计原则

- **高度集成**：核心功能集中在`src/framework.py`，通过组合模式集成各模块
- **模块化**：每个模块独立但接口清晰，便于测试和维护
- **少文件**：核心代码控制在10个左右Python文件，避免过度拆分

### 1.3 数据集目录调整

**当前状态**：
- 数据集位于`dataset/`目录：
  - `dataset/ispd_2015_contest_benchmark/` - ISPD 2015基准测试
  - `dataset/titan_release_1.3.1/` - Titan23基准测试

**调整方案**（统一使用`data/`目录）：
- 创建符号链接或复制数据集到`data/`目录：
  ```bash
  # 方案1：创建符号链接（推荐，节省空间）
  cd chipmas/data
  ln -s ../dataset/ispd_2015_contest_benchmark ispd2015
  ln -s ../dataset/titan_release_1.3.1 titan23
  
  # 方案2：复制数据（如果符号链接不可用）
  cp -r ../dataset/ispd_2015_contest_benchmark data/ispd2015
  cp -r ../dataset/titan_release_1.3.1 data/titan23
  ```

**最终目录结构**：
- `data/ispd2015/` - ispd2015 benchmark
- `data/titan23/` - titan23 benchmark
- `data/knowledge_base/` - 知识库数据
- `data/results/` - 实验结果归档

## 二、核心模块实现

### 2.1 知识库模块 (`src/knowledge_base.py`)

**功能**：管理历史案例，支持案例存储、检索、更新

**关键接口**：

- `load()`: 加载知识库
- `add_case()`: 添加新案例
- `get_case()`: 获取案例
- `export()`: 导出知识库

**数据结构**：

```python
Case = {
    'design_id': str,
    'features': np.array,              # 设计特征向量
    'partition_strategy': dict,        # 分区策略（模块分配、边界）
    'negotiation_patterns': dict,      # 边界协商模式（协商历史、参数、结果）
    'quality_metrics': dict,          # HPWL、边界代价、运行时间等
    'embedding': np.array             # 语义嵌入向量
}
```

### 2.2 RAG检索模块 (`src/rag_retriever.py`)

**功能**：三级检索（粗粒度→细粒度→语义检索）

**关键方法**：

- `coarse_retrieve()`: 基于规模和类型筛选
- `fine_retrieve()`: 基于特征向量相似度
- `semantic_retrieve()`: 基于嵌入模型语义相似度
- `retrieve()`: 统一检索接口，返回top-k=10

### 2.3 协调者智能体 (`src/coordinator.py`)

**功能**：统一RAG检索、全局协调、奖励分配

**关键方法**：

- `retrieve_rag()`: 执行RAG检索并广播结果
- `coordinate()`: 全局协调各分区智能体
- `compute_global_reward()`: 计算全局奖励
- `update()`: PPO训练更新

**网络结构**：PPO策略网络（2层MLP，256, 128）

### 2.4 分区智能体 (`src/partition_agent.py`)

**功能**：局部优化、边界协商、策略执行

**关键方法**：

- `encode_state()`: GAT状态编码
- `select_action()`: Actor网络输出动作
- `negotiate()`: 知识驱动的边界协商
- `update()`: MADDPG训练更新

**网络结构**：

- GAT编码器：3层，隐藏维度128
- Actor网络：2层MLP（256, 128）
- Critic网络：3层MLP（512, 256, 128）
- 协商网络：2层MLP（128, 64）

### 2.5 边界协商模块 (`src/negotiation.py`)

**功能**：实现知识驱动的边界协商协议

**关键方法**：

- `identify_boundary_modules()`: 识别高代价边界模块
- `find_similar_negotiation()`: 在RAG结果中查找相似协商案例
- `negotiate()`: 执行协商请求
- `execute_migration()`: 执行模块迁移

### 2.6 训练模块 (`src/training.py`)

**功能**：MADDPG（分区智能体）和PPO（协调者）训练

**关键类**：

- `MADDPGTrainer`: 分区智能体训练
- `PPOTrainer`: 协调者训练
- `TrainingManager`: 统一训练管理器

### 2.7 环境模块 (`src/environment.py`)

**功能**：布局环境，状态、奖励、动作空间定义

**关键类**：

- `PlacementEnv`: 布局环境
- `State`: 状态表示（局部状态+RAG状态）
- `RewardCalculator`: 奖励计算（局部+全局+边界+RAG奖励）

### 2.8 主框架 (`src/framework.py`)

**功能**：集成所有组件，提供统一接口

**关键类**：

- `ChipMASRAG`: 主框架类
- `run()`: 运行布局优化
- `train()`: 训练模型
- `evaluate()`: 评估性能

### 2.9 OpenRoad接口 (`src/utils/openroad_interface.py`)

**功能**：与OpenRoad布局工具集成，计算HPWL

**重要说明**：本地和服务器上已有OpenRoad成功集成案例，**不要重新开始**，基于现有成功案例进行集成。

**ChipMASRAG与OpenRoad的集成方式**：

**核心问题**：论文方法如何与OpenRoad集成，如何影响OpenRoad表现，如何跑出预期结果。

**关键点**：
1. ChipMASRAG**独立生成分区方案**（不依赖OpenRoad的partition management）
2. 将分区方案转换为OpenRoad可识别的约束（DEF格式的REGIONS和COMPONENTS）
3. OpenRoad根据分区约束进行布局，**分区约束影响OpenRoad的布局结果**
4. 从OpenRoad布局结果中提取HPWL和边界代价，验证分区方案的有效性

**ChipMASRAG如何影响OpenRoad表现**：

1. **分区约束影响布局质量**：
   - 好的分区方案（低边界代价）→ OpenRoad布局时跨分区连接少 → 最终HPWL更优
   - 差的分区方案（高边界代价）→ OpenRoad布局时跨分区连接多 → 最终HPWL较差
   - **证明方式**：对比不同分区方案的最终HPWL，证明ChipMASRAG分区方案产生的HPWL更优

2. **分区约束影响布局效率**：
   - 平衡的分区使得各分区优化更充分
   - 合理的模块分配减少布局冲突，提升可布线性
   - **证明方式**：对比分区质量指标（边界代价、跨分区连接数）与最终HPWL的相关性

3. **知识驱动的分区优化**：
   - RAG检索历史案例，指导分区方案生成
   - 多智能体协商优化边界模块分配
   - **证明方式**：对比有RAG vs 无RAG、有协商 vs 无协商的最终HPWL差异

**集成流程**（基于现有OpenRoad成功案例）：

1. **阶段1：ChipMASRAG分区生成**（独立于OpenRoad）
   - 输入：设计网表（Verilog）、设计特征
   - 过程：
     - RAG检索历史案例
     - 多智能体协商生成分区方案
     - 输出分区方案（模块到分区的映射）
   - 输出：分区方案JSON文件
     ```json
     {
       "partitions": {
         "partition_0": [module_id_1, module_id_2, ...],
         "partition_1": [module_id_3, module_id_4, ...],
         ...
       },
       "boundary_modules": [...],
       "negotiation_history": [...]
     }
     ```

2. **阶段2：分区方案转换为OpenRoad约束**（关键步骤）
   - **基于现有OpenRoad成功案例**，将分区方案转换为OpenRoad可识别的约束
   - 方法：通过DEF文件的`REGIONS`和`GROUPS`部分指定模块到分区的映射
   - **关键**：确保分区约束能被OpenRoad正确识别和应用
   - 实现：`src/utils/openroad_interface.py::convert_partition_to_def_constraints()`
   - **验证**：检查生成的DEF文件，确保REGIONS和GROUPS分配正确
   
   **同时生成partition netlist**：
   - 根据partition_scheme提取每个partition的模块，生成独立的Verilog文件
   - 保存位置：`results/ispd2015/design_name/`（与log、layout.def同一目录）
   - 文件命名：`{partition_id}_{timestamp}.v`（使用时间戳区分版本，避免覆盖）
   - 同时保存：`partition_scheme_{timestamp}.json`（包含分区方案和一致性验证报告）
   - 实现：`src/utils/openroad_interface.py::save_partition_netlists()`
   - **一致性验证**：自动验证partition netlist与floorplan_with_partition.def中的分区信息一致
     - 验证方法：比较DEF文件中GROUPS部分的组件列表与netlist中模块对应的组件列表
     - 验证结果保存在`partition_scheme_{timestamp}.json`的`consistency_report`字段中
     - 实现：`src/utils/openroad_interface.py::_verify_partition_consistency()`

3. **阶段3：OpenRoad布局生成**（使用现有成功案例的流程）
   - **基于现有OpenRoad成功案例**，使用相同的TCL脚本模板和参数
   - 输入：
     - LEF文件（tech.lef, cells.lef）- ISPD 2015提供
     - DEF文件（floorplan.def）- ISPD 2015提供（已添加分区约束）
     - Verilog网表（design.v）- ISPD 2015提供
   - OpenRoad脚本（参考现有成功案例）：
     ```tcl
     read_lef tech.lef
     read_lef cells.lef
     read_def floorplan_with_partition.def  # 包含ChipMASRAG分区约束
     read_verilog design.v
     place_design  # OpenRoad根据分区约束进行布局
     # 使用OpenRoad API提取HPWL（参考现有成功案例的API调用方式）
     ```
   - **关键**：确保OpenRoad能正确应用分区约束，生成符合约束的布局
   - 输出：最终布局DEF文件和HPWL值
   - 实现：`src/utils/openroad_interface.py::generate_layout_with_partition()`

4. **阶段4：HPWL和边界代价分析**（验证分区方案有效性）
   - 从OpenRoad输出中提取HPWL值（使用现有成功案例的解析方法）
   - 从DEF文件分析跨分区连接
   - 计算各分区内部HPWL（排除跨分区连接）
   - 计算边界代价：$\text{BC} = \frac{\text{HPWL}_{\text{partitioned}} - \sum_{i=1}^{k} \text{HPWL}_i}{\sum_{i=1}^{k} \text{HPWL}_i} \times 100\%$
   - **关键**：验证分区方案的有效性，证明好的分区方案产生更好的HPWL
   - 实现：`src/utils/openroad_interface.py::calculate_hpwl_and_boundary_cost()`

**如何跑出预期结果**：

1. **确保分区约束正确应用**：
   - 验证DEF文件中的REGIONS和COMPONENTS分配正确
   - 检查OpenRoad日志，确认分区约束被识别
   - 对比有约束 vs 无约束的布局结果

2. **确保OpenRoad参数一致**：
   - 使用相同的OpenRoad版本和参数（参考现有成功案例）
   - 确保所有对比实验使用相同的OpenRoad配置
   - 记录所有OpenRoad参数，确保可复现

3. **验证分区方案影响布局质量**：
   - 对比ChipMASRAG分区方案 vs 随机分区 vs 几何分区的最终HPWL
   - 证明ChipMASRAG分区方案产生的HPWL更优（目标：提升>15%）
   - 分析边界代价与最终HPWL的相关性（目标：R² > 0.7）

**关键方法**：

- `convert_partition_to_def_constraints(partition_scheme, design_file)`: 将ChipMASRAG分区方案转换为OpenRoad可用的DEF约束
- `save_partition_netlists(partition_scheme, design_dir, output_dir, timestamp)`: 保存每个partition的netlist（Verilog文件）
- `_verify_partition_consistency(...)`: 验证partition netlist与floorplan_with_partition.def中的分区信息一致性
- `generate_layout_with_partition(partition_scheme, design_file)`: 使用OpenRoad根据分区方案生成布局
- `calculate_hpwl(layout_def_file)`: 从OpenRoad输出中提取HPWL值
- `calculate_partition_hpwl(layout_def_file, partition_scheme)`: 计算各分区内部HPWL
- `extract_boundary_connections(layout_def_file, partition_scheme)`: 提取跨分区连接

**Partition Netlist生成与一致性验证**：

1. **生成方法**：
   - 输入：`partition_scheme`（分区方案）、`design.v`（原始Verilog网表）
   - 过程：
     - 解析Verilog文件，提取所有模块定义
     - 根据partition_scheme中的module_ids，匹配并提取属于每个partition的模块
     - 为每个partition生成独立的Verilog文件
   - 输出：
     - `{partition_id}_{timestamp}.v`：每个partition的netlist文件
     - `partition_scheme_{timestamp}.json`：分区方案和一致性验证报告
   - 保存位置：`results/ispd2015/design_name/`（与log、layout.def同一目录）

2. **一致性验证方法**：
   - **验证目标**：确保partition netlist中的模块对应的组件，确实在`floorplan_with_partition.def`中该partition的GROUPS部分
   - **验证步骤**：
     1. 读取`floorplan_with_partition.def`中的GROUPS部分，提取每个分区的组件列表
     2. 从partition_scheme和Verilog模块构建模块到组件的映射（与`convert_partition_to_def_constraints`中的逻辑一致）
     3. 对于每个partition：
        - 获取该partition的netlist中的模块对应的组件集合
        - 获取DEF文件中该partition的GROUPS中的组件集合
        - 验证：netlist中的组件应该在DEF的GROUPS中（允许DEF中有额外组件，但不允许netlist中有缺失）
   - **验证结果**：
     - 保存在`partition_scheme_{timestamp}.json`的`consistency_report`字段中
     - 包含每个partition的验证结果：组件数量、缺失组件、额外组件、一致性状态
     - 如果发现不一致，会记录警告信息，但不影响主流程

3. **一致性保证机制**：
   - **共同数据源**：partition_scheme是唯一的来源，DEF和netlist都基于它生成
   - **相同的映射逻辑**：DEF生成和netlist生成使用相同的模块到组件映射规则
   - **自动验证**：每次生成partition netlist时自动执行一致性验证
   - **验证报告**：验证结果保存在JSON文件中，便于事后检查和调试

4. **文件组织**：
   ```
   results/ispd2015/design_name/
   ├── layout_{timestamp}.def              # OpenRoad生成的布局DEF文件
   ├── partition_0_{timestamp}.v           # Partition 0的netlist
   ├── partition_1_{timestamp}.v           # Partition 1的netlist
   ├── partition_2_{timestamp}.v           # Partition 2的netlist
   ├── partition_3_{timestamp}.v           # Partition 3的netlist
   ├── partition_scheme_{timestamp}.json   # 分区方案和一致性验证报告
   └── logs/                               # OpenRoad执行日志
       ├── openroad_stdout_{timestamp}.log
       ├── openroad_stderr_{timestamp}.log
       └── openroad_combined_{timestamp}.log
   ```

**ISPD 2015缺少liberty文件的解决方案**：

1. **问题**：ISPD 2015基准测试只提供LEF、DEF、Verilog文件，没有liberty（.lib）文件
2. **影响**：
   - OpenRoad的partition management功能需要liberty文件进行时序分析
   - 但OpenRoad的placement功能**不需要**liberty文件，只需要LEF和DEF即可
3. **解决方案**：
   - **不使用OpenRoad的partition management**，而是ChipMASRAG独立生成分区方案
   - **仅使用OpenRoad的placement功能**进行布局验证和HPWL计算
   - **分区经验获取**：从ChipMASRAG自身运行结果中提取，而非从OpenRoad获取
4. **分区经验获取方法**：
   - **自举构建**：ChipMASRAG在ISPD 2015上运行，生成分区方案和布局结果
   - **提取分区经验**：
     - 分区策略：模块到分区的映射（从ChipMASRAG输出的JSON中提取）
     - 边界协商模式：协商历史、迁移决策（从ChipMASRAG运行日志中提取）
     - 质量指标：边界代价、HPWL、运行时间（从OpenRoad布局结果和DEF文件中提取）
   - **知识库构建**：将这些经验存入知识库，供后续设计使用
   - 实现：`scripts/build_kb.py::extract_partition_experience_from_results()`

**实现细节**：

```python
# src/utils/openroad_interface.py
class OpenRoadInterface:
    def convert_partition_to_def_constraints(self, partition_scheme, design_file):
        """将ChipMASRAG分区方案转换为OpenRoad DEF约束"""
        # 1. 读取原始DEF文件
        # 2. 根据partition_scheme创建REGIONS约束
        # 3. 将模块分配到对应REGION
        # 4. 生成新的DEF文件（包含分区约束）
        pass
    
    def generate_layout_with_partition(self, partition_scheme, design_file):
        """使用OpenRoad根据分区方案生成布局"""
        # 1. 转换分区方案为DEF约束
        # 2. 生成OpenRoad TCL脚本
        # 3. 调用OpenRoad执行布局
        # 4. 返回布局DEF文件路径
        pass
    
    def calculate_hpwl(self, layout_def_file):
        """从OpenRoad布局结果中提取HPWL"""
        # 1. 使用OpenRoad API获取HPWL（参考现有成功案例的API调用方式）
        # 2. 或从DEF文件中解析net信息计算HPWL
        # 3. 返回HPWL值（单位：um）
        pass
    
    def calculate_partition_hpwl(self, layout_def_file, partition_scheme):
        """计算各分区内部HPWL（排除跨分区连接）"""
        # 1. 解析DEF文件中的net连接
        # 2. 根据partition_scheme识别跨分区连接
        # 3. 计算各分区内部HPWL
        # 4. 返回分区HPWL字典
        pass
```

## 三、知识库重新构建

### 3.1 知识库要求（每个案例必须包含）

1. **设计特征向量**：规模、类型、模块分布、连接度等
2. **分区策略**：分区方案、模块分配、分区边界
3. **边界协商模式**：边界模块识别、协商目标、协商参数、协商结果
4. **质量指标**：HPWL、边界代价、运行时间、成功率
5. **语义嵌入**：用于语义检索的嵌入向量
6. **策略参数**：Actor-Critic策略参数（可选）

### 3.2 构建策略

**脚本**：`scripts/build_kb.py`

**数据源选择**：

- **优先使用ChipMASRAG自身运行结果（自举构建）**
  - 原因：ISPD 2015没有liberty文件，无法使用OpenRoad的partition management
  - 方法：ChipMASRAG在ISPD 2015上运行，生成分区方案和布局结果，提取分区经验
- 或使用ChipHier实验结果（如果可用）
- 或使用其他布局工具结果（DREAMPlace等）

**构建步骤**：

1. **特征提取**：设计规模、类型、模块特征、连接图特征、约束特征
2. **分区策略提取**：
   - 从ChipMASRAG运行结果中提取分区方案（模块到分区的映射）
   - 提取分区边界信息
   - **注意**：不依赖OpenRoad的partition management，而是从ChipMASRAG自身输出中提取
3. **协商模式提取**：
   - 从ChipMASRAG运行日志中提取协商历史
   - 记录边界模块列表、协商决策（源智能体→目标智能体）、协商参数和结果
   - **注意**：协商模式完全由ChipMASRAG生成，不依赖OpenRoad
4. **质量指标提取**：
   - 从OpenRoad布局结果中提取HPWL（使用OpenRoad API，参考现有成功案例）
   - 计算边界代价（通过分析DEF文件中的跨分区连接）
   - 记录运行时间（ChipMASRAG分区生成时间 + OpenRoad布局时间）
   - **注意**：虽然ISPD 2015没有liberty文件，但OpenRoad的placement功能可以正常工作，只需LEF和DEF文件
5. **嵌入生成**：使用sentence-transformers或BERT生成语义嵌入
6. **质量验证**：检查案例完整性、验证特征有效性、确保检索质量

**ISPD 2015分区经验获取方法**：

由于ISPD 2015没有liberty文件，无法使用OpenRoad的partition management功能，因此：

1. **ChipMASRAG独立生成分区方案**：
   - 不依赖OpenRoad的partition management
   - 通过多智能体协商生成分区方案
   - 输出分区方案JSON文件

2. **OpenRoad仅用于布局验证和HPWL计算**：
   - 将ChipMASRAG的分区方案转换为DEF约束
   - 使用OpenRoad的placement功能生成布局（不需要liberty文件）
   - 从OpenRoad输出中提取HPWL值

3. **分区经验从ChipMASRAG运行结果中提取**：
   - 分区策略：从ChipMASRAG输出的分区方案JSON中提取
   - 协商模式：从ChipMASRAG的运行日志中提取
   - 质量指标：从OpenRoad的布局结果中提取HPWL，从DEF文件中分析边界代价

4. **自举构建流程**：
   ```
   设计1 → ChipMASRAG生成分区方案 → OpenRoad布局验证 → 提取分区经验 → 存入知识库
   设计2 → ChipMASRAG生成分区方案（可使用设计1的经验） → OpenRoad布局验证 → 提取分区经验 → 存入知识库
   ...
   ```

**输出**：`data/knowledge_base/kb_cases.json`（案例数量根据实际构建结果，目标≥300个）

## 四、实验实现

### 4.1 实验运行器 (`experiments/runner.py`)

**功能**：统一实验入口，管理实验生命周期

**关键方法**：

- `run_experiment()`: 运行单个设计
- `run_benchmark()`: 运行ISPD 2015基准测试（16个设计）
- `run_ablation()`: 运行消融实验

### 4.2 评估器 (`experiments/evaluator.py`)

**功能**：计算评估指标

**指标**：

- HPWL（半周线长）
- 成功率（布局是否合法）
- 加速比（KB命中vs未命中）
- 规模无关性（子问题规模、运行时间）

**关键方法**：

- `calculate_boundary_cost()`: 计算边界代价
- `calculate_partition_balance()`: 计算分区平衡度
- `calculate_negotiation_success_rate()`: 计算协商成功率
- `calculate_partition_quality_score()`: 计算分区质量评分
- `calculate_layout_quality_score()`: 计算最终布局质量评分
- `evaluate_partition_layout_correlation()`: 评估分区质量与布局质量的相关性

### 4.3 日志系统 (`experiments/logger.py`)

**功能**：完整记录实验过程

**记录内容**：

- 实验配置（超参数、环境信息）
- 训练过程（损失、奖励、步数）
- 评估结果（HPWL、成功率等）
- 时间戳、随机种子、版本信息

**输出格式**：

- JSON格式结果文件
- 文本格式日志文件
- TensorBoard事件文件（可选）

## 五、实验计划（证明论文有效性的关键实验）

### 5.1 主实验：ISPD 2015基准测试（16个设计）

**目的**：证明ChipMASRAG在解质量和可扩展性上的优势

**设计列表**（16个，位于`data/ispd2015/`）：

- mgc_pci_bridge32_a, mgc_pci_bridge32_b
- mgc_fft_1, mgc_fft_2, mgc_fft_a, mgc_fft_b
- mgc_des_perf_1, mgc_des_perf_a, mgc_des_perf_b
- mgc_edit_dist_a
- mgc_matrix_mult_1, mgc_matrix_mult_a, mgc_matrix_mult_b
- mgc_superblue11_a, mgc_superblue12, mgc_superblue16_a

**每个设计包含的文件**：
- `cells.lef`: 标准单元库定义
- `design.v`: Verilog网表
- `floorplan.def`: 初始floorplan定义
- `tech.lef`: 工艺技术文件
- `placement.constraints`: 布局约束（可选）

**评估指标**：

- HPWL（与DREAMPlace、ChipDRAG公开数据对比）
- 成功率（目标≥80%）
- 运行时间
- 知识库命中率
- 最大可处理规模（目标≥1.2M）

**分区效果展现方法**：

#### 5.1.1 分区质量指标

1. **边界代价（Boundary Cost）**：
   - 定义：$\text{BC} = \frac{\text{HPWL}_{\text{partitioned}} - \sum_{i=1}^{k} \text{HPWL}_i}{\sum_{i=1}^{k} \text{HPWL}_i} \times 100\%$
   - 测量：使用OpenRoad计算完整HPWL和各分区内部HPWL
   - 目标：常规设计<50%，高耦合设计通过协商降低>30%
   - 可视化：绘制边界代价分布图，对比不同分区方法
   - 实现：`experiments/evaluator.py::calculate_boundary_cost()`

2. **跨分区连接数（Cross-Partition Connections）**：
   - 定义：连接多个分区的net数量
   - 测量：统计跨分区连接的net数和引脚数
   - 目标：相比静态分区减少>25%
   - 可视化：绘制跨分区连接热力图，展示分区边界
   - 实现：`src/utils/boundary_analyzer.py::count_cross_partition_connections()`

3. **分区平衡度（Partition Balance）**：
   - 定义：各分区规模的标准差/平均规模
   - 测量：计算各分区的模块数和连接数
   - 目标：平衡度<0.3（各分区规模相近）
   - 可视化：绘制分区规模分布图
   - 实现：`experiments/evaluator.py::calculate_partition_balance()`

4. **协商成功率（Negotiation Success Rate）**：
   - 定义：成功迁移的边界模块数/尝试迁移的边界模块数
   - 测量：记录协商前后的模块分配变化
   - 目标：>80%
   - 可视化：绘制协商过程曲线，展示边界代价随协商迭代的变化
   - 实现：`experiments/evaluator.py::calculate_negotiation_success_rate()`

#### 5.1.2 分区质量与最终布局质量的关系证明

**核心问题**：分区好是否意味着拼凑起来的完整设计布局好？

**答案**：是的，但需要系统化证明。分区质量直接影响最终布局质量，因为：
1. 低边界代价意味着跨分区连接少，最终HPWL更优
2. 平衡的分区使得各分区优化更充分，整体质量提升
3. 合理的模块分配减少布局冲突，提升可布线性

**证明方法**：

1. **相关性分析**：
   - 计算边界代价与最终HPWL的相关系数（目标：R² > 0.7）
   - 计算跨分区连接数与最终HPWL的相关系数（目标：R² > 0.6）
   - 实现：`scripts/analyze_results.py::analyze_partition_quality_correlation()`

2. **对比实验**：
   - **实验A**：ChipMASRAG分区方案 vs 随机分区 vs 几何分区
     - 使用相同的OpenRoad工具和参数生成布局
     - 对比最终HPWL
     - 证明：ChipMASRAG分区方案产生的最终HPWL更优（目标：提升>15%）
   - **实验B**：有协商 vs 无协商
     - 使用相同的OpenRoad工具和参数生成布局
     - 对比最终HPWL和边界代价
     - 证明：协商优化边界代价，最终HPWL提升>10%

3. **可视化展现**：
   - **分区可视化**：
     - 绘制分区布局图，用不同颜色标识各分区
     - 标注边界模块和跨分区连接
     - 实现：`src/utils/visualization.py::visualize_partition()`
   - **边界代价可视化**：
     - 绘制边界代价热力图，展示各分区对之间的边界代价
     - 绘制协商前后边界代价对比图
     - 实现：`src/utils/visualization.py::visualize_boundary_cost()`
   - **最终布局可视化**：
     - 使用OpenRoad生成布局图
     - 标注分区边界和跨分区连接
     - 对比不同分区方法的最终布局
     - 实现：`src/utils/visualization.py::visualize_final_layout()`

4. **定量分析**：
   - **分区质量评分**：
     - 综合边界代价、跨分区连接数、分区平衡度
     - 公式：$\text{Partition Quality} = w_1 \cdot (1 - \text{BC}/100) + w_2 \cdot (1 - \text{CPC}/\text{Total}) + w_3 \cdot (1 - \text{Balance})$
     - 其中$w_1=0.5, w_2=0.3, w_3=0.2$
     - 实现：`experiments/evaluator.py::calculate_partition_quality_score()`
   - **最终布局质量评分**：
     - 基于HPWL、时序、可布线性
     - 公式：$\text{Layout Quality} = f(\text{HPWL}, \text{Timing}, \text{Routability})$
     - 实现：`experiments/evaluator.py::calculate_layout_quality_score()`
   - **相关性验证**：
     - 计算分区质量评分与最终布局质量评分的相关系数
     - 目标：R² > 0.75，证明强相关性
     - 实现：`experiments/evaluator.py::evaluate_partition_layout_correlation()`

5. **案例研究**：
   - 选择3-5个代表性设计（不同边界代价水平）
   - 详细分析分区方案如何影响最终布局
   - 展示协商过程如何改善分区质量
   - 实现：`scripts/analyze_results.py::case_study_partition_effect()`

**实验流程**：

1. **分区生成**：
   - ChipMASRAG生成分区方案（模块到分区的映射）
   - 记录分区质量指标（边界代价、跨分区连接数等）
   - 可视化分区布局

2. **布局生成**：
   - 使用OpenRoad根据分区方案生成详细布局
   - 使用相同的OpenRoad工具和参数（确保公平对比）
   - 记录最终HPWL和其他质量指标

3. **质量评估**：
   - 计算分区质量评分
   - 计算最终布局质量评分
   - 分析分区质量与布局质量的相关性

4. **对比分析**：
   - 对比不同分区方法的最终布局质量
   - 分析协商对分区质量和布局质量的改善
   - 可视化展现分区效果

**证明点**：
- ChipMASRAG在规模扩展能力上优于ChipDRAG（1.2M vs ~200K）
- ChipMASRAG在HPWL质量上优于或接近DREAMPlace
- **分区质量与最终布局质量强相关（R² > 0.75）**
- **ChipMASRAG的分区方案产生的最终布局质量优于静态分区方法（HPWL提升>15%）**
- **协商优化显著改善分区质量和最终布局质量（边界代价降低>30%，HPWL提升>10%）**

### 5.2 知识库复用效果实验（核心证明点1）

**目的**：证明RAG检索机制的有效性，知识驱动优化的加速效果

**设计**：选择3-5个不同规模的代表性设计

- 小规模：mgc_pci_bridge32_a (29K)
- 中规模：mgc_fft_1 (32K), mgc_des_perf_b (113K)
- 大规模：mgc_matrix_mult_1 (155K)

**实验设计**：

- 对比：有KB vs 无KB（禁用RAG检索）
- 指标：分区计算时间、总运行时间、加速比
- 目标：平均加速比≥60倍

**证明点**：RAG检索能显著加速优化过程，验证知识驱动优化的有效性

### 5.3 规模无关性分析（核心证明点2）

**目的**：证明双重规模无关机制（层次化分解+多智能体并行）

**实验设计**：

- 选择5-8个不同规模的设计（28K-1.2M）
- 记录：原始规模、子问题数量、平均子问题规模、运行时间
- 分析：子问题规模比例（目标1/35）、运行时间vs规模关系（验证线性）

**指标**：

- 子问题规模/原始规模（目标≤1/35）
- 运行时间 = O(n)（线性关系，而非指数）
- 训练时间与设计规模无关（多智能体并行效果）

**证明点**：通过层次化分解和多智能体并行，实现从指数复杂度到多项式复杂度的转换

### 5.4 消融实验（核心证明点3）

**目的**：证明各核心组件的必要性和贡献

**实验设计**（在代表性设计上，如mgc_matrix_mult_1）：

1. **完整ChipMASRAG**（基线）
2. **无RAG检索**：禁用RAG，仅使用动态规划
3. **无边界协商**：禁用知识驱动的边界协商
4. **无协调者**：各分区智能体独立检索（无统一协调）
5. **单智能体**：不使用多智能体架构

**评估指标**：

- HPWL（质量损失百分比）
- 边界代价（跨分区连接比例）
- 运行时间
- 训练时间

**证明点**：

- RAG检索贡献：HPWL增加<10%，时间增加<20%
- 边界协商贡献：HPWL增加<15%
- 协调者贡献：HPWL增加<5%
- 多智能体架构必要性：单智能体性能显著下降

### 5.5 知识驱动边界协商效果实验（核心证明点4）

**目的**：证明知识驱动的边界协商协议优于传统协商，重点证明多智能体协商分区相比现有方法的优势

**核心创新点**：知识驱动的多智能体协商分区

**多智能体协商要解决的核心问题**：

1. **边界代价优化问题**：
   - **问题**：静态分区方法（如OpenROAD par、几何划分）在分区边界处产生大量跨分区连接，导致边界代价高（>150%甚至>250%）
   - **解决**：通过多智能体动态协商，识别高代价边界模块，参考历史协商模式，将模块迁移到更合适的分区，减少跨分区连接
   - **目标**：将边界代价降低>30%（常规设计）或>40%（极端高耦合设计）

2. **跨分区连接最小化问题**：
   - **问题**：传统方法无法动态调整分区边界，导致跨分区连接数过多，影响最终HPWL
   - **解决**：智能体间通过协商协议，动态迁移边界模块，最小化跨分区连接数
   - **目标**：跨分区连接数减少>25%

3. **全局一致性保证问题**：
   - **问题**：各分区独立优化可能导致全局不一致，边界模块分配不合理
   - **解决**：协调者智能体统一管理RAG检索结果，各分区智能体基于共享知识进行协商，保证全局一致性
   - **目标**：协商成功率>80%，全局HPWL提升>15%

4. **知识复用与泛化问题**：
   - **问题**：传统方法无法利用历史设计经验，每次都要从头优化
   - **解决**：通过RAG检索相似历史案例的协商模式，指导当前设计的边界协商
   - **目标**：知识驱动协商比传统协商收敛快>40%，边界代价降低>20%

5. **规模扩展性问题**：
   - **问题**：单智能体方法无法并行处理大规模设计，训练时间随规模线性增长
   - **解决**：多智能体并行协商，每个智能体负责一个分区，训练时间与设计规模无关
   - **目标**：训练时间不随设计规模线性增长，可处理1.2M+规模设计

**与现有分区方法对比**：

1. **OpenROAD par工具**（https://openroad.readthedocs.io/en/latest/main/src/par/README.html）

   - 方法：基于几何划分和连接度划分的静态分区
   - 局限：缺乏历史知识复用，无法利用相似设计的成功经验；边界优化有限
   - ChipMASRAG优势：
     - 通过RAG检索复用历史协商模式
     - 多智能体动态协商，而非静态划分
     - 知识驱动的边界优化，而非仅基于当前状态
     - 专门针对边界代价优化的协商协议

2. **K-SpecPart**（Bustany et al., 2023, arXiv:2305.06167）

   - **方法**：基于监督式谱框架的超图多路划分
     - 使用机器学习模型（需要训练数据）改进分区解
     - 基于谱图理论，利用超图的拉普拉斯矩阵特征
     - 监督学习框架，需要标注的训练数据
   - **局限**：
     - 需要训练数据，对未见过的设计类型泛化能力有限
     - 主要关注划分质量（cut size、平衡度），边界代价优化次要
     - 静态划分，一次性生成分区方案
     - 需要为不同规模设计训练不同模型
   - **ChipMASRAG优势**：
     - **知识驱动vs监督学习**：无需预训练，通过RAG检索动态适配，支持知识库持续更新
     - **多智能体协商vs静态划分**：动态协商优化边界模块分配，而非一次性划分
     - **边界代价优化**：专门针对边界代价的协商机制，K-SpecPart主要关注cut size
     - **可扩展性**：多智能体并行，训练时间与设计规模无关；K-SpecPart需要为不同规模训练模型
     - **知识复用**：历史经验复用，加速优化过程（知识库命中时加速>60倍）

3. **Constraints-Driven General Partitioning**（Bustany et al., 2023, ICCAD 2023）

   - **方法**：约束驱动的通用划分工具
     - 支持多种约束类型（时序、功耗、面积等）
     - 基于约束满足的划分算法
     - 通用工具，适用于多种VLSI物理设计场景
   - **局限**：
     - 主要关注约束满足，对边界代价优化有限
     - 静态划分，缺乏动态协商
     - 无法利用历史设计经验
     - 边界优化次要，主要关注约束满足
   - **ChipMASRAG优势**：
     - **知识驱动vs约束驱动**：通过RAG检索历史协商模式，而非仅基于约束规则
     - **动态协商vs静态划分**：多智能体协商优化边界，而非一次性划分
     - **边界代价优化**：专门针对边界代价的协商协议，Constraints-Driven主要关注约束满足
     - **知识复用**：历史经验复用，加速优化过程
     - **多智能体协作**：多智能体并行协商，提升效率

4. **Pin vs Block关系理论**（Landman & Russo, 1971, IEEE Trans. Computers）

   - **理论**：经典的引脚-模块关系理论
     - 理论模型：$P = 2.5 \times N^{0.5}$（P为引脚数，N为模块数）
     - 分析分区对引脚数的影响
     - 静态理论模型，用于分析分区质量
   - **局限**：
     - 静态理论模型，未考虑动态优化
     - 未涉及历史知识复用
     - 仅理论分析，未提供实际优化方法
     - 未考虑边界代价的动态优化
   - **ChipMASRAG优势**：
     - **动态协商vs静态理论**：动态协商优化引脚分配，而非仅基于理论模型
     - **知识驱动**：考虑历史案例的协商模式，而非仅基于理论公式
     - **多智能体协作**：多智能体协作优化边界连接，而非单一优化器
     - **实际应用**：针对实际布局问题，而非仅理论分析
     - **边界代价优化**：专门针对边界代价的协商协议，理论模型未涉及

**基线分区方法总结**（备用参考，优先使用 K-SpecPart）：

根据 K-SpecPart 论文和超图分区研究，常见的基线分区方法包括：

1. **hMETIS**（业界标准）：
   - 多级（multilevel）超图分区器
   - 粗化→初始分区→细化（FM 算法）
   - K-SpecPart 使用 hMETIS 作为 hint

2. **谱聚类**（Spectral Clustering）：
   - 基于图 Laplacian 矩阵特征向量
   - 考虑全局结构
   - 适合中小规模设计

3. **连通性感知贪心**（Greedy with Connectivity）：
   - BFS 扩展 + 连接性启发式
   - 速度快，适合大规模设计
   - 适合快速基线测试

4. **随机分区**（Random）：
   - 仅用于对比基线，不推荐实际使用

**当前实验方案：优先使用 K-SpecPart 公开代码**

根据用户建议，优先使用 K-SpecPart 的公开实现作为主要基线对比，因为：
- ✅ 代码已公开且维护良好
- ✅ 论文方法明确，结果可复现
- ✅ 可以直接与 ChipMASRAG 进行公平对比
- ✅ 能够获取 legalized HPWL（通过 OpenROAD）

**对比实验可行性分析**：

1. **K-SpecPart (Bustany et al., 2023, arXiv:2305.06167)**：
   - **代码可用性**：✅ **代码已公开**
     - GitHub仓库：https://github.com/TILOS-AI-Institute/HypergraphPartitioning
     - 包含K-SpecPart完整实现和benchmark
     - 提供Titan23 benchmarks和解决方案
     - **K-SpecPart 输出格式**：`.part.K` 文件，每行一个顶点的分区ID
   - **数据集**：
     - K-SpecPart 使用超图格式（.hgr）：
       ```
       <num_hyperedges> <num_vertices> [fmt]
       <vertex_list_for_hyperedge_1>
       <vertex_list_for_hyperedge_2>
       ...
       ```
     - ISPD 2015 可以转换为 .hgr 格式（从 DEF/Verilog 提取超图）
   - **对比策略**：
     - **优先方案**：在 ISPD 2015 上运行 K-SpecPart，使用 OpenROAD 生成布局获取 legalized HPWL
     - **实验流程**：详见下文"K-SpecPart 与 OpenROAD 衔接方案"
     - **重点**：边界代价、知识复用能力、可扩展性（无需预训练vs需要训练）

2. **Constraints-Driven General Partitioning (Bustany et al., 2023, ICCAD 2023)**：
   - **代码可用性**：✅ **可能有公开工具**
     - 可能集成在OpenROAD中或作为独立工具
     - 需要检查：https://github.com/ABKGroup/TritonPart（TritonPart相关）
     - 需要检查OpenROAD相关仓库
   - **数据集**：需要确认是否使用ISPD 2015或可用的公开数据集
   - **对比策略**：
     - **优先**：如果工具可用，运行对比实验
     - **备选**：如果工具不可用，引用论文数据，重点对比动态协商vs静态划分
     - **重点**：边界代价、动态协商vs静态划分、知识复用能力

3. **Pin vs Block理论 (Landman & Russo, 1971)**：
   - **公开结果**：经典理论论文，无公开代码
   - **数据集**：理论模型，不依赖特定数据集
   - **对比策略**：
     - 使用理论模型预测边界代价：$P = 2.5 \times N^{0.5}$
     - 在ISPD 2015设计上应用理论模型
     - 对比理论预测与实际布局结果的差异
     - **重点**：证明动态协商优于静态理论模型

**对比实验设计**：

1. **实验设置**：
   - 使用ISPD 2015基准测试（16个设计）
   - 所有方法使用相同的OpenRoad工具和参数生成布局
   - 对比最终HPWL、边界代价、运行时间
   - 实现：`experiments/runner.py::run_comparison_experiment()`

2. **分区方法与OpenROAD衔接的正确方案**（**重要：降低复杂度的核心**）：

### 2.0 关键问题澄清

**❌ 错误方案**（之前的理解）：
```
分区方案 → 添加 REGIONS 约束到完整 DEF → OpenROAD 跑完整设计
```
**问题**：
- 还是跑完整设计，**规模没有降低**
- 分区约束反而限制优化空间
- **没有体现"降低复杂度"的论文核心目标**

**✅ 正确方案**（与论文一致）：
```
分区方案 → 各分区单独跑 OpenROAD → 拼接结果 → （可选）全局优化
   ↓              ↓                    ↓            ↓
降低规模    并行处理（规模小）    边界代价分析   最终 HPWL
```
**核心思想**：
- ✅ **每个分区单独优化**（规模降低到 1/K）
- ✅ **并行处理**（各分区独立，可并行）
- ✅ **拼接评估**（衡量分区质量）

### 2.0.1 物理位置映射策略

**关键决策**：分区ID到物理位置的映射顺序

**K-SpecPart的特点**：
- 只输出逻辑分区ID（0,1,2,3），不考虑物理位置
- 优化目标：minimize cut size（逻辑层面）
- **物理位置映射是后处理**

**ChipMASRAG的实现**：
- **采用两阶段方法**：
  1. **阶段1**：Agent协商逻辑分区（不考虑物理位置）
  2. **阶段2**：基于连接性优化物理位置映射
- 好处：
  - Agent只关注逻辑分组，降低复杂度
  - RAG检索的是逻辑分组策略（不同设计die size不同）
  - 与K-SpecPart对等（都是逻辑分区+物理映射）

**统一的物理位置映射算法**（K-SpecPart和ChipMASRAG共用）：

```python
def optimize_physical_layout(logical_partitions, connectivity_matrix):
    """
    基于分区间连接性优化物理位置映射
    
    目标：连接数多的分区应该物理相邻
    
    策略：
    1. 构建分区间连接矩阵
       connectivity_matrix[(i,j)] = 分区i和j之间的跨分区连接数
    
    2. 定义物理位置的相邻关系
       2x2网格：
       +-------+-------+
       |   2   |   3   |  (上)
       +-------+-------+
       |   0   |   1   |  (下)
       +-------+-------+
       相邻对：(0,1), (0,2), (1,3), (2,3)
       对角：(0,3), (1,2) - 不相邻
    
    3. 优化目标：最小化 Σ(connectivity[i,j] * distance[pos_i, pos_j])
       即：连接多的分区，物理距离应该小
    
    4. 求解方法：贪心算法或ILP
    """
    pass
```

**公平对比保证**：
- ✅ K-SpecPart和ChipMASRAG使用**相同的物理位置映射算法**
- ✅ 对比差异**纯粹来自逻辑分区质量**
- ✅ 物理映射算法保持一致，更好地比较分区方法的差异

### 2.0.2 分区数量的决定

**K-SpecPart**：
- 用户预先指定（作为输入参数）
- 论文测试：K=2, 3, 4

**ChipMASRAG**：
- **基线实验采用固定K=4**
- 理由：
  1. 多智能体架构（4个Agent）
  2. 经典配置（2x2网格）
  3. 与K-SpecPart公平对比（相同K）
  4. 简化实现和训练
- 未来扩展：
  - 动态K：根据设计规模决定（target_partition_size ≈ 35K）
  - 递归分区：层次化分解

**分区数量的权衡**：
- K太小（K=2）：每个分区仍然很大，规模降低不明显
- K适中（K=4）：平衡了规模降低和边界代价
- K太大（K=16）：分区太多，边界代价可能很高

### 2.0.3 分区方法有效性的衡量

**1. 规模降低效果**：
```python
avg_partition_size = sum(len(part) for part in partitions) / K
scale_reduction = avg_partition_size / len(all_components)
# 目标：scale_reduction ≤ 1/35（论文目标）
```

**2. 边界代价（Boundary Cost）**：
```python
BC = (HPWL_stitched - sum(HPWL_partition_i)) / sum(HPWL_partition_i) × 100%
```
- HPWL_stitched：拼接后完整设计的HPWL
- HPWL_partition_i：第i个分区内部的HPWL
- 目标：BC < 50%（常规设计），通过协商降低>30%

**3. 最终布局质量对比**：
- 直接方法：HPWL_direct（跑完整设计）
- 分区方法（无全局优化）：HPWL_stitched
- 分区方法（有全局优化）：HPWL_final

**4. 运行时间**：
```
直接方法 = T_direct

分区方法 = T_partition + max(T_partition_i) + T_stitch + T_global
         = T_partition + T_max_partition + T_global
```
- T_max_partition：最慢分区的时间（**并行时只看最慢的**）
- 加速比 = T_direct / (T_partition + T_max_partition + T_global)

**5. 可扩展性**：
- 最大可处理规模：1.2M+ 组件
- 子问题规模保持稳定（≈35K，不随原设计规模增长）

2. **K-SpecPart 与 OpenROAD 衔接方案**（**优先实验方案**）：

**GitHub 仓库**：https://github.com/TILOS-AI-Institute/HypergraphPartitioning

**核心思路**（正确版本）：
```
K-SpecPart 逻辑分区 → 基于连接性优化物理位置 → 各分区单独跑 OpenROAD → 拼接 → 评估
```

### 2.1 完整实验流程

**阶段1：ISPD 2015 转换为超图格式**

K-SpecPart 需要超图格式（.hgr）输入：
```
<num_hyperedges> <num_vertices> [fmt]
<vertex_list_for_hyperedge_1>
<vertex_list_for_hyperedge_2>
...
```

转换方法：
- 输入：ISPD 2015 的 DEF 文件（包含 components 和 nets）
- 提取：每个 component 作为顶点，每个 net 作为超边
- 输出：`.hgr` 格式文件
- 实现：`scripts/convert_ispd2015_to_hgr.py`

```python
def convert_ispd2015_to_hgr(def_file, output_hgr):
    """
    将 ISPD 2015 DEF 文件转换为 K-SpecPart 可用的超图格式
    
    输入：DEF 文件（包含 COMPONENTS 和 NETS）
    输出：.hgr 文件
    """
    # 1. 解析 DEF 文件
    parser = DEFParser(def_file)
    parser.parse()
    
    # 2. 提取超图信息
    vertices = list(parser.components.keys())  # 每个 component 是一个顶点
    vertex_to_id = {v: i+1 for i, v in enumerate(vertices)}  # K-SpecPart 使用 1-based index
    
    hyperedges = []
    for net_name, net_info in parser.nets.items():
        # 提取 net 连接的 components
        connected_vertices = []
        for conn in net_info.get('connections', []):
            comp = conn.get('comp')
            if comp and comp in vertex_to_id:
                connected_vertices.append(vertex_to_id[comp])
        if len(connected_vertices) >= 2:  # 只保留连接 2 个及以上顶点的超边
            hyperedges.append(connected_vertices)
    
    # 3. 写入 .hgr 文件
    with open(output_hgr, 'w') as f:
        # 第一行：<num_hyperedges> <num_vertices>
        f.write(f"{len(hyperedges)} {len(vertices)}\n")
        # 每行一个超边：顶点列表（空格分隔）
        for hedge in hyperedges:
            f.write(" ".join(map(str, hedge)) + "\n")
    
    return vertex_to_id  # 返回映射关系，用于后续结果转换
```

**阶段2：运行 K-SpecPart**

使用 K-SpecPart GitHub 代码运行分区：
```bash
# 克隆 K-SpecPart 代码
cd ~/chipmas
git clone https://github.com/TILOS-AI-Institute/HypergraphPartitioning.git

# 运行 K-SpecPart（参考其 README）
cd HypergraphPartitioning/K_SpecPart
# 假设命令格式为：
julia run_kspecpart.jl <input.hgr> <num_partitions> <imbalance> <output.part>

# 示例：对 mgc_fft_1 进行 4-way 分区，允许 5% 不平衡
julia run_kspecpart.jl ../../data/ispd2015/mgc_fft_1.hgr 4 0.05 ../../results/kspecpart/mgc_fft_1.part.4
```

K-SpecPart 输出格式（`.part.K` 文件）：
```
0
1
0
2
1
...
```
每行一个数字，表示对应顶点的分区ID（0-based）

**阶段3：层级化改造 + 功能验证（关键！分区时同步完成）**

**核心思想**：分区完成后，立即进行层级化改造，将扁平网表转换为层次化网表（顶层+分区），并通过Formal验证确保功能等价。

```python
def perform_hierarchical_transformation(design, partition_scheme):
    """
    层级化改造（K-SpecPart和ChipMASRAG共用）
    
    输入：
    - design: 原始扁平设计
    - partition_scheme: {component_name: partition_id}
      （来自K-SpecPart或ChipMASRAG，格式统一）
    
    输出：
    - top_netlist: 顶层网表（纯胶水代码）
    - partition_netlists: 各分区网表（提取的子设计）
    - verification_passed: 功能等价性验证结果
    """
    
    # ===== Step 1: 分析跨分区连接 =====
    print("Step 1: 分析跨分区连接...")
    boundary_nets = []
    partition_interfaces = {i: [] for i in range(K)}
    
    for net in design.nets:
        # 找出该net连接的所有分区
        connected_partitions = set()
        pins_per_partition = {}
        
        for pin in net.pins:
            comp = pin.component
            part_id = partition_scheme[comp]
            connected_partitions.add(part_id)
            
            if part_id not in pins_per_partition:
                pins_per_partition[part_id] = []
            pins_per_partition[part_id].append(pin)
        
        # 如果连接多个分区，这是一个边界net
        if len(connected_partitions) > 1:
            boundary_nets.append({
                'net': net,
                'connected_partitions': connected_partitions,
                'pins_per_partition': pins_per_partition
            })
            
            # 为每个相关分区创建接口端口
            for part_id in connected_partitions:
                interface_port = create_interface_port(
                    net,
                    part_id,
                    pins_per_partition[part_id]
                )
                partition_interfaces[part_id].append(interface_port)
    
    print(f"  发现 {len(boundary_nets)} 个跨分区net")
    
    # ===== Step 2: 提取各分区网表 =====
    print("Step 2: 提取各分区网表...")
    partition_netlists = {}
    
    for part_id in range(K):
        # 找出该分区的所有组件
        partition_components = [
            comp for comp, pid in partition_scheme.items()
            if pid == part_id
        ]
        
        # 生成分区网表
        verilog_lines = []
        module_name = f"partition_{part_id}"
        verilog_lines.append(f"module {module_name} (")
        
        # 端口列表
        ports = []
        
        # 2.1 顶层I/O端口（如果该分区连接到顶层）
        top_io_ports = get_partition_top_io_ports(
            design, 
            part_id, 
            partition_scheme
        )
        for port in top_io_ports:
            ports.append(f"    {port.direction} [{port.width-1}:0] {port.name}")
        
        # 2.2 分区间接口端口
        for bnet in boundary_nets:
            if part_id in bnet['connected_partitions']:
                direction = infer_port_direction(
                    bnet['net'],
                    part_id,
                    bnet['pins_per_partition'][part_id]
                )
                port_name = f"iface_{bnet['net'].name}"
                width = bnet['net'].width
                ports.append(f"    {direction} [{width-1}:0] {port_name}")
        
        verilog_lines.append(",\n".join(ports))
        verilog_lines.append(");\n")
        
        # 2.3 内部信号声明
        internal_nets = get_internal_nets(
            design, 
            part_id, 
            partition_scheme, 
            boundary_nets
        )
        for net in internal_nets:
            verilog_lines.append(f"    wire [{net.width-1}:0] {net.name};")
        verilog_lines.append("")
        
        # 2.4 组件实例化（从原始设计复制）
        for comp in partition_components:
            inst = design.get_component_instance(comp)
            verilog_lines.append(f"    {inst.cell_type} {comp} (")
            
            connections = []
            for pin_name, net in inst.pin_connections.items():
                if is_boundary_net(net, boundary_nets):
                    # 跨分区net → 连接到module端口
                    signal = f"iface_{net.name}"
                else:
                    # 内部net → 保持原名
                    signal = net.name
                connections.append(f"        .{pin_name}({signal})")
            
            verilog_lines.append(",\n".join(connections))
            verilog_lines.append("    );\n")
        
        verilog_lines.append("endmodule\n")
        partition_netlists[part_id] = "\n".join(verilog_lines)
        
        print(f"  ✅ partition_{part_id}: {len(partition_components)} 组件")
    
    # ===== Step 3: 生成顶层网表（集成）=====
    print("Step 3: 生成顶层网表（集成分区）...")
    verilog_lines = []
    
    # 3.1 顶层module定义
    verilog_lines.append(f"module {design.top_module_name} (")
    ports = [
        f"    {p.direction} [{p.width-1}:0] {p.name}"
        for p in design.top_ports
    ]
    verilog_lines.append(",\n".join(ports))
    verilog_lines.append(");\n")
    
    # 3.2 内部信号声明（跨分区wire）
    for bnet in boundary_nets:
        net = bnet['net']
        verilog_lines.append(
            f"    wire [{net.width-1}:0] inter_partition_{net.name};"
        )
    verilog_lines.append("")
    
    # 3.3 实例化各分区module
    for part_id in range(K):
        module_name = f"partition_{part_id}"
        instance_name = f"u_{module_name}"
        
        verilog_lines.append(f"    {module_name} {instance_name} (")
        
        # 解析分区module端口
        module_info = parse_module_ports(partition_netlists[part_id])
        
        # 连接端口
        connections = []
        for port_name, port_info in module_info.ports.items():
            if port_name.startswith("iface_"):
                # 分区间接口 → 连接到内部wire
                net_name = port_name.replace("iface_", "")
                signal = f"inter_partition_{net_name}"
            else:
                # 顶层I/O → 直连
                signal = port_name
            connections.append(f"        .{port_name}({signal})")
        
        verilog_lines.append(",\n".join(connections))
        verilog_lines.append("    );\n")
    
    verilog_lines.append("endmodule\n")
    top_netlist = "\n".join(verilog_lines)
    
    print(f"  ✅ 顶层网表生成完成")
    
    # ===== Step 4: 功能等价性验证（Formal）=====
    print("Step 4: 功能等价性验证...")
    verification_passed = verify_functional_equivalence(
        original_flat_netlist=design.verilog,
        hierarchical_netlists={
            'top': top_netlist,
            'partitions': partition_netlists
        }
    )
    
    if not verification_passed:
        raise ValueError("❌ 层级化改造失败：功能不等价！")
    
    print("✅ 功能等价性验证通过")
    
    # ===== Step 5: 保存结果 =====
    save_hierarchical_netlists(
        top_netlist,
        partition_netlists,
        output_dir="hierarchical_netlists"
    )
    
    return {
        'top_netlist': top_netlist,
        'partition_netlists': partition_netlists,
        'boundary_nets': boundary_nets,
        'verification_passed': verification_passed
    }

def verify_functional_equivalence(original_flat_netlist, hierarchical_netlists):
    """
    使用Yosys进行Formal验证
    
    验证：原始扁平网表 ≡ (顶层网表 + 分区网表)
    """
    temp_dir = create_temp_verification_dir()
    
    # 保存网表文件
    original_file = save_netlist(temp_dir, "original.v", original_flat_netlist)
    top_file = save_netlist(temp_dir, "top.v", hierarchical_netlists['top'])
    partition_files = []
    for part_id, netlist in hierarchical_netlists['partitions'].items():
        f = save_netlist(temp_dir, f"partition_{part_id}.v", netlist)
        partition_files.append(f)
    
    # Yosys验证脚本
    yosys_script = f"""
# 读取原始设计（golden）
read_verilog {original_file}
hierarchy -check -auto-top
proc; opt; memory; opt; clean
rename -top golden

# 读取层级化设计（revised）
read_verilog {top_file}
{chr(10).join(f"read_verilog {f}" for f in partition_files)}
hierarchy -check -auto-top
proc; opt; memory; opt; clean
rename -top revised

# 形式等价性检查
equiv_make golden revised equiv
hierarchy -check
equiv_simple -seq 5
equiv_induct -seq 5
equiv_status -assert
"""
    
    script_file = os.path.join(temp_dir, "verify.ys")
    with open(script_file, 'w') as f:
        f.write(yosys_script)
    
    # 运行Yosys
    result = subprocess.run(
        ["yosys", "-s", script_file],
        capture_output=True,
        text=True,
        cwd=temp_dir
    )
    
    if "Equivalence successfully proven" in result.stdout:
        return True
    else:
        print("❌ Formal验证失败")
        print(result.stdout)
        print(result.stderr)
        return False
```

**阶段4：基于连接性优化物理位置映射**

```python
def optimize_physical_mapping(partition_scheme, boundary_nets):
    """
    优化逻辑分区到物理位置的映射
    
    输入：
    - part_file: K-SpecPart 输出的逻辑分区（.part.4）
    - mapping_file: 顶点映射关系（.mapping.json）
    - def_file: 原始 DEF 文件
    
    输出：
    - physical_mapping: {partition_id: physical_region}
    """
    # 1. 读取逻辑分区
    logical_partitions = read_logical_partitions(part_file, mapping_file)
    
    # 2. 分析分区间连接性
    connectivity_matrix = analyze_partition_connectivity(
        logical_partitions,
        def_file
    )
    # connectivity_matrix[(i,j)] = 分区i和j之间的跨分区连接数
    
    # 3. 优化物理位置映射
    physical_regions = [
        (0, 0, 2500, 2500),           # 位置0：左下
        (2500, 0, 5000, 2500),        # 位置1：右下
        (0, 2500, 2500, 5000),        # 位置2：左上
        (2500, 2500, 5000, 5000)      # 位置3：右上
    ]
    
    physical_mapping = optimize_assignment(
        logical_partitions,
        connectivity_matrix,
        physical_regions
    )
    
    return physical_mapping
```

**阶段5：各分区单独跑OpenROAD**（规模降低，速度快）

**说明**：阶段3已经生成了分区网表，这里直接使用。

```bash
# 对每个分区单独运行OpenROAD（规模降低到1/K）
for partition in partition_0 partition_1 partition_2 partition_3; do
    openroad -no_init -exit <<EOF
    # 读取工艺文件
    read_lef tech.lef
    read_lef cells.lef
    
    # 读取分区网表
    read_verilog ${partition}.v
    link_design ${partition}
    
    # 初始化floorplan（规模缩小到1/K）
    initialize_floorplan -die_area "0 0 2500 2500" ...
    
    # 全局布局（速度快，因为规模小）
    global_placement
    
    # 详细布局
    detailed_placement
    
    # 提取分区内部HPWL
    # 使用OpenROAD API
    
    # 输出分区布局
    write_def ${partition}_layout.def
EOF
done
```

**关键点**：
- ✅ 各分区**独立运行**，可以**并行**
- ✅ 每个分区的die_area是原设计的1/K
- ✅ **运行时间大幅降低**（规模效应）
- ✅ 提取各分区内部HPWL（HPWL_partition_i）

**阶段6：为各分区生成macro LEF**

```python
def generate_partition_macro_lef(part_id, partition_layout, physical_region):
    """
    从分区布局生成abstract LEF（macro定义）
    
    用于顶层OpenROAD，将分区作为宏单元
    """
    lef_content = f"""
VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;

MACRO partition_{part_id}_macro
    CLASS BLOCK ;
    ORIGIN 0 0 ;
    SIZE {physical_region[2]-physical_region[0]} BY {physical_region[3]-physical_region[1]} ;
    SYMMETRY X Y ;
"""
    
    # 从分区布局中提取边界引脚
    parser = DEFParser(partition_layout)
    parser.parse()
    
    # 识别边界引脚（连接到iface_*的引脚）
    boundary_pins = identify_boundary_pins(parser, part_id)
    
    for pin in boundary_pins:
        lef_content += f"""
    PIN {pin.name}
        DIRECTION {pin.direction} ;
        USE SIGNAL ;
        PORT
            LAYER {pin.layer} ;
            RECT {pin.x1} {pin.y1} {pin.x2} {pin.y2} ;
        END
    END {pin.name}
"""
    
    lef_content += "END partition_{part_id}_macro\n"
    lef_content += "END LIBRARY\n"
    
    return lef_content
```

**阶段7：顶层OpenROAD布局（边界代价计算）**

**核心改进**：直接在顶层跑OpenROAD，只对跨分区连接进行布局。

```bash
# 运行OpenROAD顶层布局
openroad -no_init -exit <<EOF
# 1. 读取工艺文件
read_lef tech.lef
read_lef cells.lef

# 2. 读取分区macro LEF
read_lef partition_0_macro.lef
read_lef partition_1_macro.lef
read_lef partition_2_macro.lef
read_lef partition_3_macro.lef

# 3. 读取顶层网表
read_verilog top_level.v
link_design design_top

# 4. 初始化floorplan（完整die size）
initialize_floorplan -die_area "0 0 5000 5000" ...

# 5. 放置macro（各分区，固定位置）
place_macro u_partition_0 0 0 N -fixed
place_macro u_partition_1 2500 0 N -fixed
place_macro u_partition_2 0 2500 N -fixed
place_macro u_partition_3 2500 2500 N -fixed

# 6. 全局布局（只处理顶层连接，macro固定）
global_placement

# 7. 详细布局
detailed_placement

# 8. 提取边界HPWL
# 使用OpenROAD API提取跨分区net的HPWL
# HPWL_boundary = ...

# 9. 输出
write_def top_level_final.def
EOF
```

**边界代价计算（改进方法）**：

```python
def calculate_boundary_cost_improved(partition_layouts, top_level_hpwl):
    """
    边界代价计算（改进版本）
    
    核心思想：
    - 分母：各分区内部HPWL之和（HPWL_internal_total）
    - 分子：顶层OpenROAD计算的跨分区连接HPWL（HPWL_boundary）
    - 边界代价：BC = HPWL_boundary / HPWL_internal_total × 100%
    
    优势：
    ✅ 物理意义清晰：边界代价 = 跨分区连接的额外HPWL
    ✅ Legalized HPWL：顶层OpenROAD给出的是真实可布线HPWL
    ✅ 计算准确：考虑了布线拥塞和绕障
    """
    # Step 1: 提取各分区内部HPWL（从阶段5获得）
    HPWL_internal = {}
    for part_id, layout_file in partition_layouts.items():
        # 从OpenROAD输出或DEF文件提取
        HPWL_internal[part_id] = extract_hpwl_from_layout(layout_file)
    
    HPWL_internal_total = sum(HPWL_internal.values())
    
    # Step 2: 边界HPWL（从顶层OpenROAD获得）
    HPWL_boundary = top_level_hpwl
    
    # Step 3: 边界代价
    BC = (HPWL_boundary / HPWL_internal_total) * 100
    
    return {
        'BC': BC,
        'HPWL_boundary': HPWL_boundary,
        'HPWL_internal_total': HPWL_internal_total,
        'HPWL_per_partition': HPWL_internal,
        'interpretation': interpret_boundary_cost(BC)
    }

def interpret_boundary_cost(BC):
    """
    边界代价的物理意义
    """
    if BC < 0:
        return "负边界代价：全局优化带来额外收益"
    elif BC < 30:
        return "低边界代价：分区非常成功"
    elif BC < 50:
        return "中等边界代价：分区可接受"
    elif BC < 100:
        return "较高边界代价：需要优化"
    else:
        return "高边界代价：分区策略需要改进"
```

**阶段8：（旧的阶段4，已删除，因为网表在阶段3生成）**

**阶段9：拼接评估（可选）**

```python
def generate_partition_netlists(logical_partitions, physical_mapping, design_dir):
    """
    【此函数已合并到阶段3的层级化改造中】
    
    关键：每个分区是一个独立的子设计，规模降低到1/K
    """
    for part_id, components in logical_partitions.items():
        # 1. 提取分区内的模块
        partition_verilog = extract_partition_verilog(
            components,
            design_dir / "design.v"
        )
        
        # 2. 边界信号作为top-level ports
        boundary_signals = identify_boundary_signals(
            part_id,
            logical_partitions,
            connectivity_matrix
        )
        
        # 3. 生成分区的Verilog网表
        save_partition_verilog(
            partition_verilog,
            boundary_signals,
            f"{part_id}.v"
        )
        
        # 4. 生成分区的DEF（缩小的die_area）
        physical_region = physical_mapping[part_id]
        partition_def = generate_partition_def(
            components,
            physical_region,
            f"{part_id}_floorplan.def"
        )
```

**阶段5：各分区单独跑OpenROAD**

```bash
# 对每个分区单独运行OpenROAD（规模降低，速度快）
for partition in partition_0 partition_1 partition_2 partition_3; do
    openroad -no_init -exit <<EOF
    # 读取工艺文件
    read_lef tech.lef
    read_lef cells.lef
    
    # 读取分区的网表和floorplan
    read_verilog ${partition}.v
    link_design ${partition}
    
    # 初始化floorplan（规模缩小到1/K）
    initialize_floorplan -die_area "0 0 2500 2500" ...
    
    # 全局布局（速度快，因为规模小）
    global_placement
    
    # 详细布局
    detailed_placement
    
    # 输出分区布局
    write_def ${partition}_layout.def
EOF
done
```

**关键点**：
- ✅ 各分区**独立运行**，可以**并行**
- ✅ 每个分区的die_area是原设计的1/K
- ✅ **运行时间大幅降低**（规模效应）

**阶段6：拼接各分区布局**

```python
def stitch_partition_layouts(partition_layouts, physical_mapping, original_def):
    """
    拼接各分区的布局结果，生成完整设计的布局
    """
    # 1. 读取原始DEF（获取die_area、nets等）
    original_parser = DEFParser(original_def)
    original_parser.parse()
    
    # 2. 读取各分区的布局，转换坐标到完整die上
    stitched_components = {}
    for part_id, layout_file in partition_layouts.items():
        parser = DEFParser(layout_file)
        parser.parse()
        
        # 获取分区在完整die上的偏移（从physical_mapping）
        region = physical_mapping[part_id]
        offset_x, offset_y = region[0], region[1]
        
        # 转换坐标
        for comp, comp_info in parser.components.items():
            x, y = comp_info['position']
            stitched_components[comp] = {
                'position': (x + offset_x, y + offset_y),
                'orientation': comp_info['orientation']
            }
    
    # 3. 生成拼接后的完整DEF
    stitched_def = generate_stitched_def(
        original_parser,
        stitched_components
    )
    
    return stitched_def
```

**阶段7：（可选）全局优化**

```bash
# 在拼接后的布局上运行全局优化
openroad -no_init -exit <<EOF
read_lef tech.lef
read_lef cells.lef
read_def stitched_layout.def
read_verilog design.v
link_design design

# 仅运行增量优化（不重新placement）
global_placement -incremental

# 输出最终布局
write_def final_layout.def
EOF
```

**阶段8（之前的阶段3，现为阶段8）：评估与对比**

与 ChipMASRAG 的对比（正确版本）：
```python
def convert_kspecpart_to_openroad_constraints(
    part_file,      # K-SpecPart 输出的 .part.K 文件
    vertex_to_id,   # 从阶段1获得的映射关系（component_name -> vertex_id）
    def_file,       # 原始 ISPD 2015 DEF 文件
    output_def      # 输出的带分区约束的 DEF 文件
):
    """
    将 K-SpecPart 分区结果转换为 OpenROAD DEF 约束
    
    流程：
    1. 读取 K-SpecPart 的分区结果（顶点 -> 分区ID）
    2. 反向映射为 component_name -> 分区ID
    3. 在 DEF 文件中添加 REGIONS 和 GROUPS 约束
    """
    # 1. 读取 K-SpecPart 分区结果
    id_to_vertex = {v_id: v_name for v_name, v_id in vertex_to_id.items()}
    partition_assignment = {}
    
    with open(part_file, 'r') as f:
        for vertex_id, line in enumerate(f, start=1):  # K-SpecPart 使用 1-based
            part_id = int(line.strip())
            if vertex_id in id_to_vertex:
                component_name = id_to_vertex[vertex_id]
                partition_assignment[component_name] = part_id
    
    # 2. 构建分区方案（与 ChipMASRAG 格式一致）
    partition_scheme = {}
    for comp, part_id in partition_assignment.items():
        part_key = f"partition_{part_id}"
        if part_key not in partition_scheme:
            partition_scheme[part_key] = []
        partition_scheme[part_key].append(comp)
    
    # 3. 调用已有的 DEF 约束转换函数
    from src.utils.openroad_interface import OpenRoadInterface
    openroad_interface = OpenRoadInterface()
    openroad_interface.convert_partition_to_def_constraints(
        partition_scheme,
        def_file,
        output_def
    )
```

### 2.2 ChipMASRAG 的完整流程（正确版本）

**ChipMASRAG流程**：

**阶段1：RAG检索 + 多智能体协商（逻辑分区）**
```python
# 1. 协调者执行RAG检索
coordinator = CoordinatorAgent()
rag_results = coordinator.retrieve_rag(design_features, top_k=10)

# 2. 多智能体协商（不考虑物理位置，只关注逻辑分组）
agents = [PartitionAgent(id=i) for i in range(4)]  # 4个Agent

logical_partitions = multi_agent_negotiation(
    agents,
    design,
    rag_results
)
# 输出：逻辑分区
# partition_0: [comp1, comp5, ...] - 只是逻辑分组
# partition_1: [comp2, comp6, ...]
# partition_2: [comp3, comp7, ...]
# partition_3: [comp4, comp9, ...]
```

**阶段2-8：与K-SpecPart完全相同**
- 阶段2：基于连接性优化物理位置映射（**相同算法**）
- 阶段3：生成各分区的子网表和DEF（**相同方法**）
- 阶段4：各分区单独跑OpenROAD（**相同参数**）
- 阶段5：拼接各分区布局（**相同算法**）
- 阶段6：（可选）全局优化（**相同方法**）
- 阶段7：评估与对比（**相同指标**）

### 2.3 两种方法的完整对比（更新版本）

| 阶段 | K-SpecPart | ChipMASRAG | 是否相同 |
|------|-----------|-----------|---------|
| **1. 逻辑分区生成** | 监督式谱框架（Julia） | RAG + 多智能体协商（Python） | ❌ **唯一差异** |
| **   输出格式** | `.part.4`文件 | `partition_scheme` dict | ❌ 不同（需转换） |
| **2. 转换为统一格式** | 转换为`partition_scheme` | 已是`partition_scheme` | ✅ 统一后相同 |
| **3. 层级化改造** | `perform_hierarchical_transformation()` | `perform_hierarchical_transformation()` | ✅ **完全相同** |
| **   - 分析边界连接** | 相同函数 | 相同函数 | ✅ 相同 |
| **   - 提取分区网表** | 相同函数 | 相同函数 | ✅ 相同 |
| **   - 生成顶层网表** | 相同函数 | 相同函数 | ✅ 相同 |
| **   - 功能验证（Yosys）** | Formal验证 | Formal验证 | ✅ 相同 |
| **4. 物理位置优化** | 基于连接性优化 | 基于连接性优化 | ✅ **完全相同** |
| **5. 各分区单独OpenROAD** | 独立布局（规模1/K） | 独立布局（规模1/K） | ✅ **完全相同** |
| **6. 生成macro LEF** | 从分区布局提取 | 从分区布局提取 | ✅ 相同 |
| **7. 顶层OpenROAD** | 只布局跨分区连接 | 只布局跨分区连接 | ✅ **完全相同** |
| **8. 边界代价计算** | BC = HPWL_boundary / HPWL_internal × 100% | BC = HPWL_boundary / HPWL_internal × 100% | ✅ **完全相同** |

**关键结论**：
- ✅ **唯一差异**：阶段1的逻辑分区算法
  - K-SpecPart：监督式谱框架
  - ChipMASRAG：RAG + 多智能体协商
- ✅ **阶段2-8完全相同**：公平对比保证
  - 相同的层级化改造流程
  - 相同的功能验证方法（Yosys Formal）
  - 相同的物理位置优化算法
  - 相同的OpenROAD工具和参数
  - 相同的边界代价计算方法
- ✅ 可以**纯粹对比分区质量**对最终布局的影响

### 2.4 对比指标（完整版本）

**1. 规模降低效果**：
```python
# 各分区的规模
partition_sizes = [len(p) for p in partitions]
avg_partition_size = np.mean(partition_sizes)
scale_reduction = avg_partition_size / len(all_components)

# 目标：scale_reduction ≤ 1/35
```

**2. 边界代价（核心指标）**：
```python
# 计算边界代价
BC = (HPWL_stitched - sum(HPWL_partition_i)) / sum(HPWL_partition_i) × 100%
```
- HPWL_stitched：拼接后完整设计的HPWL
- HPWL_partition_i：第i个分区内部的HPWL（不含跨分区连接）
- **目标**：
  - 常规设计：BC < 50%
  - ChipMASRAG：通过协商降低BC > 30%

**3. 最终布局质量对比**：

| 方法 | HPWL | 说明 |
|------|------|------|
| **直接方法（基线）** | HPWL_direct | 直接跑完整设计 |
| **分区方法（拼接）** | HPWL_stitched | 拼接各分区布局 |
| **分区方法（优化）** | HPWL_final | 拼接后全局优化 |

**质量评估**：
- HPWL_stitched vs HPWL_direct：分区是否导致质量损失
- BC：边界代价评估分区质量
- HPWL_final vs HPWL_direct：全局优化后的最终质量

**4. 运行时间（关键优势）**：
```
直接方法时间 = T_direct

分区方法时间 = T_partition + max(T_partition_i) + T_stitch + T_global
```
- T_partition：分区算法时间
- max(T_partition_i)：最慢分区的OpenROAD时间（**并行时只看最慢的**）
- T_stitch：拼接时间（很快，可忽略）
- T_global：全局优化时间（可选）

**加速比** = T_direct / (T_partition + max(T_partition_i) + T_global)

**预期**：
- 大规模设计（> 100K）：加速比 > 2-5x
- 知识库命中时：T_partition很小，加速比更高

**5. 分区质量（逻辑层面）**：
- **Cut size**：跨分区连接数（K-SpecPart优化目标）
- **Balance**：各分区规模的平衡度
- **分区间连接性**：connectivity_matrix

**6. 可扩展性**：
- 最大可处理规模：1.2M+ 组件
- 子问题规模保持稳定（≈35K）
- 训练时间与设计规模的关系

**7. 方法特点对比**：

| 特点 | K-SpecPart | ChipMASRAG |
|------|-----------|-----------|
| **需要hint** | 是（hMETIS） | 否（RAG检索） |
| **知识复用** | 否 | 是（加速>60倍） |
| **主要优化目标** | Cut size（逻辑） | 边界代价（物理+逻辑） |
| **分区方式** | 静态划分 | 动态协商 |
| **可扩展性** | 需为不同规模训练 | 1.2M+，无需调参 |
| **预训练需求** | 需要 | 不需要 |

**公平对比保证**：

1. **相同的 OpenROAD 工具和参数**：
   - 使用相同的 OpenROAD 版本
   - 使用相同的 global_placement 和 detailed_placement 参数
   - 使用相同的 LEF/DEF 文件（仅分区约束不同）

2. **相同的评估指标**：
   - 使用相同的 HPWL 计算方法（OpenROAD API）
   - 使用相同的边界代价计算方法

3. **相同的数据集**：
   - 使用 ISPD 2015（16 个设计）
   - 相同的分区数量（K=4）
   - 相同的平衡约束（ε=5%）

### 2.3 实验实现

**脚本组织**：

1. `scripts/convert_ispd2015_to_hgr.py`：ISPD 2015 转换为超图格式
2. `scripts/run_kspecpart.sh`：批量运行 K-SpecPart
3. `scripts/convert_kspecpart_to_openroad.py`：K-SpecPart 结果转换为 OpenROAD 约束
4. `scripts/compare_with_kspecpart.py`：完整对比实验运行器
5. `scripts/analyze_kspecpart_results.py`：结果分析和可视化

**使用方法**：

```bash
# 完整流程（一键运行）
cd ~/chipmas
python scripts/compare_with_kspecpart.py \
    --designs mgc_fft_1 mgc_des_perf_1 mgc_matrix_mult_1 \
    --num-partitions 4 \
    --imbalance 0.05 \
    --output-dir results/kspecpart_comparison

# 分析结果
python scripts/analyze_kspecpart_results.py \
    --kspecpart-results results/kspecpart_comparison \
    --chipmasrag-results results/chipmasrag_baseline \
    --output results/comparison_report.pdf
```

### 2.4 预期结果

**K-SpecPart 优势**：
- 分区质量高（cut size 小）
- 算法成熟，结果稳定

**ChipMASRAG 预期优势**：
- **边界代价优化**：专门针对边界代价的协商机制，K-SpecPart 主要关注 cut size
- **知识复用**：RAG 检索历史案例，知识库命中时加速 >60倍
- **无需预训练**：K-SpecPart 需要 hint（通常用 hMETIS），ChipMASRAG 通过 RAG 动态适配
- **可扩展性**：多智能体并行，训练时间与设计规模无关
- **最终布局质量**：通过动态协商优化边界，预期 legalized HPWL 提升 >10-15%

**对比目标**：

| 指标 | K-SpecPart | ChipMASRAG 目标 |
|------|-----------|----------------|
| Cut size | 基准 | 相近或略优（±5%） |
| Legalized HPWL | 基准 | 提升 >10-15% |
| 边界代价 | 基准 | 降低 >25-30% |
| 运行时间 | 基准 | 知识库命中时：加速 >60倍 |
| 可扩展性 | 需为不同规模设计调参 | 1.2M+ 设计，训练时间与规模无关 |

3. **Constraints-Driven对比**：
   - **如果工具可用且支持ISPD 2015**：
     - 运行Constraints-Driven生成分区方案
     - 使用相同OpenRoad生成布局
     - 对比分区质量、边界代价、最终HPWL
     - 实现：`scripts/run_comparison.py::compare_with_constraints_driven()`
   - **如果工具不可用或不支持ISPD 2015**：
     - 引用论文数据（ICCAD 2023）
     - 对比方法特点和理论优势
     - 重点对比：边界代价、动态协商vs静态划分、知识复用能力
   - **对比指标**：
     - 边界代价（ChipMASRAG目标：降低>20%）
     - 约束满足率（两者都应满足，对比满足约束时的边界代价）
     - 最终HPWL（ChipMASRAG目标：提升>15%）
     - 运行时间（ChipMASRAG知识库命中时加速>60倍）

4. **Pin vs Block理论对比**：
   - **理论模型应用**：
     - 使用Pin vs Block理论模型预测边界代价
     - 公式：$P = 2.5 \times N^{0.5}$，其中P为引脚数，N为模块数
     - 在ISPD 2015设计上计算理论预测的跨分区连接数
     - 实现：`scripts/run_comparison.py::compare_with_pin_block_theory()`
   - **对比分析**：
     - 对比理论预测与实际布局结果的差异
     - 证明动态协商优于静态理论模型
     - 重点对比：实际布局质量、动态优化vs静态理论
   - **对比指标**：
     - 边界代价（ChipMASRAG目标：降低>30%）
     - 跨分区连接数（ChipMASRAG目标：减少>25%）
     - 最终HPWL（ChipMASRAG目标：提升>15%）
     - 理论vs实际差异（证明动态协商优于静态理论）

**对比实验表格设计**：

| 方法 | 边界代价 | 最终HPWL | 运行时间 | 可扩展性 | 知识复用 | 动态协商 |
|------|---------|---------|---------|---------|---------|---------|
| **ChipMASRAG** | 基准 | 基准 | 基准 | 1.2M+ | 是（加速>60倍） | 是 |
| OpenROAD par | +50-100% | +10-20% | 相似 | 相似 | 否 | 否 |
| K-SpecPart | +25-50% | +5-15% | 相似 | 需训练 | 否 | 否 |
| Constraints-Driven | +20-40% | +5-15% | 相似 | 相似 | 否 | 否 |
| Pin vs Block理论 | +30-60% | +10-20% | N/A | N/A | 否 | 否 |

**Titan23到OpenRoad转换方法**（用于扩展实验对象）：

**数据集位置**：`data/titan23/`

根据Titan23官方文档（https://www.eecg.utoronto.ca/~kmurray/titan.html），Titan23提供：
- HDL源文件：`data/titan23/benchmarks/titan23/` 目录下
- VQM格式（Altera Quartus II）
- BLIF格式（学术CAD工具）
- 转换工具：`data/titan23/vqm_to_blif/` 目录提供VQM到BLIF的转换工具

**已实现的转换工具**：

1. **BLIF到Verilog转换**（`src/utils/convert_blif_to_verilog.py`）：
   - 使用yosys将BLIF格式转换为Verilog格式
   - 支持命令行参数，可指定输出文件
   - 使用方法：`python3 src/utils/convert_blif_to_verilog.py <blif文件> -o <输出verilog文件>`

2. **OpenROAD综合和布局脚本**（`src/utils/titan23_to_openroad.tcl`）：
   - 使用OpenROAD的nangate45工艺对titan23设计进行综合和布局
   - 支持环境变量配置（DESIGN、VERILOG_FILE、OUTPUT_DIR）
   - 包含完整的OpenROAD流程：读取库、综合、布局、输出结果

3. **一键运行脚本**（`scripts/run_titan23_openroad.sh`）：
   - 自动查找BLIF文件
   - 自动转换BLIF到Verilog
   - 自动运行OpenROAD综合和布局
   - 使用方法：`./scripts/run_titan23_openroad.sh <设计名称> [输出目录]`

**转换流程**：

1. **BLIF到Verilog转换**：
   - 使用`src/utils/convert_blif_to_verilog.py`工具
   - 或直接使用yosys：`yosys -p "read_blif design.blif; write_verilog design.v"`

2. **OpenROAD综合和布局**：
   - 使用`src/utils/titan23_to_openroad.tcl`脚本
   - 需要配置nangate45工艺文件路径（在脚本中设置`openroad_flow_scripts`变量）
   - 根据设计规模调整die_area和core_area参数

3. **一键运行**（推荐）：
   - 使用`scripts/run_titan23_openroad.sh`脚本
   - 自动完成所有转换步骤

**注意**：
- Titan23是FPGA设计，转换为ASIC后可能失去FPGA特定优化
- 转换后的设计主要用于扩展实验对象，验证分区方法在不同规模设计上的效果
- 详细使用说明见`data/titan23/README.txt`中的"Titan23 设计在 OpenROAD 上的综合和布局指南"章节
- **优先使用ISPD 2015**：ISPD 2015已经是ASIC格式，可直接用于OpenRoad，无需转换

**对比实验实现**：

1. **对比实验运行器**（`scripts/run_comparison.py`）：
   - `compare_with_kspecpart()`: 与K-SpecPart对比（ISPD 2015）
   - `compare_with_kspecpart_titan23()`: 与K-SpecPart对比（Titan23）
   - `compare_with_constraints_driven()`: 与Constraints-Driven对比
   - `compare_with_pin_block_theory()`: 与Pin vs Block理论对比
   - `generate_comparison_table()`: 生成对比表格

2. **格式转换工具**（已实现）：
   - `src/utils/convert_blif_to_verilog.py`: BLIF转Verilog（使用yosys）
   - `src/utils/titan23_to_openroad.tcl`: OpenROAD综合和布局脚本
   - `scripts/run_titan23_openroad.sh`: 一键运行完整流程
   - 详细使用说明见`data/titan23/README.txt`

3. **对比结果分析**（`scripts/analyze_results.py`）：
   - `analyze_comparison_results()`: 分析对比实验结果
   - `visualize_comparison()`: 可视化对比结果
   - `generate_comparison_report()`: 生成对比报告

**数据集路径配置**：
- ISPD 2015：`data/ispd2015/`
- Titan23：`data/titan23/benchmarks/titan23/`
- 在配置文件中指定数据集路径，便于切换和复用

**证明实验设计**：

#### 实验5.5.1：协商模式有效性证明（与现有方法对比）

- **对比方法**：

  1. **ChipMASRAG**（知识驱动多智能体协商）- 本文方法
  2. **OpenROAD par**（静态几何划分）- 基线方法
  3. **K-SpecPart**（Bustany et al., 2023）- 监督式谱框架
  4. **Constraints-Driven General Partitioning**（Bustany et al., 2023）- 约束驱动划分工具
  5. **Pin vs Block理论**（Landman & Russo, 1971）- 经典理论方法
  6. **无协商基线**（随机分区）- 基线方法

- **与K-SpecPart的对比**：

  **K-SpecPart方法特点**：
  - 基于监督式谱框架的超图多路划分
  - 使用机器学习模型（需要训练数据）改进分区解
  - 主要关注划分质量（cut size、平衡度）
  - 静态划分，一次性生成分区方案

  **ChipMASRAG优势**：
  - **知识驱动vs监督学习**：无需预训练，通过RAG检索动态适配，支持知识库持续更新
  - **多智能体协商vs静态划分**：动态协商优化边界模块分配，而非一次性划分
  - **边界代价优化**：专门针对边界代价的协商机制，K-SpecPart主要关注cut size
  - **可扩展性**：多智能体并行，训练时间与设计规模无关；K-SpecPart需要为不同规模训练模型

  **对比指标**：
  - 边界代价（ChipMASRAG目标：降低>30%）
  - 跨分区连接数（ChipMASRAG目标：减少>25%）
  - 最终HPWL（使用相同OpenRoad，ChipMASRAG目标：提升>15%）
  - 运行时间（ChipMASRAG目标：知识库命中时加速>60倍）
  - 可扩展性（ChipMASRAG可处理1.2M+，K-SpecPart需要为不同规模训练）

- **与Constraints-Driven General Partitioning的对比**：

  **Constraints-Driven方法特点**：
  - 约束驱动的通用划分工具
  - 主要关注约束满足（时序、功耗、面积等）
  - 静态划分，缺乏动态协商
  - 支持多种约束类型

  **ChipMASRAG优势**：
  - **知识驱动vs约束驱动**：通过RAG检索历史协商模式，而非仅基于约束规则
  - **动态协商vs静态划分**：多智能体协商优化边界，而非一次性划分
  - **边界代价优化**：专门针对边界代价的协商协议，Constraints-Driven主要关注约束满足
  - **知识复用**：历史经验复用，加速优化过程

  **对比指标**：
  - 边界代价（ChipMASRAG目标：降低>30%）
  - 约束满足率（两者都应满足，对比满足约束时的边界代价）
  - 最终HPWL（使用相同OpenRoad，ChipMASRAG目标：提升>15%）
  - 运行时间（ChipMASRAG目标：知识库命中时加速>60倍）

- **与Pin vs Block理论的对比**：

  **Pin vs Block理论特点**：
  - 经典的引脚-模块关系理论（Landman & Russo, 1971）
  - 理论模型：$P = 2.5 \times N^{0.5}$（P为引脚数，N为模块数）
  - 静态理论模型，未考虑动态优化
  - 未涉及历史知识复用

  **ChipMASRAG优势**：
  - **动态协商vs静态理论**：动态协商优化引脚分配，而非仅基于理论模型
  - **知识驱动**：考虑历史案例的协商模式，而非仅基于理论公式
  - **多智能体协作**：多智能体协作优化边界连接，而非单一优化器
  - **实际应用**：针对实际布局问题，而非仅理论分析

  **对比指标**：
  - 边界代价（ChipMASRAG目标：降低>30%）
  - 跨分区连接数（ChipMASRAG目标：减少>25%）
  - 最终HPWL（使用相同OpenRoad，ChipMASRAG目标：提升>15%）
  - 理论vs实际：对比理论预测与实际布局结果的差异

- **评估指标**：
  - 边界代价（明确定义见5.5.2）
  - 跨分区连接数
  - 协商成功率（成功迁移的边界模块比例）
  - 最终HPWL（通过OpenRoad计算，使用相同工具和参数）
  - 运行时间
  - 可扩展性（不同规模设计的性能）
  - 知识复用效果（知识库命中率、加速比）

- **证明点**：
  - ChipMASRAG的边界代价显著低于静态划分方法（目标：降低>30%）
  - 相比K-SpecPart：边界代价降低>25%，知识驱动无需预训练
  - 相比Constraints-Driven：边界代价降低>20%，动态协商优于静态划分
  - 相比Pin vs Block理论：实际布局质量提升>15%，动态协商优于静态理论
  - 协商成功率>80%，证明多智能体协作有效性
  - 在超高耦合设计（边界代价>250%）上优势更明显
  - 规模扩展能力优于现有方法（可处理1.2M+，训练时间与规模无关）

#### 实验5.5.2：知识驱动vs传统协商

- **对比**：
  - 知识驱动协商：参考RAG检索的历史协商模式
  - 传统协商：仅基于当前状态的贪心协商
- **指标**：
  - 边界代价降低幅度
  - 协商迭代次数
  - 协商收敛速度
- **证明点**：知识驱动协商能更快收敛到更优解（迭代次数减少>40%，边界代价降低>20%）

#### 实验5.5.3：多智能体协作优势

- **对比**：
  - 多智能体协商：多个分区智能体同时协商
  - 单智能体优化：单一优化器处理所有分区
- **指标**：
  - 边界代价
  - 协商时间
  - 可扩展性（不同规模设计的性能）
- **证明点**：多智能体并行协商提升效率（协商时间减少>50%），且规模无关（训练时间不随规模线性增长）

### 5.5.2 边界代价的明确定义和分析方法

**边界代价定义**（基于ChipHier数据和分析）：

边界代价（Boundary Cost）定义为分区导致的额外HPWL代价，计算公式：

$\text{Boundary Cost} = \frac{\text{HPWL}*{\text{partitioned}} - \sum*{i=1}^{k} \text{HPWL}*i}{\sum*{i=1}^{k} \text{HPWL}_i} \times 100\%$

其中：

- $\text{HPWL}_{\text{partitioned}}$：完整设计的HPWL（包含边界连接）
- $\text{HPWL}_i$：第$i$个分区内部HPWL（不含跨分区连接）
- $k$：分区数量

**边界代价的物理意义**：

1. **负边界代价**（<0%）：全局优化能够同时优化边界，实现超越各分区独立优化之和的效果
2. **低边界代价**（0-50%）：分区方法有效，边界连接较少
3. **中等边界代价**（50-150%）：边界连接较多，但仍可接受
4. **高边界代价**（150-250%）：边界连接显著，需要优化
5. **极端高边界代价**（>250%）：超高耦合设计，传统方法难以处理

**边界代价分析方法**（结合ChipHier数据）：

1. **边界连接识别**：

   - 识别跨分区的连接（net）
   - 统计每个连接的引脚数
   - 计算边界连接的HPWL贡献
   - 实现：`src/utils/boundary_analyzer.py`

2. **边界模块识别**：

   - 识别连接多个分区的模块（boundary modules）
   - 计算每个边界模块的连接度（degree）
   - 评估迁移该模块的潜在收益
   - 实现：`src/negotiation.py::identify_boundary_modules()`

3. **边界代价分解**：

   - 按连接类型分解：时序关键连接、普通连接
   - 按分区对分解：分析特定分区对之间的边界代价
   - 按模块类型分解：分析不同类型模块的边界贡献
   - 实现：`src/utils/boundary_analyzer.py::decompose_boundary_cost()`

4. **协商目标量化**：

   - 目标边界代价：$\text{Target BC} < 50\%$（对于常规设计）
   - 协商收益：$\Delta \text{BC} = \text{BC}*{\text{before}} - \text{BC}*{\text{after}}$
   - 协商效率：$\text{Efficiency} = \frac{\Delta \text{BC}}{\text{Negotiation Time}}$
   - 实现：`src/negotiation.py::evaluate_negotiation_benefit()`

**实验验证方法**：

1. **边界代价测量**：

   - 使用OpenRoad计算完整HPWL
   - 计算各分区内部HPWL（排除跨分区连接）
   - 计算边界代价百分比
   - 实现：`experiments/evaluator.py::calculate_boundary_cost()`

2. **边界代价分析**：

   - 绘制边界代价分布图
   - 分析边界代价与设计特征的关系（规模、连接度、模块类型）
   - 对比不同分区方法的边界代价
   - 实现：`scripts/analyze_results.py::analyze_boundary_cost()`

3. **协商效果评估**：

   - 记录协商前后的边界代价
   - 分析协商对边界代价的改善
   - 验证知识驱动协商的有效性
   - 实现：`experiments/evaluator.py::evaluate_negotiation_effect()`

**基于ChipHier数据的边界代价模式**：

根据ChipHier实验结果，边界代价呈现三种模式：

1. **负边界代价设计**（-66.3%到-17.1%）：

   - 特点：低耦合设计，全局优化能同时优化边界
   - 案例：mgc_fft_1, mgc_fft_2, mgc_matrix_mult_1, mgc_pci_bridge32_b
   - ChipMASRAG策略：重点优化分区质量，边界协商收益有限

2. **中等边界代价设计**（13.9%到109.1%）：

   - 特点：中等耦合，边界代价可控
   - 案例：mgc_des_perf_1 (13.9%), mgc_edit_dist_a (109.1%)
   - ChipMASRAG策略：通过协商优化边界模块分配，目标将边界代价降低>30%

3. **高边界代价设计**（>240%）：

   - 特点：超高耦合，传统方法难以处理
   - 案例：mgc_fft_a, mgc_matrix_mult_a（>250%）
   - ChipMASRAG策略：知识驱动的协商协议发挥关键作用，在这些极端案例上实现全面胜出（边界代价降低>40%）

**边界代价优化目标**：

- 对于常规设计：将边界代价控制在<50%
- 对于高耦合设计：通过协商将边界代价降低>30%
- 对于极端案例（>250%）：证明ChipMASRAG在这些设计上的独特优势（边界代价降低>40%，HPWL质量提升>20%）

### 5.6 知识库质量分析

**目的**：验证知识库构建质量和覆盖率

**实验设计**：

- 分析：16个ISPD 2015设计的知识库命中率
- 统计：不同设计类型的覆盖率
- 评估：检索到的案例质量（相似度分布）

**证明点**：知识库能有效覆盖ISPD 2015设计，检索质量高

### 5.7 训练规模无关性验证（核心证明点5）

**目的**：证明多智能体并行实现训练规模无关

**实验设计**：

- 选择3-5个不同规模的设计
- 记录：训练时间、训练步数、收敛速度
- 分析：训练时间与设计规模的关系

**证明点**：训练时间不随设计规模线性增长，验证多智能体并行的规模无关性

## 六、实验归档与可复现性

### 6.1 归档结构

每次实验自动创建时间戳目录：

```
data/results/{YYYYMMDD_HHMMSS}/
├── config.json              # 完整实验配置
├── git_commit.txt           # Git提交哈希
├── environment.txt          # 环境信息（Python版本、包版本）
├── logs/
│   ├── experiment.log      # 主日志
│   ├── training.log        # 训练日志
│   └── evaluation.log       # 评估日志
├── checkpoints/             # 模型检查点
│   ├── coordinator_*.pt
│   └── agent_*.pt
├── results.json             # 结果汇总
└── README.md                # 实验说明
```

### 6.2 远程服务器配置

**服务器信息**：
- 地址：`172.30.31.98`
- 用户：`keqin`
- 密码：`keqin123`
- SSH连接：`ssh -o ServerAliveInterval=10 keqin@172.30.31.98`
- 工作目录：`~/chipmas/`

**代码和数据同步方法**：

1. **初始同步**（首次部署）：
   ```bash
   # 在本地执行，将代码和数据同步到服务器
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
     chipmas/ keqin@172.30.31.98:~/chipmas/
   ```

2. **增量同步**（代码更新后）：
   ```bash
   # 同步代码（排除大数据文件）
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
     --exclude='data/results/' --exclude='data/knowledge_base/' \
     chipmas/ keqin@172.30.31.98:~/chipmas/
   ```

3. **结果回传**（实验完成后）：
   ```bash
   # 从服务器拉取实验结果
   rsync -avz keqin@172.30.31.98:~/chipmas/data/results/ \
     chipmas/data/results/
   ```

4. **SSH配置**（避免频繁输入密码）：
   ```bash
   # 在本地 ~/.ssh/config 中添加：
   Host chipmas-server
       HostName 172.30.31.98
       User keqin
       ServerAliveInterval 10
       ServerAliveCountMax 3
   ```
   然后使用：`ssh chipmas-server`

**远程实验运行流程**：

1. **准备阶段**：
   - 在本地开发和测试代码
   - 使用rsync同步代码到服务器
   - SSH登录服务器验证环境

2. **运行阶段**：
   - 在服务器上运行实验：`cd ~/chipmas && python scripts/run_experiment.py`
   - 使用screen或tmux保持会话：`screen -S chipmas_exp`
   - 定期检查实验进度

3. **结果获取**：
   - 实验完成后使用rsync拉取结果
   - 检查`data/results/{timestamp}/`目录
   - 分析实验结果

### 6.3 可复现性保证

- **随机种子**：固定随机种子，记录在config.json
- **版本控制**：记录Git提交哈希、依赖包版本
- **配置完整**：所有超参数保存在config.json
- **数据完整性**：知识库版本、数据集版本记录

### 6.4 日志记录

- **实时日志**：实验过程实时输出到控制台和文件
- **结构化日志**：关键事件以JSON格式记录
- **错误处理**：异常信息完整记录，便于调试

## 七、技术栈

### 7.1 核心依赖

- PyTorch 2.0+（神经网络、强化学习）
- torch-geometric（GAT实现）
- numpy, scipy（数值计算）
- networkx（图处理）
- pyyaml（配置管理）
- tqdm（进度条）

### 7.2 可选依赖

- sentence-transformers（语义嵌入，用于语义检索）
- tensorboard（训练可视化）
- matplotlib（结果可视化）

## 八、具体实施步骤

### 快速开始（首次运行）

**目标**：在1个小设计上验证完整流程，确保所有组件正常工作

**工作流程**：
1. **本地开发**：在本地编写和测试代码
2. **同步到服务器**：使用rsync将代码同步到服务器
3. **服务器测试**：在服务器上运行实验

**代码同步方法**（开发过程中频繁使用）：
```bash
# 从本地同步代码到服务器（排除大数据文件）
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data/results/' --exclude='data/knowledge_base/' \
  chipmas/ keqin@172.30.31.98:~/chipmas/
```

**步骤**：
1. 完成阶段0的环境准备（在服务器上）
2. 完成阶段1的基础设施（本地开发，同步到服务器测试）
3. 完成阶段2的核心组件（本地开发，同步到服务器测试）
4. 完成阶段3的训练系统（本地开发，同步到服务器测试）
5. 完成阶段4的实验系统（重点：OpenRoad接口，在服务器上实现和测试）
6. 在服务器上使用mgc_pci_bridge32_a测试端到端流程

**成功标准**：
- [ ] 能生成分区方案
- [ ] 能转换为OpenRoad约束
- [ ] OpenRoad API能生成布局
- [ ] 能通过API提取HPWL值
- [ ] 能计算边界代价

### 阶段0：环境准备与数据集配置（1-2天）

**步骤0.1：创建项目结构**（**在服务器上执行**）
```bash
# 在服务器上创建项目结构
ssh chipmas-server
cd ~/chipmas
mkdir -p src/utils experiments data/knowledge_base data/results configs scripts
touch src/__init__.py src/utils/__init__.py experiments/__init__.py
```

**步骤0.2：配置数据集目录**（**在服务器上执行**）
```bash
# 在服务器上配置数据集目录
ssh chipmas-server
cd ~/chipmas
mkdir -p data
cd data
# 创建符号链接（或复制，根据实际情况）
ln -s ../dataset/ispd_2015_contest_benchmark ispd2015
ln -s ../dataset/titan_release_1.3.1 titan23
# 验证
ls -la ispd2015/ | head -5
ls -la titan23/benchmarks/titan23/ | head -5
```

**步骤0.3：配置远程服务器**（**必需**，实验在服务器上运行）
```bash
# 在本地配置SSH（~/.ssh/config）
cat >> ~/.ssh/config << EOF
Host chipmas-server
    HostName 172.30.31.98
    User keqin
    ServerAliveInterval 10
    ServerAliveCountMax 3
EOF

# 测试连接
ssh chipmas-server "mkdir -p ~/chipmas"

# 在服务器上准备环境
ssh chipmas-server
cd ~/chipmas
# 后续步骤在服务器上执行
```

**步骤0.4：安装依赖**（**在服务器上执行**）
```bash
# 在服务器上创建requirements.txt
ssh chipmas-server
cd ~/chipmas
cat > requirements.txt << EOF
torch>=2.0.0
torch-geometric>=2.3.0
numpy>=1.24.0
scipy>=1.10.0
networkx>=3.0
pyyaml>=6.0
tqdm>=4.65.0
sentence-transformers>=2.2.0
matplotlib>=3.7.0
EOF

# 在服务器上安装依赖
pip install -r requirements.txt
```

**步骤0.5：验证OpenRoad环境**（**在服务器上执行**）
```bash
# 在服务器上检查OpenRoad是否可用（基于现有成功案例）
ssh chipmas-server
# 测试OpenRoad基本功能（使用现有成功案例的验证方法）
# 确认OpenRoad API可用，参考现有成功案例的API调用方式
```

**验证点**：
- [ ] 项目结构创建完成
- [ ] 数据集目录链接/复制成功
- [ ] 远程服务器可连接（如使用）
- [ ] 依赖包安装成功
- [ ] OpenRoad环境验证通过

### 阶段1：基础设施实现（1-2周）

**步骤1.1：实现知识库模块** (`src/knowledge_base.py`)（**本地开发，同步到服务器测试**）
- 在本地实现`load()`, `add_case()`, `get_case()`, `export()`方法
- 数据结构：Case包含design_id, features, partition_strategy, negotiation_patterns, quality_metrics, embedding
- **测试**：创建测试用例，验证案例存储和检索功能
- **同步和验证**：
  ```bash
  # 同步代码到服务器
  rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    chipmas/src/ keqin@172.30.31.98:~/chipmas/src/
  # 在服务器上验证
  ssh chipmas-server "cd ~/chipmas && python -c 'from src.knowledge_base import KnowledgeBase; kb = KnowledgeBase(); print(\"OK\")'"
  ```

**步骤1.2：实现RAG检索模块** (`src/rag_retriever.py`)
- 实现`coarse_retrieve()`: 基于规模和类型筛选
- 实现`fine_retrieve()`: 基于特征向量相似度
- 实现`semantic_retrieve()`: 基于嵌入向量相似度
- 实现`retrieve()`: 统一接口，返回top-k=10
- **测试**：使用模拟数据测试三级检索流程
- **验证**：确保检索结果按相似度排序，top-k正确

**步骤1.3：实现环境模块** (`src/environment.py`)
- 实现`PlacementEnv`: 布局环境类
- 实现`State`: 状态表示（局部状态+RAG状态）
- 实现`RewardCalculator`: 奖励计算（局部+全局+边界+RAG奖励）
- **测试**：使用小规模设计测试环境初始化和状态转换
- **验证**：确保状态空间和动作空间定义正确，奖励计算合理

**步骤1.4：实现资源监控** (`src/utils/resource_monitor.py`)
- 实现时间、内存、CPU监控功能
- **测试**：验证监控数据准确性
- **验证**：确保能正确记录各阶段资源使用

**验证点**：
- [ ] 知识库模块可正常加载和存储案例
- [ ] RAG检索能正确返回top-k结果
- [ ] 环境模块能正确初始化和执行动作
- [ ] 资源监控能正确记录数据

### 阶段2：核心组件实现（2-3周）

**步骤2.1：实现神经网络** (`src/networks.py`)
- 实现GAT编码器（3层，隐藏维度128）
- 实现Actor网络（2层MLP，256, 128）
- 实现Critic网络（3层MLP，512, 256, 128）
- 实现协商网络（2层MLP，128, 64）
- **测试**：使用小规模图测试GAT编码，使用随机输入测试各网络前向传播
- **验证**：确保网络输出维度正确，梯度可正常反向传播

**步骤2.2：实现分区智能体** (`src/partition_agent.py`)
- 实现`encode_state()`: GAT状态编码
- 实现`select_action()`: Actor网络输出动作
- 实现`negotiate()`: 知识驱动的边界协商
- **测试**：使用小规模设计测试智能体基本功能
- **验证**：确保状态编码正确，动作选择合理

**步骤2.3：实现协调者智能体** (`src/coordinator.py`)
- 实现`retrieve_rag()`: 执行RAG检索并广播结果
- 实现`coordinate()`: 全局协调各分区智能体
- 实现`compute_global_reward()`: 计算全局奖励
- **测试**：测试协调者与多个分区智能体的交互
- **验证**：确保RAG检索结果正确广播，全局奖励计算正确

**步骤2.4：实现边界协商协议** (`src/negotiation.py`)
- 实现`identify_boundary_modules()`: 识别高代价边界模块
- 实现`find_similar_negotiation()`: 在RAG结果中查找相似协商案例
- 实现`negotiate()`: 执行协商请求
- 实现`execute_migration()`: 执行模块迁移
- **测试**：使用小规模设计测试协商流程
- **验证**：确保边界模块识别准确，协商能降低边界代价

**验证点**：
- [ ] 神经网络前向和反向传播正常
- [ ] 分区智能体能正确编码状态和选择动作
- [ ] 协调者能正确检索和广播RAG结果
- [ ] 边界协商能正确识别和迁移模块

### 阶段3：训练系统实现（1-2周）

**步骤3.1：实现MADDPG训练器** (`src/training.py::MADDPGTrainer`)
- 实现分区智能体的MADDPG训练逻辑
- 实现经验回放缓冲区
- 实现目标网络更新
- **测试**：使用小规模设计进行短期训练测试
- **验证**：确保训练损失下降，策略网络更新正常

**步骤3.2：实现PPO训练器** (`src/training.py::PPOTrainer`)
- 实现协调者的PPO训练逻辑
- 实现优势函数计算
- 实现策略裁剪
- **测试**：使用小规模设计进行短期训练测试
- **验证**：确保训练损失下降，策略网络更新正常

**步骤3.3：实现训练管理器** (`src/training.py::TrainingManager`)
- 实现统一训练流程管理
- 实现检查点保存和加载
- 实现训练日志记录
- **测试**：测试完整训练流程
- **验证**：确保训练能正常进行，检查点可正确保存和加载

**步骤3.4：实现主框架集成** (`src/framework.py`)
- 实现`ChipMASRAG`主类
- 实现`run()`: 运行布局优化
- 实现`train()`: 训练模型
- 实现`evaluate()`: 评估性能
- **测试**：使用最小设计测试完整流程
- **验证**：确保框架能正确集成所有组件

**验证点**：
- [ ] MADDPG训练器能正常训练分区智能体
- [ ] PPO训练器能正常训练协调者
- [ ] 训练管理器能正确管理训练流程
- [ ] 主框架能正确集成所有组件并运行

### 阶段4：实验系统实现（1-2周）

**步骤4.1：实现OpenRoad接口** (`src/utils/openroad_interface.py`)（**在服务器上实现和测试**）
- **关键步骤**：基于现有OpenRoad成功案例的API调用方式
- 实现`convert_partition_to_def_constraints()`: 将分区方案转换为DEF约束
- 实现`generate_layout_with_partition()`: 使用OpenRoad API生成布局
- 实现`calculate_hpwl()`: 使用OpenRoad API提取HPWL值（**参考现有成功案例的API调用方式**）
- 实现`calculate_partition_hpwl()`: 计算各分区内部HPWL
- **测试**：在服务器上使用1个小设计（如mgc_pci_bridge32_a）测试完整流程
- **验证**：
  - [ ] 分区方案能正确转换为DEF约束
  - [ ] OpenRoad API能正确调用并生成布局
  - [ ] HPWL值能通过API正确提取（**使用现有成功案例的API方式**）
  - [ ] 边界代价能正确计算

**步骤4.2：实现边界分析器** (`src/utils/boundary_analyzer.py`)
- 实现`count_cross_partition_connections()`: 统计跨分区连接
- 实现`decompose_boundary_cost()`: 分解边界代价
- 实现`calculate_boundary_cost_from_def()`: 从DEF文件计算边界代价
- **测试**：使用已知分区方案验证边界代价计算
- **验证**：确保边界代价计算与预期一致

**步骤4.3：实现实验运行器** (`experiments/runner.py`)
- 实现`run_experiment()`: 运行单个设计
- 实现`run_benchmark()`: 运行ISPD 2015基准测试（16个设计）
- 实现`run_ablation()`: 运行消融实验
- **测试**：使用1个小设计测试实验运行流程
- **验证**：确保实验能正确运行并生成结果

**步骤4.4：实现评估器** (`experiments/evaluator.py`)
- 实现`calculate_boundary_cost()`: 计算边界代价
- 实现`calculate_partition_balance()`: 计算分区平衡度
- 实现`calculate_negotiation_success_rate()`: 计算协商成功率
- 实现`calculate_partition_quality_score()`: 计算分区质量评分
- 实现`calculate_layout_quality_score()`: 计算最终布局质量评分
- **测试**：使用已知结果验证评估指标计算
- **验证**：确保评估指标计算正确

**步骤4.5：实现日志系统** (`experiments/logger.py`)
- 实现实验配置记录
- 实现训练过程记录
- 实现评估结果记录
- 实现自动时间戳目录创建
- **测试**：运行一次实验，检查日志和归档
- **验证**：确保所有信息正确记录，归档结构完整

**步骤4.6：构建初始知识库** (`scripts/build_kb.py`)
- **功能**：知识库构建和更新脚本，支持以下功能：
  1. **从设计文件构建初始知识库**：从 ISPD 2015 设计文件提取基本特征
  2. **从实验结果更新知识库**：从 ChipMASRAG 运行结果中提取完整案例
  3. **自动搜索本地结果**：自动搜索本地实验结果目录并更新知识库
  4. **自动搜索远程结果**：自动搜索远程服务器实验结果目录并更新知识库
  5. **一键构建**：使用 `--all` 选项执行所有操作（构建初始+更新本地+更新远程）

- **使用方法**：
  ```bash
  # 方法1：构建初始知识库（从设计文件）
  python scripts/build_kb.py --design-dirs data/ispd2015/mgc_pci_bridge32_a data/ispd2015/mgc_fft_1
  
  # 方法2：从指定实验结果目录更新
  python scripts/build_kb.py --results-dir data/results/20240101_120000
  
  # 方法3：自动搜索本地实验结果并更新
  python scripts/build_kb.py --auto-local
  
  # 方法4：自动搜索远程服务器实验结果并更新
  python scripts/build_kb.py --auto-remote --remote-server 172.30.31.98 --remote-user keqin --sync-remote
  
  # 方法5：一键执行所有操作（推荐）
  python scripts/build_kb.py --all --remote-server 172.30.31.98 --remote-user keqin --sync-remote
  ```

- **自举构建策略**：
  1. 从设计文件构建初始知识库（基本特征）
  2. 运行 ChipMASRAG 生成分区方案和布局结果
  3. 从运行结果提取完整案例（分区策略、协商模式、质量指标）
  4. 生成语义嵌入
  5. 存入知识库
  6. 迭代优化：重复步骤2-5，逐步扩展知识库

- **测试**：在1-2个小设计上测试知识库构建流程
- **验证**：
  - [ ] 知识库案例格式正确
  - [ ] 案例包含所有必需字段
  - [ ] RAG检索能正确找到案例
  - [ ] 自动搜索功能正常工作
  - [ ] 远程服务器连接和同步功能正常

**验证点**：
- [ ] OpenRoad接口能正确生成布局和提取HPWL
- [ ] 边界分析器能正确计算边界代价
- [ ] 实验运行器能正确运行实验
- [ ] 评估器能正确计算所有指标
- [ ] 日志系统能正确记录和归档
- [ ] 初始知识库构建成功，包含至少10个案例

### 阶段5：验证与测试（1周）

**步骤5.1：端到端测试**（**在服务器上执行**）
- 在服务器上使用最小设计（mgc_pci_bridge32_a）测试完整流程：
  1. ChipMASRAG生成分区方案
  2. 转换为OpenRoad约束
  3. 调用OpenRoad API生成布局
  4. 使用OpenRoad API提取HPWL和边界代价
  5. 评估结果
- **验证**：确保整个流程无错误，能生成有效结果

**步骤5.2：OpenRoad集成验证**（最关键，**在服务器上执行**）
- 在服务器上使用1个小设计验证：
  - [ ] 分区约束能正确转换为DEF格式
  - [ ] OpenRoad API能正确识别和应用约束
  - [ ] HPWL能通过API正确提取（**使用现有成功案例的API调用方式**）
  - [ ] 边界代价能正确计算
- **验证**：对比有约束vs无约束的布局结果，确认约束生效
- **重要**：参考现有OpenRoad成功案例的API调用方式，不要使用不存在的命令

**步骤5.3：知识库检索验证**
- 测试RAG检索功能：
  - [ ] 粗粒度检索能正确筛选
  - [ ] 细粒度检索能正确排序
  - [ ] 语义检索能正确找到相似案例
  - [ ] top-k结果合理
- **验证**：确保检索结果与预期一致

**步骤5.4：边界协商验证**
- 使用1个小设计测试协商流程：
  - [ ] 边界模块识别准确
  - [ ] 协商能降低边界代价
  - [ ] 模块迁移正确执行
- **验证**：对比协商前后的边界代价，确认改善

**验证点**：
- [ ] 端到端流程无错误
- [ ] OpenRoad集成验证通过
- [ ] 知识库检索验证通过
- [ ] 边界协商验证通过

### 阶段6：实验执行（3-4周）

**步骤6.1：主实验 - ISPD 2015基准测试**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
# 使用screen或tmux保持会话
screen -S chipmas_exp
python scripts/run_experiment.py --benchmark ispd2015 --all
# 按Ctrl+A然后D退出screen，使用screen -r chipmas_exp重新连接
```
- 运行16个ISPD 2015设计
- 记录HPWL、成功率、运行时间、知识库命中率
- **验证**：确保所有设计都能成功运行，成功率≥80%

**步骤6.2：知识库复用效果实验**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
screen -S chipmas_kb_reuse
python scripts/run_experiment.py --experiment kb_reuse \
  --designs mgc_pci_bridge32_a mgc_fft_1 mgc_des_perf_b mgc_matrix_mult_1
```
- 对比有KB vs 无KB（禁用RAG检索）
- 计算加速比（目标≥60倍）
- **验证**：确保加速比达到目标

**步骤6.3：规模无关性分析**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
screen -S chipmas_scalability
python scripts/run_experiment.py --experiment scalability \
  --designs mgc_pci_bridge32_a mgc_fft_1 mgc_des_perf_b mgc_matrix_mult_1 mgc_superblue16_a
```
- 记录原始规模、子问题规模、运行时间
- 分析子问题规模比例（目标≤1/35）
- 验证运行时间线性关系
- **验证**：确保规模无关性指标达到目标

**步骤6.4：消融实验**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
screen -S chipmas_ablation
python scripts/run_experiment.py --experiment ablation \
  --design mgc_matrix_mult_1 \
  --variants full no_rag no_negotiation no_coordinator single_agent
```
- 对比完整ChipMASRAG vs 各变体
- 记录HPWL、边界代价、运行时间
- **验证**：确保各组件贡献符合预期

**步骤6.5：知识驱动边界协商效果实验**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
screen -S chipmas_comparison

# 与K-SpecPart对比（如果可用）
python scripts/run_comparison.py --method kspecpart --benchmark ispd2015

# 与Constraints-Driven对比（如果可用）
python scripts/run_comparison.py --method constraints_driven --benchmark ispd2015

# 与Pin vs Block理论对比
python scripts/run_comparison.py --method pin_block --benchmark ispd2015
```
- 对比边界代价、最终HPWL、运行时间
- **验证**：确保对比结果符合预期

**步骤6.6：训练规模无关性验证**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
screen -S chipmas_training_scalability
python scripts/run_experiment.py --experiment training_scalability \
  --designs mgc_pci_bridge32_a mgc_fft_1 mgc_matrix_mult_1
```
- 记录训练时间、训练步数、收敛速度
- **验证**：确保训练时间不随规模线性增长

**步骤6.7：知识库质量分析**（**在服务器上执行**）
```bash
# 在服务器上运行
ssh chipmas-server
cd ~/chipmas
python scripts/analyze_results.py --kb_quality
```
- 分析16个设计的知识库命中率
- 统计不同设计类型的覆盖率
- 评估检索到的案例质量
- **验证**：确保知识库质量符合要求

**验证点**：
- [ ] 主实验所有设计成功运行
- [ ] 知识库复用效果达到目标（加速≥60倍）
- [ ] 规模无关性指标达到目标（子问题规模≤1/35）
- [ ] 消融实验证明各组件必要性
- [ ] 边界协商效果达到目标（边界代价降低>30%）
- [ ] 训练规模无关性验证通过
- [ ] 知识库质量分析通过

### 阶段7：结果分析与归档（1周）

**步骤7.1：结果汇总**（**可在本地或服务器上执行**）
```bash
# 如果结果已同步到本地，可在本地分析
# 或在服务器上分析
ssh chipmas-server
cd ~/chipmas
python scripts/analyze_results.py --summary
```
- 汇总所有实验结果
- 生成对比表格
- 分析各组件贡献

**步骤7.2：生成实验报告**
- 整理实验数据
- 生成可视化图表
- 撰写实验分析

**步骤7.3：归档实验数据**
- 确保所有实验结果已归档到`data/results/{timestamp}/`
- 验证归档完整性
- 记录实验配置和版本信息

**验证点**：
- [ ] 所有实验结果已汇总
- [ ] 实验报告已生成
- [ ] 所有数据已正确归档

### 关键检查点总结

**阶段0检查点**：
- [ ] 项目结构创建完成
- [ ] 数据集目录配置正确
- [ ] 远程服务器可连接（如使用）
- [ ] 所有依赖包安装成功
- [ ] OpenRoad环境验证通过

**阶段1检查点**：
- [ ] 知识库模块可正常加载和存储案例
- [ ] RAG检索能正确返回top-k结果
- [ ] 环境模块能正确初始化和执行动作
- [ ] 资源监控能正确记录数据

**阶段2检查点**：
- [ ] 神经网络前向和反向传播正常
- [ ] 分区智能体能正确编码状态和选择动作
- [ ] 协调者能正确检索和广播RAG结果
- [ ] 边界协商能正确识别和迁移模块

**阶段3检查点**：
- [ ] MADDPG训练器能正常训练分区智能体
- [ ] PPO训练器能正常训练协调者
- [ ] 训练管理器能正确管理训练流程
- [ ] 主框架能正确集成所有组件并运行

**阶段4检查点**（最关键）：
- [ ] **OpenRoad接口能正确生成布局和提取HPWL**（最重要）
- [ ] 边界分析器能正确计算边界代价
- [ ] 实验运行器能正确运行实验
- [ ] 评估器能正确计算所有指标
- [ ] 日志系统能正确记录和归档
- [ ] 初始知识库构建成功，包含至少10个案例

**阶段5检查点**（验证阶段）：
- [ ] 端到端流程无错误
- [ ] **OpenRoad集成验证通过**（最关键）
- [ ] 知识库检索验证通过
- [ ] 边界协商验证通过

**阶段6检查点**（实验执行）：
- [ ] 主实验所有设计成功运行（成功率≥80%）
- [ ] 知识库复用效果达到目标（加速≥60倍）
- [ ] 规模无关性指标达到目标（子问题规模≤1/35）
- [ ] 消融实验证明各组件必要性
- [ ] 边界协商效果达到目标（边界代价降低>30%）
- [ ] 训练规模无关性验证通过
- [ ] 知识库质量分析通过

### 常见问题排查

**问题1：OpenRoad无法识别分区约束**
- 检查DEF文件格式是否正确
- 验证REGIONS和COMPONENTS分配是否正确
- 检查OpenRoad日志中的错误信息
- 参考现有成功案例的DEF格式

**问题2：HPWL提取失败**
- **使用OpenRoad API提取HPWL**（参考现有成功案例的API调用方式）
- 不要使用不存在的命令（如report_wirelength）
- 验证API调用逻辑
- 检查OpenRoad版本兼容性

**问题3：知识库检索无结果**
- 检查知识库是否已构建
- 验证案例格式是否正确
- 检查检索参数设置
- 确认嵌入向量已生成

**问题4：边界协商无效果**
- 检查边界模块识别逻辑
- 验证协商决策是否正确
- 检查模块迁移执行逻辑
- 对比协商前后的边界代价

**问题5：训练不收敛**
- 检查奖励函数设计
- 调整学习率
- 验证网络初始化
- 检查训练数据质量

## 九、关键实现细节

### 9.1 ChipMASRAG与OpenRoad配合流程

**完整工作流程**：

1. **ChipMASRAG分区生成阶段**（独立于OpenRoad）：
   ```
   输入：设计网表(design.v) + 设计特征
   ↓
   RAG检索历史案例
   ↓
   多智能体协商生成分区方案
   ↓
   输出：分区方案JSON文件
   {
     "partitions": {
       "partition_0": [module_ids...],
       "partition_1": [module_ids...],
       ...
     },
     "boundary_modules": [...],
     "negotiation_history": [...]
   }
   ```

2. **分区方案转换阶段**（准备OpenRoad输入和生成partition netlist）：
   ```
   输入：分区方案JSON + 原始DEF文件(floorplan.def) + 原始Verilog网表(design.v)
   ↓
   转换分区方案为DEF约束（REGIONS和GROUPS分配）
   ↓
   生成partition netlist（每个partition的独立Verilog文件）
   ↓
   验证一致性（确保netlist与DEF中的分区信息一致）
   ↓
   输出：
   - 带分区约束的DEF文件（floorplan_with_partition.def）
   - Partition netlist文件（{partition_id}_{timestamp}.v）
   - 分区方案和验证报告（partition_scheme_{timestamp}.json）
   ```

3. **OpenRoad布局生成阶段**（仅用于验证和HPWL计算）：
   ```
   输入：
   - LEF文件(tech.lef, cells.lef) - ISPD 2015提供
   - DEF文件(floorplan.def) - ISPD 2015提供（已添加分区约束）
   - Verilog网表(design.v) - ISPD 2015提供
   ↓
   OpenRoad TCL脚本：
   read_lef tech.lef
   read_lef cells.lef
   read_def floorplan_with_partition.def
   read_verilog design.v
   place_design
   report_wirelength
   ↓
   输出：最终布局DEF文件 + HPWL值
   ```

4. **HPWL和边界代价计算阶段**：
   ```
   输入：最终布局DEF文件 + 分区方案JSON
   ↓
   解析DEF文件中的net连接
   ↓
   根据分区方案识别跨分区连接
   ↓
   计算：
   - 完整HPWL（使用OpenRoad API提取，参考现有成功案例的API调用方式）
   - 各分区内部HPWL（排除跨分区连接）
   - 边界代价 = (完整HPWL - 分区HPWL之和) / 分区HPWL之和
   ↓
   输出：HPWL值、边界代价、分区质量指标
   ```

**关键实现细节**：

1. **分区方案到DEF约束的转换**：
   - 使用DEF文件的`REGIONS`部分定义分区区域
   - 使用`COMPONENTS`部分的`PLACEMENT`属性将模块分配到对应REGION
   - 实现：`src/utils/openroad_interface.py::convert_partition_to_def_constraints()`

2. **OpenRoad脚本生成**：
   - 自动生成TCL脚本，包含所有必要的OpenRoad命令
   - 处理ISPD 2015缺少liberty文件的情况（仅使用placement功能）
   - 实现：`src/utils/openroad_interface.py::generate_openroad_script()`

3. **HPWL提取**：
   - **使用OpenRoad API提取HPWL**（参考现有成功案例的API调用方式）
   - 不要使用不存在的命令（如report_wirelength）
   - 实现：`src/utils/openroad_interface.py::calculate_hpwl()`（使用API）

4. **边界代价计算**：
   - 从DEF文件中解析所有net连接
   - 根据分区方案判断哪些net是跨分区的
   - 计算跨分区连接的HPWL贡献
   - 实现：`src/utils/boundary_analyzer.py::calculate_boundary_cost_from_def()`

**ISPD 2015特殊处理**：

1. **缺少liberty文件**：
   - 不影响OpenRoad的placement功能（只需要LEF和DEF）
   - 不影响HPWL计算（HPWL不依赖时序信息）
   - 仅影响时序分析功能（ChipMASRAG不依赖时序分析）

2. **分区经验获取**：
   - 不从OpenRoad的partition management获取（因为需要liberty文件）
   - 从ChipMASRAG自身运行结果中提取：
     - 分区方案：从ChipMASRAG输出的JSON文件中提取
     - 协商模式：从ChipMASRAG的运行日志中提取
     - 质量指标：从OpenRoad的布局结果中提取HPWL，从DEF文件中分析边界代价

3. **知识库构建**：
   - 自举过程：ChipMASRAG在ISPD 2015上运行，生成分区方案
   - 经验提取：从运行结果中提取分区策略、协商模式、质量指标
   - 知识库更新：将提取的经验存入知识库，供后续设计使用

4. **Die Size 知识库（未来工作）**：
   - **问题**：从 floorplan.def 读取的 die size 可能过大（如 265000x265000），导致 OpenROAD OOM
   - **参考案例**：成功案例（dreamplace_experiment/chipkag）使用固定的 die size (5000x5000)，不读 floorplan.def
   - **解决方案**：
     - 将参考设计的 die size 加入知识库，标记为"可运行"（HPWL 为实际值）
     - 将从 floorplan.def 读出的 die size 标记为"OOM"（HPWL 为正无穷或超大数）
     - RAG 检索时优先检索"可运行"的 die size，用于生成 OpenROAD TCL
     - 实现：在知识库案例中添加 `die_size` 字段和 `die_size_status` 字段（"runnable" 或 "oom"）
     - 在 TCL 生成时，如果 RAG 检索到合理的 die size，使用检索到的值；否则使用默认值
   - **实现位置**：
     - 知识库案例格式扩展：`src/knowledge_base.py`
     - TCL 生成逻辑：`src/utils/openroad_interface.py::_generate_tcl_script()`
     - 知识库构建：`scripts/build_kb.py`（提取 die size 和运行状态）

### 9.2 状态编码

- 使用GAT对分区内模块图进行编码
- 融合RAG检索结果到状态表示
- 边界模块单独编码

### 9.3 奖励函数

- 局部奖励：分区内HPWL改进
- 全局奖励：整体HPWL改进（权重0.3）
- 边界惩罚：跨分区连接比例（权重0.5）
- RAG奖励：知识复用有效性（权重0.2）

### 9.4 动态规划兜底

- RAG未命中时使用DP计算分区策略
- DP状态：实例子集+分区分配
- 状态转移考虑边界代价

### 9.5 知识库构建与更新

**构建策略**：

- 初始构建：使用ChipMASRAG在ISPD 2015上的运行结果
- 自举过程：先用DP生成初始案例，逐步积累
- 质量保证：每个案例必须包含完整的分区策略和协商模式

**更新机制**：

- 新设计优化成功后自动添加到知识库
- 更新特征向量和嵌入
- 记录分区策略和协商模式
- 定期清理低质量案例

**ISPD 2015分区经验提取方法**：

由于ISPD 2015没有liberty文件，无法使用OpenRoad的partition management，因此：

1. **分区策略提取**：
   - 从ChipMASRAG输出的分区方案JSON文件中提取
   - 包含：模块到分区的映射、分区边界信息
   - 实现：`scripts/build_kb.py::extract_partition_strategy()`

2. **协商模式提取**：
   - 从ChipMASRAG运行日志中提取协商历史
   - 包含：边界模块列表、协商决策、协商参数和结果
   - 实现：`scripts/build_kb.py::extract_negotiation_patterns()`

3. **质量指标提取**：
   - HPWL：使用OpenRoad API提取（参考现有成功案例的API调用方式）
   - 边界代价：通过分析DEF文件中的跨分区连接计算
   - 运行时间：记录ChipMASRAG分区生成时间和OpenRoad布局时间
   - 实现：`scripts/build_kb.py::extract_quality_metrics()`

## 十、质量保证

### 10.1 代码质量

- 类型注解（Type Hints）
- 文档字符串（Docstrings）
- 单元测试（核心模块）
- 代码审查

### 10.2 实验质量

- 多次运行验证稳定性
- 异常情况处理
- 结果验证（HPWL合理性检查）

### 10.3 文档质量

- README.md：项目说明、快速开始
- 代码注释：关键算法说明
- 实验报告：结果分析与讨论

## 十一、层级化改造与分区流程总结

### 11.1 完整工作流程

**K-SpecPart的完整流程**：
```
1. ISPD 2015 → HGR格式转换
   ↓
2. K-SpecPart逻辑分区（Julia）→ .part.4文件
   ↓
3. 转换为统一格式（partition_scheme）
   ↓
【以下与ChipMASRAG完全相同】
   ↓
4. 层级化改造（提取分区网表 + 生成顶层网表）
   ↓
5. 功能验证（Yosys Formal）
   ↓
6. 物理位置优化（连接性驱动）
   ↓
7. 各分区单独OpenROAD（规模1/K）
   ↓
8. 生成macro LEF
   ↓
9. 顶层OpenROAD（边界代价）
   ↓
10. 边界代价计算
```

**ChipMASRAG的完整流程**：
```
1. RAG检索历史案例
   ↓
2. 多智能体协商逻辑分区 → partition_scheme
   ↓
【以下与K-SpecPart完全相同】
   ↓
3. 层级化改造（提取分区网表 + 生成顶层网表）
   ↓
4. 功能验证（Yosys Formal）
   ↓
5. 物理位置优化（连接性驱动）
   ↓
6. 各分区单独OpenROAD（规模1/K）
   ↓
7. 生成macro LEF
   ↓
8. 顶层OpenROAD（边界代价）
   ↓
9. 边界代价计算
```

### 11.2 关键技术点

**1. 层级化改造（阶段3-4）**
- **目标**：将扁平网表转换为层次化网表
- **输入**：原始扁平设计 + partition_scheme
- **输出**：顶层网表 + 各分区网表
- **验证**：Yosys Formal验证功能等价
- **代码位置**：`src/utils/hierarchical_transformation.py`

**2. 功能等价性验证（阶段4）**
- **工具**：Yosys
- **方法**：Formal equivalence checking
- **验证内容**：原始扁平网表 ≡ (顶层网表 + 分区网表)
- **代码位置**：`src/utils/hierarchical_transformation.py::verify_functional_equivalence()`

**3. 物理位置优化（阶段5）**
- **目标**：基于分区间连接性优化物理位置映射
- **方法**：连接性驱动的贪心算法或ILP
- **公平性保证**：K-SpecPart和ChipMASRAG使用相同算法
- **代码位置**：`src/utils/physical_mapping.py::optimize_physical_layout()`

**4. 边界代价计算（阶段9）**
- **公式**：BC = HPWL_boundary / HPWL_internal_total × 100%
- **分母**：各分区内部HPWL之和（从阶段7获得）
- **分子**：顶层OpenROAD计算的跨分区连接HPWL（从阶段9获得）
- **优势**：
  - ✅ 物理意义清晰
  - ✅ Legalized HPWL
  - ✅ 计算准确（考虑布线拥塞）
- **代码位置**：`src/utils/boundary_analyzer.py::calculate_boundary_cost_improved()`

### 11.3 实现路线图

**阶段A：层级化改造基础设施（1-2周）**
- [ ] 实现`perform_hierarchical_transformation()`
- [ ] 实现`verify_functional_equivalence()`（Yosys集成）
- [ ] 实现`optimize_physical_layout()`
- [ ] 单元测试：小规模设计验证

**阶段B：K-SpecPart集成（1周）**
- [ ] 实现`convert_ispd2015_to_hgr.py`
- [ ] 实现`convert_kspecpart_to_partition_scheme()`
- [ ] 运行K-SpecPart并转换结果
- [ ] 验证：K-SpecPart完整流程通过

**阶段C：ChipMASRAG集成（1周）**
- [ ] 实现ChipMASRAG逻辑分区（RAG + 多智能体）
- [ ] 输出`partition_scheme`
- [ ] 复用阶段A的层级化改造流程
- [ ] 验证：ChipMASRAG完整流程通过

**阶段D：OpenROAD布局（2周）**
- [ ] 实现各分区单独OpenROAD运行
- [ ] 实现macro LEF生成
- [ ] 实现顶层OpenROAD运行
- [ ] 提取HPWL和边界代价
- [ ] 验证：边界代价计算正确

**阶段E：对比实验（1-2周）**
- [ ] 运行K-SpecPart完整流程（16个设计）
- [ ] 运行ChipMASRAG完整流程（16个设计）
- [ ] 对比边界代价、legalized HPWL、运行时间
- [ ] 生成对比报告

### 11.4 代码组织

**新增文件**：
```
src/utils/
├── hierarchical_transformation.py  # 层级化改造
│   ├── perform_hierarchical_transformation()
│   ├── analyze_boundary_connections()
│   ├── extract_partition_netlist()
│   ├── integrate_top_netlist()
│   └── verify_functional_equivalence()
├── physical_mapping.py             # 物理位置优化
│   ├── optimize_physical_layout()
│   └── analyze_partition_connectivity()
├── macro_lef_generator.py          # Macro LEF生成
│   ├── generate_partition_macro_lef()
│   └── extract_boundary_pins()
└── boundary_analyzer.py (更新)     # 边界代价计算
    └── calculate_boundary_cost_improved()

scripts/
├── convert_ispd2015_to_hgr.py     # ISPD 2015转HGR
├── run_kspecpart_full_flow.py     # K-SpecPart完整流程
└── run_chipmasrag_full_flow.py    # ChipMASRAG完整流程

experiments/
└── common_flow.py                  # 公共流程（阶段3-9）
    └── run_common_flow()
```

### 11.5 预期成果

**论文贡献点**：
1. ✅ **知识驱动vs监督学习**：ChipMASRAG无需预训练，通过RAG动态适配
2. ✅ **动态协商vs静态划分**：ChipMASRAG动态优化边界，K-SpecPart一次性划分
3. ✅ **边界代价优化**：ChipMASRAG专门针对边界代价，目标降低>25-30%
4. ✅ **知识复用**：ChipMASRAG知识库命中时加速>60倍
5. ✅ **可扩展性**：ChipMASRAG可处理1.2M+设计，训练时间与规模无关

**实验目标**：
- 边界代价：ChipMASRAG相比K-SpecPart降低>25%
- Legalized HPWL：ChipMASRAG相比K-SpecPart提升>10-15%
- 运行时间：知识库命中时加速>60倍
- 可扩展性：1.2M+设计，训练时间与规模无关

### To-dos
- [ ] 创建项目结构：目录、配置文件、requirements.txt、README.md
- [ ] 实现知识库模块：案例存储、检索、更新接口，支持重新构建的知识库格式
- [ ] 实现RAG检索模块：三级检索（粗粒度→细粒度→语义），返回top-k=10
- [ ] 实现布局环境：状态空间、动作空间、奖励函数（局部+全局+边界+RAG）
- [ ] 实现神经网络：GAT编码器（3层128维）、Actor（2层MLP）、Critic（3层MLP）、协商网络（2层MLP）
- [ ] 实现分区智能体：GAT状态编码、Actor-Critic策略、协商网络、动作选择
- [ ] 实现协调者智能体：RAG统一检索、全局协调、PPO策略网络
- [ ] 实现边界协商协议：识别边界模块、查找相似协商案例、执行协商迁移
- [ ] 实现训练系统：MADDPG（分区智能体）、PPO（协调者）、训练管理器
- [ ] 实现主框架：集成所有组件，提供统一接口（run/train/evaluate）
- [ ] 重新构建知识库：从ChipMASRAG运行结果或ChipHier提取案例，包含设计特征、分区策略、协商模式、质量指标、语义嵌入
- [ ] 实现实验系统：实验运行器、评估器（HPWL/成功率/加速比）、日志系统
- [ ] 运行主实验：ISPD 2015全部16个设计，记录HPWL、成功率、运行时间、知识库命中率
- [ ] 运行知识库复用实验：3-5个代表性设计，计算加速比（目标≥60倍）
- [ ] 运行规模无关性分析：验证子问题规模（1/35）和运行时间线性关系
- [ ] 运行消融实验：完整/无RAG/无协商/无协调者/单智能体，对比HPWL和时间
- [ ] 运行知识驱动边界协商实验：对比知识驱动协商vs传统协商
- [ ] 运行训练规模无关性验证：验证训练时间与设计规模无关
- [ ] 分析知识库质量：16个设计的命中率、覆盖率、检索质量
- [ ] 结果分析：汇总所有实验结果，生成对比表格，分析各组件贡献
- [ ] 归档实验：按时间戳组织结果，记录配置/日志/检查点，确保可复现
