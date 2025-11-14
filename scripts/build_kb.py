"""
知识库构建脚本
从ChipMASRAG运行结果中提取分区经验，构建和扩展知识库

功能：
1. 特征提取：设计规模、类型、模块特征、连接图特征
2. 分区策略提取：从运行结果JSON中提取分区方案
3. 协商模式提取：从运行日志中提取协商历史
4. 质量指标提取：HPWL、边界代价、运行时间
5. 嵌入生成：使用sentence-transformers生成语义嵌入
6. 质量验证：检查案例完整性、验证特征有效性
"""

import os
import sys
import json
import re
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import yaml
import warnings

# 抑制torchvision的Beta警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_base import KnowledgeBase
from src.utils.def_parser import DEFParser
from src.utils.boundary_analyzer import BoundaryAnalyzer
from src.utils.embedding_loader import load_embedding_model, EmbeddingModel


class KnowledgeBaseBuilder:
    """知识库构建器"""
    
    def __init__(
        self,
        kb_file: str,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_model_type: Optional[str] = None,
        embedding_cache_dir: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        config_file: Optional[str] = None
    ):
        """
        初始化知识库构建器
        
        Args:
            kb_file: 知识库文件路径
            embedding_model_name: 嵌入模型名称
                - sentence-transformers模型: "sentence-transformers/all-MiniLM-L6-v2"
                - 本地模型路径: "/path/to/local/model"
                - Ollama模型: "ollama:nomic-embed-text" 或 "nomic-embed-text" (需要设置model_type="ollama")
            embedding_model_type: 模型类型 ('sentence-transformers', 'ollama', 'auto')
            embedding_cache_dir: 模型缓存目录
            ollama_base_url: Ollama服务地址（如果使用Ollama）
            config_file: 配置文件路径（可选）
        """
        self.kb_file = Path(kb_file)
        self.kb = KnowledgeBase(str(self.kb_file))
        self.kb.load()
        
        # 加载嵌入模型
        try:
            self.embedding_model: Optional[EmbeddingModel] = load_embedding_model(
                model_name=embedding_model_name,
                model_type=embedding_model_type,
                cache_dir=embedding_cache_dir,
                ollama_base_url=ollama_base_url
            )
            self.embedding_dim = self.embedding_model.get_embedding_dimension()
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
            self.embedding_dim = 384  # all-MiniLM-L6-v2的默认维度
        
        # 加载配置
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}
        
        self.boundary_analyzer = BoundaryAnalyzer()
    
    def extract_design_features(
        self,
        design_dir: str,
        design_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        提取设计特征
        
        Args:
            design_dir: 设计目录路径（包含design.v, floorplan.def等）
            design_id: 设计ID（如果为None，从目录名提取）
        
        Returns:
            设计特征字典
        """
        design_path = Path(design_dir)
        if design_id is None:
            design_id = design_path.name
        
        features = {
            'design_id': design_id,
            'design_dir': str(design_path),
        }
        
        # 1. 从DEF文件提取基本信息
        def_file = design_path / "floorplan.def"
        if def_file.exists():
            parser = DEFParser(str(def_file))
            parser.parse()
            
            features['num_components'] = len(parser.components)
            features['num_nets'] = len(parser.nets)
            features['die_area'] = parser.die_area
            features['units_per_micron'] = parser.units_per_micron
            
            # 计算芯片面积（微米²）
            if parser.die_area[2] > parser.die_area[0] and parser.die_area[3] > parser.die_area[1]:
                width = (parser.die_area[2] - parser.die_area[0]) / parser.units_per_micron
                height = (parser.die_area[3] - parser.die_area[1]) / parser.units_per_micron
                features['chip_area_um2'] = width * height
            else:
                features['chip_area_um2'] = 0.0
        else:
            features['num_components'] = 0
            features['num_nets'] = 0
            features['die_area'] = (0, 0, 0, 0)
            features['units_per_micron'] = 1000
            features['chip_area_um2'] = 0.0
        
        # 2. 从Verilog文件提取模块信息
        verilog_file = design_path / "design.v"
        if verilog_file.exists():
            module_info = self._parse_verilog_modules(str(verilog_file))
            features['num_modules'] = module_info['num_modules']
            features['module_names'] = module_info['module_names']
            features['module_hierarchy'] = module_info['hierarchy']
        else:
            features['num_modules'] = 0
            features['module_names'] = []
            features['module_hierarchy'] = {}
        
        # 3. 计算连接图特征
        if def_file.exists() and parser.nets:
            graph_features = self._compute_graph_features(parser.nets, parser.components)
            features.update(graph_features)
        else:
            features['avg_net_degree'] = 0.0
            features['max_net_degree'] = 0
            features['avg_component_degree'] = 0.0
            features['max_component_degree'] = 0
        
        # 4. 生成特征向量（用于相似度计算）
        feature_vector = self._generate_feature_vector(features)
        features['feature_vector'] = feature_vector.tolist()
        
        return features
    
    def _parse_verilog_modules(self, verilog_file: str) -> Dict[str, Any]:
        """
        解析Verilog文件，提取模块信息
        
        Args:
            verilog_file: Verilog文件路径
        
        Returns:
            模块信息字典
        """
        with open(verilog_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 移除注释
        content = re.sub(r'//.*?\n', '\n', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # 查找所有模块定义
        module_pattern = r'\bmodule\s+(\w+)\s*[#(]'
        modules = re.findall(module_pattern, content)
        
        # 构建模块层次（简单版本：查找模块实例化）
        hierarchy = {}
        for module in modules:
            # 查找该模块的实例化
            inst_pattern = rf'\b{module}\s+\w+\s*\([^)]*\)\s*;'
            instances = re.findall(inst_pattern, content)
            hierarchy[module] = len(instances)
        
        return {
            'num_modules': len(modules),
            'module_names': modules,
            'hierarchy': hierarchy
        }
    
    def _compute_graph_features(
        self,
        nets: Dict[str, Dict[str, Any]],
        components: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        计算连接图特征
        
        Args:
            nets: 网络字典
            components: 组件字典
        
        Returns:
            图特征字典
        """
        # 计算net的平均度和最大度
        net_degrees = []
        for net_id, net_info in nets.items():
            if 'pins' in net_info:
                degree = len(net_info['pins'])
                net_degrees.append(degree)
        
        avg_net_degree = np.mean(net_degrees) if net_degrees else 0.0
        max_net_degree = max(net_degrees) if net_degrees else 0
        
        # 计算组件的平均度和最大度（连接到多少个net）
        component_degrees = {}
        for net_id, net_info in nets.items():
            if 'pins' in net_info:
                for pin in net_info['pins']:
                    comp_name = pin.get('component', '')
                    if comp_name:
                        component_degrees[comp_name] = component_degrees.get(comp_name, 0) + 1
        
        comp_degree_values = list(component_degrees.values())
        avg_component_degree = np.mean(comp_degree_values) if comp_degree_values else 0.0
        max_component_degree = max(comp_degree_values) if comp_degree_values else 0
        
        return {
            'avg_net_degree': float(avg_net_degree),
            'max_net_degree': int(max_net_degree),
            'avg_component_degree': float(avg_component_degree),
            'max_component_degree': int(max_component_degree)
        }
    
    def _generate_feature_vector(self, features: Dict[str, Any]) -> np.ndarray:
        """
        生成特征向量（用于相似度计算）
        
        Args:
            features: 设计特征字典
        
        Returns:
            特征向量（numpy array）
        """
        # 特征向量包括：
        # 1. 规模特征（归一化）
        # 2. 连接度特征
        # 3. 面积特征
        
        vector = []
        
        # 规模特征（使用对数归一化）
        num_modules = features.get('num_modules', 0)
        num_components = features.get('num_components', 0)
        num_nets = features.get('num_nets', 0)
        
        vector.append(np.log1p(num_modules))
        vector.append(np.log1p(num_components))
        vector.append(np.log1p(num_nets))
        
        # 连接度特征
        vector.append(features.get('avg_net_degree', 0.0))
        vector.append(features.get('max_net_degree', 0))
        vector.append(features.get('avg_component_degree', 0.0))
        vector.append(features.get('max_component_degree', 0))
        
        # 面积特征（归一化）
        chip_area = features.get('chip_area_um2', 0.0)
        vector.append(np.log1p(chip_area))
        
        # 密度特征（组件数/面积）
        if chip_area > 0:
            density = num_components / chip_area
            vector.append(np.log1p(density))
        else:
            vector.append(0.0)
        
        return np.array(vector, dtype=np.float32)
    
    def extract_partition_strategy(
        self,
        partition_scheme_file: str
    ) -> Dict[str, Any]:
        """
        从分区方案JSON文件中提取分区策略
        
        Args:
            partition_scheme_file: 分区方案JSON文件路径
        
        Returns:
            分区策略字典
        """
        if not Path(partition_scheme_file).exists():
            return {}
        
        try:
            with open(partition_scheme_file, 'r') as f:
                scheme = json.load(f)
            
            strategy = {
                'partitions': scheme.get('partitions', {}),
                'num_partitions': len(scheme.get('partitions', {})),
                'boundary_modules': scheme.get('boundary_modules', []),
                'num_boundary_modules': len(scheme.get('boundary_modules', []))
            }
            
            # 计算分区平衡度
            if 'partitions' in scheme:
                partition_sizes = [len(modules) for modules in scheme['partitions'].values()]
                if partition_sizes:
                    avg_size = np.mean(partition_sizes)
                    std_size = np.std(partition_sizes)
                    strategy['balance_ratio'] = float(std_size / avg_size) if avg_size > 0 else 0.0
                else:
                    strategy['balance_ratio'] = 0.0
            
            return strategy
        except Exception as e:
            print(f"提取分区策略失败: {e}")
            return {}
    
    def extract_negotiation_patterns(
        self,
        log_file: str
    ) -> Dict[str, Any]:
        """
        从运行日志中提取协商模式
        
        Args:
            log_file: 日志文件路径
        
        Returns:
            协商模式字典
        """
        if not Path(log_file).exists():
            return {}
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            patterns = {
                'negotiation_history': [],
                'num_negotiations': 0,
                'successful_migrations': 0,
                'failed_migrations': 0
            }
            
            # 查找协商记录（根据实际日志格式调整）
            # 示例格式：NEGOTIATION: agent_0 -> agent_1, module: xxx, result: success/fail
            negotiation_pattern = r'NEGOTIATION[:\s]+agent_(\d+)\s*->\s*agent_(\d+)[,\s]+module[:\s]+(\w+)[,\s]+result[:\s]+(\w+)'
            matches = re.finditer(negotiation_pattern, log_content, re.IGNORECASE)
            
            for match in matches:
                source_agent = int(match.group(1))
                target_agent = int(match.group(2))
                module_id = match.group(3)
                result = match.group(4).lower()
                
                negotiation_record = {
                    'source_agent': source_agent,
                    'target_agent': target_agent,
                    'module_id': module_id,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }
                
                patterns['negotiation_history'].append(negotiation_record)
                
                if result == 'success':
                    patterns['successful_migrations'] += 1
                else:
                    patterns['failed_migrations'] += 1
            
            patterns['num_negotiations'] = len(patterns['negotiation_history'])
            
            # 计算协商成功率
            if patterns['num_negotiations'] > 0:
                patterns['success_rate'] = patterns['successful_migrations'] / patterns['num_negotiations']
            else:
                patterns['success_rate'] = 0.0
            
            return patterns
        except Exception as e:
            print(f"提取协商模式失败: {e}")
            return {}
    
    def extract_quality_metrics(
        self,
        layout_def_file: str,
        partition_scheme: Optional[Dict[str, Any]] = None,
        runtime: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        提取质量指标：HPWL、边界代价、运行时间
        
        Args:
            layout_def_file: 布局DEF文件路径
            partition_scheme: 分区方案（用于计算边界代价）
            runtime: 运行时间（秒）
        
        Returns:
            质量指标字典
        """
        metrics = {}
        
        # 1. 从DEF文件计算HPWL
        layout_path = Path(layout_def_file)
        if layout_path.exists():
            try:
                parser = DEFParser(str(layout_path))
                parser.parse()
                
                # 使用DEFParser的内置方法计算HPWL（更可靠）
                if hasattr(parser, 'calculate_total_hpwl'):
                    hpwl = parser.calculate_total_hpwl()
                else:
                    # 回退到手动计算
                    hpwl = self._calculate_hpwl_from_def(parser.nets, parser.components)
                
                metrics['hpwl'] = float(hpwl) if hpwl > 0 else 0.0
                metrics['num_placed_components'] = len([c for c in parser.components.values() if c.get('status') != 'UNPLACED'])
                metrics['num_components'] = len(parser.components)
                metrics['num_nets'] = len(parser.nets)
            except Exception as e:
                print(f"警告：提取质量指标失败 {layout_def_file}: {e}")
                metrics['hpwl'] = 0.0
                metrics['num_placed_components'] = 0
                metrics['num_components'] = 0
                metrics['num_nets'] = 0
        else:
            print(f"警告：布局文件不存在: {layout_def_file}")
            metrics['hpwl'] = 0.0
            metrics['num_placed_components'] = 0
            metrics['num_components'] = 0
            metrics['num_nets'] = 0
        
        # 2. 计算边界代价（如果有分区方案）
        if partition_scheme and 'partitions' in partition_scheme:
            boundary_cost = self._calculate_boundary_cost(
                layout_def_file,
                partition_scheme
            )
            metrics['boundary_cost'] = boundary_cost
        else:
            metrics['boundary_cost'] = 0.0
        
        # 3. 运行时间
        if runtime is not None:
            metrics['runtime_seconds'] = float(runtime)
        else:
            metrics['runtime_seconds'] = 0.0
        
        # 4. 其他指标（如果之前没有设置）
        if 'num_modules' not in metrics:
            metrics['num_modules'] = len(partition_scheme.get('partitions', {})) if partition_scheme else 0
        if 'num_nets' not in metrics:
            metrics['num_nets'] = 0
        
        return metrics
    
    def _calculate_hpwl_from_def(
        self,
        nets: Dict[str, Dict[str, Any]],
        components: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        从DEF文件计算HPWL
        
        Args:
            nets: 网络字典
            components: 组件字典
        
        Returns:
            HPWL值（微米）
        """
        total_hpwl = 0.0
        
        for net_id, net_info in nets.items():
            if 'pins' not in net_info:
                continue
            
            # 获取该net所有引脚的位置
            x_coords = []
            y_coords = []
            
            for pin in net_info['pins']:
                comp_name = pin.get('component', '')
                if comp_name and comp_name in components:
                    comp = components[comp_name]
                    if comp.get('status') in ['PLACED', 'FIXED']:
                        x = comp.get('x', 0)
                        y = comp.get('y', 0)
                        x_coords.append(x)
                        y_coords.append(y)
            
            # 计算该net的HPWL
            if x_coords and y_coords:
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)
                hpwl = (max_x - min_x) + (max_y - min_y)
                total_hpwl += hpwl
        
        # 转换为微米（假设units_per_micron=1000）
        return total_hpwl / 1000.0
    
    def _calculate_boundary_cost(
        self,
        layout_def_file: str,
        partition_scheme: Dict[str, Any]
    ) -> float:
        """
        计算边界代价
        
        Args:
            layout_def_file: 布局DEF文件路径
            partition_scheme: 分区方案
        
        Returns:
            边界代价百分比
        """
        if not Path(layout_def_file).exists():
            return 0.0
        
        try:
            parser = DEFParser(str(layout_def_file))
            parser.parse()
            
            # 构建模块到分区的映射
            module_to_partition = {}
            for partition_id, module_ids in partition_scheme.get('partitions', {}).items():
                for module_id in module_ids:
                    module_to_partition[module_id] = partition_id
            
            # 计算各分区内部HPWL
            partition_hpwls = {}
            for partition_id in partition_scheme.get('partitions', {}).keys():
                partition_hpwls[partition_id] = 0.0
            
            # 计算完整HPWL
            total_hpwl = self._calculate_hpwl_from_def(parser.nets, parser.components)
            
            # 计算各分区内部HPWL（排除跨分区连接）
            # 简化版本：假设所有连接都是跨分区的（需要更精确的实现）
            # 这里返回一个估算值
            num_partitions = len(partition_scheme.get('partitions', {}))
            if num_partitions > 0:
                estimated_partition_hpwl = total_hpwl / num_partitions
                partition_hpwl_sum = estimated_partition_hpwl * num_partitions
                
                if partition_hpwl_sum > 0:
                    boundary_cost = ((total_hpwl - partition_hpwl_sum) / partition_hpwl_sum) * 100.0
                else:
                    boundary_cost = 0.0
            else:
                boundary_cost = 0.0
            
            return boundary_cost
        except Exception as e:
            print(f"计算边界代价失败: {e}")
            return 0.0
    
    def generate_embedding(self, case: Dict[str, Any]) -> np.ndarray:
        """
        生成语义嵌入向量
        
        Args:
            case: 案例字典
        
        Returns:
            嵌入向量（numpy array）
        """
        if self.embedding_model is None:
            # 如果没有嵌入模型，返回零向量
            return np.zeros(self.embedding_dim, dtype=np.float32)
        
        # 构建文本描述
        text_parts = []
        
        # 设计信息
        if 'design_id' in case:
            text_parts.append(f"Design: {case['design_id']}")
        
        # 规模信息
        if 'quality_metrics' in case:
            metrics = case['quality_metrics']
            if 'num_modules' in metrics:
                text_parts.append(f"Modules: {metrics['num_modules']}")
            if 'num_nets' in metrics:
                text_parts.append(f"Nets: {metrics['num_nets']}")
            if 'hpwl' in metrics:
                text_parts.append(f"HPWL: {metrics['hpwl']:.2f}")
        
        # 分区信息
        if 'partition_strategy' in case:
            strategy = case['partition_strategy']
            if 'num_partitions' in strategy:
                text_parts.append(f"Partitions: {strategy['num_partitions']}")
            if 'balance_ratio' in strategy:
                text_parts.append(f"Balance: {strategy['balance_ratio']:.2f}")
        
        # 协商信息
        if 'negotiation_patterns' in case:
            patterns = case['negotiation_patterns']
            if 'num_negotiations' in patterns:
                text_parts.append(f"Negotiations: {patterns['num_negotiations']}")
            if 'success_rate' in patterns:
                text_parts.append(f"Success Rate: {patterns['success_rate']:.2f}")
        
        text = " ".join(text_parts)
        
        # 生成嵌入
        try:
            embedding = self.embedding_model.encode(text)
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            return embedding.astype(np.float32)
        except Exception as e:
            print(f"生成嵌入失败: {e}")
            return np.zeros(self.embedding_dim, dtype=np.float32)
    
    def build_case(
        self,
        design_dir: str,
        partition_scheme_file: Optional[str] = None,
        layout_def_file: Optional[str] = None,
        log_file: Optional[str] = None,
        runtime: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        构建完整案例
        
        Args:
            design_dir: 设计目录路径
            partition_scheme_file: 分区方案JSON文件路径（可选）
            layout_def_file: 布局DEF文件路径（可选）
            log_file: 运行日志文件路径（可选）
            runtime: 运行时间（秒，可选）
        
        Returns:
            完整案例字典
        """
        design_path = Path(design_dir)
        design_id = design_path.name
        
        # 1. 提取设计特征
        print(f"提取设计特征: {design_id}")
        features = self.extract_design_features(design_dir, design_id)
        
        # 2. 提取分区策略
        partition_strategy = {}
        if partition_scheme_file:
            print(f"提取分区策略: {partition_scheme_file}")
            partition_strategy = self.extract_partition_strategy(partition_scheme_file)
        elif (design_path / "partition_scheme.json").exists():
            partition_strategy = self.extract_partition_strategy(
                str(design_path / "partition_scheme.json")
            )
        
        # 3. 提取协商模式
        negotiation_patterns = {}
        if log_file:
            print(f"提取协商模式: {log_file}")
            negotiation_patterns = self.extract_negotiation_patterns(log_file)
        elif (design_path / "logs" / "experiment.log").exists():
            negotiation_patterns = self.extract_negotiation_patterns(
                str(design_path / "logs" / "experiment.log")
            )
        
        # 4. 提取质量指标
        quality_metrics = {}
        if layout_def_file:
            print(f"提取质量指标: {layout_def_file}")
            quality_metrics = self.extract_quality_metrics(
                layout_def_file,
                partition_strategy,
                runtime
            )
        elif (design_path / "layout.def").exists():
            quality_metrics = self.extract_quality_metrics(
                str(design_path / "layout.def"),
                partition_strategy,
                runtime
            )
        else:
            # 如果没有布局文件，至少提取基本特征
            quality_metrics = {
                'num_modules': features.get('num_modules', 0),
                'num_nets': features.get('num_nets', 0),
                'hpwl': 0.0,
                'boundary_cost': 0.0,
                'runtime_seconds': runtime if runtime else 0.0
            }
        
        # 5. 构建案例
        case = {
            'design_id': design_id,
            'features': features.get('feature_vector', []),
            'partition_strategy': partition_strategy,
            'negotiation_patterns': negotiation_patterns,
            'quality_metrics': quality_metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        # 6. 生成嵌入
        print(f"生成语义嵌入: {design_id}")
        embedding = self.generate_embedding(case)
        case['embedding'] = embedding.tolist()
        
        return case
    
    def validate_case(self, case: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证案例完整性
        
        Args:
            case: 案例字典
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 检查必需字段
        required_fields = ['design_id', 'features', 'partition_strategy', 
                          'negotiation_patterns', 'quality_metrics', 'embedding']
        for field in required_fields:
            if field not in case:
                errors.append(f"缺少必需字段: {field}")
        
        # 检查特征向量
        if 'features' in case:
            features = case['features']
            if not isinstance(features, list) or len(features) == 0:
                errors.append("特征向量无效")
        
        # 检查嵌入向量
        if 'embedding' in case:
            embedding = case['embedding']
            if not isinstance(embedding, list) or len(embedding) != self.embedding_dim:
                errors.append(f"嵌入向量维度不匹配: 期望{self.embedding_dim}, 实际{len(embedding) if isinstance(embedding, list) else 0}")
        
        # 检查质量指标
        if 'quality_metrics' in case:
            metrics = case['quality_metrics']
            if 'hpwl' not in metrics or metrics['hpwl'] < 0:
                errors.append("HPWL无效")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def add_case_to_kb(
        self,
        case: Dict[str, Any],
        validate: bool = True
    ) -> bool:
        """
        添加案例到知识库
        
        Args:
            case: 案例字典
            validate: 是否验证案例
        
        Returns:
            是否成功添加
        """
        if validate:
            is_valid, errors = self.validate_case(case)
            if not is_valid:
                print(f"案例验证失败: {errors}")
                return False
        
        success = self.kb.add_case(case)
        if success:
            print(f"成功添加案例: {case.get('design_id', 'unknown')}")
        else:
            print(f"添加案例失败: {case.get('design_id', 'unknown')}")
        
        return success
    
    def build_from_results_dir(
        self,
        results_dir: str,
        validate: bool = True
    ) -> int:
        """
        从实验结果目录构建知识库
        
        Args:
            results_dir: 实验结果目录路径
            validate: 是否验证案例
        
        Returns:
            成功添加的案例数量
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            print(f"结果目录不存在: {results_dir}")
            return 0
        
        added_count = 0
        
        # 查找所有设计目录
        for design_dir in results_path.iterdir():
            if not design_dir.is_dir():
                continue
            
            # 查找分区方案和布局文件
            partition_scheme_file = None
            layout_def_file = None
            log_file = None
            
            # 查找partition_scheme_*.json
            for json_file in design_dir.glob("partition_scheme_*.json"):
                partition_scheme_file = str(json_file)
                break
            
            # 查找layout_*.def
            for def_file in design_dir.glob("layout_*.def"):
                layout_def_file = str(def_file)
                break
            
            # 查找日志文件
            log_dir = design_dir / "logs"
            if log_dir.exists():
                for log in log_dir.glob("*.log"):
                    log_file = str(log)
                    break
            
            # 构建案例
            try:
                case = self.build_case(
                    str(design_dir),
                    partition_scheme_file=partition_scheme_file,
                    layout_def_file=layout_def_file,
                    log_file=log_file
                )
                
                if self.add_case_to_kb(case, validate=validate):
                    added_count += 1
            except Exception as e:
                print(f"构建案例失败 {design_dir.name}: {e}")
                continue
        
        return added_count
    
    def build_from_designs(
        self,
        design_dirs: List[str],
        validate: bool = True
    ) -> int:
        """
        从设计目录列表构建知识库（用于初始构建）
        
        Args:
            design_dirs: 设计目录路径列表
            validate: 是否验证案例
        
        Returns:
            成功添加的案例数量
        """
        added_count = 0
        
        for design_dir in design_dirs:
            design_path = Path(design_dir)
            if not design_path.exists():
                print(f"设计目录不存在: {design_dir}")
                continue
            
            try:
                # 构建基本案例（没有分区方案和布局结果）
                case = self.build_case(str(design_dir))
                
                if self.add_case_to_kb(case, validate=validate):
                    added_count += 1
            except Exception as e:
                print(f"构建案例失败 {design_path.name}: {e}")
                continue
        
        return added_count
    
    def save(self) -> bool:
        """保存知识库"""
        return self.kb.save()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        stats = {
            'num_cases': self.kb.size(),
            'kb_file': str(self.kb_file),
            'embedding_dim': self.embedding_dim
        }
        
        if self.kb.size() > 0:
            cases = self.kb.get_all_cases()
            
            # 统计设计规模分布
            scales = []
            for case in cases:
                if 'quality_metrics' in case:
                    metrics = case['quality_metrics']
                    if 'num_modules' in metrics:
                        scales.append(metrics['num_modules'])
            
            if scales:
                stats['scale_stats'] = {
                    'min': int(min(scales)),
                    'max': int(max(scales)),
                    'mean': float(np.mean(scales)),
                    'median': float(np.median(scales))
                }
        
        return stats


def find_local_results_dirs(results_base_dir: str = "data/results") -> List[str]:
    """
    查找本地实验结果目录（递归搜索）
    
    Args:
        results_base_dir: 实验结果基础目录
    
    Returns:
        实验结果目录列表
    """
    results_path = Path(results_base_dir)
    if not results_path.exists():
        return []
    
    result_dirs = set()
    # 递归搜索包含实验结果文件的目录
    # 先找到所有包含实验结果文件的目录
    partition_files = list(results_path.rglob("partition_scheme_*.json"))
    layout_files = list(results_path.rglob("layout_*.def"))
    
    # 提取包含这些文件的目录
    for file_path in partition_files + layout_files:
        result_dirs.add(str(file_path.parent))
    
    # 去重并排序（最新的在前）
    result_dirs = sorted(result_dirs, reverse=True)
    return result_dirs


def find_remote_results_dirs(
    remote_server: str,
    remote_user: str,
    remote_dir: str
) -> List[str]:
    """
    查找远程服务器实验结果目录（递归搜索）
    
    Args:
        remote_server: 远程服务器地址
        remote_user: 远程服务器用户
        remote_dir: 远程服务器工作目录（从该目录递归搜索）
    
    Returns:
        远程实验结果目录列表
    """
    import subprocess
    
    try:
        # 使用 SSH 查找远程结果目录（递归搜索）
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        # 递归搜索包含实验结果文件的目录
        find_cmd = f"find {remote_dir} -type f \\( -name 'partition_scheme_*.json' -o -name 'layout_*.def' \\) 2>/dev/null | head -50 | xargs -I {{}} dirname {{}} | sort -u"
        
        result = subprocess.run(
            f"{ssh_cmd} '{find_cmd}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            dirs = [d.strip() for d in result.stdout.strip().split('\n') if d.strip()]
            # 过滤出包含实验结果的目录
            valid_dirs = []
            for dir_path in dirs:
                # 检查远程目录是否包含实验结果
                check_cmd = f"test -f {dir_path}/partition_scheme_*.json -o -f {dir_path}/layout_*.def || find {dir_path} -maxdepth 2 -name 'partition_scheme_*.json' -o -name 'layout_*.def' | head -1 | grep -q ."
                check_result = subprocess.run(
                    f"{ssh_cmd} '{check_cmd}'",
                    shell=True,
                    capture_output=True,
                    timeout=10
                )
                if check_result.returncode == 0:
                    valid_dirs.append(dir_path)
            return sorted(valid_dirs, reverse=True)  # 最新的在前
        else:
            print(f"查找远程结果目录失败: {result.stderr}")
            return []
    except subprocess.TimeoutExpired:
        print("连接远程服务器超时")
        return []
    except Exception as e:
        print(f"查找远程结果目录出错: {e}")
        return []


def sync_remote_results(
    remote_server: str,
    remote_user: str,
    remote_dir: str,
    local_dir: str
) -> bool:
    """
    同步远程实验结果到本地
    
    Args:
        remote_server: 远程服务器地址
        remote_user: 远程服务器用户
        remote_dir: 远程目录路径
        local_dir: 本地目录路径
    
    Returns:
        是否成功同步
    """
    import subprocess
    
    try:
        # 使用 rsync 同步
        rsync_cmd = [
            "rsync",
            "-avz",
            "--exclude=*.log",  # 排除日志文件（太大）
            f"{remote_user}@{remote_server}:{remote_dir}/",
            f"{local_dir}/"
        ]
        
        result = subprocess.run(
            rsync_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode == 0:
            print(f"成功同步远程结果: {remote_dir} -> {local_dir}")
            return True
        else:
            print(f"同步远程结果失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("同步远程结果超时")
        return False
    except Exception as e:
        print(f"同步远程结果出错: {e}")
        return False


def main():
    """主函数"""
    import argparse
    import subprocess
    
    parser = argparse.ArgumentParser(description='构建和扩展知识库')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--kb-file', type=str, default=None,
                       help='知识库文件路径（覆盖配置文件）')
    parser.add_argument('--results-dir', type=str, default=None,
                       help='实验结果目录路径（从结果构建）')
    parser.add_argument('--results-base-dir', type=str, default=None,
                       help='实验结果基础目录（自动搜索所有结果目录，默认从项目根目录递归搜索）')
    parser.add_argument('--design-dirs', type=str, nargs='+', default=None,
                       help='设计目录路径列表（从设计构建基本案例）')
    parser.add_argument('--design-base-dir', type=str, default='data/ispd2015',
                       help='设计基础目录（自动搜索所有设计目录）')
    parser.add_argument('--auto-local', action='store_true',
                       help='自动搜索本地实验结果目录并更新知识库')
    parser.add_argument('--auto-remote', action='store_true',
                       help='自动搜索远程服务器实验结果目录并更新知识库')
    parser.add_argument('--remote-server', type=str, default=None,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default=None,
                       help='远程服务器用户')
    parser.add_argument('--remote-dir', type=str, default='~',
                       help='远程服务器搜索目录（默认从~递归搜索）')
    parser.add_argument('--sync-remote', action='store_true',
                       help='同步远程结果到本地（需要--auto-remote）')
    parser.add_argument('--all', action='store_true',
                       help='执行所有操作：构建初始知识库+更新本地+更新远程')
    parser.add_argument('--validate', action='store_true', default=True,
                       help='验证案例完整性')
    parser.add_argument('--stats', action='store_true',
                       help='显示知识库统计信息')
    
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        kb_config = config.get('knowledge_base', {})
        kb_file = args.kb_file or kb_config.get('case_file', 'data/knowledge_base/kb_cases.json')
        embedding_model = kb_config.get('embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        embedding_model_type = kb_config.get('embedding_model_type', 'auto')
        embedding_cache_dir = kb_config.get('embedding_cache_dir', None)
        ollama_base_url = kb_config.get('ollama_base_url', 'http://localhost:11434')
    else:
        kb_file = args.kb_file or 'data/knowledge_base/kb_cases.json'
        embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
        embedding_model_type = 'auto'
        embedding_cache_dir = None
        ollama_base_url = 'http://localhost:11434'
    
    # 创建构建器
    builder = KnowledgeBaseBuilder(
        kb_file=kb_file,
        embedding_model_name=embedding_model,
        embedding_model_type=embedding_model_type,
        embedding_cache_dir=embedding_cache_dir,
        ollama_base_url=ollama_base_url,
        config_file=str(config_path) if config_path.exists() else None
    )
    
    # 显示统计信息
    if args.stats:
        stats = builder.get_statistics()
        print("\n知识库统计信息:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return
    
    # 构建知识库
    total_added = 0
    
    if args.all:
        # 执行所有操作
        print("=" * 60)
        print("开始构建和更新知识库")
        print("=" * 60)
        
        # 1. 构建初始知识库（从设计文件）
        design_path = Path(args.design_base_dir)
        if design_path.exists():
            design_dirs = []
            for item in design_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    if (item / "design.v").exists() and (item / "floorplan.def").exists():
                        design_dirs.append(str(item))
            
            if design_dirs:
                print(f"\n构建初始知识库（找到 {len(design_dirs)} 个设计）...")
                added = builder.build_from_designs(design_dirs, validate=args.validate)
                total_added += added
                if added > 0:
                    builder.save()
        
        # 2. 更新本地结果
        local_base_dir = args.results_base_dir or "/Users/keqin/Documents/workspace/chip-rag"
        local_results = find_local_results_dirs(local_base_dir)
        if local_results:
            print(f"\n更新本地结果（找到 {len(local_results)} 个结果目录）...")
            for result_dir in local_results:
                added = builder.build_from_results_dir(result_dir, validate=args.validate)
                total_added += added
            if total_added > 0:
                builder.save()
        
        # 3. 更新远程结果
        if args.auto_remote or args.remote_server:
            remote_server = args.remote_server or config.get('remote', {}).get('server')
            remote_user = args.remote_user or config.get('remote', {}).get('user', 'keqin')
            remote_dir = args.remote_dir or config.get('remote', {}).get('dir', '~')
            
            if remote_server:
                remote_results = find_remote_results_dirs(remote_server, remote_user, remote_dir)
                if remote_results:
                    print(f"\n更新远程结果（找到 {len(remote_results)} 个结果目录）...")
                    temp_results_dir = Path("data/results_remote_temp")
                    temp_results_dir.mkdir(parents=True, exist_ok=True)
                    
                    for remote_result_dir in remote_results:
                        if args.sync_remote:
                            remote_name = Path(remote_result_dir).name
                            local_temp_dir = temp_results_dir / remote_name
                            local_temp_dir.mkdir(parents=True, exist_ok=True)
                            
                            if sync_remote_results(remote_server, remote_user, remote_result_dir, str(local_temp_dir)):
                                added = builder.build_from_results_dir(str(local_temp_dir), validate=args.validate)
                                total_added += added
                    
                    # 清理临时目录
                    if temp_results_dir.exists():
                        import shutil
                        try:
                            shutil.rmtree(temp_results_dir)
                        except:
                            pass
                    
                    if total_added > 0:
                        builder.save()
    
    elif args.auto_local:
        # 自动搜索本地结果
        local_base_dir = args.results_base_dir or "/Users/keqin/Documents/workspace/chip-rag"
        local_results = find_local_results_dirs(local_base_dir)
        if not local_results:
            print(f"本地未找到实验结果目录: {local_base_dir}")
            return
        
        print(f"找到 {len(local_results)} 个本地实验结果目录")
        for result_dir in local_results:
            print(f"\n处理: {result_dir}")
            added = builder.build_from_results_dir(result_dir, validate=args.validate)
            total_added += added
            if added > 0:
                builder.save()
    
    elif args.auto_remote:
        # 自动搜索远程结果
        remote_server = args.remote_server or config.get('remote', {}).get('server')
        remote_user = args.remote_user or config.get('remote', {}).get('user', 'keqin')
        remote_dir = args.remote_dir or config.get('remote', {}).get('dir', '~')
        
        if not remote_server:
            print("错误：必须指定 --remote-server 或配置文件中设置 remote.server")
            return
        
        remote_results = find_remote_results_dirs(remote_server, remote_user, remote_dir)
        if not remote_results:
            print("远程服务器未找到实验结果目录")
            return
        
        print(f"找到 {len(remote_results)} 个远程实验结果目录")
        temp_results_dir = Path("data/results_remote_temp")
        temp_results_dir.mkdir(parents=True, exist_ok=True)
        
        for remote_result_dir in remote_results:
            print(f"\n处理远程目录: {remote_result_dir}")
            if args.sync_remote:
                remote_name = Path(remote_result_dir).name
                local_temp_dir = temp_results_dir / remote_name
                local_temp_dir.mkdir(parents=True, exist_ok=True)
                
                if sync_remote_results(remote_server, remote_user, remote_result_dir, str(local_temp_dir)):
                    added = builder.build_from_results_dir(str(local_temp_dir), validate=args.validate)
                    total_added += added
                    if added > 0:
                        builder.save()
        
        # 清理临时目录
        if temp_results_dir.exists():
            import shutil
            try:
                shutil.rmtree(temp_results_dir)
            except:
                pass
    
    elif args.results_dir:
        # 从指定实验结果目录构建
        print(f"从实验结果目录构建: {args.results_dir}")
        total_added = builder.build_from_results_dir(
            args.results_dir,
            validate=args.validate
        )
    
    elif args.design_dirs:
        # 从指定设计目录构建
        print(f"从设计目录构建: {args.design_dirs}")
        total_added = builder.build_from_designs(
            args.design_dirs,
            validate=args.validate
        )
    
    else:
        print("错误：必须指定以下选项之一：")
        print("  --results-dir: 指定实验结果目录")
        print("  --design-dirs: 指定设计目录列表")
        print("  --auto-local: 自动搜索本地实验结果")
        print("  --auto-remote: 自动搜索远程实验结果")
        print("  --all: 执行所有操作（构建初始+更新本地+更新远程）")
        return
    
    # 保存知识库
    if total_added > 0:
        if builder.save():
            print(f"\n✓ 成功添加 {total_added} 个案例到知识库")
            print(f"知识库文件: {kb_file}")
        else:
            print("\n✗ 保存知识库失败")
    else:
        print("\n- 没有添加任何案例")
    
    # 显示统计信息
    stats = builder.get_statistics()
    print("\n知识库统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

