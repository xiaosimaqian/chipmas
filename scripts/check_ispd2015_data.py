#!/usr/bin/env python3
"""
检查 ISPD 2015 设计的数据收集情况
"""

import os
import sys
from pathlib import Path
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.def_parser import DEFParser
from src.utils.die_size_config import DIE_SIZE_CONFIG

def parse_design_info(design_dir):
    """解析设计的基本信息"""
    design_dir = Path(design_dir)
    design_name = design_dir.name
    
    info = {
        'design_name': design_name,
        'has_cells_lef': False,
        'has_tech_lef': False,
        'has_design_v': False,
        'has_floorplan_def': False,
        'component_count': 0,
        'net_count': 0,
        'pin_count': 0,
        'die_area_from_def': None,
        'core_area_from_def': None,
        'die_area_configured': None,
        'core_area_configured': None,
        'floorplan_def_size': None,
    }
    
    # 检查文件存在性
    info['has_cells_lef'] = (design_dir / 'cells.lef').exists()
    info['has_tech_lef'] = (design_dir / 'tech.lef').exists()
    info['has_design_v'] = (design_dir / 'design.v').exists()
    info['has_floorplan_def'] = (design_dir / 'floorplan.def').exists()
    
    # 解析 floorplan.def
    if info['has_floorplan_def']:
        def_file = design_dir / 'floorplan.def'
        info['floorplan_def_size'] = def_file.stat().st_size / 1024  # KB
        
        try:
            parser = DEFParser(str(def_file))
            parser.parse()
            
            info['component_count'] = len(parser.components)
            info['net_count'] = len(parser.nets)
            
            # 计算总引脚数
            total_pins = 0
            for net_name, net_info in parser.nets.items():
                total_pins += len(net_info.get('connections', []))
            info['pin_count'] = total_pins
            
            # 从DEF读取die area
            if parser.die_area:
                x1, y1, x2, y2 = parser.die_area
                info['die_area_from_def'] = f"{x1} {y1} {x2} {y2}"
                info['die_width_from_def'] = x2 - x1
                info['die_height_from_def'] = y2 - y1
            
        except Exception as e:
            info['parse_error'] = str(e)
    
    # 获取配置的die size
    if design_name in DIE_SIZE_CONFIG:
        die_area, core_area = DIE_SIZE_CONFIG[design_name]
        info['die_area_configured'] = die_area
        info['core_area_configured'] = core_area
        
        # 解析配置的die size
        parts = die_area.split()
        if len(parts) == 4:
            x1, y1, x2, y2 = map(int, parts)
            info['die_width_configured'] = x2 - x1
            info['die_height_configured'] = y2 - y1
    
    return info


