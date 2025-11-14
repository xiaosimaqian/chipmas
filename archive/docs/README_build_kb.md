# 知识库构建脚本使用说明

## 概述

`build_kb.py` 脚本用于构建和扩展 ChipMASRAG 知识库。它可以从以下来源提取分区经验并构建知识库：

1. **从实验结果构建**：从 ChipMASRAG 运行结果中提取完整案例（包括分区策略、协商模式、质量指标）
2. **从设计文件构建**：从设计文件（Verilog、DEF）中提取基本特征（用于初始构建）

## 功能特性

### 1. 设计特征提取
- 从 DEF 文件提取：组件数、网络数、芯片面积
- 从 Verilog 文件提取：模块数、模块层次
- 计算连接图特征：平均度、最大度、连接密度

### 2. 分区策略提取
- 从分区方案 JSON 文件中提取：
  - 分区分配（模块到分区的映射）
  - 分区数量
  - 边界模块列表
  - 分区平衡度

### 3. 协商模式提取
- 从运行日志中提取：
  - 协商历史记录
  - 协商成功率
  - 成功/失败的模块迁移

### 4. 质量指标提取
- HPWL（半周线长）
- 边界代价
- 运行时间
- 其他质量指标

### 5. 语义嵌入生成
- 使用 sentence-transformers 生成语义嵌入向量
- 支持语义检索

### 6. 质量验证
- 检查案例完整性
- 验证特征有效性
- 确保检索质量

## 使用方法

### 基本用法

#### 1. 从设计文件构建初始知识库

```bash
# 从指定设计目录构建基本案例（没有分区方案和布局结果）
python3 scripts/build_kb.py \
    --design-dirs data/ispd2015/mgc_pci_bridge32_a \
                   data/ispd2015/mgc_fft_1 \
    --config configs/default.yaml
```

#### 2. 从实验结果更新知识库

```bash
# 从指定实验结果目录构建知识库
python3 scripts/build_kb.py \
    --results-dir data/results/20240101_120000 \
    --config configs/default.yaml
```

#### 3. 自动搜索本地实验结果并更新

```bash
# 自动搜索本地所有实验结果目录并更新知识库
python3 scripts/build_kb.py --auto-local --config configs/default.yaml
```

#### 4. 自动搜索远程服务器实验结果并更新

```bash
# 自动搜索远程服务器实验结果目录并更新知识库
python3 scripts/build_kb.py \
    --auto-remote \
    --remote-server 172.30.31.98 \
    --remote-user keqin \
    --sync-remote \
    --config configs/default.yaml
```

#### 5. 一键执行所有操作（推荐）

```bash
# 构建初始知识库 + 更新本地结果 + 更新远程结果
python3 scripts/build_kb.py \
    --all \
    --remote-server 172.30.31.98 \
    --remote-user keqin \
    --sync-remote \
    --config configs/default.yaml
```

#### 6. 显示知识库统计信息

```bash
python3 scripts/build_kb.py --stats --config configs/default.yaml
```

### 高级用法

#### 指定知识库文件路径

```bash
python scripts/build_kb.py \
    --kb-file data/knowledge_base/my_kb.json \
    --results-dir data/results/20240101_120000
```

#### 禁用验证（快速构建）

```bash
python scripts/build_kb.py \
    --results-dir data/results/20240101_120000 \
    --no-validate
```

## 输入文件格式

### 分区方案文件格式

分区方案文件应为 JSON 格式，包含以下字段：

```json
{
  "partitions": {
    "partition_0": ["module_1", "module_2", ...],
    "partition_1": ["module_3", "module_4", ...],
    ...
  },
  "boundary_modules": ["module_5", "module_6", ...],
  "negotiation_history": [
    {
      "source_agent": 0,
      "target_agent": 1,
      "module_id": "module_5",
      "result": "success",
      "timestamp": "2024-01-01T12:00:00"
    },
    ...
  ]
}
```

### 日志文件格式

日志文件应包含协商记录，格式如下：

```
NEGOTIATION: agent_0 -> agent_1, module: module_5, result: success
NEGOTIATION: agent_1 -> agent_2, module: module_6, result: fail
...
```

## 输出格式

