"""
处理已有的DREAMPlace布局结果并添加到知识库
从results目录查找所有已生成的布局文件，提取特征和质量指标
"""

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

from scripts.build_kb_from_dreamplace import build_case_from_dreamplace
from scripts.build_kb import KnowledgeBaseBuilder


def find_existing_layouts(
    remote_server: str,
    remote_user: str,
    dreamplace_dir: str = "~/dreamplace_experiment/DREAMPlace"
) -> List[Dict[str, str]]:
    """
    查找已有的布局文件
    
    Returns:
        设计列表，每个包含 design_id 和 layout_def
    """
    designs = []
    
    try:
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        find_cmd = f"find {dreamplace_dir}/install/results -name '*.gp.def' -type f 2>/dev/null"
        
        result = subprocess.run(
            f"{ssh_cmd} '{find_cmd}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            def_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            for def_file in def_files:
                # 从路径提取设计名称
                # 例如: ~/dreamplace_experiment/DREAMPlace/install/results/mgc_fft_1/mgc_fft_1.gp.def
                path_parts = def_file.split('/')
                filename = Path(def_file).stem.replace('.gp', '')
                
                # 尝试从路径中提取设计名称
                design_id = None
                for part in reversed(path_parts):
                    if part and part not in ['results', 'install', 'dreamplace_experiment', 'DREAMPlace', 'design.gp.def', 'floorplan.gp.def']:
                        # 如果包含mgc_或design_等前缀，使用它
                        if 'mgc_' in part or 'design' in part.lower():
                            design_id = part.replace('.gp.def', '').replace('design_', '').replace('_gp', '')
                            break
                
                # 如果没找到，使用文件名
                if not design_id:
                    design_id = filename
                
                # 跳过通用名称
                if design_id in ['design', 'floorplan']:
                    # 尝试从父目录获取
                    parent_dir = path_parts[-2] if len(path_parts) > 1 else None
                    if parent_dir and parent_dir not in ['results', 'design', 'floorplan']:
                        design_id = parent_dir
                    else:
                        continue
                
                designs.append({
                    'design_id': design_id,
                    'layout_def': def_file
                })
        
        # 去重
        seen = set()
        unique_designs = []
        for d in designs:
            key = d['design_id']
            if key not in seen:
                seen.add(key)
                unique_designs.append(d)
        
        return sorted(unique_designs, key=lambda x: x['design_id'])
    except Exception as e:
        print(f"查找布局文件失败: {e}")
        return []


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='处理已有的DREAMPlace布局结果')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--remote-server', type=str, required=True,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default='keqin',
                       help='远程用户')
    parser.add_argument('--dreamplace-dir', type=str, default='~/dreamplace_experiment/DREAMPlace',
                       help='DREAMPlace目录')
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
    print("处理已有的DREAMPlace布局结果")
    print("=" * 70)
    
    # 查找已有的布局文件
    print(f"\n1. 查找已有的布局文件...")
    designs = find_existing_layouts(
        args.remote_server,
        args.remote_user,
        args.dreamplace_dir
    )
    
    print(f"找到 {len(designs)} 个布局文件")
    for d in designs[:10]:
        print(f"  {d['design_id']}: {d['layout_def']}")
    if len(designs) > 10:
        print(f"  ... 还有 {len(designs) - 10} 个")
    
    if not designs:
        print("未找到任何布局文件，退出")
        return
    
    # 处理每个设计
    print(f"\n2. 处理布局文件并添加到知识库...")
    added_count = 0
    failed_count = 0
    skipped_count = 0
    
    # 加载已有知识库，检查哪些设计已经存在
    builder.kb.load()
    existing_designs = {case['design_id'] for case in builder.kb.cases}
    
    for i, design in enumerate(designs, 1):
        design_id = design['design_id']
        layout_def = design['layout_def']
        
        print(f"\n[{i}/{len(designs)}] 处理: {design_id}")
        
        # 检查是否已存在
        if design_id in existing_designs:
            print(f"  ⚠ 设计 {design_id} 已存在于知识库，跳过")
            skipped_count += 1
            continue
        
        # 尝试从本地设计文件提取特征
        local_design_dir = Path('data/ispd2015') / design_id
        design_source_dir = str(local_design_dir) if local_design_dir.exists() else None
        
        # 构建案例
        case = build_case_from_dreamplace(
            builder,
            design_id,
            layout_def,
            design_source_dir
        )
        
        if case:
            # 添加到知识库
            try:
                builder.kb.add_case(case)
                builder.kb.save()
                print(f"  ✓ 成功添加案例: {design_id}")
                added_count += 1
            except Exception as e:
                print(f"  ✗ 添加失败: {design_id}: {e}")
                failed_count += 1
        else:
            print(f"  ✗ 构建案例失败: {design_id}")
            failed_count += 1
    
    # 显示统计
    print("\n" + "=" * 70)
    print("完成！")
    print(f"  成功: {added_count}/{len(designs)}")
    print(f"  失败: {failed_count}/{len(designs)}")
    print(f"  跳过: {skipped_count}/{len(designs)}")
    
    stats = builder.get_statistics()
    print(f"\n知识库统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()



