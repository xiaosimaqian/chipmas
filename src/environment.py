"""
布局环境模块
定义状态、奖励、动作空间
"""

import numpy as np
import torch
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from .utils.openroad_interface import OpenRoadInterface
from .utils.boundary_analyzer import BoundaryAnalyzer


@dataclass
class State:
    """状态表示"""
    local_state: np.ndarray  # 局部状态（分区内模块特征）
    global_state: np.ndarray  # 全局状态（所有分区信息）
    rag_state: np.ndarray  # RAG检索结果状态
    partition_id: int  # 当前分区ID
    
    def to_tensor(self) -> torch.Tensor:
        """转换为PyTorch张量"""
        combined = np.concatenate([self.local_state, self.global_state, self.rag_state])
        return torch.FloatTensor(combined)


class RewardCalculator:
    """奖励计算器"""
    
    def __init__(
        self,
        local_weight: float = 0.3,
        global_weight: float = 0.3,
        boundary_weight: float = 0.3,
        rag_weight: float = 0.1
    ):
        """
        初始化奖励计算器
        
        Args:
            local_weight: 局部奖励权重
            global_weight: 全局奖励权重
            boundary_weight: 边界奖励权重
            rag_weight: RAG奖励权重
        """
        self.local_weight = local_weight
        self.global_weight = global_weight
        self.boundary_weight = boundary_weight
        self.rag_weight = rag_weight
    
    def calculate_local_reward(
        self,
        partition_hpwl: float,
        previous_hpwl: float
    ) -> float:
        """
        计算局部奖励（分区内部HPWL改善）
        
        Args:
            partition_hpwl: 当前分区HPWL
            previous_hpwl: 之前分区HPWL
        
        Returns:
            局部奖励
        """
        if previous_hpwl > 0:
            improvement = (previous_hpwl - partition_hpwl) / previous_hpwl
            return improvement
        return 0.0
    
    def calculate_global_reward(
        self,
        total_hpwl: float,
        previous_total_hpwl: float
    ) -> float:
        """
        计算全局奖励（总HPWL改善）
        
        Args:
            total_hpwl: 当前总HPWL
            previous_total_hpwl: 之前总HPWL
        
        Returns:
            全局奖励
        """
        if previous_total_hpwl > 0:
            improvement = (previous_total_hpwl - total_hpwl) / previous_total_hpwl
            return improvement
        return 0.0
    
    def calculate_boundary_reward(
        self,
        boundary_cost: float,
        previous_boundary_cost: float
    ) -> float:
        """
        计算边界奖励（边界代价降低）
        
        Args:
            boundary_cost: 当前边界代价
            previous_boundary_cost: 之前边界代价
        
        Returns:
            边界奖励
        """
        if previous_boundary_cost > 0:
            improvement = (previous_boundary_cost - boundary_cost) / previous_boundary_cost
            return improvement
        return 0.0
    
    def calculate_rag_reward(
        self,
        rag_similarity: float,
        rag_improvement: float
    ) -> float:
        """
        计算RAG奖励（知识复用效果）
        
        Args:
            rag_similarity: RAG检索相似度
            rag_improvement: 使用RAG后的改善
        
        Returns:
            RAG奖励
        """
        # 结合相似度和改善程度
        reward = rag_similarity * rag_improvement
        return reward
    
    def calculate_total_reward(
        self,
        local_reward: float,
        global_reward: float,
        boundary_reward: float,
        rag_reward: float = 0.0
    ) -> float:
        """
        计算总奖励
        
        Args:
            local_reward: 局部奖励
            global_reward: 全局奖励
            boundary_reward: 边界奖励
            rag_reward: RAG奖励
        
        Returns:
            总奖励
        """
        total = (
            self.local_weight * local_reward +
            self.global_weight * global_reward +
            self.boundary_weight * boundary_reward +
            self.rag_weight * rag_reward
        )
        return total


