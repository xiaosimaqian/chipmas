"""
知识库管理模块
管理历史案例，支持案例存储、检索、更新
"""

import json
import os
import numpy as np
from typing import Dict, List, Optional, Any
from pathlib import Path


class KnowledgeBase:
    """知识库管理类"""
    
    def __init__(self, case_file: str, max_cases: int = 1000):
        """
        初始化知识库
        
        Args:
            case_file: 知识库文件路径
            max_cases: 最大案例数量
        """
        self.case_file = Path(case_file)
        self.max_cases = max_cases
        self.cases: List[Dict[str, Any]] = []
        self._case_index: Dict[str, int] = {}  # design_id -> index
        
    def load(self) -> bool:
        """
        加载知识库
        
        Returns:
            是否成功加载
        """
        if not self.case_file.exists():
            # 如果文件不存在，创建空知识库
            self.cases = []
            return True
            
        try:
            with open(self.case_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.cases = data.get('cases', [])
                
            # 构建索引
            self._case_index = {
                case['design_id']: i 
                for i, case in enumerate(self.cases)
            }
            
            return True
        except Exception as e:
            print(f"加载知识库失败: {e}")
            self.cases = []
            return False
    
    def save(self) -> bool:
        """
        保存知识库到文件
        
        Returns:
            是否成功保存
        """
        try:
            # 确保目录存在
            self.case_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '1.0',
                'num_cases': len(self.cases),
                'cases': self.cases
            }
            
            with open(self.case_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"保存知识库失败: {e}")
            return False
    
    def add_case(self, case: Dict[str, Any]) -> bool:
        """
        添加新案例
        
        Args:
            case: 案例字典，包含以下字段：
                - design_id: 设计ID
                - features: 设计特征向量（numpy array）
                - partition_strategy: 分区策略
                - negotiation_patterns: 协商模式
                - quality_metrics: 质量指标
                - embedding: 语义嵌入向量（numpy array）
        
        Returns:
            是否成功添加
        """
        if 'design_id' not in case:
            print("案例缺少design_id字段")
            return False
        
        design_id = case['design_id']
        
        # 检查是否已存在
        if design_id in self._case_index:
            # 更新现有案例
            idx = self._case_index[design_id]
            self.cases[idx] = case
        else:
            # 添加新案例
            self.cases.append(case)
            self._case_index[design_id] = len(self.cases) - 1
        
        # 如果超过最大数量，删除最旧的案例
        if len(self.cases) > self.max_cases:
            # 删除第一个案例（FIFO）
            removed_id = self.cases[0]['design_id']
            del self.cases[0]
            # 重建索引
            self._case_index = {
                case['design_id']: i 
                for i, case in enumerate(self.cases)
            }
        
        return True
    
    def get_case(self, design_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定案例
        
        Args:
            design_id: 设计ID
        
        Returns:
            案例字典，如果不存在返回None
        """
        if design_id not in self._case_index:
            return None
        
        idx = self._case_index[design_id]
        return self.cases[idx]
    
    def get_all_cases(self) -> List[Dict[str, Any]]:
        """
        获取所有案例
        
        Returns:
            案例列表
        """
        return self.cases.copy()
    
    def get_features_matrix(self) -> np.ndarray:
        """
        获取所有案例的特征矩阵
        
        Returns:
            特征矩阵 (num_cases, feature_dim)
        """
        if not self.cases:
            return np.array([])
        
        features_list = []
        for case in self.cases:
            if 'features' in case and case['features'] is not None:
                features_list.append(np.array(case['features']))
        
        if not features_list:
            return np.array([])
        
        return np.vstack(features_list)
    
    def get_embeddings_matrix(self) -> np.ndarray:
        """
        获取所有案例的嵌入矩阵
        
        Returns:
            嵌入矩阵 (num_cases, embedding_dim)
        """
        if not self.cases:
            return np.array([])
        
        embeddings_list = []
        for case in self.cases:
            if 'embedding' in case and case['embedding'] is not None:
                embeddings_list.append(np.array(case['embedding']))
        
        if not embeddings_list:
            return np.array([])
        
        return np.vstack(embeddings_list)
    
    def get_cases_by_scale(self, min_scale: int, max_scale: int) -> List[Dict[str, Any]]:
        """
        根据设计规模筛选案例
        
        Args:
            min_scale: 最小规模
            max_scale: 最大规模
        
        Returns:
            符合条件的案例列表
        """
        filtered = []
        for case in self.cases:
            if 'quality_metrics' in case:
                metrics = case['quality_metrics']
                # 假设quality_metrics中有num_modules字段
                if 'num_modules' in metrics:
                    num_modules = metrics['num_modules']
                    if min_scale <= num_modules <= max_scale:
                        filtered.append(case)
        return filtered
    
    def size(self) -> int:
        """
        获取知识库大小
        
        Returns:
            案例数量
        """
        return len(self.cases)
    
    def export(self, export_file: str) -> bool:
        """
        导出知识库到指定文件
        
        Args:
            export_file: 导出文件路径
        
        Returns:
            是否成功导出
        """
        try:
            export_path = Path(export_file)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '1.0',
                'num_cases': len(self.cases),
                'cases': self.cases
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"导出知识库失败: {e}")
            return False

