"""
边界协商模块
实现知识驱动的边界协商协议
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from .rag_retriever import RAGRetriever
from .utils.boundary_analyzer import BoundaryAnalyzer


class NegotiationProtocol:
    """边界协商协议"""
    
    def __init__(
        self,
        rag_retriever: Optional[RAGRetriever] = None,
        boundary_analyzer: Optional[BoundaryAnalyzer] = None
    ):
        """
        初始化协商协议
        
        Args:
            rag_retriever: RAG检索器（用于查找相似协商案例）
            boundary_analyzer: 边界分析器（用于识别边界模块）
        """
        self.rag_retriever = rag_retriever
        self.boundary_analyzer = boundary_analyzer or BoundaryAnalyzer()
        self.negotiation_history: List[Dict[str, Any]] = []
    
    def identify_boundary_modules(
        self,
        partition_scheme: Dict[str, List[str]],
        netlist: Dict[str, Any],
        threshold: float = 0.5
    ) -> Dict[str, List[str]]:
        """
        识别高代价边界模块
        
        Args:
            partition_scheme: 分区方案
            netlist: 网表信息
            threshold: 阈值（跨分区连接比例）
        
        Returns:
            各分区的边界模块列表 {partition_id: [boundary_module_ids]}
        """
        return self.boundary_analyzer.identify_boundary_modules(
            partition_scheme, netlist, threshold
        )
    
    def find_similar_negotiation(
        self,
        boundary_modules: Dict[str, List[str]],
        partition_scheme: Dict[str, List[str]],
        design_features: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        在RAG结果中查找相似协商案例
        
        Args:
            boundary_modules: 边界模块列表
            partition_scheme: 分区方案
            design_features: 设计特征向量
        
        Returns:
            相似协商案例列表
        """
        if self.rag_retriever is None:
            return []
        
        # 使用RAG检索相似案例
        rag_results = self.rag_retriever.retrieve(
            query_features=design_features,
            query_text=self._generate_negotiation_query(boundary_modules, partition_scheme)
        )
        
        # 提取协商模式
        negotiation_cases = []
        for case in rag_results:
            if 'negotiation_patterns' in case:
                negotiation_cases.append(case['negotiation_patterns'])
        
        return negotiation_cases
    
    def _generate_negotiation_query(
        self,
        boundary_modules: Dict[str, List[str]],
        partition_scheme: Dict[str, List[str]]
    ) -> str:
        """
        生成协商查询文本（用于语义检索）
        
        Args:
            boundary_modules: 边界模块列表
            partition_scheme: 分区方案
        
        Returns:
            查询文本
        """
        parts = []
        parts.append(f"Partitions: {len(partition_scheme)}")
        
        total_boundary = sum(len(modules) for modules in boundary_modules.values())
        parts.append(f"Boundary modules: {total_boundary}")
        
        return " ".join(parts)
    
    def negotiate(
        self,
        source_partition: str,
        target_partition: str,
        module_id: str,
        partition_scheme: Dict[str, List[str]],
        similar_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        执行协商请求
        
        Args:
            source_partition: 源分区ID
            target_partition: 目标分区ID
            module_id: 要迁移的模块ID
            partition_scheme: 当前分区方案
            similar_cases: 相似协商案例（可选）
        
        Returns:
            (是否接受, 协商结果信息)
        """
        # 检查迁移是否合法（平衡约束等）
        if not self._check_migration_validity(
            source_partition, target_partition, module_id, partition_scheme
        ):
            return False, {'reason': 'invalid_migration'}
        
        # 如果有相似案例，参考案例进行决策
        if similar_cases:
            decision = self._make_decision_from_cases(
                source_partition, target_partition, module_id, similar_cases
            )
        else:
            # 使用默认策略（贪心）
            decision = self._make_greedy_decision(
                source_partition, target_partition, module_id, partition_scheme
            )
        
        # 记录协商历史
        negotiation_record = {
            'source_partition': source_partition,
            'target_partition': target_partition,
            'module_id': module_id,
            'decision': decision,
            'similar_cases_used': len(similar_cases) if similar_cases else 0
        }
        self.negotiation_history.append(negotiation_record)
        
        return decision, negotiation_record
    
    def _check_migration_validity(
        self,
        source_partition: str,
        target_partition: str,
        module_id: str,
        partition_scheme: Dict[str, List[str]]
    ) -> bool:
        """
        检查迁移是否合法（满足平衡约束等）
        
        Args:
            source_partition: 源分区ID
            target_partition: 目标分区ID
            module_id: 模块ID
            partition_scheme: 分区方案
        
        Returns:
            是否合法
        """
        # 检查模块是否在源分区中
        if source_partition not in partition_scheme:
            return False
        
        if module_id not in partition_scheme[source_partition]:
            return False
        
        # 检查目标分区是否存在
        if target_partition not in partition_scheme:
            return False
        
        # 检查平衡约束（分区大小不能超过限制）
        source_modules = partition_scheme.get(source_partition, [])
        target_modules = partition_scheme.get(target_partition, [])
        
        # 计算总模块数
        total_modules = sum(len(modules) for modules in partition_scheme.values())
        if total_modules == 0:
            return False
        
        # 计算理想分区大小和允许范围
        num_partitions = len(partition_scheme)
        ideal_size = total_modules / num_partitions
        
        # 检查迁移后是否满足平衡约束（假设epsilon=0.05）
        epsilon = 0.05
        max_size = ideal_size * (1 + epsilon)
        min_size = ideal_size * (1 - epsilon)
        
        source_size_after = len(source_modules) - 1
        target_size_after = len(target_modules) + 1
        
        # 迁移后两个分区都应在允许范围内
        if source_size_after < min_size or target_size_after > max_size:
            return False
        
        return True
    
    def _make_decision_from_cases(
        self,
        source_partition: str,
        target_partition: str,
        module_id: str,
        similar_cases: List[Dict[str, Any]]
    ) -> bool:
        """
        基于相似案例做出决策
        
        Args:
            source_partition: 源分区ID
            target_partition: 目标分区ID
            module_id: 模块ID
            similar_cases: 相似协商案例
        
        Returns:
            是否接受迁移
        """
        # 统计相似案例中的成功迁移比例
        success_count = 0
        total_count = 0
        
        for case in similar_cases:
            if 'migrations' in case:
                for migration in case['migrations']:
                    if (migration.get('source') == source_partition and
                        migration.get('target') == target_partition):
                        total_count += 1
                        if migration.get('success', False):
                            success_count += 1
        
        # 如果成功比例超过阈值，接受迁移
        if total_count > 0:
            success_rate = success_count / total_count
            return success_rate > 0.6  # 阈值：60%
        
        # 如果没有相似案例，使用默认策略
        return True
    
    def _make_greedy_decision(
        self,
        source_partition: str,
        target_partition: str,
        module_id: str,
        partition_scheme: Dict[str, List[str]]
    ) -> bool:
        """
        使用贪心策略做出决策
        
        Args:
            source_partition: 源分区ID
            target_partition: 目标分区ID
            module_id: 模块ID
            partition_scheme: 分区方案
        
        Returns:
            是否接受迁移
        """
        # 基于边界代价降低等指标做出决策
        # 这里使用启发式：如果目标分区比源分区小，更可能接受（平衡分区）
        source_size = len(partition_scheme.get(source_partition, []))
        target_size = len(partition_scheme.get(target_partition, []))
        
        # 如果目标分区更小，接受迁移（有助于平衡）
        if target_size < source_size:
            return True
        
        # 否则，基于随机概率（可以后续改进为基于边界代价）
        import random
        return random.random() > 0.5
    
    def execute_migration(
        self,
        source_partition: str,
        target_partition: str,
        module_id: str,
        partition_scheme: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        执行模块迁移
        
        Args:
            source_partition: 源分区ID
            target_partition: 目标分区ID
            module_id: 模块ID
            partition_scheme: 当前分区方案
        
        Returns:
            更新后的分区方案
        """
        # 创建副本
        new_scheme = {k: v.copy() for k, v in partition_scheme.items()}
        
        # 从源分区移除模块
        if source_partition in new_scheme and module_id in new_scheme[source_partition]:
            new_scheme[source_partition].remove(module_id)
        
        # 添加到目标分区
        if target_partition in new_scheme:
            new_scheme[target_partition].append(module_id)
        
        return new_scheme
    
    def get_negotiation_history(self) -> List[Dict[str, Any]]:
        """
        获取协商历史
        
        Returns:
            协商历史列表
        """
        return self.negotiation_history.copy()
    
    def reset_history(self):
        """重置协商历史"""
        self.negotiation_history = []

