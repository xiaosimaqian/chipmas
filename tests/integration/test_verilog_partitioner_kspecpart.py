"""
VerilogPartitioner集成测试 - 使用真实K-SpecPart结果

测试使用mgc_fft_1的K-SpecPart分区结果
"""

import sys
from pathlib import Path
import json

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.verilog_partitioner import VerilogPartitioner, perform_verilog_partitioning


def test_kspecpart_integration():
    """使用真实K-SpecPart结果测试"""
    print("=" * 60)
    print("VerilogPartitioner集成测试 - K-SpecPart结果")
    print("=" * 60)
    
    # 路径配置
    project_root = Path(__file__).parent.parent.parent
    design_v = project_root / "data" / "ispd2015" / "mgc_fft_1" / "design.v"
    part_file = project_root / "results" / "kspecpart" / "mgc_fft_1" / "mgc_fft_1.part.4"
    mapping_file = project_root / "results" / "kspecpart" / "mgc_fft_1" / "mgc_fft_1.mapping.json"
    output_dir = project_root / "tests" / "results" / "verilog_partitioner" / "mgc_fft_1"
    
    # 检查输入文件
    print("\n检查输入文件...")
    if not design_v.exists():
        print(f"  ⚠️  设计文件不存在: {design_v}")
        print("  跳过测试（需要先准备ISPD 2015数据）")
        return
    
    if not part_file.exists():
        print(f"  ⚠️  分区文件不存在: {part_file}")
        print("  跳过测试（需要先运行K-SpecPart）")
        return
    
    if not mapping_file.exists():
        print(f"  ⚠️  映射文件不存在: {mapping_file}")
        print("  跳过测试（需要先运行K-SpecPart）")
        return
    
    print(f"  ✓ 设计文件: {design_v}")
    print(f"  ✓ 分区文件: {part_file}")
    print(f"  ✓ 映射文件: {mapping_file}")
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 执行分区
    print("\n执行Verilog分区...")
    try:
        result = perform_verilog_partitioning(
            design_v,
            part_file,
            mapping_file,
            output_dir
        )
        
        # 验证结果
        print("\n验证结果...")
        
        # 1. 检查文件生成
        assert result['top_file'].exists(), "top.v未生成"
        assert result['boundary_file'].exists(), "boundary_nets.json未生成"
        
        print(f"  ✓ top.v: {result['top_file']}")
        print(f"  ✓ boundary_nets.json: {result['boundary_file']}")
        
        for pid, pfile in result['partition_files'].items():
            assert pfile.exists(), f"partition_{pid}.v未生成"
            print(f"  ✓ partition_{pid}.v: {pfile}")
        
        # 2. 检查统计信息
        stats = result['stats']
        print(f"\n统计信息:")
        print(f"  分区数: {stats['num_partitions']}")
        print(f"  总instances: {stats['num_instances']}")
        print(f"  总nets: {stats['num_nets']}")
        print(f"  Boundary nets: {stats['num_boundary_nets']}")
        print(f"  Internal nets: {stats['num_internal_nets']}")
        print(f"  Cutsize占比: {stats['num_boundary_nets']/stats['num_nets']*100:.2f}%")
        
        print(f"\n分区大小:")
        for pid, size in stats['partition_sizes'].items():
            pct = size / stats['num_instances'] * 100
            print(f"  Partition {pid}: {size} instances ({pct:.1f}%)")
        
        # 3. 检查boundary nets
        boundary_nets = result['boundary_nets']
        print(f"\nBoundary nets分析:")
        print(f"  总数: {len(boundary_nets)}")
        
        # 统计跨分区连接
        partition_pairs = {}
        for net_name, info in boundary_nets.items():
            partitions = tuple(sorted(info['partitions']))
            if partitions not in partition_pairs:
                partition_pairs[partitions] = []
            partition_pairs[partitions].append(net_name)
        
        print(f"  跨分区连接分布:")
        for pair, nets in sorted(partition_pairs.items()):
            print(f"    Partition {pair[0]} ↔ {pair[1]}: {len(nets)} nets")
        
        # 4. 检查生成的文件大小
        print(f"\n生成文件大小:")
        for pid, pfile in result['partition_files'].items():
            size_kb = pfile.stat().st_size / 1024
            print(f"  partition_{pid}.v: {size_kb:.1f} KB")
        
        top_size_kb = result['top_file'].stat().st_size / 1024
        print(f"  top.v: {top_size_kb:.1f} KB")
        
        # 5. 检查文件内容（前几行）
        print(f"\n检查partition_0.v内容（前10行）:")
        with open(result['partition_files'][0], 'r') as f:
            lines = f.readlines()[:10]
            for i, line in enumerate(lines, 1):
                print(f"  {i:2d}: {line.rstrip()}")
        
        print(f"\n检查top.v内容（前10行）:")
        with open(result['top_file'], 'r') as f:
            lines = f.readlines()[:10]
            for i, line in enumerate(lines, 1):
                print(f"  {i:2d}: {line.rstrip()}")
        
        # 6. 验证boundary nets数量与K-SpecPart的cutsize一致
        print(f"\n验证Cutsize一致性:")
        # 读取K-SpecPart统计信息（如果有）
        stats_file = project_root / "results" / "kspecpart" / "mgc_fft_1" / "mgc_fft_1_stats.json"
        if stats_file.exists():
            with open(stats_file, 'r') as f:
                kspecpart_stats = json.load(f)
                kspecpart_cutsize = kspecpart_stats.get('cutsize', 0)
                print(f"  K-SpecPart Cutsize: {kspecpart_cutsize}")
                print(f"  VerilogPartitioner Boundary nets: {len(boundary_nets)}")
                if kspecpart_cutsize > 0:
                    diff = abs(len(boundary_nets) - kspecpart_cutsize)
                    diff_pct = diff / kspecpart_cutsize * 100
                    print(f"  差异: {diff} ({diff_pct:.1f}%)")
                    if diff_pct < 10:
                        print(f"  ✓ Cutsize基本一致（差异<10%）")
                    else:
                        print(f"  ⚠️  Cutsize差异较大，需要检查")
        
        print("\n" + "=" * 60)
        print("✓ VerilogPartitioner集成测试通过！")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    test_kspecpart_integration()

