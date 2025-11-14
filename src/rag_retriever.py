"""
RAG检索模块
实现三级检索：粗粒度→细粒度→语义检索
"""

import warnings
# 抑制torchvision的Beta警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')

import numpy as np
from typing import List, Dict, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity

from .knowledge_base import KnowledgeBase
from .utils.embedding_loader import load_embedding_model, EmbeddingModel


class RAGRetriever:
    """RAG检索器"""
    
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_model_type: Optional[str] = None,
        embedding_cache_dir: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        coarse_top_k: int = 50,
        fine_top_k: int = 20,
        semantic_top_k: int = 10,
        similarity_threshold: float = 0.7
    ):
        """
        初始化RAG检索器
        
        Args:
            knowledge_base: 知识库实例
            embedding_model_name: 嵌入模型名称
                - sentence-transformers模型: "sentence-transformers/all-MiniLM-L6-v2"
                - 本地模型路径: "/path/to/local/model"
                - Ollama模型: "ollama:nomic-embed-text" 或 "nomic-embed-text" (需要设置model_type="ollama")
            embedding_model_type: 模型类型 ('sentence-transformers', 'ollama', 'auto')
            embedding_cache_dir: 模型缓存目录
            ollama_base_url: Ollama服务地址（如果使用Ollama）
            coarse_top_k: 粗粒度检索返回top-k
            fine_top_k: 细粒度检索返回top-k
            semantic_top_k: 语义检索返回top-k（最终结果）
            similarity_threshold: 相似度阈值
        """
        self.kb = knowledge_base
        self.coarse_top_k = coarse_top_k
        self.fine_top_k = fine_top_k
        self.semantic_top_k = semantic_top_k
        self.similarity_threshold = similarity_threshold
        
        # 加载嵌入模型
        try:
            self.embedding_model: Optional[EmbeddingModel] = load_embedding_model(
                model_name=embedding_model_name,
                model_type=embedding_model_type,
                cache_dir=embedding_cache_dir,
                ollama_base_url=ollama_base_url
            )
        except Exception as e:
            print(f"警告：加载嵌入模型失败: {e}")
            print("\n解决方案：")
            print("1. 使用本地sentence-transformers模型:")
            print("   - 先下载模型: python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"sentence-transformers/all-MiniLM-L6-v2\")'")
            print("   - 然后使用本地路径")
            print("2. 使用Ollama (推荐):")
            print("   - 安装Ollama: https://ollama.com/download")
            print("   - 下载嵌入模型: ollama pull nomic-embed-text")
            print("   - 在配置中设置: embedding_model_name: 'ollama:nomic-embed-text'")
            print("3. 跳过语义嵌入功能，仅使用特征向量检索")
            self.embedding_model = None
    
    def coarse_retrieve(
        self,
        query_features: np.ndarray,
        design_scale: Optional[int] = None,
        design_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        粗粒度检索：基于规模和类型筛选
        
        Args:
            query_features: 查询特征向量
            design_scale: 设计规模（模块数）
            design_type: 设计类型（可选）
        
        Returns:
            候选案例列表
        """
        all_cases = self.kb.get_all_cases()
        
        if not all_cases:
            return []
        
        # 如果指定了规模，进行规模筛选
        if design_scale is not None:
            # 规模范围：±50%
            min_scale = int(design_scale * 0.5)
            max_scale = int(design_scale * 1.5)
            filtered_cases = self.kb.get_cases_by_scale(min_scale, max_scale)
        else:
            filtered_cases = all_cases
        
        # 如果指定了类型，进行类型筛选
        if design_type is not None:
            filtered_cases = [
                case for case in filtered_cases
                if case.get('design_type') == design_type
            ]
        
        # 如果筛选后数量仍然很多，使用特征相似度进行初步筛选
        if len(filtered_cases) > self.coarse_top_k:
            # 计算特征相似度
            query_features = query_features.reshape(1, -1)
            case_features = self.kb.get_features_matrix()
            
            if case_features.size > 0 and query_features.shape[1] == case_features.shape[1]:
                similarities = cosine_similarity(query_features, case_features)[0]
                # 获取top-k
                top_indices = np.argsort(similarities)[::-1][:self.coarse_top_k]
                filtered_cases = [filtered_cases[i] for i in top_indices if i < len(filtered_cases)]
        
        return filtered_cases[:self.coarse_top_k]
    
    def fine_retrieve(
        self,
        query_features: np.ndarray,
        candidate_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        细粒度检索：基于特征向量相似度
        
        Args:
            query_features: 查询特征向量
            candidate_cases: 候选案例列表
        
        Returns:
            筛选后的案例列表
        """
        if not candidate_cases:
            return []
        
        # 提取候选案例的特征
        candidate_features = []
        valid_cases = []
        
        for case in candidate_cases:
            if 'features' in case and case['features'] is not None:
                candidate_features.append(np.array(case['features']))
                valid_cases.append(case)
        
        if not candidate_features:
            return []
        
        candidate_features = np.vstack(candidate_features)
        query_features = query_features.reshape(1, -1)
        
        # 计算余弦相似度
        if query_features.shape[1] == candidate_features.shape[1]:
            similarities = cosine_similarity(query_features, candidate_features)[0]
        else:
            # 特征维度不匹配，返回所有候选
            return valid_cases
        
        # 获取top-k
        top_indices = np.argsort(similarities)[::-1][:self.fine_top_k]
        return [valid_cases[i] for i in top_indices]
    
    def semantic_retrieve(
        self,
        query_text: str,
        candidate_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        语义检索：基于嵌入模型语义相似度
        
        Args:
            query_text: 查询文本（设计描述或特征文本化）
            candidate_cases: 候选案例列表
        
        Returns:
            最终检索结果列表
        """
        if not candidate_cases or self.embedding_model is None:
            return candidate_cases[:self.semantic_top_k]
        
        # 生成查询嵌入
        try:
            query_embedding = self.embedding_model.encode(query_text, convert_to_numpy=True)
            query_embedding = query_embedding.reshape(1, -1)
        except Exception as e:
            print(f"生成查询嵌入失败: {e}")
            return candidate_cases[:self.semantic_top_k]
        
        # 提取候选案例的嵌入
        candidate_embeddings = []
        valid_cases = []
        
        for case in candidate_cases:
            if 'embedding' in case and case['embedding'] is not None:
                candidate_embeddings.append(np.array(case['embedding']))
                valid_cases.append(case)
            else:
                # 如果没有预计算的嵌入，实时生成
                try:
                    case_text = self._case_to_text(case)
                    case_embedding = self.embedding_model.encode(case_text)
                    if not isinstance(case_embedding, np.ndarray):
                        case_embedding = np.array(case_embedding)
                    candidate_embeddings.append(case_embedding)
                    valid_cases.append(case)
                except Exception as e:
                    print(f"生成案例嵌入失败: {e}")
                    continue
        
        if not candidate_embeddings:
            return []
        
        candidate_embeddings = np.vstack(candidate_embeddings)
        
        # 计算语义相似度
        similarities = cosine_similarity(query_embedding, candidate_embeddings)[0]
        
        # 应用相似度阈值
        filtered_indices = np.where(similarities >= self.similarity_threshold)[0]
        
        if len(filtered_indices) == 0:
            # 如果没有满足阈值的，返回top-k
            top_indices = np.argsort(similarities)[::-1][:self.semantic_top_k]
        else:
            # 在满足阈值的案例中选择top-k
            filtered_similarities = similarities[filtered_indices]
            top_filtered_indices = np.argsort(filtered_similarities)[::-1][:self.semantic_top_k]
            top_indices = filtered_indices[top_filtered_indices]
        
        return [valid_cases[i] for i in top_indices]
    
    def _case_to_text(self, case: Dict[str, Any]) -> str:
        """
        将案例转换为文本描述（用于语义检索）
        
        Args:
            case: 案例字典
        
        Returns:
            文本描述
        """
        parts = []
        
        if 'design_id' in case:
            parts.append(f"Design: {case['design_id']}")
        
        if 'quality_metrics' in case:
            metrics = case['quality_metrics']
            if 'num_modules' in metrics:
                parts.append(f"Modules: {metrics['num_modules']}")
            if 'num_nets' in metrics:
                parts.append(f"Nets: {metrics['num_nets']}")
        
        if 'partition_strategy' in case:
            strategy = case['partition_strategy']
            if 'num_partitions' in strategy:
                parts.append(f"Partitions: {strategy['num_partitions']}")
        
        return " ".join(parts)
    
    def retrieve(
        self,
        query_features: np.ndarray,
        query_text: Optional[str] = None,
        design_scale: Optional[int] = None,
        design_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        统一检索接口：三级检索流程
        
        Args:
            query_features: 查询特征向量
            query_text: 查询文本（可选，用于语义检索）
            design_scale: 设计规模
            design_type: 设计类型
        
        Returns:
            最终检索结果列表（top-k=10）
        """
        # 1. 粗粒度检索
        coarse_results = self.coarse_retrieve(
            query_features,
            design_scale=design_scale,
            design_type=design_type
        )
        
        if not coarse_results:
            return []
        
        # 2. 细粒度检索
        fine_results = self.fine_retrieve(query_features, coarse_results)
        
        if not fine_results:
            return []
        
        # 3. 语义检索（如果有查询文本）
        if query_text is not None:
            semantic_results = self.semantic_retrieve(query_text, fine_results)
        else:
            # 如果没有查询文本，直接返回细粒度结果
            semantic_results = fine_results[:self.semantic_top_k]
        
        return semantic_results

