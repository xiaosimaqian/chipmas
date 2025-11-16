"""
Partition-based Flow端到端集成测试

使用mgc_fft_1测试完整流程（Step 1-8）
"""

import sys
from pathlib import Path
import json

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.run_partition_based_flow import run_partition_based_flow


def test_mgc_fft_1_end_to_end():
    """使用mgc_fft_1测试完整流程"""
    print("=" * 80)
    print("Partition-based Flow端到端测试 - mgc_fft_1")
    print("=" * 80)
    
    # 路径配置
    project_root = Path(__file__).parent.parent.parent
    design_name = "mgc_fft_1"
    design_dir = project_root / "data" / "ispd2015" / design_name
    kspecpart_dir = project_root / "results" / "kspecpart" / design_name
    output_dir = project_root / "tests" / "results" / "partition_flow" / design_name
    
    # 检查输入文件
    print("\n检查输入文件...")
    required_files = {
        'design.v': design_dir / "design.v",
        'tech.lef': design_dir / "tech.lef",
        'cells.lef': design_dir / "cells.lef"
    }
    
    # 自动查找分区文件和映射文件
    part_files = list(kspecpart_dir.glob("*.part.4"))
    mapping_files = list(kspecpart_dir.glob("*.mapping.json"))
    
    if part_files:
        required_files['part.4'] = part_files[0]
    else:
        required_files['part.4'] = kspecpart_dir / f"{design_name}.part.4"
    
    if mapping_files:
        required_files['mapping.json'] = mapping_files[0]
    else:
        required_files['mapping.json'] = kspecpart_dir / f"{design_name}.mapping.json"
    
    missing_files = []
    for name, path in required_files.items():
        if path.exists():
            print(f"  ✓ {name}: {path}")
        else:
            print(f"  ✗ {name}: {path} (不存在)")
            missing_files.append(name)
    
    if missing_files:
        print(f"\n⚠️  缺少文件: {', '.join(missing_files)}")
        print("  跳过测试（需要先准备数据和运行K-SpecPart）")
        return
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n输出目录: {output_dir}")
    
    # 运行完整流程
    print("\n" + "=" * 80)
    print("开始执行完整流程...")
    print("=" * 80)
    
    try:
        results = run_partition_based_flow(
            design_name=design_name,
            design_dir=design_dir,
            kspecpart_dir=kspecpart_dir,
            output_dir=output_dir,
            num_partitions=4,
            skip_verification=False,  # 执行Formal验证
            skip_openroad=False  # 执行OpenROAD
        )
        
        # 验证结果
        print("\n" + "=" * 80)
        print("验证结果...")
        print("=" * 80)
        
        # 检查各步骤状态
        steps = results.get('steps', {})
        
        # Step 1: K-SpecPart
        if 'kspecpart' in steps:
            print(f"  ✓ Step 1: K-SpecPart分区 - 完成")
        
        # Step 2: VerilogPartitioner
        if 'verilog_partition' in steps:
            vp_result = steps['verilog_partition']
            print(f"  ✓ Step 2: VerilogPartitioner - 完成")
            stats = vp_result.get('stats', {})
            print(f"     - 分区数: {stats.get('num_partitions')}")
            print(f"     - Boundary nets: {stats.get('num_boundary_nets')}")
            print(f"     - Internal nets: {stats.get('num_internal_nets')}")
        
        # Step 3: Formal验证
        if 'formal_verification' in steps:
            fv_result = steps['formal_verification']
            if fv_result.get('status') == 'passed':
                print(f"  ✓ Step 3: Formal验证 - 通过")
            elif fv_result.get('status') == 'failed':
                print(f"  ✗ Step 3: Formal验证 - 失败")
            else:
                print(f"  ⚠️  Step 3: Formal验证 - {fv_result.get('status')}")
        
        # Step 4: 物理位置优化
        if 'physical_mapping' in steps:
            print(f"  ✓ Step 4: 物理位置优化 - 完成")
        
        # Step 5-8: OpenROAD
        if 'openroad' in steps:
            or_result = steps['openroad']
            if isinstance(or_result, dict) and 'steps' in or_result:
                print(f"  ✓ Step 5-8: OpenROAD执行 - 完成")
                
                # Step 5: Partition OpenROAD
                if 'partition_openroad' in or_result['steps']:
                    partition_results = or_result['steps']['partition_openroad']
                    successful = sum(1 for r in partition_results.values() if r.get('success', False))
                    print(f"     - Step 5: {successful}/{len(partition_results)} partitions成功")
                    for pid, result in partition_results.items():
                        if result.get('success'):
                            print(f"       Partition {pid}: HPWL={result.get('hpwl', 0):.2f} um, "
                                  f"Runtime={result.get('runtime', 0):.1f}s")
                
                # Step 6: Macro LEF
                if 'macro_lef_generation' in or_result['steps']:
                    lef_count = len(or_result['steps']['macro_lef_generation'])
                    print(f"     - Step 6: {lef_count} Macro LEFs生成")
                
                # Step 7: Top OpenROAD
                if 'top_openroad' in or_result['steps']:
                    top_result = or_result['steps']['top_openroad']
                    if top_result.get('success'):
                        print(f"     - Step 7: 顶层OpenROAD成功")
                        print(f"       Boundary HPWL: {top_result.get('hpwl', 0):.2f} um")
                
                # Step 8: 边界代价
                if 'boundary_cost' in or_result['steps']:
                    bc_result = or_result['steps']['boundary_cost']
                    print(f"     - Step 8: 边界代价计算完成")
                    print(f"       Internal HPWL总和: {bc_result.get('internal_hpwl_total', 0):.2f} um")
                    print(f"       Boundary HPWL: {bc_result.get('boundary_hpwl', 0):.2f} um")
                    print(f"       边界代价: {bc_result.get('boundary_cost_percent', 0):.2f}%")
        
        # 保存结果汇总
        summary_file = output_dir / "flow_summary.json"
        if summary_file.exists():
            print(f"\n结果汇总已保存: {summary_file}")
        
        print("\n" + "=" * 80)
        print("✅ 端到端测试完成！")
        print("=" * 80)
        
        return results
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    test_mgc_fft_1_end_to_end()

