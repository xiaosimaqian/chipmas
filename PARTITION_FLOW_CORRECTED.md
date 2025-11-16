# Partition-based Flow 实现方案（修正版）

## 🎯 用户核心问题

> **您的观点**（✅ 完全正确）：
> 1. "ISPD 2015的design.v就是门级网表，只不过是flatten的"
> 2. "分区后.part.4如何形成分区后的netlist是我关心的"

## ✅ 确认：ISPD 2015提供的文件

```bash
data/ispd2015/mgc_fft_1/
├── design.v        # ✅ 门级网表（flatten）
│   module fft (...);
│   ms00f80 x_out_7_reg_0_ (.ck(ispd_clk), .d(n_13984), .o(x_out_7_0));
│   ms00f80 x_out_7_reg_1_ (.ck(ispd_clk), .d(n_16556), .o(x_out_7_1));
│   ...32281个标准单元实例
│   endmodule
│
├── floorplan.def   # ✅ 物理floorplan
└── tech.lef        # ✅ 工艺库
└── cells.lef       # ✅ 标准单元库
```

**关键发现**：
- ✅ `design.v`是**门级网表**（有`ms00f80`等实例）
- ✅ 是**flatten**的（所有实例在同一层）
- ✅ 与`floorplan.def`中的components **一一对应**

---

## 🔄 两种方案对比（重新评估）

### 方案A：从Verilog网表分区（✅ 可行！推荐！）

**输入**：
- `design.v`（flatten门级网表）
- `.part.4`（K-SpecPart分区结果：component → partition映射）

**流程**：
```python
# 步骤1：解析flatten网表
def parse_flat_netlist(design_v):
    """
    解析design.v，提取：
    1. module instances（例如：ms00f80 x_out_7_reg_0_ (...)）
    2. wire nets（连接关系）
    3. 顶层IO（input/output）
    """
    return {
        'instances': {'x_out_7_reg_0_': {'type': 'ms00f80', 'connections': {...}}},
        'nets': {'n_13984': ['x_out_7_reg_0_', ...]},
        'io': ['ispd_clk', 'x_in_0_0', ...]
    }

# 步骤2：根据.part.4分配instances到partitions
def assign_instances_to_partitions(instances, part_file):
    """
    读取.part.4，分配实例：
    partition_0 = ['x_out_7_reg_0_', 'x_out_7_reg_1_', ...]  (7297个)
    partition_1 = [...]  (7329个)
    ...
    """
    partitions = {0: [], 1: [], 2: [], 3: []}
    with open(part_file) as f:
        for idx, line in enumerate(f):
            partition_id = int(line.strip())
            instance_name = list(instances.keys())[idx]
            partitions[partition_id].append(instance_name)
    return partitions

# 步骤3：识别internal和boundary nets
def identify_nets(instances, partitions):
    """
    分析每个net连接了哪些partitions：
    - internal_net: 只连接1个partition内的实例
    - boundary_net: 连接2个或更多partitions的实例
    """
    internal_nets = {0: [], 1: [], 2: [], 3: []}
    boundary_nets = {}
    
    for net_name, connected_instances in nets.items():
        # 检查这些instances分别在哪些partitions
        partitions_connected = set()
        for inst in connected_instances:
            for pid, insts in partitions.items():
                if inst in insts:
                    partitions_connected.add(pid)
        
        if len(partitions_connected) == 1:
            # Internal net
            pid = partitions_connected.pop()
            internal_nets[pid].append(net_name)
        else:
            # Boundary net
            boundary_nets[net_name] = list(partitions_connected)
    
    return internal_nets, boundary_nets

# 步骤4：生成partition子网表（Verilog）
def generate_partition_netlist(partition_id, instances, nets):
    """
    生成partition_0.v：
    
    module partition_0 (
        // 顶层IO（如果连接到这个partition）
        input ispd_clk,
        // Boundary nets（作为这个partition的IO）
        input n_13984,
        output x_out_7_0,
        ...
    );
        // 只包含这个partition的instances
        ms00f80 x_out_7_reg_0_ (.ck(ispd_clk), .d(n_13984), .o(x_out_7_0));
        ...
    endmodule
    """
    pass

# 步骤5：生成顶层网表（Verilog）
def generate_top_netlist(boundary_nets, physical_regions):
    """
    生成top.v：
    
    module top (
        input ispd_clk,
        input x_in_0_0,
        ...
        output x_out_7_0,
        ...
    );
        // 实例化各个partition（作为黑盒）
        partition_0 u_partition_0 (
            .ispd_clk(ispd_clk),
            .n_13984(n_13984),
            .x_out_7_0(x_out_7_0),
            ...
        );
        
        partition_1 u_partition_1 (...);
        partition_2 u_partition_2 (...);
        partition_3 u_partition_3 (...);
        
        // 只有boundary nets的连线（wire declarations）
        wire n_13984;
        wire x_out_7_0;
        ...
    endmodule
    """
    pass
```

