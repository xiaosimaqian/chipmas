"""
测试单个Partition的OpenROAD执行

用于快速验证OpenROAD集成是否正常工作
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.partition_openroad_flow import PartitionOpenROADFlow


def test_single_partition():
    """测试单个partition的OpenROAD执行"""
    print("=" * 80)
    print("测试单个Partition OpenROAD执行")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent.parent
    design_name = "mgc_fft_1"
    design_dir = project_root / "data" / "ispd2015" / design_name
    output_dir = project_root / "tests" / "results" / "openroad_test" / design_name
    
    # 使用已生成的分区网表
    hierarchical_dir = project_root / "tests" / "results" / "partition_flow" / design_name / "hierarchical_netlists"
    
    if not hierarchical_dir.exists():
        print(f"  ⚠️  分区网表目录不存在: {hierarchical_dir}")
        print("  请先运行: python3 scripts/run_partition_based_flow.py --skip-openroad")
        return
    
    partition_netlists = {
        0: hierarchical_dir / "partition_0.v"
    }
    
    top_netlist = hierarchical_dir / "top.v"
    boundary_nets_file = hierarchical_dir / "boundary_nets.json"
    
    # 检查文件
    for pid, netlist in partition_netlists.items():
        if not netlist.exists():
            print(f"  ✗ partition_{pid}.v 不存在")
            return
        print(f"  ✓ partition_{pid}.v: {netlist}")
    
    if not top_netlist.exists():
        print(f"  ✗ top.v 不存在")
        return
    print(f"  ✓ top.v: {top_netlist}")
    
    # 物理区域（简化测试，只测试partition 0）
    physical_regions = {
        0: (0, 0, 25000, 25000)  # (x, y, width, height)
    }
    
    # 创建flow实例
    flow = PartitionOpenROADFlow(
        design_name=design_name,
        design_dir=design_dir,
        partition_netlists=partition_netlists,
        top_netlist=top_netlist,
        physical_regions=physical_regions,
        tech_lef=design_dir / "tech.lef",
        cells_lef=design_dir / "cells.lef",
        output_dir=output_dir
    )
    
    # 运行单个partition的OpenROAD
    print("\n运行Partition 0的OpenROAD...")
    result = flow.run_partition_openroad(
        partition_id=0,
        netlist_path=partition_netlists[0],
        physical_region=physical_regions[0]
    )
    
    if result.get('success'):
        print(f"\n✅ Partition 0 OpenROAD执行成功！")
        print(f"  HPWL: {result.get('hpwl', 0):.2f} um")
        print(f"  运行时间: {result.get('runtime', 0):.1f}s")
        print(f"  DEF文件: {result.get('def_file')}")
    else:
        print(f"\n❌ Partition 0 OpenROAD执行失败")
        print(f"  错误: {result.get('error', 'Unknown')}")
        print(f"  日志: {result.get('log_file')}")


if __name__ == '__main__':
    test_single_partition()

