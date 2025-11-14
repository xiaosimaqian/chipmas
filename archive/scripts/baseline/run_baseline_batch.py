#!/usr/bin/env python3
"""
批量运行ISPD 2015设计的随机划分基线实验（按规模排序）
在服务器后台运行，充分利用资源
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
    
    注意：按DIE面积排序而不是组件数量，因为DIE面积直接影响OpenROAD的内存需求。
    大面积的布局即使组件数少，也可能导致OOM。
    
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
        designs.append((design_name, num_components, die_area))
        print(f"  {design_name}: {num_components} 个组件, DIE面积: {die_area/1e6:.2f} mm²")
    
    # 按DIE面积排序（从小到大），这样可以先跑小设计，避免大设计导致OOM
    designs.sort(key=lambda x: x[2])
    
    return designs


def run_in_background(designs: List[str], data_dir: Path, output_dir: Path, 
                     seed: int, log_file: Path) -> subprocess.Popen:
    """
    在后台运行基线实验
    
    Args:
        designs: 设计名称列表
        data_dir: 数据目录
        output_dir: 输出目录
        seed: 随机种子
        log_file: 日志文件路径
    
    Returns:
        subprocess.Popen对象
    """
    cmd = [
        sys.executable,
        str(project_root / "scripts" / "run_baseline_experiments.py"),
        "--designs"] + designs + [
        "--data-dir", str(data_dir),
        "--output-dir", str(output_dir),
        "--seed", str(seed),
        "--skip-existing"
    ]
    
    # 在后台运行
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'w') as f:
        process = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            env=os.environ.copy()
        )
    
    return process


def main():
    parser = argparse.ArgumentParser(description='批量运行ISPD 2015设计的随机划分基线实验（按DIE面积排序）')
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
        '--background',
        action='store_true',
        help='在后台运行（使用nohup）'
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
    print("ISPD 2015 基线实验批量运行（按DIE面积排序）")
    print("="*80)
    print(f"数据目录: {data_dir}")
    print(f"输出目录: {output_dir}")
    print(f"随机种子: {args.seed}")
    print()
    
    # 获取所有设计并按DIE面积排序
    print("扫描设计并计算规模（组件数和DIE面积）...")
    designs_sorted = get_all_designs_sorted(data_dir)
    
    if not designs_sorted:
        print("错误: 未找到任何设计")
        return 1
    
    print(f"\n找到 {len(designs_sorted)} 个设计（按DIE面积从小到大）:")
    for i, (name, num_comp, die_area) in enumerate(designs_sorted, 1):
        print(f"  {i:2d}. {name:30s} ({num_comp:6d} 个组件, {die_area/1e6:8.2f} mm²)")
    
    # 限制设计数量（用于测试）
    if args.max_designs:
        designs_sorted = designs_sorted[:args.max_designs]
        print(f"\n限制为前 {args.max_designs} 个设计")
    
    design_names = [name for name, _, _ in designs_sorted]
    
    # 创建日志文件
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = project_root / "results" / "baseline_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"baseline_batch_{timestamp}.log"
    
    if args.background:
        # 使用nohup在后台运行
        print(f"\n在后台运行实验...")
        print(f"日志文件: {log_file}")
        print(f"使用以下命令查看日志: tail -f {log_file}")
        print(f"使用以下命令查看进程: ps aux | grep run_baseline")
        
        # 构建命令
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "run_baseline_experiments.py"),
            "--designs"] + design_names + [
            "--data-dir", str(data_dir),
            "--output-dir", str(output_dir),
            "--seed", str(args.seed),
            "--skip-existing"
        ]
        
        # 使用nohup运行
        with open(log_file, 'w') as f:
            f.write(f"ISPD 2015 基线实验批量运行\n")
            f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"设计列表: {', '.join(design_names)}\n")
            f.write(f"{'='*80}\n\n")
            f.flush()
            
            process = subprocess.Popen(
                ["nohup"] + cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(project_root),
                env=os.environ.copy()
            )
        
        print(f"\n进程已启动，PID: {process.pid}")
        print(f"可以使用以下命令查看进程状态:")
        print(f"  ps -p {process.pid}")
        print(f"  tail -f {log_file}")
        
        # 保存PID到文件
        pid_file = log_dir / f"baseline_batch_{timestamp}.pid"
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        print(f"PID已保存到: {pid_file}")
        
    else:
        # 前台运行
        print(f"\n开始运行实验（日志将同时输出到控制台和文件）...")
        print(f"日志文件: {log_file}")
        
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "run_baseline_experiments.py"),
            "--designs"] + design_names + [
            "--data-dir", str(data_dir),
            "--output-dir", str(output_dir),
            "--seed", str(args.seed),
            "--skip-existing"
        ]
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(project_root),
                env=os.environ.copy(),
                text=True,
                bufsize=1
            )
            
            # 实时输出到控制台和文件
            for line in process.stdout:
                print(line, end='')
                f.write(line)
                f.flush()
            
            process.wait()
            return_code = process.returncode
        
        print(f"\n实验完成，返回码: {return_code}")
        return return_code
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

