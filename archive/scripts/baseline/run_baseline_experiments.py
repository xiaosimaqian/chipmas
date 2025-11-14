#!/usr/bin/env python3
"""
批量运行ISPD 2015设计的随机划分基线实验
生成论文实验所需的基线数据
"""

import sys
import os
from pathlib import Path
import json
import time
import random
import argparse
from typing import Dict, List, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.openroad_interface import OpenRoadInterface
from src.utils.def_parser import DEFParser
from src.utils.boundary_analyzer import BoundaryAnalyzer


def create_baseline_partition(components: List[str], nets: List[List[str]], 
                             num_partitions: int = 4, 
                             method: str = 'auto') -> Dict[str, List[str]]:
    """
    创建合理的基线划分方案
    
    使用考虑连接性的分区方法，而不是简单的随机打乱。
    参考: K-SpecPart (Bustany et al. ICCAD 2022)
    
    Args:
        components: 组件列表
        nets: 网线列表（每个网线是组件列表）
        num_partitions: 分区数量
        method: 分区方法 ['auto', 'hmetis', 'spectral', 'greedy', 'random']
    
    Returns:
        分区方案 {partition_id: [component_ids]}
    """
    if method == 'random':
        # 保留简单随机方法作为对比
        print(f"  - 使用随机分区（仅用于对比）...")
        sys.stdout.flush()
        shuffled = components.copy()
        random.shuffle(shuffled)
        
        partition_scheme = {}
        partition_size = len(shuffled) // num_partitions
        
        for i in range(num_partitions):
            partition_id = f"partition_{i}"
            start_idx = i * partition_size
            if i == num_partitions - 1:
                partition_scheme[partition_id] = shuffled[start_idx:]
            else:
                partition_scheme[partition_id] = shuffled[start_idx:start_idx + partition_size]
        
        return partition_scheme
    
    # 使用合理的分区方法
    try:
        from src.partitioners.baseline_partitioner import BaselinePartitioner
        
        partitioner = BaselinePartitioner(
            num_partitions=num_partitions,
            balance_constraint=0.05
        )
        
        hypergraph = {
            'components': components,
            'nets': nets
        }
        
        return partitioner.partition(hypergraph, method=method)
        
    except Exception as e:
        print(f"  警告: 基线分区器失败({e})，回退到贪心方法...")
        sys.stdout.flush()
        
        # 简单的贪心备选方案
        return create_simple_greedy_partition(components, nets, num_partitions)


def create_simple_greedy_partition(components: List[str], nets: List[List[str]], 
                                  num_partitions: int = 4) -> Dict[str, List[str]]:
    """简化的贪心分区（备选方案）"""
    print(f"  - 使用简化贪心分区...")
    sys.stdout.flush()
    
    # 构建邻接关系
    comp_neighbors = {}
    for comp in components:
        comp_neighbors[comp] = set()
    
    for net in nets:
        for comp1 in net:
            if comp1 in comp_neighbors:
                for comp2 in net:
                    if comp2 != comp1 and comp2 in comp_neighbors:
                        comp_neighbors[comp1].add(comp2)
    
    # 随机选择种子
    random.seed(42)
    seeds = random.sample(components, min(num_partitions, len(components)))
    
    partition_scheme = {f"partition_{i}": [seed] for i, seed in enumerate(seeds)}
    assigned = set(seeds)
    
    # 轮流扩展每个分区
    target_size = len(components) / num_partitions
    
    while len(assigned) < len(components):
        for i in range(num_partitions):
            if len(assigned) >= len(components):
                break
            
            part_key = f"partition_{i}"
            current_part = partition_scheme[part_key]
            
            # 找到与当前分区连接最多的未分配组件
            best_comp = None
            best_conn = -1
            
            for comp in components:
                if comp in assigned:
                    continue
                
                # 计算与当前分区的连接数
                conn_count = sum(1 for c in current_part if c in comp_neighbors[comp])
                
                if conn_count > best_conn:
                    best_conn = conn_count
                    best_comp = comp
            
            # 如果没有找到连接的组件，随机选择
            if best_comp is None:
                unassigned = [c for c in components if c not in assigned]
                if unassigned:
                    best_comp = random.choice(unassigned)
            
            if best_comp:
                partition_scheme[part_key].append(best_comp)
                assigned.add(best_comp)
    
    return partition_scheme


