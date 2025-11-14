#!/usr/bin/env python3
"""
干净的 OpenROAD 运行脚本
用于运行 ISPD 2015 原始设计，完成 detailed placement
"""

import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.openroad_interface import OpenRoadInterface


def run_clean_openroad(design_name: str, design_dir: Path, output_dir: Path):
    """
    运行干净的 OpenROAD 流程（无分区约束）
    
    Args:
        design_name: 设计名称（如 mgc_fft_1）
        design_dir: 设计目录路径
        output_dir: 输出目录路径
    """
    print(f"\n{'='*80}")
    print(f"运行干净的 OpenROAD 流程: {design_name}")
    print(f"{'='*80}\n")
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查必要文件
    required_files = ["tech.lef", "cells.lef", "design.v", "floorplan.def"]
    missing_files = []
    for f in required_files:
        if not (design_dir / f).exists():
            missing_files.append(f)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    
    print(f"✓ 设计目录: {design_dir}")
    print(f"✓ 输出目录: {output_dir}")
    print(f"✓ 必要文件检查通过\n")
    
    # 初始化 OpenROAD 接口（使用默认配置，无分区）
    openroad_interface = OpenRoadInterface(
        binary_path="openroad",
        timeout=None,  # 不设置超时
        use_api=True,
        threads=None  # 使用默认线程配置
    )
    
    # 生成输出 DEF 路径
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_def = output_dir / f"{design_name}_layout_{timestamp}.def"
    
    # 生成 TCL 脚本并运行 OpenROAD
    print("生成 TCL 脚本...")
    try:
        tcl_script = openroad_interface._generate_tcl_script(
            design_dir,
            str(design_dir / "floorplan.def"),
            str(output_def)
        )
        print(f"✓ TCL 脚本已生成: {tcl_script}\n")
    except Exception as e:
        print(f"❌ TCL 脚本生成失败: {e}")
        return False
    
    # 运行 OpenROAD
    print("开始运行 OpenROAD（这可能需要一些时间）...")
    start_time = time.time()
    
    try:
        output_def_path, layout_info = openroad_interface._run_openroad(
            tcl_script,
            str(output_dir)
        )
        
        runtime = time.time() - start_time
        
        if layout_info.get("status") == "success":
            print(f"\n✓ OpenROAD 执行成功！")
            print(f"  运行时间: {layout_info.get('runtime', runtime):.2f} 秒 ({layout_info.get('runtime', runtime)/60:.2f} 分钟)")
            print(f"  输出 DEF: {output_def_path}")
            
            # 提取 HPWL（从 layout_info 或 DEF 文件）
            hpwl = layout_info.get('hpwl')
            if hpwl is None and output_def_path and Path(output_def_path).exists():
                try:
                    from src.utils.def_parser import DEFParser
                    parser = DEFParser(str(output_def_path))
                    parser.parse()
                    hpwl = parser.calculate_hpwl()
                except Exception as e:
                    print(f"  ⚠️  HPWL 提取失败: {e}")
            
            if hpwl:
                print(f"  HPWL: {hpwl:.2f} um")
            
            # 保存结果摘要
            summary_file = output_dir / f"{design_name}_summary_{timestamp}.txt"
            with open(summary_file, 'w') as f:
                f.write(f"设计名称: {design_name}\n")
                f.write(f"运行时间: {layout_info.get('runtime', runtime):.2f} 秒\n")
                if hpwl:
                    f.write(f"HPWL: {hpwl:.2f} um\n")
                f.write(f"输出 DEF: {output_def_path}\n")
                f.write(f"TCL 脚本: {tcl_script}\n")
                if 'log_files' in layout_info:
                    f.write(f"\n日志文件:\n")
                    for log_type, log_path in layout_info['log_files'].items():
                        f.write(f"  {log_type}: {log_path}\n")
            print(f"  结果摘要: {summary_file}")
            
            # 日志文件信息
            if 'log_files' in layout_info:
                print(f"  日志文件:")
                for log_type, log_path in layout_info['log_files'].items():
                    print(f"    {log_type}: {log_path}")
            
            return True
        else:
            print(f"\n❌ OpenROAD 执行失败")
            error_msg = layout_info.get('error', 'Unknown error')
            print(f"  错误信息: {error_msg}")
            print(f"  运行时间: {layout_info.get('runtime', runtime):.2f} 秒")
            
            # 保存错误日志
            error_log = logs_dir / f"openroad_error_{timestamp}.log"
            with open(error_log, 'w') as f:
                f.write(f"设计名称: {design_name}\n")
                f.write(f"运行时间: {layout_info.get('runtime', runtime):.2f} 秒\n")
                f.write(f"错误信息: {error_msg}\n")
                if 'log_files' in layout_info:
                    f.write(f"\n详细日志:\n")
                    for log_type, log_path in layout_info['log_files'].items():
                        f.write(f"  {log_type}: {log_path}\n")
            print(f"  错误日志: {error_log}")
            
            return False
            
    except Exception as e:
        runtime = time.time() - start_time
        print(f"\n❌ OpenROAD 执行异常: {e}")
        print(f"  运行时间: {runtime:.2f} 秒")
        
        # 保存异常日志
        error_log = logs_dir / f"openroad_exception_{timestamp}.log"
        with open(error_log, 'w') as f:
            f.write(f"设计名称: {design_name}\n")
            f.write(f"运行时间: {runtime:.2f} 秒\n")
            f.write(f"异常信息: {str(e)}\n")
        print(f"  异常日志: {error_log}")
        
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 run_clean_openroad.py <design_name>")
        print("示例: python3 run_clean_openroad.py mgc_fft_1")
        sys.exit(1)
    
    design_name = sys.argv[1]
    
    # 设置路径
    base_dir = Path(__file__).parent.parent
    design_dir = base_dir / "data" / "dataset" / "ispd_2015_contest_benchmark" / design_name
    output_dir = base_dir / "results" / "reference_runs" / design_name
    
    if not design_dir.exists():
        print(f"❌ 设计目录不存在: {design_dir}")
        sys.exit(1)
    
    # 运行 OpenROAD
    success = run_clean_openroad(design_name, design_dir, output_dir)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

