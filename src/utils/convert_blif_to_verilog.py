#!/usr/bin/env python3
"""
将 BLIF 格式转换为 Verilog 格式的工具
用于将 titan23 的 BLIF 网表转换为 OpenROAD 可用的 Verilog
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path


def convert_blif_to_verilog_yosys(blif_file: str, output_verilog: str, liberty_file: str = None) -> bool:
    """
    使用 yosys 将 BLIF 转换为 Verilog，并尝试综合到标准单元
    
    Args:
        blif_file: 输入的 BLIF 文件路径
        output_verilog: 输出的 Verilog 文件路径
        liberty_file: 标准单元库文件路径（.lib格式，可选）
    
    Returns:
        True if successful, False otherwise
    """
    # 构建 yosys 脚本
    # 参考: https://github.com/YosysHQ/yosys
    yosys_script = f"""
# 读取 BLIF 文件
read_blif {blif_file}

# 清理设计
proc; opt; memory; opt; fsm; opt

# 获取顶层模块名（BLIF 文件中的 .model 名称）
hierarchy -auto-top

# 尝试将 FPGA 原语转换为通用逻辑
# 使用 techmap 多次迭代，尽可能转换所有原语
techmap; opt
techmap; opt

# 如果还有未映射的原语，尝试使用 memory 命令处理
memory -nomap

# 再次 techmap 和优化
techmap; opt

# 如果提供了 liberty 文件，映射到标准单元库
"""
    
    # 如果提供了 liberty 文件，添加映射步骤
    if liberty_file and os.path.exists(liberty_file):
        yosys_script += f"""
# 读取标准单元库
read_liberty {liberty_file}

# 映射触发器到标准单元库
dfflibmap -liberty {liberty_file}

# 映射组合逻辑到标准单元库
abc -liberty {liberty_file}

# 清理
clean
"""
    else:
        # 如果没有 liberty 文件，只做通用综合
        yosys_script += """
# 没有 liberty 文件，只做通用综合
# 输出将是通用逻辑门（AND, OR, NOT 等）
"""
    
    yosys_script += f"""
# 最终优化
opt -fast

# 写入 Verilog
write_verilog {output_verilog}
"""
    
    try:
        result = subprocess.run(
            ['yosys', '-q', '-s', '/dev/stdin'],
            input=yosys_script.encode(),
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Yosys 转换失败: {e}", file=sys.stderr)
        print(f"错误输出: {e.stderr.decode()}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("错误: 找不到 yosys 命令，请先安装 yosys", file=sys.stderr)
        return False


def convert_blif_to_verilog_simple(blif_file: str, output_verilog: str) -> bool:
    """
    简单的 BLIF 到 Verilog 转换（仅处理基本语法）
    这是一个简化版本，可能不适用于所有 BLIF 文件
    
    Args:
        blif_file: 输入的 BLIF 文件路径
        output_verilog: 输出的 Verilog 文件路径
    
    Returns:
        True if successful, False otherwise
    """
    # 这是一个占位符实现
    # 完整的 BLIF 到 Verilog 转换需要解析 BLIF 语法
    print("警告: 简单的 BLIF 转换器尚未实现", file=sys.stderr)
    print("建议使用 yosys 进行转换", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(
        description='将 BLIF 格式转换为 Verilog 格式'
    )
    parser.add_argument(
        'blif_file',
        type=str,
        help='输入的 BLIF 文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='输出的 Verilog 文件路径（默认为输入文件名.v）'
    )
    parser.add_argument(
        '--method',
        type=str,
        choices=['yosys', 'simple'],
        default='yosys',
        help='转换方法（默认: yosys）'
    )
    parser.add_argument(
        '--liberty',
        type=str,
        help='标准单元库文件路径（.lib格式，用于综合到标准单元）'
    )
    
    args = parser.parse_args()
    
    blif_path = Path(args.blif_file)
    if not blif_path.exists():
        print(f"错误: 文件不存在: {args.blif_file}", file=sys.stderr)
        sys.exit(1)
    
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = blif_path.with_suffix('.v')
    
    print(f"转换 {blif_path} -> {output_path}")
    
    if args.method == 'yosys':
        success = convert_blif_to_verilog_yosys(str(blif_path), str(output_path), args.liberty)
    else:
        success = convert_blif_to_verilog_simple(str(blif_path), str(output_path))
    
    if success:
        print(f"✓ 转换成功: {output_path}")
        sys.exit(0)
    else:
        print(f"✗ 转换失败", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