def main():
    ispd_dir = Path("data/ispd2015")
    
    if not ispd_dir.exists():
        print(f"❌ 目录不存在: {ispd_dir}")
        return
    
    # 获取所有设计
    designs = sorted([d for d in os.listdir(ispd_dir) if (ispd_dir / d).is_dir()])
    
    print("=" * 100)
    print("ISPD 2015 数据收集情况检查")
    print("=" * 100)
    print(f"\n总共 {len(designs)} 个设计\n")
    
    all_info = []
    
    for i, design in enumerate(designs, 1):
        design_dir = ispd_dir / design
        info = parse_design_info(design_dir)
        all_info.append(info)
        
        print(f"\n{i:2d}. {design}")
        print("-" * 80)
        
        # 文件完整性
        files_ok = (info['has_cells_lef'] and info['has_tech_lef'] and 
                   info['has_design_v'] and info['has_floorplan_def'])
        status = "✅" if files_ok else "❌"
        print(f"  文件完整性: {status}")
        print(f"    - cells.lef:      {'✅' if info['has_cells_lef'] else '❌'}")
        print(f"    - tech.lef:       {'✅' if info['has_tech_lef'] else '❌'}")
        print(f"    - design.v:       {'✅' if info['has_design_v'] else '❌'}")
        print(f"    - floorplan.def:  {'✅' if info['has_floorplan_def'] else '❌'}")
        
        # 设计规模
        if info['component_count'] > 0:
            print(f"\n  设计规模:")
            print(f"    - 组件数: {info['component_count']:,}")
            print(f"    - 网络数: {info['net_count']:,}")
            print(f"    - 引脚数: {info['pin_count']:,}")
            print(f"    - DEF文件大小: {info['floorplan_def_size']:.1f} KB")
        
        # Die Size对比
        if info['die_area_from_def'] and info['die_area_configured']:
            print(f"\n  Die Size:")
            print(f"    - 从DEF读取:  {info['die_area_from_def']}")
            print(f"      尺寸: {info['die_width_from_def']} x {info['die_height_from_def']}")
            print(f"    - 配置使用:  {info['die_area_configured']}")
            print(f"      尺寸: {info['die_width_configured']} x {info['die_height_configured']}")
            
            # 判断是否有显著差异
            ratio = (info['die_width_from_def'] * info['die_height_from_def']) / \
                   (info['die_width_configured'] * info['die_height_configured'])
            if ratio > 10:
                print(f"    ⚠️  DEF中的die size是配置的 {ratio:.1f}x (可能导致OOM)")
        
        if 'parse_error' in info:
            print(f"  ⚠️  解析错误: {info['parse_error']}")
    
    # 汇总统计
    print("\n" + "=" * 100)
    print("汇总统计")
    print("=" * 100)
    
    total_components = sum(info['component_count'] for info in all_info)
    total_nets = sum(info['net_count'] for info in all_info)
    total_pins = sum(info['pin_count'] for info in all_info)
    
    print(f"\n总体规模:")
    print(f"  - 总组件数: {total_components:,}")
    print(f"  - 总网络数: {total_nets:,}")
    print(f"  - 总引脚数: {total_pins:,}")
    
    print(f"\n规模分布:")
    components = [info['component_count'] for info in all_info if info['component_count'] > 0]
    if components:
        print(f"  - 最小: {min(components):,} 组件")
        print(f"  - 最大: {max(components):,} 组件")
        print(f"  - 平均: {sum(components)//len(components):,} 组件")
    
    # 按组件数排序
    print(f"\n按规模排序（从小到大）:")
    sorted_info = sorted(all_info, key=lambda x: x['component_count'])
    for i, info in enumerate(sorted_info, 1):
        if info['component_count'] > 0:
            print(f"  {i:2d}. {info['design_name']:25s} - {info['component_count']:7,} 组件")
    
    # 保存详细信息到JSON
    output_file = "data/ispd2015_design_info.json"
    with open(output_file, 'w') as f:
        json.dump(all_info, f, indent=2)
    print(f"\n✅ 详细信息已保存到: {output_file}")
    
    # 检查缺失的数据
    print("\n" + "=" * 100)
    print("需要收集的数据")
    print("=" * 100)
    print("\n对于每个设计，还需要运行OpenROAD收集以下数据:")
    print("  1. ✅ Die Size配置 - 已完成（16/16）")
    print("  2. ❌ Legalized HPWL - 未收集")
    print("  3. ❌ 全局布局时间 - 未收集")
    print("  4. ❌ 详细布局时间 - 未收集")
    print("  5. ❌ 总运行时间 - 未收集")
    print("  6. ❌ 内存使用峰值 - 未收集")
    print("  7. ❌ 布局质量指标 - 未收集")
    
    print("\n建议的下一步工作:")
    print("  1. 在服务器上运行所有16个设计的OpenROAD baseline")
    print("  2. 收集每个设计的legalized HPWL和运行时间")
    print("  3. 将结果保存到统一的JSON文件中")
    print("  4. 创建baseline数据表，作为后续对比的基准")


if __name__ == "__main__":
    main()


