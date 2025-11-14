"""
嵌入模型加载器
支持多种嵌入模型后端：
1. sentence-transformers (HuggingFace)
2. Ollama (本地)
3. 本地模型文件
"""

import os
import warnings
from typing import Optional, Union, Any
import numpy as np

# 抑制torchvision的Beta警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')


class EmbeddingModel:
    """嵌入模型基类"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.embedding_dim: Optional[int] = None
    
    def encode(self, texts: Union[str, list]) -> np.ndarray:
        """
        生成嵌入向量
        
        Args:
            texts: 文本或文本列表
        
        Returns:
            嵌入向量（单个文本返回1D数组，多个文本返回2D数组）
        """
        raise NotImplementedError
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        if self.embedding_dim is None:
            raise ValueError("嵌入维度未初始化")
        return self.embedding_dim


class SentenceTransformerModel(EmbeddingModel):
    """使用sentence-transformers的嵌入模型"""
    
    def __init__(self, model_name: str, cache_dir: Optional[str] = None):
        super().__init__(model_name)
        try:
            from sentence_transformers import SentenceTransformer
            
            # 尝试从本地缓存加载
            if cache_dir:
                os.environ['TRANSFORMERS_CACHE'] = cache_dir
                os.environ['HF_HOME'] = cache_dir
            
            # 检查是否是本地路径
            if os.path.exists(model_name):
                # 使用本地路径
                self.model = SentenceTransformer(model_name)
            else:
                # 尝试在线加载，如果失败则尝试离线模式
                try:
                    self.model = SentenceTransformer(model_name)
                except Exception as e:
                    # 尝试使用本地缓存
                    cache_path = os.path.expanduser("~/.cache/huggingface/hub")
                    if os.path.exists(cache_path):
                        # 尝试从缓存加载
                        try:
                            self.model = SentenceTransformer(model_name, cache_folder=cache_path)
                        except:
                            raise e
                    else:
                        raise e
            
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
        except Exception as e:
            raise RuntimeError(f"无法加载sentence-transformers模型 {model_name}: {e}")
    
    def encode(self, texts: Union[str, list]) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings[0] if len(embeddings) == 1 else embeddings


class OllamaEmbeddingModel(EmbeddingModel):
    """使用Ollama的嵌入模型"""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        """
        初始化Ollama嵌入模型
        
        Args:
            model_name: Ollama模型名称（如 nomic-embed-text, mxbai-embed-large）
            base_url: Ollama服务地址
        """
        super().__init__(model_name)
        self.base_url = base_url
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("使用Ollama需要安装requests库: pip install requests")
        
        # 检查Ollama服务是否可用
        try:
            response = self.requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama服务不可用: {base_url}")
        except Exception as e:
            raise RuntimeError(f"无法连接到Ollama服务 {base_url}: {e}")
        
        # 检查模型是否存在
        models = response.json().get('models', [])
        model_names = [m.get('name', '') for m in models]
        if model_name not in model_names:
            print(f"警告: 模型 {model_name} 不在Ollama中，将尝试使用")
            print(f"可用模型: {', '.join(model_names[:5])}")
            print(f"提示: 运行 'ollama pull {model_name}' 下载模型")
        
        # nomic-embed-text的默认维度是768
        # 可以根据实际模型调整
        self.embedding_dim = 768  # nomic-embed-text的维度
    
    def encode(self, texts: Union[str, list]) -> np.ndarray:
        """
        使用Ollama API生成嵌入
        
        Args:
            texts: 文本或文本列表
        
        Returns:
            嵌入向量
        """
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = []
        for text in texts:
            try:
                response = self.requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model_name,
                        "prompt": text
                    },
                    timeout=30
                )
                response.raise_for_status()
                embedding = response.json().get('embedding')
                if embedding is None:
                    raise ValueError("Ollama返回的嵌入为空")
                embeddings.append(embedding)
            except Exception as e:
                raise RuntimeError(f"Ollama嵌入生成失败: {e}")
        
        embeddings = np.array(embeddings)
        # 更新实际维度
        if len(embeddings) > 0:
            self.embedding_dim = len(embeddings[0])
        
        return embeddings[0] if len(embeddings) == 1 else embeddings


def load_embedding_model(
    model_name: str,
    model_type: Optional[str] = None,
    cache_dir: Optional[str] = None,
    ollama_base_url: str = "http://localhost:11434"
) -> EmbeddingModel:
    """
    加载嵌入模型（自动检测类型）
    
    Args:
        model_name: 模型名称或路径
        model_type: 模型类型 ('sentence-transformers', 'ollama', 'auto')
        cache_dir: 缓存目录（用于sentence-transformers）
        ollama_base_url: Ollama服务地址
    
    Returns:
        嵌入模型实例
    
    Examples:
        # 使用sentence-transformers（在线）
        model = load_embedding_model("sentence-transformers/all-MiniLM-L6-v2")
        
        # 使用本地sentence-transformers模型
        model = load_embedding_model("/path/to/local/model")
        
        # 使用Ollama
        model = load_embedding_model("nomic-embed-text", model_type="ollama")
        
        # 自动检测（优先尝试sentence-transformers，失败则尝试Ollama）
        model = load_embedding_model("sentence-transformers/all-MiniLM-L6-v2", model_type="auto")
    """
    if model_type is None or model_type == "auto":
        # 自动检测
        # 1. 如果是本地路径，使用sentence-transformers
        if os.path.exists(model_name):
            model_type = "sentence-transformers"
        # 2. 如果以ollama:开头，使用Ollama
        elif model_name.startswith("ollama:"):
            model_name = model_name[7:]  # 移除"ollama:"前缀
            model_type = "ollama"
        # 3. 否则先尝试sentence-transformers，失败则尝试Ollama
        else:
            try:
                return SentenceTransformerModel(model_name, cache_dir)
            except Exception as e:
                print(f"sentence-transformers加载失败: {e}")
                print("尝试使用Ollama...")
                try:
                    return OllamaEmbeddingModel(model_name, ollama_base_url)
                except Exception as e2:
                    raise RuntimeError(
                        f"所有嵌入模型加载方式都失败:\n"
                        f"  - sentence-transformers: {e}\n"
                        f"  - Ollama: {e2}\n"
                        f"提示: 1) 检查网络连接或使用本地模型\n"
                        f"      2) 安装Ollama并运行 'ollama pull nomic-embed-text'"
                    )
    
    if model_type == "sentence-transformers":
        return SentenceTransformerModel(model_name, cache_dir)
    elif model_type == "ollama":
        return OllamaEmbeddingModel(model_name, ollama_base_url)
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")




