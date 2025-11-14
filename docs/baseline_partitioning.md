# 基线分区方法说明

## 背景

之前使用简单的 `random.shuffle()` 对所有组件进行随机分区是不合理的，因为：
1. 完全忽略了网表的连接性（connectivity）
2. 对于百万级组件，效率极低
3. 不符合超图分区的基本原则

## 参考文献

**K-SpecPart: Supervised embedding algorithms and cut overlay for improved hypergraph partitioning**  
Ismail Bustany, Andrew B. Kahng, Ioannis Koutis, Bodhisatta Pramanik, Zhiang Wang  
ICCAD 2022

## 实现的基线方法

### 1. hMETIS（推荐 - 业界标准）

**原理**：多级（multilevel）超图分区
- **粗化（Coarsening）**：逐级合并顶点，构建层次结构
- **初始分区**：在最粗级别进行分区
- **细化（Refinement）**：使用 FM 算法逐级优化

**优点**：
- 业界认可的 state-of-the-art 工具
- 质量高，速度快
- K-SpecPart 论文的基线方法

**使用条件**：
- 需要安装 hMETIS
- 支持超图输入

**性能**：
- ISPD98 benchmarks: ~1000-5000 cutsize
- Titan23 benchmarks: ~500-5000 cutsize

### 2. 谱聚类（Spectral Clustering）

**原理**：基于图 Laplacian 矩阵的特征向量
1. **构建图**：Clique expansion（每个超边展开为团）
2. **Laplacian 矩阵**：L = D - A
3. **特征分解**：求解 L @ x = λ * D @ x
4. **聚类**：对特征向量进行 K-means 聚类

**优点**：
- 考虑全局结构
- 理论基础扎实（K-SpecPart 的核心）
- 不依赖外部工具

**缺点**：
- 对大规模设计计算量大
- 需要 scipy、sklearn

**适用场景**：
- 中小规模设计（< 100K 组件）
- 无法使用 hMETIS 时

### 3. 连通性感知贪心（Greedy - 当前使用）

**原理**：BFS 扩展 + 连接性启发式
1. 随机选择 K 个种子组件
2. 优先添加与当前分区连接数多的组件
3. 维持平衡约束

**优点**：
- 实现简单
- 速度快（线性时间）
- 考虑连接性

**缺点**：
- 质量不如 hMETIS 和谱聚类
- 局部贪心可能陷入次优解

**适用场景**：
- 快速基线测试
- 大规模设计（> 100K 组件）

### 4. 纯随机（仅用于对比）

**原理**：`random.shuffle()` + 均匀分配

**使用场景**：仅作为对比基线，不推荐实际使用

## 方法选择建议

| 设计规模 | 推荐方法 | 备选方法 | 预期cutsize提升 |
|---------|---------|---------|----------------|
| < 10K 组件 | hMETIS | 谱聚类 | 最佳 |
| 10K-100K 组件 | hMETIS | 贪心 | 很好 |
| 100K-1M 组件 | 贪心 | hMETIS | 较好 |
| > 1M 组件 | 贪心 | 不推荐其他 | 基础 |

## 实现细节

### 超图表示

```python
hypergraph = {
    'components': ['c1', 'c2', ...],  # 组件列表
    'nets': [                          # 网线列表
        ['c1', 'c2', 'c3'],           # 网线1连接的组件
        ['c2', 'c4'],                  # 网线2连接的组件
        ...
    ]
}
```

### 分区结果

```python
partition_scheme = {
    'partition_0': ['c1', 'c5', ...],
    'partition_1': ['c2', 'c6', ...],
    'partition_2': ['c3', 'c7', ...],
    'partition_3': ['c4', 'c8', ...],
}
```

## 性能对比（预期）

基于 K-SpecPart 论文的结果：

| 方法 | Cutsize（相对） | 运行时间 | 可扩展性 |
|-----|----------------|---------|---------|
| Random | 1.0（最差） | 最快 | 极好 |
| Greedy | 0.7-0.8 | 快 | 很好 |
| Spectral | 0.5-0.6 | 中等 | 中等 |
| hMETIS | 0.4-0.5（最佳） | 快 | 好 |
| K-SpecPart | 0.3-0.4（理论最佳） | 较慢 | 一般 |

注：K-SpecPart 使用 hMETIS 作为 hint，并通过监督学习进一步优化

## 当前配置

```python
# chipmas/scripts/run_baseline_experiments.py

partition_method = 'greedy'  # 当前使用贪心方法
partition_scheme = create_baseline_partition(
    components, nets, 
    num_partitions=4, 
    method=partition_method
)
```

**可选方法**：
- `'auto'`: 自动选择（优先hMETIS，失败则用谱聚类）
- `'hmetis'`: 使用hMETIS
- `'spectral'`: 使用谱聚类
- `'greedy'`: 使用贪心方法（当前）
- `'random'`: 纯随机（仅用于对比）

## 未来改进方向

1. **安装 hMETIS**：获得最佳分区质量
2. **实现 K-SpecPart**：进一步提升质量（需要大量工作）
3. **并行化**：谱聚类的特征值求解可以并行化
4. **自适应选择**：根据设计规模自动选择方法
5. **参数调优**：平衡约束、分区数量等

## 参考资源

- hMETIS: http://glaros.dtc.umn.edu/gkhome/metis/hmetis/
- K-SpecPart论文: https://arxiv.org/abs/2305.06167
- KaHyPar: https://github.com/kahypar/kahypar
- TritonPart: https://github.com/ABKGroup/TritonPart


