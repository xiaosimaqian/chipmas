# 阶段1端到端集成测试使用说明

## 测试概述

`test_stage1_end_to_end.py` 是阶段1（层级化改造）的完整集成测试，**真实运行OpenROAD**验证以下流程：

1. **层级化改造** - 将平坦网表分解为分区网表和顶层网表
2. **Formal验证** - 使用Yosys验证功能等价性
3. **物理位置优化** - 基于连接性优化分区布局
4. **OpenROAD布局** - 真实运行OpenROAD对每个分区进行布局
5. **Macro LEF生成** - 从OpenROAD生成的真实DEF提取Macro LEF

⚠️  **重要**: 本测试**无任何模拟或mock数据**，所有文件均为真实运行生成。

## 前置条件

### 必需

- ✅ **OpenROAD已安装且可用**
  - 验证: `openroad -version`
  - 安装: 参考 [OpenROAD官方文档](https://github.com/The-OpenROAD-Project/OpenROAD)

- ✅ **Yosys已安装且可用**
  - 验证: `yosys -V`
  - 安装: `brew install yosys` (macOS) 或参考官方文档

### 资源要求

- ⏱️  **运行时间**: 2-5分钟/分区（共2个分区）
- 💾 **内存**: 最小2GB可用内存
- 💿 **磁盘**: 临时文件约100MB

## 运行方法

### 基本运行

```bash
cd /path/to/chipmas
python3 tests/integration/test_stage1_end_to_end.py
```

### 查看帮助

```bash
python3 tests/integration/test_stage1_end_to_end.py --help
```

## 输出说明

### 完整流程

```
================================================================================
阶段1端到端集成测试
模式: 真实OpenROAD运行 🔧
================================================================================

完整流程概览:
┌─────────────────────────────────────────────────────────────────┐
│  原始设计 (design.v - 平坦网表)                                 │
│    ↓ 步骤1: 层级化改造                                         │
│  ├─ partition_0.v (分区0网表)                                  │
│  ├─ partition_1.v (分区1网表)                                  │
│  └─ adder_4bit_top.v (顶层网表，实例化分区)                    │
│    ↓ 步骤2: Formal验证 (Yosys)                                │
│  验证: design.v ≡ {top.v + partition_*.v}                      │
│    ↓ 步骤3: 物理位置优化                                       │
│  优化分区在Die上的物理位置（基于连接性）                       │
│    ↓ 步骤4: OpenROAD布局 (真实运行)                            │
│  partition_*.v → OpenROAD → partition_*.def                    │
│    ↓ 步骤5: Macro LEF生成                                      │
│  partition_*.def → MacroLEFGenerator → partition_*.lef         │
└─────────────────────────────────────────────────────────────────┘
```

### OpenROAD运行输出

```
步骤4: OpenROAD布局（真实运行）
--------------------------------------------------------------------------------

  🔧 运行OpenROAD布局: partition_0
     TCL: partition_0.tcl
     日志: partition_0.log
  ✓ partition_0 布局成功
  ✓ DEF生成: partition_0.def (12345 bytes)

  🔧 运行OpenROAD布局: partition_1
     TCL: partition_1.tcl
     日志: partition_1.log
  ✓ partition_1 布局成功
  ✓ DEF生成: partition_1.def (11234 bytes)

  ✓ OpenROAD生成了 2 个真实DEF文件
```

### 成功输出

```
================================================================================
测试总结
================================================================================
层级化改造: ✓ 通过
Formal验证: ✓ 等价性验证通过
物理位置优化: ✓ 通过
OpenROAD布局: ✓ 真实运行成功
Macro LEF生成: ✓ 从真实DEF生成

================================================================================
✓ 阶段1端到端集成测试完成！
================================================================================

所有模块协同工作正常，流程完整可用！
所有文件均为真实运行生成，无任何模拟数据。
```

## 查看详细信息

测试脚本会实时显示：

### 网表内容
- ✅ 原始平坦网表内容
- ✅ 各分区网表内容
- ✅ 顶层网表内容

### Yosys验证
- ✅ Yosys验证脚本完整内容
- ✅ Yosys执行输出（最后30行）
- ✅ 等价性检查结果

### OpenROAD布局
- ✅ 生成的TCL脚本
- ✅ OpenROAD执行日志
- ✅ 生成的DEF文件内容（前50行）

### LEF生成
- ✅ 生成的Macro LEF文件完整内容
- ✅ LEF和DEF的对应关系说明

## 故障排查

### OpenROAD不可用

**症状:**
```
✗ OpenROAD不可用

请确保:
  1. OpenROAD已安装
  2. openroad命令在PATH中
  3. 运行: openroad -version
```

**解决方案:**

1. 检查安装:
```bash
which openroad
```

2. 检查版本:
```bash
openroad -version
```

3. 如未安装，参考[OpenROAD安装指南](https://github.com/The-OpenROAD-Project/OpenROAD)

### OpenROAD布局失败

**症状:**
```
✗ partition_0 布局失败 (返回码: 1)
最后15行日志:
  [ERROR] ...
```

**解决方案:**

1. 查看完整日志文件（路径会在输出中显示）
2. 检查网表语法是否正确
3. 检查LEF文件是否有效
4. 确保die size和core area配置合理

### Yosys验证失败

**症状:**
```
✗ Yosys执行失败
```

**解决方案:**

1. 检查Yosys安装:
```bash
yosys -V
```

2. 查看验证日志文件
3. 检查网表语法
4. 确认模块名称一致

### 内存不足

**症状:**
```
✗ partition_0 布局异常: MemoryError
```

**解决方案:**

1. 关闭其他应用释放内存
2. 使用更小的die size
3. 减少分区数量

## 测试设计说明

### 当前测试用例

- **设计**: 4位加法器（`adder_4bit`）
- **分区**: 2个分区
  - Partition 0: 低2位（bit 0-1）
  - Partition 1: 高2位（bit 2-3）
- **边界连接**: 进位信号（c2）

### 为什么使用简单设计？

1. ✅ **快速验证** - 运行时间短（<5分钟）
2. ✅ **易于理解** - 清晰的分区逻辑
3. ✅ **可预测结果** - 容易验证正确性
4. ✅ **真实流程** - 完全等同于大规模设计的流程

### 扩展到真实设计

阶段1测试通过后，相同流程可应用于：
- ISPD 2015设计（mgc_fft_1等）
- 任意Verilog RTL设计
- 支持2-N个分区

## 集成到开发流程

### Git Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit
python3 tests/integration/test_stage1_end_to_end.py
if [ $? -ne 0 ]; then
    echo "❌ 阶段1测试失败，提交中止"
    exit 1
fi
echo "✅ 阶段1测试通过"
```

### CI/CD Pipeline (GitHub Actions)

```yaml
name: Stage 1 Integration Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Install OpenROAD
        run: |
          # 添加OpenROAD安装步骤
          
      - name: Install Yosys
        run: sudo apt-get install -y yosys
      
      - name: Run Stage 1 Tests
        run: python3 tests/integration/test_stage1_end_to_end.py
        timeout-minutes: 10
```

## 性能优化建议

### 加速测试

1. **并行布局** - 修改代码使用多进程并行运行OpenROAD
2. **缓存LEF** - 复用技术LEF文件
3. **跳过可视化** - 注释掉可视化生成代码

### 减少资源消耗

1. **更小的die size** - 减小测试用的die_area
2. **更少的分区** - 使用2分区而非更多
3. **临时目录** - 确保tmpdir在SSD上

## 相关文件

### 核心实现
- `src/utils/hierarchical_transformation.py` - 层级化改造
- `src/utils/formal_verification.py` - Formal验证
- `src/utils/physical_mapping.py` - 物理位置优化
- `src/utils/macro_lef_generator.py` - Macro LEF生成

### 单元测试
- `tests/unit/test_hierarchical_transformation.py`
- `tests/unit/test_formal_verification.py`
- `tests/unit/test_physical_mapping.py`
- `tests/unit/test_macro_lef_generator.py`

### 文档
- `WORK_SUMMARY_AND_PLAN.md` - 项目总体计划
- `docs/physical_mapping_explanation.md` - 物理映射详解

## 下一步

✅ **阶段1测试通过后**，进入阶段2：

1. **公共流程实现** - `experiments/common/flow.py`
   - 集成OpenROAD partition-based flow
   - 实现boundary cost计算
   - 支持批量处理

2. **K-SpecPart集成**
   - Julia环境搭建
   - HGR格式转换
   - K-SpecPart运行流程

3. **ChipMASRAG实现**
   - 多智能体系统
   - 知识库和RAG
   - 强化学习训练

## 常见问题

### Q: 为什么必须真实运行OpenROAD？

A: 因为：
1. DEF文件格式复杂，模拟无法保证完全正确
2. PIN位置由OpenROAD计算，无法手动模拟
3. 需要验证与OpenROAD的真实集成
4. 测试的目的是验证完整端到端流程

### Q: 测试时间太长怎么办？

A: 
1. 这是一次性验证，日常开发使用单元测试
2. 可以在CI/CD中设置缓存
3. 未来可以并行化OpenROAD运行

### Q: 可以跳过Formal验证吗？

A: 不建议，因为：
1. Formal验证是保证正确性的关键
2. 运行时间很短（<5秒）
3. 可以及早发现网表生成问题

## 技术支持

遇到问题请：

1. 查看完整日志文件
2. 检查OpenROAD和Yosys版本
3. 参考单元测试代码
4. 查看`WORK_SUMMARY_AND_PLAN.md`中的故障排查章节

---

**最后更新**: 2025-11-14  
**版本**: 1.0 (真实OpenROAD版本)  
**状态**: ✅ 已验证通过