def run_baseline_for_design(design_dir: Path, output_dir: Path, seed: int = 42) -> Dict[str, Any]:
    """
    为单个设计运行基线实验
    
    Args:
        design_dir: 设计目录
        output_dir: 输出目录
        seed: 随机种子
    
    Returns:
        实验结果字典
    """
    design_name = design_dir.name
    print(f"\n{'='*80}")
    print(f"处理设计: {design_name}")
    print(f"{'='*80}")
    
    # 设置随机种子
    random.seed(seed)
    
    # 1. 解析DEF文件，获取所有组件和网线
    print(f"[步骤1/5] 开始解析DEF文件...")
    sys.stdout.flush()
    
    def_file = design_dir / "floorplan.def"
    if not def_file.exists():
        return {'status': 'error', 'error': f'DEF文件不存在: {def_file}'}
    
    parser = DEFParser(str(def_file))
    parser.parse()
    components = list(parser.components.keys())
    
    # 提取网线信息（用于分区）
    nets = []
    for net_name, net_info in parser.nets.items():
        # 提取网线连接的组件
        net_comps = []
        for conn in net_info.get('connections', []):
            comp = conn.get('comp')
            if comp and comp in components:
                net_comps.append(comp)
        if len(net_comps) >= 2:  # 只考虑连接2个及以上组件的网线
            nets.append(net_comps)
    
    print(f"✓ 找到 {len(components)} 个组件, {len(nets)} 个网线")
    sys.stdout.flush()
    
    # 2. 创建合理的基线划分方案
    print(f"[步骤2/5] 开始创建分区方案（组件数: {len(components)}）...")
    sys.stdout.flush()
    
    # 选择分区方法：auto（自动选择最佳方法）, greedy（快速贪心）, random（纯随机对比）
    partition_method = 'greedy'  # 使用贪心方法，速度快且考虑连接性
    partition_scheme = create_baseline_partition(
        components, nets, 
        num_partitions=4, 
        method=partition_method
    )
    
    print(f"✓ 创建分区方案完成（方法: {partition_method}）:")
    for pid, comps in partition_scheme.items():
        print(f"  {pid}: {len(comps)} 个组件")
    sys.stdout.flush()
    
    # 3. 转换为OpenROAD约束并生成布局
    # 不使用threads参数，让OpenROAD使用默认配置，避免内存不足
    openroad_interface = OpenRoadInterface(
        binary_path="openroad",
        timeout=None,  # 不设置超时，让OpenROAD自然完成
        use_api=True,
        threads=None  # 使用OpenROAD默认线程配置，降低内存使用
    )
    
    try:
        # 转换分区方案为DEF约束
        print(f"[步骤3/5] 开始转换分区方案为DEF约束...")
        sys.stdout.flush()
        
        def_with_partition = openroad_interface.convert_partition_to_def_constraints(
            partition_scheme=partition_scheme,
            design_dir=str(design_dir)
        )
        print(f"✓ 生成带分区约束的DEF文件: {def_with_partition}")
        sys.stdout.flush()
        
        # 生成布局
        print(f"[步骤4/5] 开始执行OpenROAD布局（这可能需要较长时间）...")
        sys.stdout.flush()
        
        layout_def, layout_info = openroad_interface.generate_layout_with_partition(
            partition_scheme=partition_scheme,
            design_dir=str(design_dir),
            output_dir=str(output_dir)
        )
        
        if layout_info['status'] != 'success':
            return {
                'status': 'error',
                'error': layout_info.get('error', 'Unknown error'),
                'layout_info': layout_info
            }
        
        print(f"✓ OpenROAD布局完成")
        print(f"✓ 运行时间: {layout_info['runtime']:.2f} 秒")
        
        # 4. 计算HPWL和边界代价
        print(f"[步骤5/5] 开始计算HPWL和边界代价...")
        sys.stdout.flush()
        
        if layout_def and Path(layout_def).exists():
            # 计算总HPWL
            print(f"  - 计算总HPWL...")
            sys.stdout.flush()
            total_hpwl = openroad_interface.calculate_hpwl(layout_def)
            
            # 计算边界代价
            print(f"  - 计算边界代价...")
            sys.stdout.flush()
            boundary_cost_info = openroad_interface.calculate_boundary_cost(
                layout_def, partition_scheme
            )
            
            # 计算各分区内部HPWL
            print(f"  - 计算各分区内部HPWL...")
            sys.stdout.flush()
            partition_hpwls = openroad_interface.calculate_partition_hpwl(
                layout_def, partition_scheme
            )
            
            # 提取跨分区连接
            print(f"  - 提取跨分区连接...")
            sys.stdout.flush()
            boundary_connections = openroad_interface.extract_boundary_connections(
                layout_def, partition_scheme
            )
            
            result = {
                'status': 'success',
                'design_name': design_name,
                'num_components': len(components),
                'partition_scheme': {k: len(v) for k, v in partition_scheme.items()},
                'total_hpwl': total_hpwl,
                'boundary_cost': boundary_cost_info['boundary_cost'],
                'boundary_hpwl': boundary_cost_info['boundary_hpwl'],
                'partition_hpwls': partition_hpwls,
                'num_boundary_connections': len(boundary_connections),
                'runtime': layout_info['runtime'],
                'layout_def': layout_def,
                'log_files': layout_info.get('log_files', {})
            }
            
            print(f"\n✓ 实验结果:")
            print(f"  总HPWL: {total_hpwl:.2f} um")
            print(f"  边界代价: {boundary_cost_info['boundary_cost']:.2f}%")
            print(f"  边界HPWL: {boundary_cost_info['boundary_hpwl']:.2f} um")
            print(f"  跨分区连接数: {len(boundary_connections)}")
            print(f"  各分区内部HPWL:")
            for pid, hpwl in partition_hpwls.items():
                print(f"    {pid}: {hpwl:.2f} um")
            
            return result
        else:
            return {
                'status': 'error',
                'error': 'Layout DEF file not generated',
                'layout_info': layout_info
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(description='批量运行ISPD 2015设计的随机划分基线实验')
    parser.add_argument(
        '--designs',
        type=str,
        nargs='+',
        default=None,
        help='指定设计名称列表（默认：所有ISPD 2015设计）'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/ispd2015',
        help='数据目录路径（默认: data/ispd2015）'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results/baseline',
        help='输出目录（默认: results/baseline）'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认: 42）'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='跳过已有结果的设计'
    )
    
    args = parser.parse_args()
    
    # 确定设计列表
    data_dir = project_root / args.data_dir
    if args.designs:
        design_dirs = [data_dir / d for d in args.designs]
    else:
        # 获取所有ISPD 2015设计
        design_dirs = [d for d in data_dir.iterdir() if d.is_dir() and (d / "floorplan.def").exists()]
        design_dirs.sort()
    
    print(f"找到 {len(design_dirs)} 个设计")
    
    # 创建输出目录
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 结果汇总
    all_results = []
    start_time = time.time()
    
    # 逐个处理设计
    for i, design_dir in enumerate(design_dirs, 1):
        design_name = design_dir.name
        design_output_dir = output_dir / design_name
        
        # 检查是否已存在结果
        if args.skip_existing:
            result_file = design_output_dir / "result.json"
            if result_file.exists():
                print(f"\n跳过 {design_name}（结果已存在）")
                continue
        
        print(f"\n[{i}/{len(design_dirs)}] 处理设计: {design_name}")
        
        # 运行基线实验
        result = run_baseline_for_design(
            design_dir=design_dir,
            output_dir=design_output_dir,
            seed=args.seed
        )
        
        # 保存结果
        design_output_dir.mkdir(parents=True, exist_ok=True)
        result_file = design_output_dir / "result.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        all_results.append(result)
        
        # 如果失败，记录但继续
        if result['status'] != 'success':
            print(f"✗ {design_name} 处理失败: {result.get('error', 'Unknown error')}")
    
    # 保存汇总结果
    summary = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_designs': len(design_dirs),
        'successful': sum(1 for r in all_results if r['status'] == 'success'),
        'failed': sum(1 for r in all_results if r['status'] == 'error'),
        'total_runtime': time.time() - start_time,
        'results': all_results
    }
    
    summary_file = output_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 打印汇总
    print(f"\n{'='*80}")
    print(f"实验汇总")
    print(f"{'='*80}")
    print(f"总设计数: {summary['total_designs']}")
    print(f"成功: {summary['successful']}")
    print(f"失败: {summary['failed']}")
    print(f"总运行时间: {summary['total_runtime']:.2f} 秒")
    print(f"\n结果已保存到: {summary_file}")
    
    # 打印成功设计的统计信息
    if summary['successful'] > 0:
        successful_results = [r for r in all_results if r['status'] == 'success']
        avg_hpwl = sum(r['total_hpwl'] for r in successful_results) / len(successful_results)
        avg_boundary_cost = sum(r['boundary_cost'] for r in successful_results) / len(successful_results)
        
        print(f"\n平均HPWL: {avg_hpwl:.2f} um")
        print(f"平均边界代价: {avg_boundary_cost:.2f}%")
    
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

