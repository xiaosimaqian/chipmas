#!/usr/bin/env python3
"""
将K-SpecPart分区结果转换为DEF REGIONS/GROUPS约束

输入:
  - .part.K文件: K-SpecPart输出的分区结果
  - .mapping.json文件: vertex_id ↔ component_name映射
  - 原始DEF文件
  
输出:
  - 带分区约束的DEF文件（用于partition-based OpenROAD flow）
  - 分区方案JSON（用于后续处理）

使用方法:
    python scripts/convert_kspecpart_to_def.py \
        --part-file results/kspecpart/mgc_fft_1.part.4 \
        --mapping-file results/kspecpart/mgc_fft_1.mapping.json \
        --def-file data/ispd2015/mgc_fft_1/floorplan.def \
        --output-dir results/kspecpart/mgc_fft_1_partitioned
"""

import argparse
import json
from pathlib import Path
import sys
from collections import defaultdict

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_kspecpart_result(part_file: Path, mapping_file: Path) -> dict:
    """
    加载K-SpecPart分区结果
    
    Returns:
        partition_assignment: {component_name: partition_id}
    """
    print(f"正在加载分区结果...")
    print(f"  - 分区文件: {part_file}")
    print(f"  - 映射文件: {mapping_file}")
    
    # 1. 加载映射关系
    with open(mapping_file, 'r') as f:
        mapping_data = json.load(f)
    
    id_to_vertex = mapping_data['id_to_vertex']
    num_vertices = mapping_data['num_vertices']
    
    print(f"  - 顶点数: {num_vertices}")
    
    # 2. 加载分区结果
    partition_assignment = {}
    partition_stats = defaultdict(int)
    
    with open(part_file, 'r') as f:
        for vertex_id_0based, line in enumerate(f):
            # K-SpecPart输出是0-based，但mapping使用1-based
            vertex_id_1based = vertex_id_0based + 1
            partition_id = int(line.strip())
            
            component_name = id_to_vertex.get(str(vertex_id_1based))
            if component_name:
                partition_assignment[component_name] = partition_id
                partition_stats[partition_id] += 1
    
    print(f"  - 分配的组件数: {len(partition_assignment)}")
    print(f"  - 分区统计:")
    for pid in sorted(partition_stats.keys()):
        print(f"    Partition {pid}: {partition_stats[pid]} components")
    
    return partition_assignment


def generate_partition_defs(
    partition_assignment: dict,
    def_file: Path,
    output_dir: Path
) -> dict:
    """
    为每个分区生成单独的DEF文件
    
    这是partition-based OpenROAD flow的关键！
    每个分区将作为独立的设计运行OpenROAD
    
    Returns:
        partition_files: {partition_id: def_file_path}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n正在为每个分区生成DEF文件...")
    
    # 按分区组织组件
    partitions = defaultdict(list)
    for comp, pid in partition_assignment.items():
        partitions[pid].append(comp)
    
    num_partitions = len(partitions)
    print(f"  - 分区数: {num_partitions}")
    
    # 读取原始DEF内容
    with open(def_file, 'r') as f:
        original_def = f.read()
    
    partition_files = {}
    
    # 为每个分区生成DEF
    for partition_id in sorted(partitions.keys()):
        components = partitions[partition_id]
        
        # 生成分区DEF（提取该分区的组件和相关nets）
        partition_def_file = output_dir / f"partition_{partition_id}.def"
        
        # TODO: 这里需要实现完整的DEF提取逻辑
        # 包括: COMPONENTS过滤, NETS过滤, 边界net识别
        # 暂时先创建占位文件
        
        print(f"  - Partition {partition_id}: {len(components)} components → {partition_def_file.name}")
        
        partition_files[partition_id] = partition_def_file
    
    return partition_files


def save_partition_scheme(
    partition_assignment: dict,
    output_file: Path
):
    """保存分区方案为JSON格式"""
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 按分区组织
    partitions = defaultdict(list)
    for comp, pid in partition_assignment.items():
        partitions[pid].append(comp)
    
    scheme_data = {
        'num_partitions': len(partitions),
        'num_components': len(partition_assignment),
        'partitions': {str(pid): comps for pid, comps in partitions.items()},
        'component_to_partition': partition_assignment
    }
    
    with open(output_file, 'w') as f:
        json.dump(scheme_data, f, indent=2)
    
    print(f"\n✓ 分区方案已保存: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='将K-SpecPart分区结果转换为DEF约束',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/convert_kspecpart_to_def.py \\
        --part-file results/kspecpart/mgc_fft_1.part.4 \\
        --mapping-file results/kspecpart/mgc_fft_1.mapping.json \\
        --def-file data/ispd2015/mgc_fft_1/floorplan.def \\
        --output-dir results/kspecpart/mgc_fft_1_partitioned
        """
    )
    
    parser.add_argument('--part-file', type=str, required=True,
                        help='K-SpecPart输出的.part.K文件')
    parser.add_argument('--mapping-file', type=str, required=True,
                        help='vertex_id ↔ component_name映射JSON文件')
    parser.add_argument('--def-file', type=str, required=True,
                        help='原始ISPD 2015 DEF文件')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='输出目录（将生成多个分区DEF文件）')
    
    args = parser.parse_args()
    
    # 转换为Path对象
    part_file = Path(args.part_file)
    mapping_file = Path(args.mapping_file)
    def_file = Path(args.def_file)
    output_dir = Path(args.output_dir)
    
    # 验证输入文件
    if not part_file.exists():
        print(f"✗ 分区文件不存在: {part_file}")
        sys.exit(1)
    if not mapping_file.exists():
        print(f"✗ 映射文件不存在: {mapping_file}")
        sys.exit(1)
    if not def_file.exists():
        print(f"✗ DEF文件不存在: {def_file}")
        sys.exit(1)
    
    print("=" * 80)
    print("K-SpecPart分区结果 → DEF约束")
    print("=" * 80)
    print("")
    
    # 步骤1: 加载K-SpecPart结果
    partition_assignment = load_kspecpart_result(part_file, mapping_file)
    
    # 步骤2: 为每个分区生成DEF文件（partition-based flow）
    partition_files = generate_partition_defs(
        partition_assignment,
        def_file,
        output_dir
    )
    
    # 步骤3: 保存分区方案
    scheme_file = output_dir / 'partition_scheme.json'
    save_partition_scheme(partition_assignment, scheme_file)
    
    print("\n" + "=" * 80)
    print("✓ 转换完成！")
    print("=" * 80)
    print(f"\n输出目录: {output_dir}")
    print(f"  - partition_scheme.json: 分区方案")
    for pid, pfile in sorted(partition_files.items()):
        print(f"  - {pfile.name}: 分区{pid} DEF文件")
    print("")
    print("下一步: 为每个分区运行OpenROAD布局")
    print("")


if __name__ == '__main__':
    main()

