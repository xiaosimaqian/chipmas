#!/usr/bin/env python3
"""
收集ISPD 2015 Clean Baseline（无分区约束）

目标：
- 运行原始ISPD 2015设计（无任何分区约束）
- 使用配置的die size（避免OOM）
- 执行OpenROAD详细布局
- 提取legalized HPWL
- 作为真正的baseline对比基准

参考：~/dreamplace_experiment/chipkag/results/chipkag_complete_experiment/
"""

import sys
import json
import time
import subprocess
import re
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.die_size_config import get_die_size
from src.utils.def_parser import DEFParser


def detect_metal_layer_direction(tech_lef_path: Path) -> tuple:
    """
    检测LEF文件中metal1和metal2的方向
    
    Returns:
        (hor_layer, ver_layer): 用于place_pins的水平和垂直层
    """
    with open(tech_lef_path, 'r') as f:
        content = f.read()
    
    # 查找metal1和metal2的DIRECTION
    metal1_match = re.search(r'LAYER metal1.*?DIRECTION\s+(\w+)', content, re.DOTALL)
    metal2_match = re.search(r'LAYER metal2.*?DIRECTION\s+(\w+)', content, re.DOTALL)
    
    if metal1_match and metal2_match:
        metal1_dir = metal1_match.group(1).upper()
        metal2_dir = metal2_match.group(1).upper()
        
        # 根据实际方向返回
        if metal1_dir == 'HORIZONTAL':
            return ('metal1', 'metal2')  # metal1水平，metal2垂直
        elif metal2_dir == 'HORIZONTAL':
            return ('metal2', 'metal1')  # metal2水平，metal1垂直
    
    # 默认：假设metal1水平
    return ('metal1', 'metal2')


def generate_tcl_script(design_name: str,
                       design_dir: Path,
                       output_dir: Path,
                       die_area: str,
                       core_area: str) -> Path:
    """
    生成OpenROAD TCL脚本
    
    参考：~/dreamplace_experiment/chipkag/results/chipkag_complete_experiment/
    """
    design_v = design_dir / 'design.v'
    tech_lef = design_dir / 'tech.lef'
    cells_lef = design_dir / 'cells.lef'
    output_def = output_dir / f"{design_name}_clean_layout.def"
    
    # 从design.v中提取顶层模块名（简单处理）
    with open(design_v, 'r') as f:
        for line in f:
            if 'module' in line and '(' in line:
                module_name = line.split()[1].split('(')[0]
                break
        else:
            module_name = design_name.split('_')[1]  # fallback: mgc_fft_1 -> fft
    
    # 自动检测metal层方向
    hor_layer, ver_layer = detect_metal_layer_direction(tech_lef)
    
    tcl_content = f"""# OpenROAD TCL脚本 - {design_name}
# Clean Baseline（无分区约束）

# 1. 读取设计文件
read_lef {tech_lef.absolute()}
read_lef {cells_lef.absolute()}
read_verilog {design_v.absolute()}

# 2. 链接设计
link_design {module_name}

# 3. 设置时钟约束
create_clock -period 10 -name clk
set_clock_uncertainty 0.1 clk

# 4. 初始化布局（使用配置的die size，避免OOM）
initialize_floorplan -die_area "{die_area}" -core_area "{core_area}" -site core

# 5. 生成轨道
make_tracks

# 6. 放置端口（自动检测metal层方向：hor={hor_layer}, ver={ver_layer}）
# 注意：必须在global_placement之前完成所有端口放置
place_pins -random -hor_layers {hor_layer} -ver_layers {ver_layer}

# 7. 全局布局
puts "开始全局布局..."
global_placement -skip_initial_place

# 7.1. 全局布局报告
puts "全局布局完成，生成报告..."
report_design_area

# 8. 详细布局
puts "开始详细布局..."
detailed_placement

# 8.1. 详细布局报告
puts "详细布局完成，生成报告..."
report_design_area

# 9. 计算HPWL
puts "计算HPWL..."
report_design_area

# 10. 输出DEF文件
write_def {output_def.absolute()}

puts "Clean Baseline布局完成: {design_name}"

# 11. 退出OpenROAD
exit
"""
    
    tcl_file = output_dir / f"{design_name}_clean.tcl"
    with open(tcl_file, 'w') as f:
        f.write(tcl_content)
    
    return tcl_file


