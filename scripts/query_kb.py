"""
知识库查询和修改工具
用于查询、查看和修改知识库中的案例
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_base import KnowledgeBase
import yaml


def query_kb(kb_file: str, design_id: Optional[str] = None, show_details: bool = False):
    """
    查询知识库
    
    Args:
        kb_file: 知识库文件路径
        design_id: 设计ID（如果指定，只查询该设计）
        show_details: 是否显示详细信息
    """
    kb = KnowledgeBase(kb_file)
    kb.load()
    
    print("=" * 60)
    print("知识库查询结果")
    print("=" * 60)
    print(f"知识库文件: {kb_file}")
    print(f"案例总数: {kb.size()}")
    print()
    
    if design_id:
        # 查询指定设计
        case = kb.get_case(design_id)
        if case:
            print(f"找到设计: {design_id}")
            print_case_details(case, show_details)
        else:
            print(f"未找到设计: {design_id}")
    else:
        # 显示所有案例摘要
        cases = kb.get_all_cases()
        print(f"所有案例列表（共 {len(cases)} 个）:")
        print("-" * 60)
        
        for i, case in enumerate(cases, 1):
            design_id = case.get('design_id', 'unknown')
            metrics = case.get('quality_metrics', {})
            num_modules = metrics.get('num_modules', 'N/A')
            num_nets = metrics.get('num_nets', 'N/A')
            hpwl = metrics.get('hpwl', 'N/A')
            timestamp = case.get('timestamp', 'N/A')
            
            # 格式化数值
            num_modules_str = str(num_modules) if num_modules != 'N/A' else 'N/A'
            num_nets_str = str(num_nets) if num_nets != 'N/A' else 'N/A'
            hpwl_str = f"{hpwl:.2f}" if isinstance(hpwl, (int, float)) else str(hpwl)
            
            print(f"{i:3d}. {design_id:30s} | 模块: {num_modules_str:>6s} | "
                  f"网络: {num_nets_str:>8s} | HPWL: {hpwl_str:>12s} | {timestamp[:19] if timestamp != 'N/A' else 'N/A'}")
            
            if show_details:
                print_case_details(case, show_details=False)
                print()


def print_case_details(case: Dict[str, Any], show_details: bool = True):
    """打印案例详细信息"""
    print("-" * 60)
    print(f"设计ID: {case.get('design_id', 'N/A')}")
    print(f"时间戳: {case.get('timestamp', 'N/A')}")
    
    # 特征向量
    features = case.get('features', [])
    if features:
        print(f"特征向量维度: {len(features)}")
        if show_details:
            print(f"特征向量: {features[:5]}..." if len(features) > 5 else f"特征向量: {features}")
    
    # 分区策略
    partition_strategy = case.get('partition_strategy', {})
    if partition_strategy:
        num_partitions = partition_strategy.get('num_partitions', 0)
        print(f"分区数量: {num_partitions}")
        if show_details:
            print(f"分区策略: {json.dumps(partition_strategy, indent=2, ensure_ascii=False)}")
    else:
        print("分区策略: 无（初始案例）")
    
    # 协商模式
    negotiation_patterns = case.get('negotiation_patterns', {})
    if negotiation_patterns:
        num_negotiations = negotiation_patterns.get('num_negotiations', 0)
        success_rate = negotiation_patterns.get('success_rate', 0.0)
        print(f"协商次数: {num_negotiations}, 成功率: {success_rate:.2%}")
        if show_details:
            print(f"协商模式: {json.dumps(negotiation_patterns, indent=2, ensure_ascii=False)}")
    else:
        print("协商模式: 无（初始案例）")
    
    # 质量指标
    quality_metrics = case.get('quality_metrics', {})
    if quality_metrics:
        print("质量指标:")
        for key, value in quality_metrics.items():
            print(f"  {key}: {value}")
    
    # 嵌入向量
    embedding = case.get('embedding', [])
    if embedding:
        print(f"嵌入向量维度: {len(embedding)}")
        if show_details:
            print(f"嵌入向量（前5维）: {embedding[:5]}...")


def update_case(kb_file: str, design_id: str, field: str, value: Any):
    """
    更新知识库中的案例
    
    Args:
        kb_file: 知识库文件路径
        design_id: 设计ID
        field: 要更新的字段（支持嵌套字段，如 quality_metrics.hpwl）
        value: 新值
    """
    kb = KnowledgeBase(kb_file)
    kb.load()
    
    case = kb.get_case(design_id)
    if not case:
        print(f"错误：未找到设计 {design_id}")
        return False
    
    # 解析嵌套字段
    fields = field.split('.')
    target = case
    for f in fields[:-1]:
        if f not in target:
            target[f] = {}
        target = target[f]
    
    # 更新值
    old_value = target.get(fields[-1])
    target[fields[-1]] = value
    
    print(f"更新案例: {design_id}")
    print(f"字段: {field}")
    print(f"旧值: {old_value}")
    print(f"新值: {value}")
    
    # 保存
    if kb.add_case(case) and kb.save():
        print("✓ 更新成功")
        return True
    else:
        print("✗ 更新失败")
        return False


def delete_case(kb_file: str, design_id: str):
    """
    删除知识库中的案例
    
    Args:
        kb_file: 知识库文件路径
        design_id: 设计ID
    """
    kb = KnowledgeBase(kb_file)
    kb.load()
    
    if design_id not in kb._case_index:
        print(f"错误：未找到设计 {design_id}")
        return False
    
    # 删除案例
    idx = kb._case_index[design_id]
    del kb.cases[idx]
    
    # 重建索引
    kb._case_index = {
        case['design_id']: i 
        for i, case in enumerate(kb.cases)
    }
    
    print(f"删除案例: {design_id}")
    
    # 保存
    if kb.save():
        print("✓ 删除成功")
        return True
    else:
        print("✗ 删除失败")
        return False


def export_case(kb_file: str, design_id: str, output_file: str):
    """
    导出单个案例到文件
    
    Args:
        kb_file: 知识库文件路径
        design_id: 设计ID
        output_file: 输出文件路径
    """
    kb = KnowledgeBase(kb_file)
    kb.load()
    
    case = kb.get_case(design_id)
    if not case:
        print(f"错误：未找到设计 {design_id}")
        return False
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(case, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 导出成功: {output_file}")
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='知识库查询和修改工具')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--kb-file', type=str, default=None,
                       help='知识库文件路径（覆盖配置文件）')
    parser.add_argument('--query', type=str, default=None,
                       help='查询指定设计ID（不指定则显示所有）')
    parser.add_argument('--details', action='store_true',
                       help='显示详细信息')
    parser.add_argument('--update', type=str, nargs=3, metavar=('DESIGN_ID', 'FIELD', 'VALUE'),
                       help='更新案例字段（例如：--update mgc_pci_bridge32_a quality_metrics.hpwl 12345.67）')
    parser.add_argument('--delete', type=str, metavar='DESIGN_ID',
                       help='删除指定设计案例')
    parser.add_argument('--export', type=str, nargs=2, metavar=('DESIGN_ID', 'OUTPUT_FILE'),
                       help='导出指定设计案例到文件')
    
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        kb_file = args.kb_file or config.get('knowledge_base', {}).get('case_file', 'data/knowledge_base/kb_cases.json')
    else:
        kb_file = args.kb_file or 'data/knowledge_base/kb_cases.json'
    
    # 执行操作
    if args.update:
        design_id, field, value = args.update
        # 尝试将值转换为数字
        try:
            if '.' in value:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            pass  # 保持字符串
        update_case(kb_file, design_id, field, value)
    elif args.delete:
        delete_case(kb_file, args.delete)
    elif args.export:
        design_id, output_file = args.export
        export_case(kb_file, design_id, output_file)
    else:
        query_kb(kb_file, args.query, args.details)


if __name__ == '__main__':
    main()

