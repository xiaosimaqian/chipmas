#!/usr/bin/env python3
"""
OpenROAD接口独立测试脚本

测试openroad_interface.py的核心功能：
1. 分区方案转换为DEF约束
2. TCL脚本生成
3. HPWL提取（如果OpenROAD可用）
4. 边界代价计算

使用方法：
    python scripts/test_openroad_interface.py --design mgc_pci_bridge32_a
    python scripts/test_openroad_interface.py --design mgc_pci_bridge32_a --run-openroad
"""

import sys
import argparse
import json
import subprocess
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.openroad_interface import OpenRoadInterface
from src.utils.def_parser import DEFParser


def create_test_partition_scheme(design_dir: Path) -> dict:
    """
    创建测试用的分区方案
    
    从DEF文件中提取组件，然后随机分配到4个分区
    """
    def_file = design_dir / "floorplan.def"
    if not def_file.exists():
        raise FileNotFoundError(f"DEF文件不存在: {def_file}")
    
    # 解析DEF文件获取所有组件
    parser = DEFParser(str(def_file))
    parser.parse()
    
    # 获取所有组件名
    all_components = list(parser.components.keys())
    
    if len(all_components) == 0:
        raise ValueError(f"DEF文件中没有找到组件: {def_file}")
    
    # 将组件分配到4个分区（简单均匀分配）
    num_partitions = 4
    partition_scheme = {}
    components_per_partition = len(all_components) // num_partitions
    
    for i in range(num_partitions):
        start_idx = i * components_per_partition
        if i == num_partitions - 1:
            # 最后一个分区包含剩余所有组件
            partition_components = all_components[start_idx:]
        else:
            partition_components = all_components[start_idx:start_idx + components_per_partition]
        
        # 使用组件名的前缀作为"模块名"（简化处理）
        # 实际应该从Verilog网表中提取模块到组件的映射
        module_ids = []
        for comp_name in partition_components:
            # 提取组件名的前缀作为模块名（例如：inst_A_1 -> module_A）
            # 这里简化处理，使用组件名的前几个字符
            if '_' in comp_name:
                module_name = comp_name.split('_')[0] + '_' + comp_name.split('_')[1] if len(comp_name.split('_')) > 1 else comp_name.split('_')[0]
            else:
                module_name = comp_name[:8]  # 取前8个字符
            if module_name not in module_ids:
                module_ids.append(module_name)
        
        partition_scheme[f"partition_{i}"] = module_ids
    
    return partition_scheme, all_components


def test_convert_partition_to_def_constraints(design_dir: Path, partition_scheme: dict):
    """测试分区方案转换为DEF约束"""
    print("\n" + "="*80)
    print("测试1: 分区方案转换为DEF约束")
    print("="*80)
    
    openroad_interface = OpenRoadInterface()
    
    # 转换分区方案为DEF约束
    output_def = openroad_interface.convert_partition_to_def_constraints(
        partition_scheme=partition_scheme,
        design_dir=str(design_dir)
    )
    
    print(f"✓ 成功生成DEF文件: {output_def}")
    
    # 验证生成的DEF文件
    if not Path(output_def).exists():
        print(f"✗ 错误: 生成的DEF文件不存在: {output_def}")
        return False
    
    # 检查DEF文件是否包含REGIONS部分
    with open(output_def, 'r') as f:
        content = f.read()
    
    if 'REGIONS' not in content:
        print("✗ 错误: 生成的DEF文件不包含REGIONS部分")
        return False
    
    if 'END REGIONS' not in content:
        print("✗ 错误: 生成的DEF文件REGIONS部分不完整")
        return False
    
    # 检查每个分区是否都有REGION定义
    # 注意：实际生成的REGION名称格式是 er0, er1, er2 等（不是 REGION_partition_0）
    for partition_id in partition_scheme.keys():
        # 从partition_id中提取数字索引（例如 "partition_0" -> 0）
        import re
        match = re.search(r'(\d+)$', str(partition_id))
        if match:
            partition_index = int(match.group(1))
            region_name = f"er{partition_index}"  # 实际格式：er0, er1, er2等
        else:
            # 如果无法提取数字，尝试使用partition_id的索引
            sorted_ids = sorted(partition_scheme.keys())
            partition_index = sorted_ids.index(partition_id)
            region_name = f"er{partition_index}"
        
        # 检查REGIONS部分和GROUPS部分
        if region_name in content:
            print(f"✓ REGION {region_name} 已定义")
        else:
            print(f"✗ 警告: REGION {region_name} 未在DEF文件中找到")
    
    # 检查COMPONENTS部分是否包含REGION属性
    if '+ REGION' not in content:
        print("✗ 警告: COMPONENTS部分未包含REGION属性")
    else:
        region_count = content.count('+ REGION')
        print(f"✓ 找到 {region_count} 个组件的REGION属性")
    
    print("✓ 测试1通过: 分区方案成功转换为DEF约束")
    return True, output_def