def extract_hpwl_from_log(log_content: str) -> dict:
    """从OpenROAD日志中提取HPWL"""
    hpwl_data = {}
    
    # 查找 "original HPWL" (global placement后的HPWL)
    # 格式: "original HPWL         2550024.0 u"
    gp_match = re.search(r'original HPWL\s+([\d.]+)\s+u\b', log_content)
    if gp_match:
        hpwl_data['global_placement_hpwl'] = float(gp_match.group(1))
    
    # 查找 "legalized HPWL" (详细布局后的HPWL)
    # 格式: "legalized HPWL        2630765.5 u"
    leg_match = re.search(r'legalized HPWL\s+([\d.]+)\s+u\b', log_content)
    if leg_match:
        hpwl_data['legalized_hpwl'] = float(leg_match.group(1))
        hpwl_data['hpwl'] = float(leg_match.group(1))
    
    return hpwl_data


def collect_clean_baseline_for_design(design_name: str, 
                                      design_dir: Path,
                                      output_dir: Path) -> dict:
    """
    为单个设计收集clean baseline
    
    Args:
        design_name: 设计名称
        design_dir: 设计目录
        output_dir: 输出目录
    
    Returns:
        结果字典
    """
    print("\n" + "=" * 80)
    print(f"处理设计: {design_name}")
    print("=" * 80)
    
    start_time = time.time()
    result = {
        'design': design_name,
        'status': 'unknown',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'error': None,
        'runtime_seconds': 0,
        'hpwl': None,
        'global_placement_hpwl': None,
        'legalized_hpwl': None,
        'component_count': 0,
        'net_count': 0,
        'die_size_used': None,
        'output_def': None,
        'tcl_file': None,
        'log_file': None
    }
    
    try:
        # 1. 检查必要文件
        design_v = design_dir / 'design.v'
        tech_lef = design_dir / 'tech.lef'
        cells_lef = design_dir / 'cells.lef'
        floorplan_def = design_dir / 'floorplan.def'
        
        if not all([design_v.exists(), tech_lef.exists(), 
                   cells_lef.exists(), floorplan_def.exists()]):
            result['status'] = 'error'
            result['error'] = "缺少必要文件"
            return result
        
        # 2. 解析floorplan.def获取设计规模
        print(f"解析设计文件...")
        parser = DEFParser(str(floorplan_def))
        parser.parse()
        
        result['component_count'] = len(parser.components)
        result['net_count'] = len(parser.nets)
        
        print(f"  组件数: {result['component_count']:,}")
        print(f"  网络数: {result['net_count']:,}")
        
        # 3. 获取配置的die size（关键：不使用floorplan.def中的die size）
        die_area_str, core_area_str = get_die_size(design_name)
        result['die_size_used'] = {
            'die_area': die_area_str,
            'core_area': core_area_str
        }
        
        print(f"  使用配置的die size: {die_area_str}")
        print(f"  使用配置的core area: {core_area_str}")
        
        # 4. 创建输出目录
        design_output_dir = output_dir / design_name
        design_output_dir.mkdir(parents=True, exist_ok=True)
        
        log_dir = design_output_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # 5. 生成TCL脚本
        print(f"生成OpenROAD TCL脚本...")
        tcl_file = generate_tcl_script(
            design_name=design_name,
            design_dir=design_dir,
            output_dir=design_output_dir,
            die_area=die_area_str,
            core_area=core_area_str
        )
        result['tcl_file'] = str(tcl_file)
        print(f"  TCL脚本: {tcl_file}")
        
        # 6. 运行OpenROAD
        print(f"运行OpenROAD详细布局（无分区约束）...")
        print(f"  这可能需要几分钟到几十分钟...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"openroad_{timestamp}.log"
        result['log_file'] = str(log_file)
        
        with open(log_file, 'w') as log_f:
            process = subprocess.run(
                ['openroad', '-exit', str(tcl_file.absolute())],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        # 7. 检查运行结果
        if process.returncode == 0:
            # 从日志中提取HPWL
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            hpwl_data = extract_hpwl_from_log(log_content)
            result.update(hpwl_data)
            
            output_def = design_output_dir / f"{design_name}_clean_layout.def"
            if output_def.exists():
                result['status'] = 'success'
                result['output_def'] = str(output_def)
                
                print(f"✅ OpenROAD运行成功")
                if result.get('legalized_hpwl'):
                    print(f"  Legalized HPWL: {result['legalized_hpwl']:,.2f}")
                if result.get('global_placement_hpwl'):
                    print(f"  Global Placement HPWL: {result['global_placement_hpwl']:,.2f}")
            else:
                result['status'] = 'error'
                result['error'] = "输出DEF文件未生成"
                print(f"❌ 输出DEF文件未生成")
        else:
            result['status'] = 'error'
            result['error'] = f"OpenROAD退出码: {process.returncode}"
            print(f"❌ OpenROAD运行失败，退出码: {process.returncode}")
            print(f"   查看日志: {log_file}")
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        result['runtime_seconds'] = time.time() - start_time
        print(f"运行时间: {result['runtime_seconds']:.1f}秒")
    
    return result


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="收集ISPD 2015 Clean Baseline")
    parser.add_argument('--design', action='append', help='指定设计名称（可多次使用，不指定则运行所有）')
    parser.add_argument('--output-dir', default='results/clean_baseline',
                       help='输出目录（默认: results/clean_baseline）')
    parser.add_argument('--skip-existing', action='store_true',
                       help='跳过已有结果的设计')
    args = parser.parse_args()
    
    # 设置路径
    project_root = Path(__file__).parent.parent
    ispd_dir = project_root / 'data' / 'ispd2015'
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 80)
    print("ISPD 2015 Clean Baseline 收集")
    print("=" * 80)
    print(f"数据目录: {ispd_dir}")
    print(f"输出目录: {output_dir}")
    print()
    
    # 获取要运行的设计列表
    if args.design:
        designs = args.design  # args.design is now a list due to action='append'
    else:
        designs = sorted([d.name for d in ispd_dir.iterdir() 
                         if d.is_dir() and not d.name.startswith('.')])
    
    print(f"待处理设计: {len(designs)} 个")
    for i, design in enumerate(designs, 1):
        print(f"  {i:2d}. {design}")
    print()
    
    # 运行收集
    all_results = []
    success_count = 0
    fail_count = 0
    
    for i, design_name in enumerate(designs, 1):
        design_dir = ispd_dir / design_name
        
        # 检查是否跳过
        if args.skip_existing:
            result_file = output_dir / design_name / 'result.json'
            if result_file.exists():
                print(f"\n[{i}/{len(designs)}] ⏭️  跳过 {design_name}（已有结果）")
                continue
        
        print(f"\n[{i}/{len(designs)}] 处理 {design_name}")
        
        # 收集baseline
        result = collect_clean_baseline_for_design(
            design_name=design_name,
            design_dir=design_dir,
            output_dir=output_dir
        )
        
        all_results.append(result)
        
        # 保存单个结果
        design_output_dir = output_dir / design_name
        design_output_dir.mkdir(parents=True, exist_ok=True)
        result_file = design_output_dir / 'result.json'
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # 统计
        if result['status'] == 'success':
            success_count += 1
            print(f"✅ {design_name} 完成")
        else:
            fail_count += 1
            print(f"❌ {design_name} 失败: {result['error']}")
    
    # 保存汇总结果
    summary = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total': len(all_results),
        'success': success_count,
        'fail': fail_count,
        'results': all_results
    }
    
    summary_file = output_dir / 'summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # 打印汇总
    print("\n" + "=" * 80)
    print("收集完成")
    print("=" * 80)
    print(f"总计: {len(all_results)} 个设计")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    
    if success_count > 0:
        successful_results = [r for r in all_results if r['status'] == 'success']
        hpwls = [r['legalized_hpwl'] for r in successful_results if r['legalized_hpwl']]
        if hpwls:
            print(f"\nLegalized HPWL统计:")
            print(f"  平均值: {sum(hpwls) / len(hpwls):,.0f}")
            print(f"  最小值: {min(hpwls):,.0f}")
            print(f"  最大值: {max(hpwls):,.0f}")
    
    print(f"\n结果已保存到: {output_dir}")
    print(f"汇总文件: {summary_file}")
    print()
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