**优点**：
- ✅ **直接从Verilog操作**（OpenROAD原生支持）
- ✅ **逻辑清晰**（从flatten → hierarchical）
- ✅ **可以做Formal验证**（flatten vs hierarchical等价性）

**缺点**：
- ⚠️ 需要**Verilog解析和生成**（但我们已有`hierarchical_transformation.py`）
- ⚠️ 需要**Formal验证**（但我们已有`formal_verification.py`）

### 方案B：从DEF分区（备选）

**输入**：
- `floorplan.def`（含32281 components和nets）
- `.part.4`（component → partition映射）

**流程**：类似方案A，但操作DEF而非Verilog

**优点**：
- ✅ DEF与OpenROAD更接近

**缺点**：
- ❌ DEF是**物理描述**，不是逻辑描述
- ❌ 难以做Formal验证
- ❌ **OpenROAD不一定能读取只有部分components的DEF**

---

## 🎯 推荐方案：从Verilog网表分区（方案A）

### 核心流程（7步）

```
输入：
  - design.v (flatten netlist)
  - mgc_fft_1.hgr.part.4 (K-SpecPart结果)

步骤1: 解析flatten netlist
  → instances: {inst_name: {type, connections}}
  → nets: {net_name: [inst_names]}
  → 使用: hierarchical_transformation.py (已实现)

步骤2: 分配instances到partitions
  → partitions[0] = [7297个instances]
  → partitions[1] = [7329个instances]
  → ...

步骤3: 识别internal和boundary nets
  → internal_nets[0] = [只连接partition_0的nets]
  → boundary_nets = {net: [connected_partitions]}

步骤4: 生成partition子网表（Verilog）
  → partition_0.v, partition_1.v, partition_2.v, partition_3.v
  → 每个包含：该partition的instances + boundary nets作为IO

步骤5: 生成顶层网表（Verilog）
  → top.v
  → 实例化4个partition模块
  → 只有boundary nets和顶层IO

步骤6: Formal验证
  → 使用Yosys验证：design.v ≈ top.v + partition_*.v
  → 使用: formal_verification.py (已实现)

步骤7: 各partition OpenROAD执行
  → 对每个partition_i.v执行OpenROAD
  → read_verilog partition_i.v
  → initialize_floorplan -die_area (物理区域)
  → global_placement + detailed_placement
  → 输出: partition_i_layout.def
```

---

## ✅ 关键决策总结

| 问题 | 决策 | 理由 |
|------|------|------|
| **有Verilog吗？** | ✅ 有！`design.v` | 您的纠正完全正确！ |
| **是否门级？** | ✅ 是！flatten门级网表 | 含`ms00f80`等标准单元 |
| **推荐方案** | ✅ 从Verilog分区（方案A） | 逻辑清晰，可Formal验证 |
| **Formal验证** | ✅ **需要！** | flatten → hierarchical需验证 |
| **DEF的作用** | ✅ 提供component名称 | 与Verilog实例对应 |
| **实现复杂度** | 中等 | 利用已有的模块 |

---

## 📋 修订后的实现计划

### Phase 1：基于Verilog的分区流程（3天）

**任务1：Verilog分区器**（1天）⭐ 核心
- 功能：`src/utils/verilog_partitioner.py`
- 输入：`design.v` + `.part.4`
- 输出：`partition_0.v` ~ `partition_3.v` + `top.v`
- 依赖：复用`hierarchical_transformation.py`的解析逻辑

