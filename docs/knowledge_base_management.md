# 知识库管理文档

**快速导航**：
- [知识库位置](#📍-知识库位置)
- [当前状态](#📊-知识库当前状态)
- [更新历史](#🔄-知识库更新历史)
- [备份策略](#🛡️-备份策略)
- [数据结构](#📝-知识库数据结构)
- [维护工具](#🔧-知识库维护工具)
- [原始数据来源](#📂-原始数据来源)

## 📍 知识库位置

### 服务器知识库
- **主知识库路径**: `~/chipmas/data/knowledge_base/kb_cases.json`
- **完整路径**: `/home/keqin/chipmas/data/knowledge_base/kb_cases.json`
- **备份目录**: `~/chipmas/data/knowledge_base/backups/`

### 本地知识库（如有）
- **主知识库路径**: `chipmas/data/knowledge_base/kb_cases.json`
- **备份目录**: `chipmas/data/knowledge_base/backups/`

---

## 📊 知识库当前状态

### 最新更新（2025-11-15）

| 指标 | 数值 |
|------|------|
| 总案例数 | 28 |
| OpenROAD案例 | 16 (ISPD 2015) |
| DreamPlace案例 | 12 (ISPD 2005: adaptec/bigblue) |
| 文件大小 | ~288 KB |
| 最后更新 | 2025-11-15T08:22:33 |
| EXP-002集成 | ✅ 已完成 |

### 案例分布

**OpenROAD案例（16个）- ISPD 2015:**
- mgc_pci_bridge32_a, mgc_pci_bridge32_b
- mgc_fft_1, mgc_fft_2, mgc_fft_a, mgc_fft_b
- mgc_des_perf_1, mgc_des_perf_a, mgc_des_perf_b
- mgc_edit_dist_a
- mgc_matrix_mult_1, mgc_matrix_mult_a, mgc_matrix_mult_b
- mgc_superblue16_a, mgc_superblue11_a, mgc_superblue12

**DreamPlace案例（12个）- ISPD 2005/其他:**
- adaptec1, adaptec2, adaptec3, adaptec4
- bigblue1, bigblue2, bigblue3, bigblue4
- mgc_matrix_mult_2
- mgc_superblue14, mgc_superblue19
- superblue16a

---

## 🔄 知识库更新历史

### 2025-11-15 08:22 - EXP-002 OpenROAD数据集成
- **操作**: 添加/更新16个ISPD 2015设计的OpenROAD完整数据
- **更新案例**: 15个
- **新增案例**: 1个 (mgc_matrix_mult_b)
- **备份文件**: `kb_cases_backup_20251115_082233.json`
- **脚本**: `scripts/update_kb_with_clean_baseline.py`
- **数据来源**: EXP-002 Clean Baseline (`results/clean_baseline/`)
- **新增字段**:
  - `legalized_hpwl`
  - `global_placement_hpwl`
  - `openroad_source`
  - `die_size`
  - `core_area`

### 2025-11-12~13 - 初始知识库构建
- **操作**: 从DreamPlace结果构建初始知识库
- **案例数**: 27个
- **脚本**: `scripts/build_kb.py`
- **数据来源**: DreamPlace实验结果

---

## 🛡️ 备份策略

### 自动备份规则
1. **每次更新前自动备份**
   - 命名格式: `kb_cases_backup_YYYYMMDD_HHMMSS.json`
   - 位置: 同目录下
   
2. **定期手动备份**（建议）
   - 每周备份到独立目录: `backups/weekly/`
   - 每月备份到独立目录: `backups/monthly/`

### 备份命令

```bash
# 手动创建带时间戳的备份
cd ~/chipmas/data/knowledge_base
cp kb_cases.json backups/kb_cases_$(date +%Y%m%d_%H%M%S).json

# 查看所有备份
ls -lh backups/

# 恢复备份（示例）
cp backups/kb_cases_backup_20251115_082233.json kb_cases.json
```

---

## 📝 知识库数据结构

### 顶层结构
```json
{
  "version": "1.0",
  "num_cases": 28,
  "last_updated": "2025-11-15T08:22:33.082076",
  "exp_002_integrated": true,
  "cases": [...]
}
```

### 单个案例结构
```json
{
  "design_id": "mgc_des_perf_1",
  "features": [...],  // 9维特征向量
  "partition_strategy": {},
  "negotiation_patterns": {},
  "quality_metrics": {
    "hpwl": 2630765.5,
    "legalized_hpwl": 2630765.5,
    "global_placement_hpwl": 2550024.0,
    "num_components": 112644,
    "num_nets": 112880,
    "runtime_seconds": 1117.19,
    "die_size": "0 0 5000 5000",
    "core_area": "250 250 4750 4750",
    "openroad_source": "EXP-002_clean_baseline",
    "boundary_cost": 0.0,
    "num_modules": 0
  },
  "timestamp": "2025-11-15T...",
  "embedding": [...]  // 128维嵌入向量
}
```

### OpenROAD案例 vs DreamPlace案例区别

| 字段 | OpenROAD案例 | DreamPlace案例 |
|------|--------------|----------------|
| `legalized_hpwl` | ✅ 有 | ❌ 无 (None) |
| `global_placement_hpwl` | ✅ 有 | ❌ 无 (None) |
| `openroad_source` | ✅ 有 ("EXP-002_clean_baseline") | ❌ 无 (None) |
| `die_size` | ✅ 有 | ❌ 无 |
| `core_area` | ✅ 有 | ❌ 无 |
| `hpwl` | ✅ 有 (=legalized_hpwl) | ✅ 有 (DreamPlace HPWL) |

---

## 🔧 知识库维护工具

### 1. 查询工具
```bash
# 查询知识库基本信息
python3 scripts/query_kb.py

# 查询特定设计
python3 scripts/query_kb.py --design mgc_fft_1
```

### 2. 更新工具
```bash
# 从EXP-002结果更新知识库
python3 scripts/update_kb_with_clean_baseline.py

# 从新实验结果更新知识库（未来）
python3 scripts/update_kb_from_experiment.py --exp EXP-003
```

### 3. 验证工具
```bash
# 验证知识库完整性
python3 scripts/validate_kb.py

# 检查重复案例
python3 scripts/check_kb_duplicates.py
```

### 4. 备份管理
```bash
# 创建备份
python3 scripts/backup_kb.py

# 列出所有备份
python3 scripts/list_kb_backups.py

# 恢复备份
python3 scripts/restore_kb.py --backup kb_cases_backup_20251115_082233.json
```

---

## ⚠️ 注意事项

### 更新知识库前必须检查：
1. ✅ **创建备份**: 确保自动创建了时间戳备份
2. ✅ **验证数据**: 确认新数据格式正确
3. ✅ **检查重复**: 避免重复添加相同设计
4. ✅ **保留原有数据**: 不要覆盖DreamPlace等其他来源的数据

### 数据一致性原则：
1. **设计ID唯一性**: 每个设计只能有一条记录
2. **数据来源标记**: 使用`openroad_source`等字段标记数据来源
3. **字段完整性**: OpenROAD案例必须包含`legalized_hpwl`等字段
4. **时间戳记录**: 每次更新记录`timestamp`

### 避免的操作：
- ❌ 直接修改JSON文件（使用脚本）
- ❌ 删除现有案例（除非确认重复）
- ❌ 更改已有案例的`design_id`
- ❌ 不备份直接更新

---

## 📈 未来计划

### 待添加的数据
1. **K-SpecPart实验结果**
   - 16个ISPD 2015设计的分区结果
   - 分区后的HPWL和边界代价
   
2. **ChipMASRAG实验结果**
   - 多智能体协商生成的分区方案
   - RAG检索命中率
   - 训练过程数据

3. **消融实验结果**
   - 不同组件的贡献分析
   - 对比数据

### 知识库增强
1. **嵌入向量更新**
   - 使用真实的设计嵌入替换占位符
   - 支持相似设计检索

2. **分区策略记录**
   - 记录详细的分区方案
   - 记录协商过程

3. **质量指标扩展**
   - 添加功耗、面积等指标
   - 添加布线完成度

---

## 📂 原始数据来源

### OpenROAD数据源（16个ISPD 2015设计）

**数据来源**: EXP-002 Clean Baseline收集

| 项目 | 路径 |
|------|------|
| **Clean Baseline结果** | `~/chipmas/results/clean_baseline/` |
| **原始设计文件** | `~/chipmas/data/datasets/ispd_2015_contest_benchmark/` |
| **实验记录** | `../EXPERIMENTS.md` (EXP-002) |
| **汇总报告** | `results/clean_baseline/summary.json` |

**各设计目录结构** (`results/clean_baseline/{design_name}/`):
```
mgc_fft_1/
├── result.json                    # 完整结果数据
├── mgc_fft_1_clean.tcl           # OpenROAD TCL脚本
├── mgc_fft_1_clean_layout.def    # 布局DEF文件
└── logs/
    └── openroad_*.log            # OpenROAD运行日志
```

**数据字段** (result.json):
- `design`: 设计名称
- `status`: 运行状态 (success/error)
- `component_count`: 组件数
- `net_count`: 网络数
- `global_placement_hpwl`: Global Placement HPWL
- `legalized_hpwl`: Legalized HPWL (详细布局后)
- `runtime_seconds`: 运行时间（秒）
- `die_size_used`: Die area和Core area
- `timestamp`: 时间戳

**16个设计列表**:
1. mgc_pci_bridge32_a (29,521组件)
2. mgc_pci_bridge32_b (28,920组件)
3. mgc_fft_1 (32,281组件)
4. mgc_fft_2 (32,281组件)
5. mgc_fft_a (30,631组件)
6. mgc_fft_b (30,631组件)
7. mgc_des_perf_1 (112,644组件)
8. mgc_des_perf_a (108,292组件)
9. mgc_des_perf_b (112,644组件)
10. mgc_edit_dist_a (127,419组件)
11. mgc_matrix_mult_1 (155,325组件)
12. mgc_matrix_mult_a (149,655组件)
13. mgc_matrix_mult_b (146,442组件)
14. mgc_superblue16_a (680,538组件)
15. mgc_superblue11_a (925,010组件)
16. mgc_superblue12 (1,285,615组件)

### DreamPlace数据源（12个ISPD 2005设计）

**数据来源**: 初始知识库构建（2025-11-12~13）

| 项目 | 路径 |
|------|------|
| **DreamPlace结果** | `~/dreamplace_experiment/DREAMPlace/install/results/` |
| **原始设计文件** | 各benchmark目录 |

**12个设计列表**:
1. adaptec1
2. adaptec2
3. adaptec3
4. adaptec4
5. bigblue1
6. bigblue2
7. bigblue3
8. bigblue4
9. mgc_matrix_mult_2
10. mgc_superblue14
11. mgc_superblue19
12. superblue16a

**数据特点**:
- 只包含 `hpwl` 字段（DreamPlace HPWL）
- 不包含 `legalized_hpwl`、`global_placement_hpwl`
- 不包含 `openroad_source` 标记
- 这些案例与OpenROAD案例**完全独立**，无重复

---

## 🔗 相关文档

- [ChipMASRAG完整计划](chipmasrag.plan.md)
- [工作总结与计划](../WORK_SUMMARY_AND_PLAN.md)
- [实验记录](../EXPERIMENTS.md)
- [项目README](../README.md) - 知识库管理章节

**实验报告**:
- [EXP-002 Clean Baseline](../results/clean_baseline/summary.json)
- [实验追踪文档](../EXPERIMENTS.md)

**脚本工具**:
- `../scripts/build_kb.py` - 构建知识库
- `../scripts/update_kb_with_clean_baseline.py` - 更新OpenROAD数据
- `../scripts/query_kb.py` - 查询知识库
- `../scripts/collect_clean_baseline.py` - 收集Clean Baseline

---

**最后更新**: 2025-11-15  
**维护者**: ChipMASRAG项目组  
**知识库版本**: 1.0  
**总案例数**: 28 (16 OpenROAD + 12 DreamPlace)

