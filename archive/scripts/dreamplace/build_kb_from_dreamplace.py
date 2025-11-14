"""
从DREAMPlace结果构建知识库案例
处理DREAMPlace生成的布局结果，提取设计特征和质量指标
"""

import warnings
# 抑制torchvision的Beta警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import yaml

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.build_kb import KnowledgeBaseBuilder


def sync_dreamplace_results(
    remote_server: str,
    remote_user: str,
    remote_results_dir: str,
    local_temp_dir: str
) -> bool:
    """
    同步DREAMPlace结果到本地
    
    Args:
        remote_server: 远程服务器地址
        remote_user: 远程用户
        remote_results_dir: 远程结果目录
        local_temp_dir: 本地临时目录
    
    Returns:
        是否成功
    """
    local_path = Path(local_temp_dir)
    local_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # 使用rsync同步
        rsync_cmd = [
            'rsync', '-avz',
            '--exclude=*.log',
            '--exclude=*.pyc',
            f'{remote_user}@{remote_server}:{remote_results_dir}/',
            str(local_path) + '/'
        ]
        
        result = subprocess.run(
            rsync_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"✓ 成功同步DREAMPlace结果: {remote_results_dir}")
            return True
        else:
            print(f"✗ 同步失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 同步出错: {e}")
        return False


def find_dreamplace_designs_from_results(local_results_dir: str) -> List[Dict[str, str]]:
    """
    从DREAMPlace results目录查找设计
    
    Args:
        local_results_dir: 本地结果目录
    
    Returns:
        设计列表，每个设计包含: design_id, layout_def, design_dir
    """
    results_path = Path(local_results_dir)
    if not results_path.exists():
        return []
    
    designs = []
    
    # 查找所有包含design.gp.def的目录
    for design_dir in results_path.iterdir():
        if not design_dir.is_dir() or design_dir.name == 'design':
            continue
        
        design_id = design_dir.name
        layout_def = design_dir / 'design' / 'design.gp.def'
        
        if layout_def.exists():
            designs.append({
                'design_id': design_id,
                'layout_def': str(layout_def),
                'design_dir': str(design_dir)
            })
    
    return designs


