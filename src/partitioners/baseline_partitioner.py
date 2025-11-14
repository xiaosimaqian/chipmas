#!/usr/bin/env python3
"""
基线分区方法实现
参考: K-SpecPart (Bustany et al. ICCAD 2022)

提供多种基线分区策略：
1. hMETIS - 业界标准（推荐）
2. 简化谱聚类 - 考虑全局连接性
3. 连通性感知贪心 - 快速基线
"""

import numpy as np
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh
from collections import defaultdict, deque


class BaselinePartitioner:
    """基线分区器基类"""
    
    def __init__(self, num_partitions: int = 4, balance_constraint: float = 0.05):
        """
        Args:
            num_partitions: 分区数量
            balance_constraint: 平衡约束 (epsilon)
        """
        self.num_partitions = num_partitions
        self.balance_constraint = balance_constraint
    
    def partition(self, hypergraph: Dict, method: str = 'auto') -> Dict[str, List[str]]:
        """
        执行分区
        
        Args:
            hypergraph: 超图表示 {'components': [...], 'nets': [...]}
            method: 分区方法 ['hmetis', 'spectral', 'greedy', 'auto']
        
        Returns:
            分区方案 {partition_id: [component_ids]}
        """
        if method == 'auto':
            # 自动选择：优先 hmetis，失败则用 spectral
            try:
                return self.partition_hmetis(hypergraph)
            except Exception as e:
                print(f"hMETIS不可用({e})，使用谱聚类...")
                return self.partition_spectral(hypergraph)
        elif method == 'hmetis':
            return self.partition_hmetis(hypergraph)
        elif method == 'spectral':
            return self.partition_spectral(hypergraph)
        elif method == 'greedy':
            return self.partition_greedy(hypergraph)
        else:
            raise ValueError(f"未知的分区方法: {method}")
    
    def partition_hmetis(self, hypergraph: Dict) -> Dict[str, List[str]]:
        """
        使用 hMETIS 进行分区
        
        hMETIS 是多级超图分区器，使用：
        - 粗化(Coarsening)：逐级合并顶点
        - 初始分区：在最粗级别分区
        - 细化(Refinement)：使用 FM 算法优化
        """
        components = hypergraph['components']
        nets = hypergraph['nets']
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.hgr', delete=False) as f:
            hgr_file = f.name
            
            # 写入 hMETIS 格式
            # 格式: <num_hyperedges> <num_vertices> [fmt]
            f.write(f"{len(nets)} {len(components)}\n")
            
            # 每行一个超边，包含其连接的顶点
            comp_to_idx = {comp: i+1 for i, comp in enumerate(components)}
            for net in nets:
                vertices = [str(comp_to_idx[comp]) for comp in net if comp in comp_to_idx]
                if vertices:
                    f.write(" ".join(vertices) + "\n")
        
        try:
            # 调用 hMETIS
            # 参数: <GraphFile> <Nparts> <UBfactor> <Nruns> <CType> <RType> <Vcycle> <Reconst> <seed>
            ubfactor = int((1 + self.balance_constraint) * 100)
            
            cmd = [
                'hmetis',
                hgr_file,
                str(self.num_partitions),
                str(ubfactor)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"hMETIS 执行失败: {result.stderr}")
            
            # 读取分区结果
            part_file = hgr_file + f".part.{self.num_partitions}"
            partition_scheme = defaultdict(list)
            
            with open(part_file, 'r') as f:
                for comp_idx, line in enumerate(f):
                    part_id = int(line.strip())
                    comp = components[comp_idx]
                    partition_scheme[f"partition_{part_id}"].append(comp)
            
            # 清理临时文件
            Path(hgr_file).unlink(missing_ok=True)
            Path(part_file).unlink(missing_ok=True)
            
            return dict(partition_scheme)
            
        except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) as e:
            # 清理临时文件
            Path(hgr_file).unlink(missing_ok=True)
            raise e
    
    def partition_spectral(self, hypergraph: Dict) -> Dict[str, List[str]]:
        """
        简化的谱聚类分区
        
        基于 K-SpecPart 论文的思想，但简化实现：
        1. 构建clique expansion图
        2. 计算Laplacian矩阵
        3. 求解特征向量
        4. K-means聚类
        """
        components = hypergraph['components']
        nets = hypergraph['nets']
        
        print(f"  - 谱聚类: {len(components)} 个组件, {len(nets)} 个网线")
        sys.stdout.flush()
        
        # 1. 构建图的邻接矩阵（clique expansion）
        print(f"  - 构建图的邻接矩阵...")
        sys.stdout.flush()
        
        comp_to_idx = {comp: i for i, comp in enumerate(components)}
        n = len(components)
        
        # 使用稀疏矩阵表示
        row_indices = []
        col_indices = []
        data = []
        
        for net in nets:
            # 将每个超边展开为团（clique）
            vertices = [comp_to_idx[comp] for comp in net if comp in comp_to_idx]
            net_size = len(vertices)
            
            if net_size < 2:
                continue
            
            # 团中每对顶点之间的边权重为 1/(|net|-1)
            weight = 1.0 / (net_size - 1)
            
            for i in range(len(vertices)):
                for j in range(i+1, len(vertices)):
                    v1, v2 = vertices[i], vertices[j]
                    row_indices.extend([v1, v2])
                    col_indices.extend([v2, v1])
                    data.extend([weight, weight])
        
        # 构建邻接矩阵
        A = sp.csr_matrix((data, (row_indices, col_indices)), shape=(n, n))
        
        # 2. 计算Laplacian矩阵
        print(f"  - 计算Laplacian矩阵...")
        sys.stdout.flush()
        
        # L = D - A，其中D是度矩阵
        degrees = np.array(A.sum(axis=1)).flatten()
        D = sp.diags(degrees)
        L = D - A
        
        # 3. 求解广义特征值问题
        print(f"  - 求解特征向量（这可能需要一些时间）...")
        sys.stdout.flush()
        
        # 求解最小的 k 个非平凡特征向量
        # 使用 D 作为归一化矩阵（normalized Laplacian）
        k = min(self.num_partitions + 1, n - 1)
        
        try:
            # 求解 L @ x = lambda * D @ x
            # 等价于 D^{-1/2} @ L @ D^{-1/2} 的特征向量
            D_inv_sqrt = sp.diags(1.0 / np.sqrt(degrees + 1e-10))
            L_norm = D_inv_sqrt @ L @ D_inv_sqrt
            
            # 求最小的k个特征值和特征向量
            eigenvalues, eigenvectors = eigsh(L_norm, k=k, which='SM')
            
            # 跳过第一个特征向量（对应于零特征值）
            embedding = eigenvectors[:, 1:self.num_partitions]
            
        except Exception as e:
            print(f"  警告: 特征值求解失败({e})，使用贪心方法...")
            return self.partition_greedy(hypergraph)
        
        # 4. K-means聚类
        print(f"  - K-means聚类...")
        sys.stdout.flush()
        
        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=self.num_partitions, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embedding)
        except ImportError:
            # 如果没有sklearn，使用简单的聚类
            print(f"  警告: sklearn不可用，使用简单聚类...")
            labels = self._simple_kmeans(embedding, self.num_partitions)
        
        # 5. 构建分区方案
        partition_scheme = defaultdict(list)
        for comp_idx, label in enumerate(labels):
            comp = components[comp_idx]
            partition_scheme[f"partition_{label}"].append(comp)
        
        # 6. 平衡调整（简单的贪心平衡）
        partition_scheme = self._balance_partitions(
            dict(partition_scheme), 
            components
        )
        
        print(f"  - 谱聚类完成")
        sys.stdout.flush()
        
        return partition_scheme
    
    def partition_greedy(self, hypergraph: Dict) -> Dict[str, List[str]]:
        """
        连通性感知的贪心分区
        
        算法：
        1. 随机选择 K 个种子组件
        2. BFS 扩展，优先添加连接数多的组件
        3. 维持平衡约束
        """
        components = hypergraph['components']
        nets = hypergraph['nets']
        
        print(f"  - 贪心分区: {len(components)} 个组件")
        sys.stdout.flush()
        
        # 1. 构建组件邻接关系
        print(f"  - 构建邻接关系...")
        sys.stdout.flush()
        
        comp_neighbors = defaultdict(set)
        for net in nets:
            for comp1 in net:
                if comp1 in components:
                    for comp2 in net:
                        if comp2 != comp1 and comp2 in components:
                            comp_neighbors[comp1].add(comp2)
        
        # 2. 随机选择种子
        import random
        random.seed(42)
        seeds = random.sample(components, min(self.num_partitions, len(components)))
        
        # 3. BFS 扩展
        print(f"  - BFS 扩展分区...")
        sys.stdout.flush()
        
        partition_scheme = {f"partition_{i}": [seed] for i, seed in enumerate(seeds)}
        assigned = set(seeds)
        
        # 目标大小（平衡约束）
        target_size = len(components) / self.num_partitions
        max_size = int(target_size * (1 + self.balance_constraint))
        
        # 优先队列：(负的连接数, 组件, 分区ID)
        from heapq import heappush, heappop
        pq = []
        
        # 初始化队列
        for part_id, seed in enumerate(seeds):
            for neighbor in comp_neighbors[seed]:
                if neighbor not in assigned:
                    heappush(pq, (-1, neighbor, part_id))
        
        # 扩展
        while pq and len(assigned) < len(components):
            _, comp, part_id = heappop(pq)
            
            if comp in assigned:
                continue
            
            part_key = f"partition_{part_id}"
            
            # 检查平衡约束
            if len(partition_scheme[part_key]) >= max_size:
                continue
            
            # 添加到分区
            partition_scheme[part_key].append(comp)
            assigned.add(comp)
            
            # 添加邻居到队列
            for neighbor in comp_neighbors[comp]:
                if neighbor not in assigned:
                    # 计算连接数（启发式：与当前分区的连接数）
                    conn_count = sum(
                        1 for c in partition_scheme[part_key]
                        if c in comp_neighbors[neighbor]
                    )
                    heappush(pq, (-conn_count, neighbor, part_id))
        
        # 4. 处理剩余未分配的组件
        unassigned = set(components) - assigned
        if unassigned:
            print(f"  - 分配剩余 {len(unassigned)} 个组件...")
            # 轮流分配到最小的分区
            for comp in unassigned:
                min_part = min(partition_scheme.keys(), 
                             key=lambda k: len(partition_scheme[k]))
                partition_scheme[min_part].append(comp)
        
        print(f"  - 贪心分区完成")
        sys.stdout.flush()
        
        return partition_scheme
    
    def _simple_kmeans(self, X: np.ndarray, k: int, max_iters: int = 100) -> np.ndarray:
        """简单的K-means实现"""
        n = X.shape[0]
        
        # 随机初始化中心
        np.random.seed(42)
        centers_idx = np.random.choice(n, k, replace=False)
        centers = X[centers_idx]
        
        labels = np.zeros(n, dtype=int)
        
        for _ in range(max_iters):
            # 分配到最近的中心
            distances = np.sum((X[:, np.newaxis] - centers) ** 2, axis=2)
            new_labels = np.argmin(distances, axis=1)
            
            if np.all(labels == new_labels):
                break
            
            labels = new_labels
            
            # 更新中心
            for i in range(k):
                mask = labels == i
                if np.any(mask):
                    centers[i] = X[mask].mean(axis=0)
        
        return labels
    
    def _balance_partitions(self, partition_scheme: Dict[str, List[str]], 
                          all_components: List[str]) -> Dict[str, List[str]]:
        """简单的平衡调整"""
        target_size = len(all_components) / self.num_partitions
        max_size = int(target_size * (1 + self.balance_constraint))
        min_size = int(target_size * (1 - self.balance_constraint))
        
        # 找出过大和过小的分区
        while True:
            over_parts = [k for k, v in partition_scheme.items() if len(v) > max_size]
            under_parts = [k for k, v in partition_scheme.items() if len(v) < min_size]
            
            if not over_parts or not under_parts:
                break
            
            # 从最大的分区移动组件到最小的分区
            over_part = max(over_parts, key=lambda k: len(partition_scheme[k]))
            under_part = min(under_parts, key=lambda k: len(partition_scheme[k]))
            
            # 移动一个组件
            if partition_scheme[over_part]:
                comp = partition_scheme[over_part].pop()
                partition_scheme[under_part].append(comp)
        
        return partition_scheme


# 为了兼容性，添加到模块级别
import sys

if __name__ == '__main__':
    # 测试代码
    partitioner = BaselinePartitioner(num_partitions=4, balance_constraint=0.05)
    
    # 示例超图
    hypergraph = {
        'components': [f'c{i}' for i in range(100)],
        'nets': [[f'c{i}', f'c{i+1}', f'c{i+2}'] for i in range(0, 98, 2)]
    }
    
    # 测试谱聚类
    result = partitioner.partition(hypergraph, method='spectral')
    print(f"谱聚类结果:")
    for part_id, comps in result.items():
        print(f"  {part_id}: {len(comps)} 个组件")


