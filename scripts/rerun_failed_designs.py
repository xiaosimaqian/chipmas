#!/usr/bin/env python3
"""
重新运行失败的设计

只重跑那些失败的设计，跳过已成功和正在运行的
"""

import subprocess
import sys
from pathlib import Path
import time

# 失败的设计列表（从分析结果得出）
FAILED_DESIGNS = [
    "mgc_fft_2",
    "mgc_fft_a", 
    "mgc_fft_b",
    "mgc_matrix_mult_1",
    "mgc_matrix_mult_a",
    "mgc_matrix_mult_b",
    "mgc_pci_bridge32_a",
    "mgc_pci_bridge32_b",
    "mgc_superblue11_a",
    "mgc_superblue12",
    "mgc_superblue16_a"
]

def main():
    print("🔄 重新运行失败的设计")
    print(f"失败设计数量: {len(FAILED_DESIGNS)}")
    print()
    
    # 确认
    print("将重新运行以下设计:")
    for i, design in enumerate(FAILED_DESIGNS, 1):
        print(f"  {i}. {design}")
    print()
    
    response = input("确认重新运行这些设计? (y/N): ")
    if response.lower() != 'y':
        print("已取消")
        return
    
    print("\n" + "=" * 80)
    print("开始重新运行...")
    print("=" * 80 + "\n")
    
    # 调用collect_clean_baseline.py，只处理这些设计
    cmd = [
        "python3",
        "scripts/collect_clean_baseline.py",
        "--output-dir", "results/clean_baseline",
        "--designs"
    ] + FAILED_DESIGNS
    
    print(f"命令: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=Path.cwd())
    
    if result.returncode == 0:
        print("\n✅ 重新运行完成")
    else:
        print(f"\n❌ 重新运行失败，退出码: {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()

