#!/usr/bin/env python3
"""
按DIE面积从小到大依次运行所有ISPD 2015设计的基线实验
每次只运行一个设计，避免资源竞争和OOM
"""

import sys
import os
from pathlib import Path
import json
import time
import subprocess
import argparse
from typing import List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.def_parser import DEFParser


def get_design_size(design_dir: Path) -> Tuple[int, int]:
    """
    获取设计规模（组件数量和DIE面积）
    
    Args:
        design_dir: 设计目录
    
    Returns:
        (组件数量, DIE面积 um²)
    """
    def_file = design_dir / "floorplan.def"
    if not def_file.exists():
        return (0, 0)
    
    try:
        parser = DEFParser(str(def_file))
        parser.parse()
        num_components = len(parser.components)
        
        # 读取DIEAREA
        import re
        with open(def_file, 'r') as f:
            content = f.read()
            match = re.search(r'DIEAREA\s+\(\s*(\d+)\s+(\d+)\s+\)\s+\(\s*(\d+)\s+(\d+)\s+\)', content)
            if match:
                die_width = int(match.group(3)) - int(match.group(1))
                die_height = int(match.group(4)) - int(match.group(2))
                die_area = die_width * die_height
            else:
                die_area = 0
        
        return (num_components, die_area)
    except Exception as e:
        print(f"警告: 无法解析 {design_dir.name}: {e}")
        return (0, 0)


def get_all_designs_sorted(data_dir: Path) -> List[Tuple[str, int, int]]:
    """
    获取所有设计并按DIE面积排序（从小到大）
    
    Args:
        data_dir: 数据目录
    
    Returns:
        [(设计名, 组件数量, DIE面积), ...] 按DIE面积从小到大排序
    """
    designs = []
    
    for design_dir in data_dir.iterdir():
        if not design_dir.is_dir():
            continue
        
        if not (design_dir / "floorplan.def").exists():
            continue
        
        design_name = design_dir.name
        num_components, die_area = get_design_size(design_dir)
        if die_area > 0:  # 只包含有效的设计
            designs.append((design_name, num_components, die_area))
    
    # 按DIE面积排序（从小到大）
    designs.sort(key=lambda x: x[2])
    
    return designs


def check_design_completed(design_name: str, output_dir: Path) -> bool:
    """
    检查设计是否已经完成
    
    Args:
        design_name: 设计名称
        output_dir: 输出目录
    
    Returns:
        是否已完成
    """
    design_output_dir = output_dir / "ispd2015" / design_name
    if not design_output_dir.exists():
        return False
    
    # 检查是否有layout.def文件
    layout_files = list(design_output_dir.glob("layout_*.def"))
    if not layout_files:
        return False
    
    # 检查最新的layout.def对应的日志文件，确认是否成功完成
    latest_layout = max(layout_files, key=lambda p: p.stat().st_mtime)
    timestamp = latest_layout.stem.replace("layout_", "")
    log_file = design_output_dir / "logs" / f"openroad_combined_{timestamp}.log"
    
    if not log_file.exists():
        return False
    
    # 检查日志中是否有成功标记
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            # 检查是否有legalized HPWL（表示detailed placement完成）
            if 'legalized HPWL' in content or 'Legalized HPWL' in content:
                # 检查是否有严重错误
                if any(keyword in content.lower() for keyword in ['fatal', 'killed', 'oom', 'out of memory']):
                    return False
                return True
    except:
        pass
    
    return False


def run_single_design(design_name: str, data_dir: Path, output_dir: Path, seed: int, log_file: Path) -> Tuple[bool, str]:
    """
    运行单个设计的基线实验
    
    Args:
        design_name: 设计名称
        data_dir: 数据目录
        output_dir: 输出目录
        seed: 随机种子
        log_file: 日志文件路径
    
    Returns:
        (是否成功, 错误信息)
    """
    cmd = [
        sys.executable,
        str(project_root / "scripts" / "run_baseline_experiments.py"),
        "--designs", design_name,
        "--data-dir", str(data_dir),
        "--output-dir", str(output_dir),
        "--seed", str(seed),
        "--skip-existing"
    ]
    
    print(f"\n{'='*80}")
    print(f"开始运行: {design_name}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    try:
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"开始运行: {design_name}\n")
            f.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
            f.flush()
            
            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(project_root),
                env=os.environ.copy()
            )
            
            # 等待进程完成
            return_code = process.wait()
            runtime = time.time() - start_time
            
            f.write(f"\n运行完成，返回码: {return_code}, 耗时: {runtime:.2f}秒\n")
            f.flush()
        
        if return_code == 0:
            # 检查是否真的成功（有layout.def文件）
            if check_design_completed(design_name, output_dir):
                print(f"✓ {design_name} 运行成功（耗时: {runtime:.2f}秒）")
                return (True, "")
            else:
                error_msg = f"返回码为0但未找到有效的layout.def文件"
                print(f"✗ {design_name} 运行失败: {error_msg}")
                return (False, error_msg)
        else:
            error_msg = f"返回码: {return_code}"
            print(f"✗ {design_name} 运行失败: {error_msg}")
            return (False, error_msg)
            
    except Exception as e:
        runtime = time.time() - start_time
        error_msg = f"异常: {str(e)}"
        print(f"✗ {design_name} 运行失败: {error_msg}")
        with open(log_file, 'a') as f:
            f.write(f"\n运行失败: {error_msg}\n")
            f.write(f"耗时: {runtime:.2f}秒\n")
        return (False, error_msg)


