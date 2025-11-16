# Partition-based Flow 实现方案澄清

## 🎯 核心问题

**用户观点**：
> "openroad不依赖def就可以执行，因此是否分区netlist执行openroad就能生成def，而不是用算法提取？所以和3是否可以合并。"

**分析结果**：✅ 完全正确！但需要澄清netlist来源。

---

## 📊 ISPD 2015现状分析

### 我们有什么：
1. ✅ `floorplan.def` - 完整设计的DEF（包含所有components和nets）
2. ✅ `tech.lef`, `cells.lef` - LEF文件
3. ✅ `.part.4` - K-SpecPart分区结果（component → partition映射）

### 我们没有什么：
1. ❌ Verilog门级网表（ISPD 2015不提供）
2. ❌ 各分区的独立DEF文件
3. ❌ 各分区的Verilog网表

---

## 🔄 两种可行方案对比

### 方案A：从DEF提取（原计划）

**流程**：
```
1. 解析floorplan.def
2. 根据.part.4，提取partition_0的components和internal nets
3. 生成partition_0.def（小规模DEF）
4. OpenROAD读取partition_0.def执行布局
5. 输出partition_0_layout.def
```

**优点**：
- ✅ 不需要Verilog网表
- ✅ 直接利用现有DEF
- ✅ 保留了原始的component定义

**缺点**：
- ❌ 需要实现DEF解析和提取逻辑
- ❌ 需要识别internal nets vs boundary nets
- ❌ 代码复杂度高

### 方案B：从Verilog网表（用户建议的理想方案）

**流程**：
```
1. 有门级Verilog网表（gate-level netlist）
2. 根据.part.4，提取partition_0的子网表
3. OpenROAD读取子网表执行布局
4. 输出partition_0_layout.def
```

**优点**：
- ✅ OpenROAD原生支持Verilog输入
- ✅ 不需要复杂的DEF提取
- ✅ 代码简洁

**缺点**：
- ❌ **ISPD 2015不提供门级Verilog网表！**
- ❌ 无法实施

### 方案C：DEF → Verilog → 分区 → OpenROAD（混合方案）

**流程**：
```
1. 从floorplan.def反向生成Verilog网表
2. 根据.part.4，提取partition_0的子网表
3. OpenROAD读取子网表执行布局
4. 输出partition_0_layout.def
```

**优点**：
- ✅ 一旦有Verilog，后续流程简洁
- ✅ 可以做Formal验证

**缺点**：
- ❌ DEF → Verilog转换复杂且不准确
- ❌ 可能丢失时序、属性等信息
- ❌ 不如直接操作DEF可靠

---

## ✅ 推荐方案：改进的方案A

### 核心改进：简化DEF提取

**关键洞察**：
- OpenROAD可以读取包含多余components的DEF
- 只要指定正确的die_area和需要布局的components即可
- **不一定要物理删除DEF中的其他components**

### 简化后的流程：

```python
def generate_partition_def_simple(
    original_def: Path,
    partition_components: List[str],  # partition_0的component列表
    physical_region: Tuple,  # (x, y, width, height)
    output_def: Path
):
    """
    简化方案：只修改DIEAREA和标记components
    不物理删除无关components
    """
    # 1. 读取原始DEF
    with open(original_def, 'r') as f:
        def_content = f.read()
    
    # 2. 修改DIEAREA（指定分区的物理区域）
    new_diearea = f"{physical_region[0]} {physical_region[1]} " \
                  f"{physical_region[0]+physical_region[2]} " \
                  f"{physical_region[1]+physical_region[3]}"
    def_content = re.sub(
        r'DIEAREA.*?;',
        f'DIEAREA ( {new_diearea} ) ;',
        def_content
    )
    
    # 3. 标记需要布局的components（添加注释或属性）
    # OpenROAD可以通过TCL脚本只处理特定components
    
    # 4. 保存
    with open(output_def, 'w') as f:
        f.write(def_content)
    
    return output_def
```

**OpenROAD TCL脚本配合**：
```tcl
read_def partition_0.def

# 只对partition_0的components执行布局
# 使用OpenROAD的component selection功能
set partition_comps [list comp1 comp2 comp3 ...]
# ... 布局逻辑 ...
```

---

## 🔥 最终推荐方案（混合最优）

### 实际可行的最佳方案：

**步骤1：智能DEF提取**（必需，但可简化）
```python
def extract_partition_def_smart(
    original_def: Path,
    partition_scheme: Dict[int, List[str]],
    physical_regions: Dict[int, Tuple]
) -> Dict[int, Path]:
    """
    智能提取：
    1. 识别internal nets（只连接partition内部）
    2. 识别boundary nets（连接多个partition）
    3. 为每个partition生成精简DEF（只含internal nets）
    """
    # 这一步无法完全避免，因为需要区分internal和boundary nets
    # 但可以简化：不需要完美提取，OpenROAD可以忽略未连接的nets
```