知识库文件为 JSON 格式，包含以下结构：

```json
{
  "version": "1.0",
  "num_cases": 10,
  "cases": [
    {
      "design_id": "mgc_pci_bridge32_a",
      "features": [1.2, 3.4, 5.6, ...],
      "partition_strategy": {
        "partitions": {...},
        "num_partitions": 4,
        "boundary_modules": [...],
        "balance_ratio": 0.15
      },
      "negotiation_patterns": {
        "negotiation_history": [...],
        "num_negotiations": 5,
        "successful_migrations": 4,
        "failed_migrations": 1,
        "success_rate": 0.8
      },
      "quality_metrics": {
        "hpwl": 12345.67,
        "boundary_cost": 25.5,
        "runtime_seconds": 120.5,
        "num_modules": 100,
        "num_nets": 200
      },
      "embedding": [0.1, 0.2, 0.3, ...],
      "timestamp": "2024-01-01T12:00:00"
    },
    ...
  ]
}
```

## 工作流程

### 自举构建流程

1. **初始构建**（从设计文件）：
   ```bash
   # 从 ISPD 2015 设计构建基本案例
   python scripts/build_kb.py \
       --design-dirs data/ispd2015/mgc_pci_bridge32_a \
                     data/ispd2015/mgc_fft_1 \
                     ...
   ```

2. **运行 ChipMASRAG**：
   - 使用初始知识库运行 ChipMASRAG
   - 生成分区方案和布局结果

3. **扩展知识库**（从运行结果）：
   ```bash
   # 从运行结果提取完整案例
   python scripts/build_kb.py \
       --results-dir data/results/20240101_120000
   ```

4. **迭代优化**：
   - 重复步骤 2-3，逐步扩展知识库
   - 知识库质量随案例积累而提升

## 注意事项

1. **特征向量维度**：确保所有案例的特征向量维度一致（默认 10 维）

2. **嵌入向量维度**：确保嵌入向量维度与配置一致（all-MiniLM-L6-v2 为 384 维）

3. **文件路径**：确保所有输入文件路径正确，脚本会自动查找常见文件名

4. **验证**：建议启用验证（默认启用），确保案例质量

5. **知识库大小**：默认最大案例数为 1000，可在配置文件中调整

## 故障排查

### 问题1：嵌入模型加载失败

**解决方案**：
- 检查是否安装了 sentence-transformers：`pip install sentence-transformers`
- 检查网络连接（首次使用需要下载模型）

### 问题2：特征向量维度不匹配

**解决方案**：
- 确保所有案例使用相同的特征提取方法
- 检查特征向量生成逻辑

### 问题3：分区策略提取失败

**解决方案**：
- 检查分区方案 JSON 文件格式是否正确
- 确保文件路径正确

### 问题4：协商模式提取失败

**解决方案**：
- 检查日志文件格式是否符合要求
- 确保日志文件包含协商记录

## 示例

### 示例1：构建初始知识库

```bash
# 从 ISPD 2015 的 5 个设计构建初始知识库
python scripts/build_kb.py \
    --design-dirs \
        data/ispd2015/mgc_pci_bridge32_a \
        data/ispd2015/mgc_fft_1 \
        data/ispd2015/mgc_fft_2 \
        data/ispd2015/mgc_des_perf_1 \
        data/ispd2015/mgc_matrix_mult_1 \
    --config configs/default.yaml
```

### 示例2：从实验结果扩展知识库

```bash
# 从实验结果目录扩展知识库
python scripts/build_kb.py \
    --results-dir data/results/20240101_120000 \
    --config configs/default.yaml
```

### 示例3：查看知识库统计信息

```bash
python scripts/build_kb.py --stats --config configs/default.yaml
```

输出示例：
```json
{
  "num_cases": 10,
  "kb_file": "data/knowledge_base/kb_cases.json",
  "embedding_dim": 384,
  "scale_stats": {
    "min": 100,
    "max": 1000,
    "mean": 500.0,
    "median": 450.0
  }
}
```

## 相关文件

- `src/knowledge_base.py`：知识库管理模块
- `src/rag_retriever.py`：RAG 检索模块
- `configs/default.yaml`：默认配置文件