def find_dreamplace_configs_from_test(
    remote_server: str,
    remote_user: str,
    remote_test_dir: str
) -> List[Dict[str, str]]:
    """
    从DREAMPlace test目录查找所有设计配置文件
    
    Args:
        remote_server: 远程服务器地址
        remote_user: 远程用户
        remote_test_dir: 远程test目录
    
    Returns:
        设计配置列表，每个包含: design_id, config_json, benchmark_type
    """
    import subprocess
    
    designs = []
    
    try:
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        # 查找所有JSON配置文件
        find_cmd = f"find {remote_test_dir} -name '*.json' -type f 2>/dev/null | grep -v 'simple.json'"
        
        result = subprocess.run(
            f"{ssh_cmd} '{find_cmd}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            json_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            for json_file in json_files:
                # 从路径提取设计信息
                # 例如: ~/dreamplace_experiment/DREAMPlace/test/ispd2015/lefdef/mgc_pci_bridge32_a.json
                path_parts = json_file.split('/')
                filename = Path(json_file).stem
                
                # 查找benchmark类型（ispd2015, ispd2005, mms等）
                benchmark_type = None
                for part in path_parts:
                    if part in ['ispd2015', 'ispd2005', 'ispd2005free', 'ispd2019', 
                               'iccad2014', 'iccad2015.ot', 'dac2012', 'mms']:
                        benchmark_type = part
                        break
                
                if benchmark_type:
                    designs.append({
                        'design_id': filename,
                        'config_json': json_file,
                        'benchmark_type': benchmark_type
                    })
        
        return sorted(designs, key=lambda x: (x['benchmark_type'], x['design_id']))
    except Exception as e:
        print(f"查找配置文件失败: {e}")
        return []


def build_case_from_dreamplace(
    builder: KnowledgeBaseBuilder,
    design_id: str,
    layout_def: str,
    design_source_dir: Optional[str] = None
) -> Optional[Dict]:
    """
    从DREAMPlace结果构建知识库案例
    
    Args:
        builder: 知识库构建器
        design_id: 设计ID
        layout_def: 布局DEF文件路径
        design_source_dir: 设计源文件目录（可选，如果提供则提取完整特征）
    
    Returns:
        案例字典或None
    """
    try:
        # 如果提供了设计源目录，从那里提取特征
        if design_source_dir and Path(design_source_dir).exists():
            case = builder.build_case(
                design_dir=design_source_dir,
                layout_def_file=layout_def
            )
        else:
            # 否则只从布局文件提取质量指标
            # 尝试从本地已有的设计文件提取特征
            local_design_dir = Path('data/ispd2015') / design_id
            if local_design_dir.exists():
                print(f"从本地设计文件提取特征: {design_id}")
                features = builder.extract_design_features(str(local_design_dir), design_id)
            else:
                # 如果本地没有，从布局DEF文件提取基本信息
                print(f"从布局文件提取基本信息: {design_id}")
                from src.utils.def_parser import DEFParser
                parser = DEFParser(layout_def)
                parser.parse()
                
                # 计算芯片面积（从DIEAREA）
                chip_area = 0.0
                if hasattr(parser, 'die_area') and parser.die_area:
                    # die_area通常是 (x1, y1, x2, y2)
                    if len(parser.die_area) >= 4:
                        width = abs(parser.die_area[2] - parser.die_area[0])
                        height = abs(parser.die_area[3] - parser.die_area[1])
                        chip_area = width * height
                
                # 计算连接度特征
                net_degrees = []
                component_degrees = {}
                for net_id, net_info in parser.nets.items():
                    if 'pins' in net_info:
                        degree = len(net_info['pins'])
                        net_degrees.append(degree)
                        for pin in net_info['pins']:
                            comp_name = pin.get('component', '')
                            if comp_name:
                                component_degrees[comp_name] = component_degrees.get(comp_name, 0) + 1
                
                avg_net_degree = float(np.mean(net_degrees)) if net_degrees else 0.0
                max_net_degree = int(max(net_degrees)) if net_degrees else 0
                comp_degree_values = list(component_degrees.values())
                avg_component_degree = float(np.mean(comp_degree_values)) if comp_degree_values else 0.0
                max_component_degree = int(max(comp_degree_values)) if comp_degree_values else 0
                
                features = {
                    'design_id': design_id,
                    'num_modules': len(parser.components),  # 使用components数量作为modules
                    'num_components': len(parser.components),
                    'num_nets': len(parser.nets),
                    'chip_area_um2': chip_area,
                    'avg_net_degree': avg_net_degree,
                    'max_net_degree': max_net_degree,
                    'avg_component_degree': avg_component_degree,
                    'max_component_degree': max_component_degree,
                }
                # 生成特征向量
                features['feature_vector'] = builder._generate_feature_vector(features).tolist()
            
            # 提取质量指标
            print(f"提取质量指标: {layout_def}")
            quality_metrics = builder.extract_quality_metrics(layout_def)
            
            # 构建案例
            from datetime import datetime
            # 确保feature_vector是列表格式
            feature_vector = features.get('feature_vector', [])
            if hasattr(feature_vector, 'tolist'):
                feature_vector = feature_vector.tolist()
            elif not isinstance(feature_vector, list):
                feature_vector = []
            
            # 确保特征向量不为空
            if not feature_vector or len(feature_vector) == 0:
                print(f"警告: {design_id} 特征向量为空，跳过")
                return None
            
            case = {
                'design_id': design_id,
                'features': feature_vector,
                'partition_strategy': {},  # DREAMPlace不进行分区
                'negotiation_patterns': {},  # DREAMPlace不进行协商
                'quality_metrics': quality_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            # 生成嵌入
            print(f"生成语义嵌入: {design_id}")
            try:
                embedding = builder.generate_embedding(case)
                if embedding is not None and len(embedding) > 0:
                    case['embedding'] = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                else:
                    # 如果嵌入生成失败，使用零向量
                    print(f"警告: {design_id} 嵌入生成失败，使用零向量")
                    case['embedding'] = [0.0] * builder.embedding_dim
            except Exception as e:
                print(f"警告: {design_id} 嵌入生成异常: {e}，使用零向量")
                case['embedding'] = [0.0] * builder.embedding_dim
        
        return case
    except Exception as e:
        print(f"✗ 构建案例失败 {design_id}: {e}")
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='从DREAMPlace结果构建知识库')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--remote-server', type=str, required=True,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default='keqin',
                       help='远程用户')
    parser.add_argument('--remote-results-dir', type=str,
                       default='~/dreamplace_experiment/DREAMPlace/results',
                       help='远程DREAMPlace结果目录（从已有结果构建）')
    parser.add_argument('--remote-test-dir', type=str,
                       default='~/dreamplace_experiment/DREAMPlace/test',
                       help='远程DREAMPlace test目录（查找所有设计配置）')
    parser.add_argument('--remote-benchmarks-dir', type=str,
                       default='~/dreamplace_experiment/DREAMPlace/benchmarks',
                       help='远程DREAMPlace benchmarks目录（可选，用于提取完整特征）')
    parser.add_argument('--from-test', action='store_true',
                       help='从test目录查找所有设计配置（而不是从results目录）')
    parser.add_argument('--local-temp-dir', type=str,
                       default='data/dreamplace_results_temp',
                       help='本地临时目录')
    parser.add_argument('--kb-file', type=str, default=None,
                       help='知识库文件路径（覆盖配置文件）')
    
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
    
    print("=" * 70)
    print("从DREAMPlace结果构建知识库")
    print("=" * 70)
    
    designs = []
    
    if args.from_test:
        # 从test目录查找所有设计配置
        print(f"\n1. 从test目录查找所有设计配置...")
        configs = find_dreamplace_configs_from_test(
            args.remote_server,
            args.remote_user,
            args.remote_test_dir
        )
        print(f"找到 {len(configs)} 个设计配置")
        
        if not configs:
            print("未找到任何设计配置，退出")
            return
        
        # 显示找到的设计
        benchmark_groups = {}
        for config in configs:
            btype = config['benchmark_type']
            if btype not in benchmark_groups:
                benchmark_groups[btype] = []
            benchmark_groups[btype].append(config['design_id'])
        
        print(f"\n按benchmark类型分组:")
        for btype, design_ids in sorted(benchmark_groups.items()):
            print(f"  {btype}: {len(design_ids)} 个设计")
        
        # 注意：这里只是找到了配置，还需要运行DREAMPlace或查找已有结果
        print(f"\n⚠️  注意: 找到的是配置文件，需要:")
        print(f"  1. 运行DREAMPlace生成布局结果，或")
        print(f"  2. 从已有results目录查找对应的布局结果")
        print(f"\n继续从results目录查找已有结果...")
        
        # 继续从results目录查找
        if not sync_dreamplace_results(
            args.remote_server,
            args.remote_user,
            args.remote_results_dir,
            args.local_temp_dir
        ):
            print("同步失败，但可以继续处理已有配置")
        else:
            designs = find_dreamplace_designs_from_results(args.local_temp_dir)
    else:
        # 1. 同步远程结果
        print(f"\n1. 同步远程结果...")
        if not sync_dreamplace_results(
            args.remote_server,
            args.remote_user,
            args.remote_results_dir,
            args.local_temp_dir
        ):
            print("同步失败，退出")
            return
        
        # 2. 查找设计
        print(f"\n2. 查找DREAMPlace设计...")
        designs = find_dreamplace_designs_from_results(args.local_temp_dir)
    
    print(f"找到 {len(designs)} 个已有布局结果")
    
    if not designs:
        print("未找到任何布局结果")
        if args.from_test:
            print("\n建议:")
            print("  1. 使用 run_dreamplace_batch.py 批量运行DREAMPlace")
            print("  2. 或手动运行DREAMPlace生成布局结果")
        return
    
    # 3. 构建案例
    print(f"\n3. 构建知识库案例...")
    added_count = 0
    
    for design_info in designs:
        design_id = design_info['design_id']
        layout_def = design_info['layout_def']
        
        # 尝试查找对应的设计源文件目录
        design_source_dir = None
        if args.remote_benchmarks_dir:
            # 可以尝试同步benchmarks目录或使用本地已有的设计文件
            local_design_dir = Path('data/ispd2015') / design_id
            if local_design_dir.exists():
                design_source_dir = str(local_design_dir)
        
        print(f"\n处理设计: {design_id}")
        case = build_case_from_dreamplace(
            builder,
            design_id,
            layout_def,
            design_source_dir
        )
        
        if case and builder.add_case_to_kb(case, validate=True):
            added_count += 1
            print(f"✓ 成功添加案例: {design_id}")
            builder.save()
        else:
            print(f"✗ 添加失败: {design_id}")
    
    # 4. 清理临时目录
    print(f"\n4. 清理临时目录...")
    temp_path = Path(args.local_temp_dir)
    if temp_path.exists():
        import shutil
        try:
            shutil.rmtree(temp_path)
            print(f"✓ 清理完成")
        except Exception as e:
            print(f"⚠ 清理失败: {e}")
    
    # 5. 显示统计
    print(f"\n" + "=" * 70)
    print(f"完成！成功添加 {added_count}/{len(designs)} 个案例")
    stats = builder.get_statistics()
    print(f"\n知识库统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == '__main__':
    main()

