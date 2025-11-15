#!/usr/bin/env python3
"""
使用最新的日志更新result.json

根据日志时间戳，只使用最新的日志文件提取HPWL
"""

import json
import re
from pathlib import Path
from datetime import datetime


def get_latest_log(log_dir):
    """获取最新的日志文件"""
    if not log_dir.exists():
        return None
    
    log_files = list(log_dir.glob("openroad_*.log"))
    if not log_files:
        return None
    
    # 按修改时间排序，返回最新的
    latest = max(log_files, key=lambda x: x.stat().st_mtime)
    return latest


def extract_hpwl_from_log(log_file):
    """从日志文件中提取HPWL"""
    if not log_file.exists():
        return None, None
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
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


def check_log_success(log_file):
    """检查日志是否显示成功完成"""
    if not log_file.exists():
        return False
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 检查成功标志
    if "Clean Baseline布局完成:" in content:
        return True
    
    # 检查错误标志
    if "Error:" in content or "[ERROR" in content:
        return False
    
    return False


def update_result_json(result_file, status, global_hpwl, legalized_hpwl, log_file, runtime=None):
    """更新result.json文件"""
    with open(result_file, 'r') as f:
        data = json.load(f)
    
    data['status'] = status
    data['global_placement_hpwl'] = global_hpwl
    data['legalized_hpwl'] = legalized_hpwl
    data['hpwl'] = legalized_hpwl
    data['log_file'] = str(log_file)
    
    if status == 'success':
        data['error'] = None
    
    # 如果有运行时间信息，更新
    if runtime is not None:
        data['runtime_seconds'] = runtime
    
    with open(result_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data


def get_log_timestamp(log_file):
    """从日志文件名提取时间戳"""
    # openroad_20251114_164428.log -> 2025-11-14 16:44:28
    match = re.search(r'openroad_(\d{8})_(\d{6})\.log', log_file.name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
    return None


def main():
    baseline_dir = Path("results/clean_baseline")
    
    if not baseline_dir.exists():
        print(f"❌ 结果目录不存在: {baseline_dir}")
        return
    
    print("🔍 扫描最新日志并更新结果...\n")
    
    updated_count = 0
    success_count = 0
    fail_count = 0
    
    for design_dir in sorted(baseline_dir.iterdir()):
        if not design_dir.is_dir():
            continue
        
        result_file = design_dir / "result.json"
        if not result_file.exists():
            continue
        
        design_name = design_dir.name
        
        # 获取最新的日志文件
        log_dir = design_dir / "logs"
        if not log_dir.exists():
            print(f"⚠️  {design_name}: 未找到logs目录")
            continue
        
        latest_log = get_latest_log(log_dir)
        if not latest_log:
            print(f"⚠️  {design_name}: 未找到日志文件")
            continue
        
        # 获取时间戳
        timestamp = get_log_timestamp(latest_log)
        log_time_str = timestamp if timestamp else latest_log.stat().st_mtime
        
        # 检查是否成功
        is_success = check_log_success(latest_log)
        
        if is_success:
            # 提取HPWL
            global_hpwl, legalized_hpwl = extract_hpwl_from_log(latest_log)
            
            if legalized_hpwl is None:
                print(f"⚠️  {design_name}: 标记成功但未找到HPWL")
                print(f"    日志: {latest_log.name} ({log_time_str})")
                continue
            
            # 更新result.json
            update_result_json(result_file, 'success', global_hpwl, legalized_hpwl, latest_log)
            
            print(f"✅ {design_name}: 成功")
            print(f"    日志: {latest_log.name} ({log_time_str})")
            print(f"    Global HPWL: {global_hpwl:,.1f}" if global_hpwl else "    Global HPWL: N/A")
            print(f"    Legalized HPWL: {legalized_hpwl:,.1f}")
            if global_hpwl:
                print(f"    Delta: {((legalized_hpwl - global_hpwl) / global_hpwl * 100):+.1f}%")
            print()
            
            success_count += 1
        else:
            # 失败的设计
            update_result_json(result_file, 'error', None, None, latest_log)
            
            print(f"❌ {design_name}: 失败")
            print(f"    日志: {latest_log.name} ({log_time_str})")
            print()
            
            fail_count += 1
        
        updated_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"✅ 完成！处理了 {updated_count} 个设计")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")
    print(f"{'=' * 60}")
    print("\n💡 现在可以重新运行: python3 scripts/parse_clean_baseline_results.py")


if __name__ == "__main__":
    main()

