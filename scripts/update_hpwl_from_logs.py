#!/usr/bin/env python3
"""
重新从日志文件中提取HPWL并更新result.json

用途：修复之前由于正则表达式错误导致HPWL为null的问题
"""

import json
import re
from pathlib import Path


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


def main():
    project_root = Path(__file__).parent.parent
    baseline_dir = project_root / 'results' / 'clean_baseline'
    
    if not baseline_dir.exists():
        print(f"❌ 目录不存在: {baseline_dir}")
        return
    
    print("=" * 80)
    print("重新提取HPWL数据")
    print("=" * 80)
    print()
    
    updated_count = 0
    skipped_count = 0
    
    for design_dir in sorted(baseline_dir.iterdir()):
        if not design_dir.is_dir():
            continue
        
        design_name = design_dir.name
        result_file = design_dir / 'result.json'
        
        if not result_file.exists():
            continue
        
        # 读取现有结果
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        # 只处理成功的设计
        if result.get('status') != 'success':
            continue
        
        # 如果已有HPWL数据，跳过
        if result.get('legalized_hpwl') is not None:
            print(f"⏭️  {design_name}: 已有HPWL数据，跳过")
            skipped_count += 1
            continue
        
        # 查找日志文件
        log_file = result.get('log_file')
        if not log_file:
            logs_dir = design_dir / 'logs'
            if logs_dir.exists():
                log_files = list(logs_dir.glob('*.log'))
                if log_files:
                    log_file = str(log_files[-1])  # 使用最新的日志
        
        if not log_file:
            print(f"❌ {design_name}: 找不到日志文件")
            continue
        
        log_path = Path(log_file) if Path(log_file).is_absolute() else project_root / log_file
        
        if not log_path.exists():
            print(f"❌ {design_name}: 日志文件不存在 - {log_path}")
            continue
        
        # 读取日志并提取HPWL
        with open(log_path, 'r') as f:
            log_content = f.read()
        
        hpwl_data = extract_hpwl_from_log(log_content)
        
        if hpwl_data:
            # 更新结果
            result.update(hpwl_data)
            
            # 保存
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"✅ {design_name}:")
            if 'global_placement_hpwl' in hpwl_data:
                print(f"   Global Placement HPWL: {hpwl_data['global_placement_hpwl']:,.1f}")
            if 'legalized_hpwl' in hpwl_data:
                print(f"   Legalized HPWL:        {hpwl_data['legalized_hpwl']:,.1f}")
            
            updated_count += 1
        else:
            print(f"⚠️  {design_name}: 日志中未找到HPWL数据")
    
    print()
    print("=" * 80)
    print(f"✅ 更新: {updated_count}")
    print(f"⏭️  跳过: {skipped_count}")
    print("=" * 80)


if __name__ == '__main__':
    main()

