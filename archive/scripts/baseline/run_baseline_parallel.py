#!/usr/bin/env python3
"""
并行运行ISPD 2015设计的随机划分基线实验
支持指定并行度（2-3个设计同时运行）
"""

import sys
import os
from pathlib import Path
import json
import time
import subprocess
import argparse
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

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
    
    # 按DIE面积排序（从小到大）
    designs.sort(key=lambda x: x[2])
    
    return designs


def run_single_design(design_name: str, data_dir: Path, output_dir: Path, 
                      seed: int, skip_existing: bool = True) -> Tuple[str, bool, str]:
    """
    运行单个设计的基线实验
    
    Args:
        design_name: 设计名称
        data_dir: 数据目录
        output_dir: 输出目录
        seed: 随机种子
        skip_existing: 是否跳过已存在的结果
    
    Returns:
        (设计名, 是否成功, 错误信息)
    """
    try:
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "run_baseline_experiments.py"),
            "--designs", design_name,
            "--data-dir", str(data_dir),
            "--output-dir", str(output_dir),
            "--seed", str(seed),
        ]
        
        if skip_existing:
            cmd.append("--skip-existing")
        
        # 运行实验
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=None  # 不设置超时
        )
        
        if result.returncode == 0:
            return (design_name, True, "")
        else:
            error_msg = result.stderr[:500] if result.stderr else result.stdout[-500:]
            return (design_name, False, error_msg)
            
    except Exception as e:
        return (design_name, False, str(e))


def main():
    parser = argparse.ArgumentParser(description='并行运行ISPD 2015设计的随机划分基线实验')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/dataset/ispd_2015_contest_benchmark',
        help='数据目录路径（默认: data/dataset/ispd_2015_contest_benchmark）'
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
        '--parallel',
        type=int,
        default=2,
        help='并行度（同时运行的设计数量，默认: 2）'
    )
    parser.add_argument(
        '--max-designs',
        type=int,
        default=None,
        help='最多处理的设计数量（用于测试）'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='跳过已存在的结果'
    )
    
    args = parser.parse_args()
    
    data_dir = project_root / args.data_dir
    output_dir = project_root / args.output_dir
    
    print("="*80)
    print("ISPD 2015 基线实验并行运行")
    print("="*80)
    print(f"数据目录: {data_dir}")
    print(f"输出目录: {output_dir}")
    print(f"随机种子: {args.seed}")
    print(f"并行度: {args.parallel}")
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
    log_file = log_dir / f"baseline_parallel_{timestamp}.log"
    
    print(f"\n开始并行运行实验（并行度: {args.parallel}）...")
    print(f"日志文件: {log_file}")
    print(f"使用以下命令查看日志: tail -f {log_file}")
    print()
    
    # 打开日志文件
    with open(log_file, 'w') as f:
        f.write(f"ISPD 2015 基线实验并行运行\n")
        f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"并行度: {args.parallel}\n")
        f.write(f"设计列表: {', '.join(design_names)}\n")
        f.write(f"{'='*80}\n\n")
        f.flush()
        
        # 使用 ProcessPoolExecutor 并行运行
        start_time = time.time()
        completed = 0
        failed = 0
        
        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            # 提交所有任务
            future_to_design = {
                executor.submit(
                    run_single_design,
                    design_name,
                    data_dir,
                    output_dir,
                    args.seed,
                    args.skip_existing
                ): design_name
                for design_name in design_names
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_design):
                design_name = future_to_design[future]
                try:
                    result_design, success, error_msg = future.result()
                    completed += 1
                    
                    if success:
                        status = "✓ 成功"
                        print(f"[{completed}/{len(design_names)}] {result_design}: {status}")
                        f.write(f"[{completed}/{len(design_names)}] {result_design}: {status}\n")
                    else:
                        status = "✗ 失败"
                        failed += 1
                        print(f"[{completed}/{len(design_names)}] {result_design}: {status}")
                        print(f"  错误: {error_msg[:200]}")
                        f.write(f"[{completed}/{len(design_names)}] {result_design}: {status}\n")
                        f.write(f"  错误: {error_msg}\n")
                    
                    f.flush()
                    
                except Exception as e:
                    completed += 1
                    failed += 1
                    print(f"[{completed}/{len(design_names)}] {design_name}: ✗ 异常 - {e}")
                    f.write(f"[{completed}/{len(design_names)}] {design_name}: ✗ 异常 - {e}\n")
                    f.flush()
        
        elapsed_time = time.time() - start_time
        
        # 写入总结
        summary = f"""
{'='*80}
实验总结
{'='*80}
总设计数: {len(design_names)}
成功: {completed - failed}
失败: {failed}
总耗时: {elapsed_time:.2f} 秒 ({elapsed_time/60:.2f} 分钟)
平均每个设计: {elapsed_time/len(design_names):.2f} 秒
完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
"""
        print(summary)
        f.write(summary)
        f.flush()
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

