#!/usr/bin/env python3
"""
从OpenROAD日志中提取HPWL并更新result.json

使用方法:
python3 scripts/extract_hpwl_from_logs.py
"""

import json
import re
from pathlib import Path


def extract_hpwl_from_log(log_file):
    """从日志文件中提取HPWL"""
    if not log_file.exists():
        return None, None
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 查找 "original HPWL" 和 "legalized HPWL"
    # original HPWL         2550024.0 u
    # legalized HPWL        2630765.5 u
    
    global_hpwl = None
    legalized_hpwl = None
    
    # 匹配模式
    global_pattern = r'original HPWL\s+([\d.]+)\s+u'
    legalized_pattern = r'legalized HPWL\s+([\d.]+)\s+u'
    
    global_match = re.search(global_pattern, content)
    legalized_match = re.search(legalized_pattern, content)
    
    if global_match:
        global_hpwl = float(global_match.group(1))
    
    if legalized_match:
        legalized_hpwl = float(legalized_match.group(1))
    
    return global_hpwl, legalized_hpwl


def update_result_json(result_file, global_hpwl, legalized_hpwl):
    """更新result.json文件"""
    with open(result_file, 'r') as f:
        data = json.load(f)
    
    data['global_placement_hpwl'] = global_hpwl
    data['legalized_hpwl'] = legalized_hpwl
    data['hpwl'] = legalized_hpwl  # hpwl字段也设置为legalized_hpwl
    
    with open(result_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data


def main():
    baseline_dir = Path("results/clean_baseline")
    
    if not baseline_dir.exists():
        print(f"❌ 结果目录不存在: {baseline_dir}")
        return
    
    print("🔍 扫描并更新HPWL数据...\n")
    
    updated_count = 0
    
    for design_dir in sorted(baseline_dir.iterdir()):
        if not design_dir.is_dir():
            continue
        
        result_file = design_dir / "result.json"
        if not result_file.exists():
            continue
        
        # 读取result.json
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        # 只处理成功的设计
        if result.get('status') != 'success':
            continue
        
        design_name = result['design']
        
        # 检查是否已有HPWL数据
        if result.get('legalized_hpwl') is not None:
            print(f"✓ {design_name}: 已有HPWL数据 (legalized={result['legalized_hpwl']:,.1f})")
            continue
        
        # 查找最新的日志文件
        log_dir = design_dir / "logs"
        if not log_dir.exists():
            print(f"⚠️  {design_name}: 未找到logs目录")
            continue
        
        log_files = sorted(log_dir.glob("openroad_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not log_files:
            print(f"⚠️  {design_name}: 未找到日志文件")
            continue
        
        # 使用最新的日志文件
        log_file = log_files[0]
        
        # 提取HPWL
        global_hpwl, legalized_hpwl = extract_hpwl_from_log(log_file)
        
        if legalized_hpwl is None:
            print(f"⚠️  {design_name}: 未能从日志中提取HPWL")
            print(f"    日志文件: {log_file}")
            continue
        
        # 更新result.json
        updated_data = update_result_json(result_file, global_hpwl, legalized_hpwl)
        
        print(f"✅ {design_name}: 已更新HPWL")
        print(f"    Global HPWL: {global_hpwl:,.1f}" if global_hpwl else "    Global HPWL: N/A")
        print(f"    Legalized HPWL: {legalized_hpwl:,.1f}")
        print(f"    Delta: {((legalized_hpwl - global_hpwl) / global_hpwl * 100):+.1f}%" if global_hpwl else "")
        print()
        
        updated_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"✅ 完成！更新了 {updated_count} 个设计的HPWL数据")
    print(f"{'=' * 60}")
    print("\n💡 现在可以重新运行: python3 scripts/parse_clean_baseline_results.py")


if __name__ == "__main__":
    main()

