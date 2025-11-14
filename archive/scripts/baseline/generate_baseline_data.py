#!/usr/bin/env python3
"""
批量生成ISPD 2015设计的随机划分基线数据
用于论文实验的基线对比
"""

import sys
import os
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.openroad_interface import OpenRoadInterface
from src.utils.def_parser import DEFParser
from src.utils.boundary_analyzer import BoundaryAnalyzer


def create_random_partition(components: List[str], num_partitions: int = 4) -> Dict[str, List[str]]:
    """
    创建随机划分方案
    
    Args:
        components: 组件列表
        num_partitions: 分区数量
    
    Returns:
        分区方案 {partition_id: [component_ids]}
    """
    # 随机打乱组件列表
    shuffled = components.copy()
    random.shuffle(shuffled)
    
    # 均匀分配到各分区
    partition_scheme = {}
    partition_size = len(shuffled) // num_partitions
    
    for i in range(num_partitions):
        partition_id = f"partition_{i}"
        start_idx = i * partition_size
        if i == num_partitions - 1:
            # 最后一个分区包含所有剩余组件
            partition_scheme[partition_id] = shuffled[start_idx:]
        else:
            partition_scheme[partition_id] = shuffled[start_idx:start_idx + partition_size]
    
    return partition_scheme


def process_design(design_dir: Path, output_dir: Path, num_partitions: int = 4) -> Dict[str, Any]:
    """
    处理单个设计：生成随机划分，运行OpenROAD，收集基线数据
    
    Args:
        design_dir: 设计目录
        output_dir: 输出目录
        num_partitions: 分区数量
    
    Returns:
        结果字典
    """
    design_name = design_dir.name
    print(f"\n{'='*80}")
    print(f"处理设计: {design_name}")
    print(f"{'='*80}")
    
    result = {
        'design_name': design_name,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'partition_scheme': None,
        'hpwl': None,
        'boundary_cost': None,
        'runtime': None,
        'error': None
    }
    
    try:
        # 1. 解析DEF文件，获取所有组件
        def_file = design_dir / "floorplan.def"
        if not def_file.exists():
            raise FileNotFoundError(f"DEF文件不存在: {def_file}")
        
        parser = DEFParser(str(def_file))
        parser.parse()
        components = list(parser.components.keys())
        
        print(f"✓ 找到 {len(components)} 个组件")
        
        # 2. 创建随机划分方案
        partition_scheme = create_random_partition(components, num_partitions)
        result['partition_scheme'] = partition_scheme
        
        print(f"✓ 创建随机划分方案:")
        for pid, comps in partition_scheme.items():
            print(f"  {pid}: {len(comps)} 个组件")
        
        # 3. 转换为DEF约束并生成布局
        openroad_interface = OpenRoadInterface(threads="max")
        
        start_time = time.time()
        layout_def, layout_info = openroad_interface.generate_layout_with_partition(
            partition_scheme=partition_scheme,
            design_dir=str(design_dir),
            output_dir=str(output_dir)
        )
        runtime = time.time() - start_time
        result['runtime'] = runtime
        
        if layout_info['status'] != 'success':
            result['status'] = 'error'
            result['error'] = layout_info.get('error', 'Unknown error')
            print(f"✗ OpenROAD执行失败: {result['error']}")
            return result
        
        print(f"✓ OpenROAD执行成功 (运行时间: {runtime:.2f} 秒)")
        
        # 4. 计算HPWL和边界代价
        if layout_def and Path(layout_def).exists():
            # 计算总HPWL
            hpwl = openroad_interface.calculate_hpwl(layout_def)
            result['hpwl'] = hpwl
            print(f"✓ 总HPWL: {hpwl:.2f} um")
            
            # 计算边界代价
            boundary_cost_info = openroad_interface.calculate_boundary_cost(
                layout_def, partition_scheme
            )
            result['boundary_cost'] = boundary_cost_info['boundary_cost']
            result['total_hpwl'] = boundary_cost_info['total_hpwl']
            result['boundary_hpwl'] = boundary_cost_info['boundary_hpwl']
            result['partition_hpwls'] = boundary_cost_info['partition_hpwls']
            
            print(f"✓ 边界代价: {result['boundary_cost']:.2f}%")
            print(f"✓ 边界HPWL: {result['boundary_hpwl']:.2f} um")
            print(f"✓ 各分区内部HPWL:")
            for pid, ph in result['partition_hpwls'].items():
                print(f"  {pid}: {ph:.2f} um")
        
        result['status'] = 'success'
        print(f"✓ 设计 {design_name} 处理完成")
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def main():
    """主函数：批量处理所有ISPD 2015设计"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量生成ISPD 2015设计的随机划分基线数据')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/ispd2015',
        help='ISPD 2015数据目录（默认: data/ispd2015）'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results/baseline_random',
        help='输出目录（默认: results/baseline_random）'
    )
    parser.add_argument(
        '--num-partitions',
        type=int,
        default=4,
        help='分区数量（默认: 4）'
    )
    parser.add_argument(
        '--designs',
        type=str,
        nargs='+',
        default=None,
        help='指定设计列表（默认: 处理所有设计）'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认: 42）'
    )
    
    args = parser.parse_args()
    
    # 设置随机种子
    random.seed(args.seed)
    
    # 确定数据目录
    data_dir = project_root / args.data_dir
    if not data_dir.exists():
        print(f"✗ 错误: 数据目录不存在: {data_dir}")
        return 1
    
    # 创建输出目录
    output_base = project_root / args.output_dir
    output_base.mkdir(parents=True, exist_ok=True)
    
    # 获取所有设计
    if args.designs:
        design_dirs = [data_dir / d for d in args.designs]
    else:
        # 自动查找所有设计目录
        design_dirs = [d for d in data_dir.iterdir() if d.is_dir() and (d / "floorplan.def").exists()]
        design_dirs.sort()
    
    print(f"\n找到 {len(design_dirs)} 个设计")
    print(f"输出目录: {output_base}")
    print(f"分区数量: {args.num_partitions}")
    print(f"随机种子: {args.seed}")
    
    # 批量处理
    all_results = []
    start_time = time.time()
    
    for i, design_dir in enumerate(design_dirs, 1):
        design_name = design_dir.name
        design_output = output_base / design_name
        design_output.mkdir(parents=True, exist_ok=True)
        
        print(f"\n[{i}/{len(design_dirs)}] 处理设计: {design_name}")
        
        result = process_design(design_dir, design_output, args.num_partitions)
        all_results.append(result)
        
        # 保存单个设计的结果
        result_file = design_output / f"baseline_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # 如果失败，继续处理下一个
        if result['status'] != 'success':
            print(f"⚠ 设计 {design_name} 处理失败，继续处理下一个...")
    
    # 保存汇总结果
    total_time = time.time() - start_time
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_designs': len(design_dirs),
        'successful': sum(1 for r in all_results if r['status'] == 'success'),
        'failed': sum(1 for r in all_results if r['status'] == 'error'),
        'total_time': total_time,
        'results': all_results
    }
    
    summary_file = output_base / f"baseline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 打印汇总
    print(f"\n{'='*80}")
    print("处理完成汇总")
    print(f"{'='*80}")
    print(f"总设计数: {len(design_dirs)}")
    print(f"成功: {summary['successful']}")
    print(f"失败: {summary['failed']}")
    print(f"总耗时: {total_time:.2f} 秒 ({total_time/3600:.2f} 小时)")
    print(f"\n汇总结果已保存到: {summary_file}")
    
    # 打印成功设计的结果摘要
    if summary['successful'] > 0:
        print(f"\n成功设计的结果摘要:")
        print(f"{'设计名':<30} {'HPWL (um)':<15} {'边界代价 (%)':<15} {'运行时间 (s)':<15}")
        print("-" * 80)
        for r in all_results:
            if r['status'] == 'success':
                hpwl = r.get('hpwl', 0)
                bc = r.get('boundary_cost', 0)
                rt = r.get('runtime', 0)
                print(f"{r['design_name']:<30} {hpwl:<15.2f} {bc:<15.2f} {rt:<15.2f}")
    
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