def test_generate_tcl_script(design_dir: Path, def_with_partition: str):
    """测试TCL脚本生成"""
    print("\n" + "="*80)
    print("测试2: 生成OpenROAD TCL脚本")
    print("="*80)
    
    openroad_interface = OpenRoadInterface()
    
    # 生成TCL脚本
    tcl_script = openroad_interface._generate_tcl_script(
        design_path=design_dir,
        def_file=def_with_partition,
        output_def=str(design_dir / "test_output" / "layout.def")
    )
    
    print(f"✓ 成功生成TCL脚本: {tcl_script}")
    
    # 验证TCL脚本
    if not Path(tcl_script).exists():
        print(f"✗ 错误: TCL脚本不存在: {tcl_script}")
        return False
    
    with open(tcl_script, 'r') as f:
        tcl_content = f.read()
    
    # 检查关键命令
    # 注意：根据参考案例，不需要read_verilog命令
    required_commands = [
        'read_lef',
        'read_def',
        'global_placement',
        'detailed_placement',
        'write_def'
    ]
    
    # 可选命令（参考案例中有）
    optional_commands = [
        'set_placement_padding'
    ]
    
    all_passed = True
    for cmd in required_commands:
        if cmd not in tcl_content:
            print(f"✗ 错误: TCL脚本缺少命令: {cmd}")
            all_passed = False
        else:
            print(f"✓ TCL脚本包含命令: {cmd}")
    
    # 检查可选命令
    for cmd in optional_commands:
        if cmd in tcl_content:
            print(f"✓ TCL脚本包含可选命令: {cmd}")
    
    if not all_passed:
        return False, None
    
    print("✓ 测试2通过: TCL脚本生成成功")
    return True, tcl_script


def test_hpwl_extraction(design_dir: Path):
    """测试HPWL提取（从DEF文件）"""
    print("\n" + "="*80)
    print("测试3: HPWL提取（从DEF文件）")
    print("="*80)
    
    openroad_interface = OpenRoadInterface()
    def_file = design_dir / "floorplan.def"
    
    if not def_file.exists():
        print(f"✗ 错误: DEF文件不存在: {def_file}")
        return False
    
    # 从DEF文件计算HPWL
    try:
        hpwl = openroad_interface.calculate_hpwl(str(def_file))
        print(f"✓ 成功计算HPWL: {hpwl:.2f} um")
        
        # 说明HPWL类型
        # floorplan.def是初始floorplan文件，组件都是UNPLACED状态
        # 如果组件有初始位置，则计算的是基于初始位置的HPWL
        # 如果组件是UNPLACED（位置为0,0），则HPWL可能不准确
        print("  注意: floorplan.def是初始文件，组件未经过placement")
        print("        此HPWL是基于初始位置的HPWL（如果组件有位置）")
        print("        或基于未放置组件的HPWL（如果组件是UNPLACED）")
        print("        这不是original HPWL或legalized HPWL")
        print("        original HPWL = global placement后的HPWL")
        print("        legalized HPWL = detailed placement后的最终HPWL")
        
        if hpwl <= 0:
            print("⚠ 警告: HPWL值为0或负数，可能DEF文件中没有有效的net连接")
        else:
            print("✓ 测试3通过: HPWL提取成功")
            return True
    except Exception as e:
        print(f"✗ 错误: HPWL计算失败: {e}")
        return False