class PlacementEnv:
    """布局环境"""
    
    def __init__(
        self,
        design_data: Dict[str, Any],
        num_partitions: int = 4,
        balance_epsilon: float = 0.05,
        reward_calculator: Optional[RewardCalculator] = None,
        design_dir: Optional[str] = None,
        openroad_interface: Optional[OpenRoadInterface] = None
    ):
        """
        初始化布局环境
        
        Args:
            design_data: 设计数据（包含网表、模块信息等）
            num_partitions: 分区数量
            balance_epsilon: 平衡约束
            reward_calculator: 奖励计算器
            design_dir: 设计目录路径（用于OpenRoad接口）
            openroad_interface: OpenRoad接口实例
        """
        self.design_data = design_data
        self.num_partitions = num_partitions
        self.balance_epsilon = balance_epsilon
        self.design_dir = design_dir
        
        if reward_calculator is None:
            self.reward_calculator = RewardCalculator()
        else:
            self.reward_calculator = reward_calculator
        
        # OpenRoad接口
        if openroad_interface is None and design_dir:
            self.openroad_interface = OpenRoadInterface()
        else:
            self.openroad_interface = openroad_interface
        
        # 边界分析器
        self.boundary_analyzer = BoundaryAnalyzer()
        
        # 初始化状态
        self.partition_scheme = self._initialize_partition_scheme()
        self.previous_metrics = self._calculate_metrics()
        self.step_count = 0
        self.max_steps = 100  # 最大步数
        self.rag_state = np.zeros(128)  # RAG状态
        self.no_improvement_count = 0  # 无改善计数
        self.step_count = 0
        self.max_steps = 100  # 最大步数
        
    def _initialize_partition_scheme(self) -> Dict[str, List[str]]:
        """
        初始化分区方案（随机或基于启发式）
        
        Returns:
            分区方案 {partition_id: [module_ids]}
        """
        # 获取所有模块
        if 'modules' in self.design_data:
            all_modules = list(self.design_data['modules'].keys())
        else:
            all_modules = []
        
        # 随机分配到各分区（后续可以用启发式方法改进）
        np.random.shuffle(all_modules)
        
        partition_scheme = {}
        modules_per_partition = len(all_modules) // self.num_partitions
        
        for i in range(self.num_partitions):
            start_idx = i * modules_per_partition
            if i == self.num_partitions - 1:
                # 最后一个分区包含剩余所有模块
                partition_scheme[f"partition_{i}"] = all_modules[start_idx:]
            else:
                partition_scheme[f"partition_{i}"] = all_modules[start_idx:start_idx + modules_per_partition]
        
        return partition_scheme
    
    def _calculate_metrics(self) -> Dict[str, float]:
        """
        计算当前指标
        
        Returns:
            指标字典
        """
        metrics = {
            'total_hpwl': 0.0,
            'boundary_cost': 0.0,
            'partition_hpwls': {}
        }
        
        # 如果有OpenRoad接口和设计目录，计算实际指标
        if self.openroad_interface and self.design_dir:
            try:
                # 生成布局（如果还没有）
                layout_def, layout_info = self.openroad_interface.generate_layout_with_partition(
                    self.partition_scheme, self.design_dir
                )
                
                if layout_info.get('status') == 'success' and Path(layout_def).exists():
                    # 计算总HPWL
                    metrics['total_hpwl'] = self.openroad_interface.calculate_hpwl(layout_def)
                    
                    # 计算分区HPWL
                    metrics['partition_hpwls'] = self.openroad_interface.calculate_partition_hpwl(
                        layout_def, self.partition_scheme
                    )
                    
                    # 计算边界代价
                    boundary_cost_info = self.openroad_interface.calculate_boundary_cost(
                        layout_def, self.partition_scheme
                    )
                    metrics['boundary_cost'] = boundary_cost_info['boundary_cost']
            except Exception as e:
                # 如果计算失败，使用网表估算
                metrics = self._estimate_metrics_from_netlist()
        else:
            # 使用网表估算指标
            metrics = self._estimate_metrics_from_netlist()
        
        return metrics
    
    def _estimate_metrics_from_netlist(self) -> Dict[str, float]:
        """
        从网表估算指标（当无法使用OpenRoad时）
        
        Returns:
            估算的指标字典
        """
        metrics = {
            'total_hpwl': 0.0,
            'boundary_cost': 0.0,
            'partition_hpwls': {}
        }
        
        if 'nets' in self.design_data:
            # 估算总HPWL（基于net数量）
            num_nets = len(self.design_data['nets'])
            # 简化估算：每个net的平均HPWL
            metrics['total_hpwl'] = num_nets * 1000.0  # 假设每个net平均1000um
        
        # 估算分区HPWL（按比例分配）
        for partition_id in self.partition_scheme.keys():
            num_modules = len(self.partition_scheme[partition_id])
            total_modules = sum(len(modules) for modules in self.partition_scheme.values())
            if total_modules > 0:
                partition_ratio = num_modules / total_modules
                metrics['partition_hpwls'][partition_id] = metrics['total_hpwl'] * partition_ratio
        
        # 估算边界代价（基于跨分区连接）
        if 'nets' in self.design_data:
            cross_stats = self.boundary_analyzer.count_cross_partition_connections(
                self.partition_scheme, self.design_data
            )
            total_nets = cross_stats.get('total_nets', 1)
            cross_nets = cross_stats.get('cross_partition_nets', 0)
            if total_nets > 0:
                # 边界代价与跨分区net比例相关
                cross_ratio = cross_nets / total_nets
                metrics['boundary_cost'] = cross_ratio * 100.0
        
        return metrics
    
    def get_state(self, partition_id: int) -> State:
        """
        获取指定分区的状态
        
        Args:
            partition_id: 分区ID
        
        Returns:
            状态对象
        """
        # 提取局部状态（当前分区的模块特征）
        partition_key = f"partition_{partition_id}"
        if partition_key not in self.partition_scheme:
            raise ValueError(f"分区 {partition_id} 不存在")
        
        local_modules = self.partition_scheme[partition_key]
        local_state = self._extract_partition_features(local_modules)
        
        # 提取全局状态（所有分区的汇总信息）
        global_state = self._extract_global_features()
        
        # RAG状态（使用实例变量，由coordinator更新）
        rag_state = self.rag_state.copy()
        
        return State(
            local_state=local_state,
            global_state=global_state,
            rag_state=rag_state,
            partition_id=partition_id
        )
    
    def _extract_partition_features(self, module_ids: List[str]) -> np.ndarray:
        """
        提取分区特征
        
        Args:
            module_ids: 模块ID列表
        
        Returns:
            特征向量
        """
        features = []
        
        # 1. 分区规模特征
        num_modules = len(module_ids)
        features.append(num_modules)
        features.append(np.log1p(num_modules))  # 对数尺度
        
        # 2. 模块连接度特征
        if 'nets' in self.design_data:
            module_connections = {module_id: 0 for module_id in module_ids}
            for net_name, net_info in self.design_data['nets'].items():
                if 'connections' in net_info:
                    for conn in net_info['connections']:
                        if 'module' in conn and conn['module'] in module_connections:
                            module_connections[conn['module']] += 1
            
            if module_connections:
                avg_connections = np.mean(list(module_connections.values()))
                max_connections = np.max(list(module_connections.values()))
                min_connections = np.min(list(module_connections.values()))
                features.extend([avg_connections, max_connections, min_connections])
            else:
                features.extend([0.0, 0.0, 0.0])
        else:
            features.extend([0.0, 0.0, 0.0])
        
        # 3. 分区内部连接特征
        if 'nets' in self.design_data:
            internal_nets = 0
            for net_name, net_info in self.design_data['nets'].items():
                if 'connections' in net_info:
                    net_modules = set()
                    for conn in net_info['connections']:
                        if 'module' in conn:
                            net_modules.add(conn['module'])
                    # 检查是否所有模块都在当前分区
                    if net_modules and all(m in module_ids for m in net_modules):
                        internal_nets += 1
            features.append(internal_nets)
        else:
            features.append(0.0)
        
        # 4. 分区边界连接特征
        if 'nets' in self.design_data:
            boundary_nets = 0
            for net_name, net_info in self.design_data['nets'].items():
                if 'connections' in net_info:
                    net_modules = set()
                    for conn in net_info['connections']:
                        if 'module' in conn:
                            net_modules.add(conn['module'])
                    # 检查是否部分模块在当前分区，部分不在
                    partition_modules = [m for m in net_modules if m in module_ids]
                    if partition_modules and len(partition_modules) < len(net_modules):
                        boundary_nets += 1
            features.append(boundary_nets)
        else:
            features.append(0.0)
        
        # 5. 填充到固定维度（64维）
        feature_array = np.array(features, dtype=np.float32)
        if len(feature_array) < 64:
            # 用零填充
            padding = np.zeros(64 - len(feature_array), dtype=np.float32)
            feature_array = np.concatenate([feature_array, padding])
        elif len(feature_array) > 64:
            # 截断
            feature_array = feature_array[:64]
        
        return feature_array
    
    def _extract_global_features(self) -> np.ndarray:
        """
        提取全局特征
        
        Returns:
            全局特征向量
        """
        features = []
        
        # 1. 总模块数
        total_modules = sum(len(modules) for modules in self.partition_scheme.values())
        features.append(total_modules)
        features.append(np.log1p(total_modules))
        
        # 2. 分区数量
        num_partitions = len(self.partition_scheme)
        features.append(num_partitions)
        
        # 3. 分区平衡度（各分区大小的标准差/平均值）
        partition_sizes = [len(modules) for modules in self.partition_scheme.values()]
        if partition_sizes:
            avg_size = np.mean(partition_sizes)
            std_size = np.std(partition_sizes)
            balance = std_size / avg_size if avg_size > 0 else 0.0
            features.append(balance)
        else:
            features.append(0.0)
        
        # 4. 总net数
        if 'nets' in self.design_data:
            total_nets = len(self.design_data['nets'])
            features.append(total_nets)
            features.append(np.log1p(total_nets))
        else:
            features.extend([0.0, 0.0])
        
        # 5. 跨分区连接统计
        if 'nets' in self.design_data:
            cross_stats = self.boundary_analyzer.count_cross_partition_connections(
                self.partition_scheme, self.design_data
            )
            features.append(cross_stats.get('cross_partition_nets', 0))
            features.append(cross_stats.get('cross_partition_pins', 0))
            total_nets = cross_stats.get('total_nets', 1)
            cross_ratio = cross_stats.get('cross_partition_nets', 0) / total_nets if total_nets > 0 else 0.0
            features.append(cross_ratio)
        else:
            features.extend([0.0, 0.0, 0.0])
        
        # 6. 各分区大小
        for partition_id in sorted(self.partition_scheme.keys()):
            size = len(self.partition_scheme[partition_id])
            features.append(size)
            # 限制最多记录8个分区的大小
            if len(features) >= 20:
                break
        
        # 填充到固定维度（32维）
        feature_array = np.array(features, dtype=np.float32)
        if len(feature_array) < 32:
            padding = np.zeros(32 - len(feature_array), dtype=np.float32)
            feature_array = np.concatenate([feature_array, padding])
        elif len(feature_array) > 32:
            feature_array = feature_array[:32]
        
        return feature_array
    
    def step(
        self,
        partition_id: int,
        action: np.ndarray,
        rag_results: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[State, float, bool, Dict[str, Any]]:
        """
        执行一步动作
        
        Args:
            partition_id: 分区ID
            action: 动作向量
            rag_results: RAG检索结果（可选）
        
        Returns:
            (next_state, reward, done, info)
        """
        # 应用动作（更新分区方案）
        self._apply_action(partition_id, action)
        
        # 计算新指标
        current_metrics = self._calculate_metrics()
        
        # 计算奖励
        reward = self._calculate_reward(
            partition_id,
            self.previous_metrics,
            current_metrics,
            rag_results
        )
        
        # 更新previous_metrics
        self.previous_metrics = current_metrics
        
        # 获取新状态
        next_state = self.get_state(partition_id)
        
        # 更新步数
        self.step_count += 1
        
        # 检查是否完成
        # 1. 达到最大步数
        # 2. 边界代价低于阈值
        # 3. 连续多步无改善
        done = False
        if self.step_count >= self.max_steps:
            done = True
        elif current_metrics.get('boundary_cost', float('inf')) < 10.0:  # 边界代价低于10%
            done = True
        else:
            # 检查是否有改善
            prev_boundary = previous_metrics.get('boundary_cost', 0.0)
            curr_boundary = current_metrics.get('boundary_cost', 0.0)
            if curr_boundary >= prev_boundary:
                self.no_improvement_count += 1
                if self.no_improvement_count >= 10:  # 连续10步无改善
                    done = True
            else:
                self.no_improvement_count = 0
        
        info = {
            'metrics': current_metrics,
            'partition_id': partition_id
        }
        
        return next_state, reward, done, info
    
    def _apply_action(self, partition_id: int, action: np.ndarray):
        """
        应用动作（更新分区方案）
        
        Args:
            partition_id: 分区ID
            action: 动作向量（动作空间：选择要迁移的模块和目标分区）
        """
        partition_key = f"partition_{partition_id}"
        if partition_key not in self.partition_scheme:
            return
        
        # 动作解释：
        # action[0]: 要迁移的模块索引（在当前分区中）
        # action[1]: 目标分区ID（归一化到[0, num_partitions-1]）
        
        if len(action) >= 2:
            # 获取当前分区的模块列表
            current_modules = self.partition_scheme[partition_key]
            if len(current_modules) == 0:
                return
            
            # 选择要迁移的模块
            module_idx = int(action[0] * len(current_modules)) % len(current_modules)
            module_to_migrate = current_modules[module_idx]
            
            # 选择目标分区
            target_partition_idx = int(action[1] * self.num_partitions) % self.num_partitions
            target_partition_key = f"partition_{target_partition_idx}"
            
            # 如果目标分区不是当前分区，执行迁移
            if target_partition_key != partition_key and target_partition_key in self.partition_scheme:
                # 检查平衡约束
                source_size = len(self.partition_scheme[partition_key])
                target_size = len(self.partition_scheme[target_partition_key])
                total_modules = sum(len(m) for m in self.partition_scheme.values())
                
                if total_modules > 0:
                    ideal_size = total_modules / self.num_partitions
                    max_size = ideal_size * (1 + self.balance_epsilon)
                    min_size = ideal_size * (1 - self.balance_epsilon)
                    
                    # 检查迁移后是否满足平衡约束
                    if (source_size - 1 >= min_size and 
                        target_size + 1 <= max_size):
                        # 执行迁移
                        self.partition_scheme[partition_key].remove(module_to_migrate)
                        self.partition_scheme[target_partition_key].append(module_to_migrate)
    
    def _calculate_reward(
        self,
        partition_id: int,
        previous_metrics: Dict[str, float],
        current_metrics: Dict[str, float],
        rag_results: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """
        计算奖励
        
        Args:
            partition_id: 分区ID
            previous_metrics: 之前的指标
            current_metrics: 当前指标
            rag_results: RAG检索结果
        
        Returns:
            奖励值
        """
        # 局部奖励
        prev_partition_hpwl = previous_metrics.get('partition_hpwls', {}).get(f"partition_{partition_id}", 0.0)
        curr_partition_hpwl = current_metrics.get('partition_hpwls', {}).get(f"partition_{partition_id}", 0.0)
        local_reward = self.reward_calculator.calculate_local_reward(
            curr_partition_hpwl, prev_partition_hpwl
        )
        
        # 全局奖励
        global_reward = self.reward_calculator.calculate_global_reward(
            current_metrics.get('total_hpwl', 0.0),
            previous_metrics.get('total_hpwl', 0.0)
        )
        
        # 边界奖励
        boundary_reward = self.reward_calculator.calculate_boundary_reward(
            current_metrics.get('boundary_cost', 0.0),
            previous_metrics.get('boundary_cost', 0.0)
        )
        
        # RAG奖励
        rag_reward = 0.0
        if rag_results:
            # 从rag_results中提取相似度（假设RAG结果包含相似度信息）
            # 计算平均相似度
            similarities = []
            for result in rag_results:
                if 'similarity' in result:
                    similarities.append(result['similarity'])
                elif 'embedding' in result and 'query_embedding' in result:
                    # 计算余弦相似度
                    from sklearn.metrics.pairwise import cosine_similarity
                    emb1 = np.array(result['embedding']).reshape(1, -1)
                    emb2 = np.array(result['query_embedding']).reshape(1, -1)
                    if emb1.shape[1] == emb2.shape[1]:
                        sim = cosine_similarity(emb1, emb2)[0][0]
                        similarities.append(sim)
            
            rag_similarity = np.mean(similarities) if similarities else 0.0
            
            # 计算实际改善（当前指标相比之前的改善）
            prev_boundary = previous_metrics.get('boundary_cost', 0.0)
            curr_boundary = current_metrics.get('boundary_cost', 0.0)
            if prev_boundary > 0:
                rag_improvement = (prev_boundary - curr_boundary) / prev_boundary
            else:
                rag_improvement = 0.0
            
            rag_reward = self.reward_calculator.calculate_rag_reward(
                rag_similarity, rag_improvement
            )
        
        # 总奖励
        total_reward = self.reward_calculator.calculate_total_reward(
            local_reward, global_reward, boundary_reward, rag_reward
        )
        
        return total_reward
    
    def reset(self) -> Dict[str, State]:
        """
        重置环境
        
        Returns:
            所有分区的初始状态字典
        """
        self.partition_scheme = self._initialize_partition_scheme()
        self.previous_metrics = self._calculate_metrics()
        self.step_count = 0
        self.rag_state = np.zeros(128)  # 重置RAG状态
        self.no_improvement_count = 0  # 重置无改善计数
        
        states = {}
        for i in range(self.num_partitions):
            states[f"partition_{i}"] = self.get_state(i)
        
        return states
    
    def set_rag_state(self, rag_state: np.ndarray):
        """
        设置RAG状态（由coordinator调用）
        
        Args:
            rag_state: RAG状态向量
        """
        if len(rag_state) == 128:
            self.rag_state = rag_state.copy()
        else:
            # 如果维度不匹配，调整大小
            if len(rag_state) < 128:
                padding = np.zeros(128 - len(rag_state))
                self.rag_state = np.concatenate([rag_state, padding])
            else:
                self.rag_state = rag_state[:128].copy()
    
    def get_partition_scheme(self) -> Dict[str, List[str]]:
        """
        获取当前分区方案
        
        Returns:
            分区方案
        """
        return self.partition_scheme.copy()

