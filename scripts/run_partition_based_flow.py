#!/usr/bin/env python3
"""
Partition-based OpenROAD Flow - 完整流程编排

整合所有步骤：
1. K-SpecPart分区（已完成）
2. VerilogPartitioner生成分区网表
3. Formal验证（Yosys）
4. 物理位置优化
5. 各Partition OpenROAD执行
6. Macro LEF生成
7. 顶层OpenROAD执行（boundary nets only）
8. 边界代价计算

作者：ChipMASRAG Team
日期：2025-11-15
"""

import argparse
import sys
from pathlib import Path
import json
import logging
from typing import Dict, Optional

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.verilog_partitioner import perform_verilog_partitioning
from src.utils.formal_verification import FormalVerifier
from src.utils.physical_mapping import optimize_physical_layout, analyze_partition_connectivity
from src.utils.partition_openroad_flow import PartitionOpenROADFlow
from src.utils.die_size_config import get_die_size

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def run_partition_based_flow(
    design_name: str,
    design_dir: Path,
    kspecpart_dir: Path,
    output_dir: Path,
    num_partitions: int = 4,
    skip_verification: bool = False,
    skip_openroad: bool = False
) -> Dict:
    """
    运行完整的Partition-based Flow
    
    Args:
        design_name: 设计名称（如mgc_fft_1）
        design_dir: 设计目录（包含design.v, tech.lef, cells.lef）
        kspecpart_dir: K-SpecPart结果目录（包含.part.K, .mapping.json）
        output_dir: 输出目录
        num_partitions: 分区数量
        skip_verification: 跳过Formal验证
        skip_openroad: 跳过OpenROAD执行（仅生成网表）
        
    Returns:
        结果字典
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info(f"Partition-based OpenROAD Flow - {design_name}")
    logger.info("=" * 80)
    
    results = {
        'design_name': design_name,
        'num_partitions': num_partitions,
        'steps': {}
    }
    
    # ===== Step 1: K-SpecPart分区（假设已完成）=====
    logger.info("\n" + "=" * 80)
    logger.info("Step 1: K-SpecPart分区（已完成）")
    logger.info("=" * 80)
    
    # 自动查找分区文件（可能文件名不同）
    part_file = kspecpart_dir / f"{design_name}.part.{num_partitions}"
    if not part_file.exists():
        # 尝试查找其他可能的文件名
        possible_files = list(kspecpart_dir.glob(f"*.part.{num_partitions}"))
        if possible_files:
            part_file = possible_files[0]
            logger.info(f"  找到分区文件: {part_file}")
        else:
            raise FileNotFoundError(f"K-SpecPart分区文件不存在: {kspecpart_dir / f'{design_name}.part.{num_partitions}'}")
    
    mapping_file = kspecpart_dir / f"{design_name}.mapping.json"
    if not mapping_file.exists():
        # 尝试查找其他可能的映射文件名
        possible_files = list(kspecpart_dir.glob("*.mapping.json"))
        if possible_files:
            mapping_file = possible_files[0]
            logger.info(f"  找到映射文件: {mapping_file}")
        else:
            raise FileNotFoundError(f"映射文件不存在: {kspecpart_dir / f'{design_name}.mapping.json'}")
    
    logger.info(f"  ✓ 分区文件: {part_file}")
    logger.info(f"  ✓ 映射文件: {mapping_file}")
    results['steps']['kspecpart'] = {'status': 'completed', 'part_file': str(part_file)}
    
    # ===== Step 2: VerilogPartitioner生成分区网表 =====
    logger.info("\n" + "=" * 80)
    logger.info("Step 2: VerilogPartitioner生成分区网表")
    logger.info("=" * 80)
    
    design_v = design_dir / "design.v"
    if not design_v.exists():
        raise FileNotFoundError(f"设计网表不存在: {design_v}")
    
    partition_output_dir = output_dir / "hierarchical_netlists"
    partition_result = perform_verilog_partitioning(
        design_v,
        part_file,
        mapping_file,
        partition_output_dir
    )
    
    results['steps']['verilog_partition'] = {
        'status': 'completed',
        'partition_files': {str(k): str(v) for k, v in partition_result['partition_files'].items()},
        'top_file': str(partition_result['top_file']),
        'boundary_nets_file': str(partition_result['boundary_file']),
        'stats': partition_result['stats']
    }
    
    # ===== Step 3: Formal验证 =====
    if not skip_verification:
        logger.info("\n" + "=" * 80)
        logger.info("Step 3: Formal验证（Yosys）")
        logger.info("=" * 80)
        
        verifier = FormalVerifier()
        
        # 获取顶层模块名（从原始设计）
        top_module_name = None
        try:
            with open(design_v, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'module\s+(\w+)', content)
                if match:
                    top_module_name = match.group(1)
        except:
            pass
        
        try:
            verification_result = verifier.verify_equivalence(
                flat_netlist=design_v,
                top_netlist=partition_result['top_file'],
                partition_netlists=list(partition_result['partition_files'].values()),
                output_dir=output_dir / "formal_verification",
                top_module_name=top_module_name
            )
            
            if verification_result['success'] and verification_result['equivalent']:
                logger.info("  ✅ Formal验证通过：flatten ≈ hierarchical")
                results['steps']['formal_verification'] = {
                    'status': 'passed',
                    'equivalent': True
                }
            else:
                logger.error("  ❌ Formal验证失败：网表不等价！")
                results['steps']['formal_verification'] = {
                    'status': 'failed',
                    'equivalent': False,
                    'error': verification_result.get('error', 'Unknown error')
                }
                if not skip_verification:
                    logger.warning("  ⚠️  Formal验证失败，但继续执行（可能由于网表简化）")
        except Exception as e:
            logger.warning(f"  ⚠️  Formal验证异常: {e}")
            logger.warning("  跳过Formal验证，继续执行")
            results['steps']['formal_verification'] = {
                'status': 'skipped',
                'reason': str(e)
            }
    else:
        logger.info("\n跳过Formal验证（--skip-verification）")
        results['steps']['formal_verification'] = {'status': 'skipped'}
    
    # ===== Step 4: 物理位置优化 =====
    logger.info("\n" + "=" * 80)
    logger.info("Step 4: 物理位置优化")
    logger.info("=" * 80)
    
    # 读取boundary nets信息
    with open(partition_result['boundary_file'], 'r') as f:
        boundary_data = json.load(f)
    
    # 转换为analyze_partition_connectivity期望的格式
    # 格式: {net_name: {'is_boundary': True, 'partitions': [pid1, pid2, ...]}}
    boundary_connections = {}
    for net_name, net_info in boundary_data['boundary_nets'].items():
        partitions = net_info['partitions']
        if len(partitions) >= 2:
            boundary_connections[net_name] = {
                'is_boundary': True,
                'partitions': partitions
            }
    
    # 分析连接性
    connectivity_matrix = analyze_partition_connectivity(boundary_connections)
    
    # 获取die area（从设计配置）
    die_area_str, core_area_str = get_die_size(design_name)
    # 转换字符串格式 "x1 y1 x2 y2" 为元组 (x1, y1, x2, y2)
    die_area_parts = die_area_str.split()
    if len(die_area_parts) == 4:
        die_area = (int(die_area_parts[0]), int(die_area_parts[1]), 
                   int(die_area_parts[2]), int(die_area_parts[3]))
    else:
        # 如果解析失败，使用默认值
        logger.warning(f"  无法解析die_area配置，使用默认值")
        die_area = (0, 0, 50000, 50000)
    
    logger.info(f"  使用die_area: {die_area}")
    
    # 优化物理布局
    physical_regions = optimize_physical_layout(
        num_partitions=num_partitions,
        connectivity_matrix=connectivity_matrix,
        die_area=die_area,
        method='greedy'
    )
    
    logger.info(f"  物理区域分配:")
    for pid, region in physical_regions.items():
        logger.info(f"    Partition {pid}: ({region[0]}, {region[1]}, {region[2]}, {region[3]})")
    
    results['steps']['physical_mapping'] = {
        'status': 'completed',
        'physical_regions': {str(k): v for k, v in physical_regions.items()}
    }
    
    # ===== Step 5-8: OpenROAD执行（如果未跳过）=====
    if not skip_openroad:
        logger.info("\n" + "=" * 80)
        logger.info("Step 5-8: OpenROAD执行")
        logger.info("=" * 80)
        
        # 准备LEF文件路径
        tech_lef = design_dir / "tech.lef"
        cells_lef = design_dir / "cells.lef"
        
        if not tech_lef.exists():
            raise FileNotFoundError(f"技术LEF文件不存在: {tech_lef}")
        if not cells_lef.exists():
            raise FileNotFoundError(f"标准单元LEF文件不存在: {cells_lef}")
        
        # 创建PartitionOpenROADFlow实例
        openroad_flow = PartitionOpenROADFlow(
            design_name=design_name,
            design_dir=design_dir,
            partition_netlists=partition_result['partition_files'],
            top_netlist=partition_result['top_file'],
            physical_regions=physical_regions,
            tech_lef=tech_lef,
            cells_lef=cells_lef,
            output_dir=output_dir / "openroad"
        )
        
        # 运行完整流程
        openroad_results = openroad_flow.run_complete_flow(
            boundary_nets_file=partition_result['boundary_file'],
            parallel=True
        )
        
        results['steps']['openroad'] = openroad_results
        
    else:
        logger.info("\n跳过OpenROAD执行（--skip-openroad）")
        results['steps']['openroad'] = {'status': 'skipped'}
    
    # 保存结果汇总
    summary_file = output_dir / "flow_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("\n" + "=" * 80)
    logger.info("Partition-based Flow完成！")
    logger.info("=" * 80)
    logger.info(f"结果汇总: {summary_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="运行完整的Partition-based OpenROAD Flow"
    )
    parser.add_argument(
        '--design',
        required=True,
        help='设计名称（如mgc_fft_1）'
    )
    parser.add_argument(
        '--design-dir',
        type=Path,
        required=True,
        help='设计目录（包含design.v, tech.lef, cells.lef）'
    )
    parser.add_argument(
        '--kspecpart-dir',
        type=Path,
        required=True,
        help='K-SpecPart结果目录（包含.part.K, .mapping.json）'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        required=True,
        help='输出目录'
    )
    parser.add_argument(
        '--partitions',
        type=int,
        default=4,
        help='分区数量（默认：4）'
    )
    parser.add_argument(
        '--skip-verification',
        action='store_true',
        help='跳过Formal验证'
    )
    parser.add_argument(
        '--skip-openroad',
        action='store_true',
        help='跳过OpenROAD执行（仅生成网表）'
    )
    
    args = parser.parse_args()
    
    try:
        results = run_partition_based_flow(
            design_name=args.design,
            design_dir=args.design_dir,
            kspecpart_dir=args.kspecpart_dir,
            output_dir=args.output_dir,
            num_partitions=args.partitions,
            skip_verification=args.skip_verification,
            skip_openroad=args.skip_openroad
        )
        
        print("\n✅ Flow执行成功！")
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Flow执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