def test_boundary_cost_calculation(design_dir: Path, partition_scheme: dict):
    """测试边界代价计算"""
    print("\n" + "="*80)
    print("测试4: 边界代价计算")
    print("="*80)
    
    openroad_interface = OpenRoadInterface()
    def_file = design_dir / "floorplan.def"
    
    if not def_file.exists():
        print(f"✗ 错误: DEF文件不存在: {def_file}")
        return False
    
    try:
        # 计算边界代价
        boundary_info = openroad_interface.calculate_boundary_cost(
            layout_def_file=str(def_file),
            partition_scheme=partition_scheme
        )
        
        print(f"✓ 总HPWL: {boundary_info['total_hpwl']:.2f} um")
        print(f"✓ 边界代价: {boundary_info['boundary_cost']:.2f}%")
        print(f"✓ 边界HPWL: {boundary_info['boundary_hpwl']:.2f} um")
        
        print("\n各分区内部HPWL:")
        for partition_id, hpwl in boundary_info['partition_hpwls'].items():
            print(f"  - {partition_id}: {hpwl:.2f} um")
        
        print("✓ 测试4通过: 边界代价计算成功")
        return True
    except Exception as e:
        print(f"✗ 错误: 边界代价计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_openroad_execution(design_dir: Path, partition_scheme: dict, run_openroad: bool = False):
    """测试OpenROAD执行（可选）"""
    print("\n" + "="*80)
    print("测试5: OpenROAD执行（可选）")
    print("="*80)
    
    if not run_openroad:
        print("⚠ 跳过OpenROAD执行测试（使用 --run-openroad 启用）")
        return True
    
    openroad_interface = OpenRoadInterface()
    
    # 检查OpenROAD是否可用
    try:
        result = subprocess.run(
            [openroad_interface.binary_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print(f"⚠ 警告: OpenROAD可能不可用 (返回码: {result.returncode})")
            print(f"   标准输出: {result.stdout}")
            print(f"   标准错误: {result.stderr}")
            return False
        print(f"✓ OpenROAD可用: {result.stdout.strip()}")
    except FileNotFoundError:
        print(f"✗ 错误: 找不到OpenROAD可执行文件: {openroad_interface.binary_path}")
        print("   请确保OpenROAD已安装并在PATH中")
        return False
    except Exception as e:
        print(f"✗ 错误: 检查OpenROAD时出错: {e}")
        return False
    
    # 执行完整的布局流程
    try:
        # 输出到results目录，而不是原始数据集目录
        # 获取项目根目录
        project_root = Path(__file__).parent.parent
        design_name = design_dir.name
        benchmark_name = design_dir.parent.name  # ispd2015
        output_dir = project_root / "results" / benchmark_name / design_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"开始执行OpenROAD布局（这可能需要一些时间）...")
        layout_def, layout_info = openroad_interface.generate_layout_with_partition(
            partition_scheme=partition_scheme,
            design_dir=str(design_dir),
            output_dir=str(output_dir)
        )
        
        if layout_info['status'] == 'success':
            print(f"✓ OpenROAD执行成功")
            print(f"✓ 布局DEF文件: {layout_def}")
            print(f"✓ 运行时间: {layout_info['runtime']:.2f} 秒")
            
            # 提取HPWL
            if 'hpwl' in layout_info and layout_info['hpwl'] > 0:
                print(f"✓ 从输出中提取的HPWL: {layout_info['hpwl']:.2f} um")
            else:
                print("⚠ 警告: 未能从输出中提取HPWL，将从DEF文件计算")
                hpwl = openroad_interface.calculate_hpwl(layout_def)
                print(f"✓ 从DEF文件计算的HPWL: {hpwl:.2f} um")
            
            print("✓ 测试5通过: OpenROAD执行成功")
            return True
        else:
            print(f"✗ OpenROAD执行失败: {layout_info.get('error', 'Unknown error')}")
            
            # 显示日志文件位置
            if 'log_files' in layout_info and layout_info['log_files']:
                log_files = layout_info['log_files']
                print(f"\n   完整日志已保存到:")
                if log_files.get('combined'):
                    print(f"   ✓ 合并日志: {log_files['combined']}")
                if log_files.get('stdout'):
                    print(f"   ✓ 标准输出: {log_files['stdout']}")
                if log_files.get('stderr'):
                    print(f"   ✓ 标准错误: {log_files['stderr']}")
            
            # 显示详细的错误信息
            if 'output_file_expected' in layout_info:
                print(f"\n   期望的输出文件: {layout_info['output_file_expected']}")
                if Path(layout_info['output_file_expected']).exists():
                    print(f"   ✓ 文件存在")
                else:
                    print(f"   ✗ 文件不存在")
            
            if 'has_errors' in layout_info and layout_info['has_errors']:
                print(f"   ⚠ 检测到错误信息（详见日志文件）")
            if 'has_warnings' in layout_info and layout_info['has_warnings']:
                print(f"   ⚠ 检测到警告信息（详见日志文件）")
            
            # 显示简要输出（最后几行）
            if 'stdout' in layout_info and layout_info['stdout']:
                print(f"\n   标准输出摘要（最后10行，完整内容见日志文件）:")
                stdout_lines = layout_info['stdout'].split('\n')
                for line in stdout_lines[-10:]:
                    if line.strip():
                        print(f"   {line}")
            
            if 'stderr' in layout_info and layout_info['stderr']:
                print(f"\n   标准错误摘要（完整内容见日志文件）:")
                stderr_lines = layout_info['stderr'].split('\n')
                for line in stderr_lines:
                    if line.strip():
                        print(f"   {line}")
            
            # 检查TCL脚本是否存在
            tcl_script = design_dir / "openroad_script.tcl"
            if tcl_script.exists():
                print(f"\n   TCL脚本位置: {tcl_script}")
                print(f"   可以手动检查TCL脚本内容")
            
            return False
    except Exception as e:
        print(f"✗ 错误: OpenROAD执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='测试OpenROAD接口')
    parser.add_argument(
        '--design',
        type=str,
        default='mgc_pci_bridge32_a',
        help='设计名称（默认: mgc_pci_bridge32_a）'
    )
    parser.add_argument(
        '--run-openroad',
        action='store_true',
        help='执行OpenROAD布局（需要OpenROAD可用）'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/ispd2015',
        help='数据目录路径（默认: data/ispd2015）'
    )
    
    args = parser.parse_args()
    
    # 确定设计目录
    data_dir = Path(project_root) / args.data_dir
    design_dir = data_dir / args.design
    
    if not design_dir.exists():
        print(f"✗ 错误: 设计目录不存在: {design_dir}")
        print(f"   可用的设计: {[d.name for d in data_dir.iterdir() if d.is_dir()]}")
        return 1
    
    print("="*80)
    print(f"OpenROAD接口测试 - 设计: {args.design}")
    print("="*80)
    print(f"设计目录: {design_dir}")
    
    # 检查必需文件
    required_files = ['floorplan.def', 'design.v', 'tech.lef', 'cells.lef']
    missing_files = []
    for file_name in required_files:
        if not (design_dir / file_name).exists():
            missing_files.append(file_name)
    
    if missing_files:
        print(f"✗ 错误: 缺少必需文件: {missing_files}")
        return 1
    
    print("✓ 所有必需文件存在")
    
    # 创建测试分区方案
    try:
        partition_scheme, all_components = create_test_partition_scheme(design_dir)
        print(f"\n✓ 创建测试分区方案:")
        print(f"  总组件数: {len(all_components)}")
        for partition_id, module_ids in partition_scheme.items():
            print(f"  {partition_id}: {len(module_ids)} 个模块")
    except Exception as e:
        print(f"✗ 错误: 创建分区方案失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 运行测试
    results = {}
    
    # 测试1: 分区方案转换为DEF约束
    try:
        success, output_def = test_convert_partition_to_def_constraints(design_dir, partition_scheme)
        results['test1'] = success
        if success:
            results['output_def'] = output_def
    except Exception as e:
        print(f"✗ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        results['test1'] = False
        return 1
    
    # 测试2: TCL脚本生成
    try:
        success, tcl_script = test_generate_tcl_script(design_dir, output_def)
        results['test2'] = success
        if success:
            results['tcl_script'] = tcl_script
    except Exception as e:
        print(f"✗ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        results['test2'] = False
    
    # 测试3: HPWL提取
    try:
        results['test3'] = test_hpwl_extraction(design_dir)
    except Exception as e:
        print(f"✗ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        results['test3'] = False
    
    # 测试4: 边界代价计算
    try:
        results['test4'] = test_boundary_cost_calculation(design_dir, partition_scheme)
    except Exception as e:
        print(f"✗ 测试4失败: {e}")
        import traceback
        traceback.print_exc()
        results['test4'] = False
    
    # 测试5: OpenROAD执行（可选）
    if args.run_openroad:
        try:
            results['test5'] = test_openroad_execution(design_dir, partition_scheme, run_openroad=True)
        except Exception as e:
            print(f"✗ 测试5失败: {e}")
            import traceback
            traceback.print_exc()
            results['test5'] = False
    else:
        results['test5'] = None
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    test_names = {
        'test1': '分区方案转换为DEF约束',
        'test2': 'TCL脚本生成',
        'test3': 'HPWL提取',
        'test4': '边界代价计算',
        'test5': 'OpenROAD执行'
    }
    
    for test_key, test_name in test_names.items():
        status = results.get(test_key)
        if status is True:
            print(f"✓ {test_name}: 通过")
        elif status is False:
            print(f"✗ {test_name}: 失败")
        elif status is None:
            print(f"⚠ {test_name}: 跳过")
    
    # 返回结果
    all_passed = all(v for v in results.values() if v is not None)
    
    if all_passed:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print("\n✗ 部分测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())

