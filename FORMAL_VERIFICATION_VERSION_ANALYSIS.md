# Formal验证版本差异分析报告

## 📋 问题总结

**现象**：
- ✅ **本地测试通过**：Yosys 0.56，Formal验证成功
- ❌ **服务器测试失败**：Yosys 0.9，Formal验证失败（1984个未证明的输出端口）

## 🔍 详细对比分析

### 环境对比

| 项目 | 本地 | 服务器 |
|------|------|--------|
| Yosys版本 | 0.56 (git sha1 9c447ad9d4b1ea589369364eea38b4d70da2c599) | 0.9 (git sha1 1979e0b) |
| Python版本 | 3.13.7 | 3.8.10 |
| 验证结果 | ✅ 通过 | ❌ 失败 |
| 运行时间 | 9.54秒 | 35.78秒 |

### Yosys验证日志对比

#### 本地（Yosys 0.56）- 成功

```
Found 1984 unproven $equiv cells (1984 groups) in equiv:
Proved 1984 previously unproven $equiv cells.  ← equiv_simple成功
Proved 0 previously unproven $equiv cells.      ← equiv_induct
Found 1984 $equiv cells in equiv:               ← 全部证明
```

**结果**：所有1984个输出端口都被证明等价 ✅

#### 服务器（Yosys 0.9）- 失败

```
Found 1984 unproven $equiv cells (1984 groups) in equiv:
Proved 0 previously unproven $equiv cells.      ← equiv_simple失败
Found 1984 unproven $equiv cells in module equiv:
Proved 0 previously unproven $equiv cells.     ← equiv_induct失败
Found 1984 $equiv cells in equiv:
  Unproven $equiv ...                           ← 全部未证明
ERROR: Found 1984 unproven $equiv cells in 'equiv_status -assert'.
```

**结果**：所有1984个输出端口都无法证明 ❌

## 🎯 根本原因

**Yosys版本差异导致的equiv_simple算法变化**

1. **Yosys 0.56**：
   - `equiv_simple`能够成功证明所有1984个输出端口
   - 算法对输出端口的等价性检查更强大

2. **Yosys 0.9**：
   - `equiv_simple`无法证明任何输出端口（`Proved 0`）
   - `equiv_induct`也无法证明
   - 可能是算法变化或bug导致

## 📊 验证脚本对比

**验证脚本完全相同**（仅路径不同）：

```tcl
# Read flat design (gold)
read_verilog data/ispd2015/mgc_fft_1/design.v
hierarchy -top fft
proc; opt_clean
flatten
rename -top gold

# Read hierarchical design (gate)
design -stash gold_design
design -push
read_verilog partition_*.v
read_verilog top.v
hierarchy -top fft
proc; opt_clean
flatten
rename -top gate

# Load gold design
design -copy-from gold_design gold

# Equivalence check
equiv_make gold gate equiv
equiv_simple      ← 关键步骤
equiv_induct
equiv_status -assert
```

## 🔧 解决方案

### 方案1：升级服务器Yosys版本（推荐）

**目标**：将服务器Yosys升级到0.56或更新版本

```bash
# 在服务器上
cd ~
git clone https://github.com/YosysHQ/yosys.git yosys_build
cd yosys_build
git checkout 0.56  # 或使用最新版本
make config-gcc
make -j$(nproc)
sudo make install  # 或添加到PATH
```

**优点**：
- 与本地环境一致
- 使用已验证可工作的版本

**缺点**：
- 需要编译时间
- 可能需要安装依赖

### 方案2：调整验证策略

**尝试更强大的验证方法**：

```tcl
# 在equiv_simple之前添加更多优化
equiv_make gold gate equiv
opt -full
equiv_simple -undef
equiv_induct -undef
equiv_status -assert
```

**或者使用sat验证**：

```tcl
equiv_make gold gate equiv
equiv_simple
sat -verify -prove-asserts -show-all equiv
```

### 方案3：接受版本差异（不推荐）

如果Yosys 0.9确实无法证明这些输出端口，但网表结构是正确的，可以考虑：
- 手动验证关键输出端口
- 使用其他验证工具
- 在文档中说明版本限制

## 📝 验证的网表结构

**已验证**：
- ✅ Boundary nets正确识别：2203个（包括1984个顶层输出端口）
- ✅ Partition网表正确生成：4个partition网表
- ✅ 顶层网表正确生成：输出端口正确连接
- ✅ 本地Yosys 0.56验证通过：所有输出端口等价

**问题**：
- ❌ 服务器Yosys 0.9无法证明输出端口等价
- ⚠️ 这是Yosys版本差异，不是网表生成问题

## 🎯 推荐行动

1. **立即行动**：升级服务器Yosys到0.56或更新版本
2. **验证**：重新运行测试，确认验证通过
3. **文档**：在README中说明Yosys版本要求（≥0.56）

## 📚 相关文件

- `src/utils/formal_verification.py`：Formal验证实现
- `tests/results/partition_flow/mgc_fft_1_local/`：本地测试结果（成功）
- `tests/results/partition_flow/mgc_fft_1_server/`：服务器测试结果（失败）

---

**分析时间**：2025-11-15  
**结论**：Yosys版本差异导致验证失败，建议升级服务器Yosys版本