**步骤2-3：合并（OpenROAD执行）**
```python
def run_partition_openroad(partition_id, partition_def, physical_region):
    """
    读取partition_def（可能包含多余的nets，但OpenROAD会忽略）
    指定die_area = physical_region
    执行global_placement + detailed_placement
    输出partition_layout.def
    """
    # 这一步就是标准的OpenROAD执行
    # 与步骤1逻辑分离，可以并行
```

---

## 📝 关于Formal验证

### 用户观点：
> "formal还是需要的，主要是netlist变化，需要把分区后集成的和原版flatten的做对比"

### 分析：

**情况A：基于DEF的物理分区**（当前方案）
```
原始: floorplan.def (32281 components, 所有nets)
分区后:
  - partition_0.def (7297 components, internal nets)
  - partition_1.def (7329 components, internal nets)
  - ...
  - top.def (4 macro components, boundary nets)
```

**逻辑变化**：
- ✅ Components不变（只是分组）
- ✅ Nets不变（只是分为internal和boundary）
- ✅ 连接关系不变
- ❌ **没有逻辑网表变化！只是物理分区！**

**结论**：**不需要Formal验证！**
- 原因：DEF是物理描述，不是逻辑描述
- 验证方式：检查components总数 + nets总数是否匹配

**情况B：如果使用Verilog网表分区**（假设有网表）
```
原始: design.v (flatten module)
分区后:
  - partition_0.v (sub-module)
  - partition_1.v (sub-module)
  - top.v (instantiates partition modules)
```

**逻辑变化**：
- ⚠️ 网表层次结构改变（flatten → hierarchical）
- ⚠️ 可能引入信号重命名

**结论**：**需要Formal验证！**

### 最终判断：

对于**基于DEF的component-level分区**：
- ❌ **不需要Formal验证**
- ✅ 只需要**一致性检查**：
  - Components总数匹配
  - Nets总数匹配（internal + boundary）
  - 连接关系完整

对于**基于Verilog的netlist-level分区**：
- ✅ **需要Formal验证**
- 使用Yosys `equiv_check`

---

## 🎯 修订后的实现步骤

### Phase 1：必需的基础设施（3天）

**任务1：Boundary Nets识别**（1天）⭐ 核心
```python
def identify_boundary_and_internal_nets(
    def_file: Path,
    partition_scheme: Dict[int, List[str]]
) -> Tuple[Dict, Dict]:
    """
    解析DEF，识别：
    1. internal_nets[partition_id] = [net_names]
    2. boundary_nets = {net_name: [connected_partitions]}
    
    这是核心逻辑，无法避免
    """
```

**任务2：简化的Partition DEF生成**（0.5天）
```python
def generate_partition_def_lite(
    original_def: Path,
    partition_id: int,
    internal_nets: List[str],
    physical_region: Tuple,
    output_def: Path
):
    """
    简化版：
    1. 复制原始DEF
    2. 修改DIEAREA为physical_region
    3. 只保留internal_nets（删除boundary nets）
    4. 保留该partition的components
    """
```

**任务3：顶层DEF生成**（1天）
```python
def generate_top_def(
    partition_lefs: Dict[int, Path],
    boundary_nets: Dict,
    physical_regions: Dict[int, Tuple]
):
    """
    生成top.def：
    1. COMPONENTS: 4个partition macros（固定位置）
    2. NETS: 只包含boundary_nets
    3. PINS: 从partition LEFs提取
    """
```

**任务4：完整流程脚本**（0.5天）
```python
# 集成上述3个模块 + 已有的：
# - physical_mapping.py（物理位置优化）
# - macro_lef_generator.py（LEF生成）
# - OpenROAD执行（并行）
```

### Phase 2：mgc_fft_1实验（1天）

### Phase 3：知识库集成（0.5天）

**总时间：5天**（比原计划少1天，因为简化了DEF提取）

---

## ✅ 关键决策总结

| 问题 | 决策 | 理由 |
|------|------|------|
| **DEF提取 vs Netlist** | ✅ 简化的DEF提取 | ISPD 2015无Verilog |
| **步骤1和3合并？** | ❌ 不完全合并，但简化步骤1 | 需要识别boundary nets |
| **Formal验证** | ❌ 不需要 | 基于DEF的物理分区，无逻辑变化 |
| **总时间** | 5天（原6天） | 简化后更快 |

---

## 📋 立即行动

**下一步**：实现 `src/utils/boundary_nets_analyzer.py`
- 功能：识别internal和boundary nets
- 时间：1天
- 优先级：P0 🔥

这是整个流程的核心，其他步骤都依赖它！