def main():
    parser = argparse.ArgumentParser(description='按DIE面积从小到大依次运行所有ISPD 2015设计的基线实验')
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
        '--skip-completed',
        action='store_true',
        help='跳过已完成的设计'
    )
    parser.add_argument(
        '--max-designs',
        type=int,
        default=None,
        help='最多处理的设计数量（用于测试）'
    )
    
    args = parser.parse_args()
    
    data_dir = project_root / args.data_dir
    output_dir = project_root / args.output_dir
    
    print("="*80)
    print("ISPD 2015 基线实验顺序运行（按DIE面积从小到大）")
    print("="*80)
    print(f"数据目录: {data_dir}")
    print(f"输出目录: {output_dir}")
    print(f"随机种子: {args.seed}")
    print(f"跳过已完成: {args.skip_completed}")
    print()
    
    # 获取所有设计并按DIE面积排序
    print("扫描设计并计算规模...")
    designs_sorted = get_all_designs_sorted(data_dir)
    
    if not designs_sorted:
        print("错误: 未找到任何设计")
        return 1
    
    print(f"\n找到 {len(designs_sorted)} 个设计（按DIE面积从小到大）:")
    for i, (name, num_comp, die_area) in enumerate(designs_sorted, 1):
        status = ""
        if args.skip_completed and check_design_completed(name, output_dir):
            status = " [已完成]"
        print(f"  {i:2d}. {name:30s} ({num_comp:6d} 个组件, {die_area/1e6:8.2f} mm²){status}")
    
    # 过滤已完成的设计
    if args.skip_completed:
        designs_sorted = [(n, c, a) for n, c, a in designs_sorted if not check_design_completed(n, output_dir)]
        print(f"\n过滤后剩余 {len(designs_sorted)} 个设计需要运行")
    
    # 限制设计数量（用于测试）
    if args.max_designs:
        designs_sorted = designs_sorted[:args.max_designs]
        print(f"\n限制为前 {args.max_designs} 个设计")
    
    if not designs_sorted:
        print("\n所有设计都已完成！")
        return 0
    
    # 创建日志文件
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = project_root / "results" / "baseline_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"baseline_sequential_{timestamp}.log"
    
    # 创建状态文件
    status_file = log_dir / f"baseline_sequential_{timestamp}.json"
    
    # 记录开始时间
    start_time = time.time()
    
    print(f"\n开始顺序运行实验...")
    print(f"日志文件: {log_file}")
    print(f"状态文件: {status_file}")
    print()
    
    # 初始化状态
    status = {
        'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_designs': len(designs_sorted),
        'completed': 0,
        'failed': 0,
        'skipped': 0,
        'results': []
    }
    
    # 依次运行每个设计
    for i, (design_name, num_comp, die_area) in enumerate(designs_sorted, 1):
        print(f"\n[{i}/{len(designs_sorted)}] 准备运行: {design_name}")
        
        # 检查是否已完成
        if args.skip_completed and check_design_completed(design_name, output_dir):
            print(f"  跳过已完成的设计: {design_name}")
            status['skipped'] += 1
            status['results'].append({
                'design': design_name,
                'status': 'skipped',
                'reason': 'already completed'
            })
            continue
        
        # 运行设计
        success, error_msg = run_single_design(
            design_name=design_name,
            data_dir=data_dir,
            output_dir=output_dir,
            seed=args.seed,
            log_file=log_file
        )
        
        # 更新状态
        if success:
            status['completed'] += 1
            status['results'].append({
                'design': design_name,
                'status': 'success',
                'components': num_comp,
                'die_area_mm2': die_area / 1e6
            })
        else:
            status['failed'] += 1
            status['results'].append({
                'design': design_name,
                'status': 'failed',
                'error': error_msg,
                'components': num_comp,
                'die_area_mm2': die_area / 1e6
            })
        
        # 保存状态
        status['last_update'] = time.strftime('%Y-%m-%d %H:%M:%S')
        status['elapsed_time'] = time.time() - start_time
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        
        # 如果失败，询问是否继续
        if not success:
            print(f"\n警告: {design_name} 运行失败")
            print("继续运行下一个设计...")
    
    # 最终总结
    total_time = time.time() - start_time
    status['end_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
    status['total_time'] = total_time
    
    print(f"\n{'='*80}")
    print("实验完成总结")
    print(f"{'='*80}")
    print(f"总设计数: {len(designs_sorted)}")
    print(f"成功: {status['completed']}")
    print(f"失败: {status['failed']}")
    print(f"跳过: {status['skipped']}")
    print(f"总耗时: {total_time/3600:.2f} 小时 ({total_time:.2f} 秒)")
    print(f"\n状态文件: {status_file}")
    print(f"日志文件: {log_file}")
    
    # 保存最终状态
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    
    return 0 if status['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())


