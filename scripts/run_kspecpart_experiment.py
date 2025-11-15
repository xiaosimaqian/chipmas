#!/usr/bin/env python3
"""
K-SpecPart完整实验脚本
1. 转换DEF到HGR
2. 运行K-SpecPart分区
3. 转换分区结果为DEF约束
4. 执行OpenROAD布局
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_kspecpart_for_design(design_name: str, 
                              num_partitions: int = 4,
                              balance_constraint: float = 0.05):
    """
    为指定设计运行完整的K-SpecPart实验
    
    Args:
        design_name: 设计名称（如 'mgc_fft_1'）
        num_partitions: 分区数量
        balance_constraint: 平衡约束（0.05 = 5%不平衡）
    """
    print("=" * 80)
    print(f"K-SpecPart实验: {design_name}")
    print("=" * 80)
    
    # 路径设置
    design_dir = project_root / 'data' / 'ispd2015' / design_name
    def_file = design_dir / 'floorplan.def'
    
    results_dir = project_root / 'results' / 'kspecpart' / design_name
    results_dir.mkdir(parents=True, exist_ok=True)
    
    hgr_file = results_dir / f'{design_name}.hgr'
    mapping_file = results_dir / f'{design_name}.mapping.json'
    part_file = results_dir / f'{design_name}.part.{num_partitions}'
    
    kspecpart_dir = project_root / 'external' / 'HypergraphPartitioning' / 'K_SpecPart'
    
    # 步骤1: 转换DEF到HGR
    print(f"\n[步骤1] 转换DEF到HGR格式...")
    convert_cmd = [
        'python3', str(project_root / 'scripts' / 'convert_ispd2015_to_hgr.py'),
        '--def-file', str(def_file),
        '--output', str(hgr_file),
        '--mapping', str(mapping_file)
    ]
    
    result = subprocess.run(convert_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ DEF转换失败:")
        print(result.stderr)
        return None
    
    print(f"✓ HGR文件: {hgr_file}")
    print(f"✓ 映射文件: {mapping_file}")
    
    # 步骤2: 运行K-SpecPart
    print(f"\n[步骤2] 运行K-SpecPart分区 (K={num_partitions}, ε={balance_constraint})...")
    
    # K-SpecPart命令
    # imb参数：balance_constraint * 100 (例如: 0.05 -> 5% imbalance)
    imb_percent = int(balance_constraint * 100)
    
    # 尝试多个可能的Julia路径
    julia_paths = [
        str(Path.home() / '.juliaup' / 'bin' / 'julia'),  # juliaup安装
        '/usr/local/bin/julia',
        '/usr/bin/julia',
        'julia'
    ]
    julia_bin = None
    for path in julia_paths:
        try:
            result_test = subprocess.run([path, '--version'], capture_output=True, timeout=5)
            if result_test.returncode == 0:
                julia_bin = path
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    if not julia_bin:
        print("❌ Julia未找到，请检查Julia安装")
        return None
    
    kspecpart_cmd = [
        julia_bin, '--project',
        '-e', 
        f'include("specpart.jl"); '
        f'import .SpecPart; '
        f'partition = SpecPart.specpart_run("{hgr_file.absolute()}", '
        f'imb={imb_percent}, num_parts={num_partitions}); '
        f'open("{part_file.absolute()}", "w") do f; '
        f'for p in partition; println(f, p); end; '
        f'end'
    ]
    
    start_time = datetime.now()
    result = subprocess.run(
        kspecpart_cmd,
        cwd=str(kspecpart_dir),
        capture_output=True,
        text=True,
        timeout=3600  # 1小时超时
    )
    runtime = (datetime.now() - start_time).total_seconds()
    
    if result.returncode != 0:
        print(f"❌ K-SpecPart执行失败:")
        print(result.stderr)
        return None
    
    print(f"✓ 分区完成，耗时: {runtime:.2f}s")
    print(f"✓ 分区文件: {part_file}")
    
    # 保存日志
    log_file = results_dir / f'{design_name}_kspecpart.log'
    with open(log_file, 'w') as f:
        f.write(f"=== K-SpecPart Log ===\n")
        f.write(f"Design: {design_name}\n")
        f.write(f"Partitions: {num_partitions}\n")
        f.write(f"Balance: {balance_constraint}\n")
        f.write(f"Runtime: {runtime:.2f}s\n\n")
        f.write(result.stdout)
    
    # 步骤3: 解析分区结果
    print(f"\n[步骤3] 解析分区结果...")
    partitions = parse_partition_file(part_file, mapping_file)
    
    print(f"  分区统计:")
    for pid, components in partitions.items():
        print(f"    Partition {pid}: {len(components)} 组件")
    
    # 保存统计信息
    stats = {
        'design': design_name,
        'num_partitions': num_partitions,
        'balance_constraint': balance_constraint,
        'runtime': runtime,
        'partition_sizes': {pid: len(comps) for pid, comps in partitions.items()},
        'hgr_file': str(hgr_file),
        'part_file': str(part_file),
        'timestamp': datetime.now().isoformat()
    }
    
    stats_file = results_dir / f'{design_name}_stats.json'
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n✓ 实验完成！")
    print(f"  结果目录: {results_dir}")
    
    return stats


def parse_partition_file(part_file: Path, mapping_file: Path) -> dict:
    """解析K-SpecPart分区结果"""
    # 读取映射关系
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
    
    # mapping格式: {"vertex_to_id": {"comp_name": vertex_id, ...}, ...}
    # 反转映射: vertex_id -> comp_name
    id_to_comp = {v: k for k, v in mapping['vertex_to_id'].items()}
    
    # 读取分区结果 (vertex_id从1开始，enumerate从0开始，所以+1)
    partitions = {}
    with open(part_file, 'r') as f:
        for idx, line in enumerate(f):
            partition_id = int(line.strip())
            vertex_id = idx + 1  # 分区文件中第idx行对应vertex_id = idx+1
            
            if partition_id not in partitions:
                partitions[partition_id] = []
            
            comp_name = id_to_comp.get(vertex_id)
            if comp_name:
                partitions[partition_id].append(comp_name)
    
    return partitions


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='K-SpecPart完整实验')
    parser.add_argument('--design', required=True, help='设计名称')
    parser.add_argument('--partitions', type=int, default=4, help='分区数量')
    parser.add_argument('--balance', type=float, default=0.05, help='平衡约束')
    
    args = parser.parse_args()
    
    stats = run_kspecpart_for_design(
        args.design,
        args.partitions,
        args.balance
    )
    
    if stats:
        print(f"\n{'=' * 80}")
        print("实验统计:")
        print(json.dumps(stats, indent=2))
        print(f"{'=' * 80}")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