**任务2：Formal验证**（0.5天）
- 验证：`design.v` ≈ `top.v` + `partition_*.v`
- 依赖：已有`formal_verification.py`

**任务3：各partition OpenROAD执行**（1天）
- 对每个`partition_i.v`执行OpenROAD
- 生成`partition_i_layout.def`
- 并行执行（4个partition同时）

**任务4：Macro LEF生成 + 顶层组装**（0.5天）
- 依赖：已有`macro_lef_generator.py`

### Phase 2：mgc_fft_1完整实验（1天）

### Phase 3：知识库集成（0.5天）

**总时间：5天**

---

## 🔥 立即行动

**第一步**：实现 `src/utils/verilog_partitioner.py`

```python
"""
Verilog Partitioner - 从flatten网表生成分区子网表

输入：
  - design.v (flatten netlist)
  - .part.4 (K-SpecPart结果)

输出：
  - partition_0.v ~ partition_3.v (子网表)
  - top.v (顶层网表，实例化各partition)
  - boundary_analysis.json (boundary nets统计)
"""

class VerilogPartitioner:
    def __init__(self, design_verilog: Path, partition_file: Path):
        self.design_verilog = design_verilog
        self.partition_file = partition_file
        
        # 复用hierarchical_transformation的解析逻辑
        from src.utils.hierarchical_transformation import HierarchicalTransformation
        self.parser = HierarchicalTransformation(...)
    
    def partition(self, num_partitions: int) -> Dict:
        """
        主流程：
        1. 解析flatten netlist
        2. 读取分区方案
        3. 识别boundary nets
        4. 生成partition子网表
        5. 生成top网表
        """
        # Step 1: Parse
        instances, nets, io = self._parse_netlist()
        
        # Step 2: Assign
        partitions = self._assign_instances(instances)
        
        # Step 3: Identify boundary
        internal_nets, boundary_nets = self._identify_boundary_nets(nets, partitions)
        
        # Step 4: Generate partition netlists
        partition_files = self._generate_partition_netlists(partitions, internal_nets, boundary_nets)
        
        # Step 5: Generate top netlist
        top_file = self._generate_top_netlist(boundary_nets, io)
        
        return {
            'partition_files': partition_files,
            'top_file': top_file,
            'boundary_analysis': {
                'boundary_nets_count': len(boundary_nets),
                'internal_nets_count': {p: len(nets) for p, nets in internal_nets.items()}
            }
        }
```

**时间**：1天  
**优先级**：P0 🔥

---

## 📊 关键指标对比

| 指标 | 方案A（Verilog） | 方案B（DEF） |
|------|------------------|--------------|
| **实现复杂度** | 中等（已有解析器） | 高（需新写DEF操作） |
| **OpenROAD兼容性** | ✅ 原生支持 | ⚠️ 不确定 |
| **Formal验证** | ✅ 可以 | ❌ 困难 |
| **逻辑清晰度** | ✅ 高 | ⚠️ 物理+逻辑混杂 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## 🎯 总结

**您的核心问题**：
> ".part.4如何形成分区后的netlist"

**答案**：
1. ✅ **解析`design.v`**（flatten门级网表）
2. ✅ **根据`.part.4`**（component → partition映射）
3. ✅ **识别boundary nets**（连接多个partition的nets）
4. ✅ **生成partition子网表**（`partition_0.v` ~ `partition_3.v`）
   - 包含：该partition的instances
   - IO：boundary nets + 顶层IO
5. ✅ **生成top网表**（`top.v`）
   - 实例化4个partition模块
   - 只有boundary nets连线
6. ✅ **Formal验证**（Yosys）
   - 验证：`design.v` ≈ `top.v` + `partition_*.v`

**关键技术**：
- **Verilog解析**：复用`hierarchical_transformation.py`
- **Boundary分析**：新实现（核心算法）
- **Verilog生成**：标准Verilog语法
- **Formal验证**：复用`formal_verification.py`

**实现时间**：5天

**是否开始？** 🚀

