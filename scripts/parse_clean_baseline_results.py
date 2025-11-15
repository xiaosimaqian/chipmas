#!/usr/bin/env python3
"""
解析Clean Baseline实验结果并更新WORK_SUMMARY_AND_PLAN.md

使用方法:
1. 先同步服务器结果: 
   rsync -avz keqin@172.30.31.98:~/chipmas/results/clean_baseline/ results/clean_baseline/
2. 运行此脚本:
   python3 scripts/parse_clean_baseline_results.py
"""

import json
import os
from pathlib import Path
from datetime import datetime


def parse_results():
    """解析所有result.json文件"""
    baseline_dir = Path("results/clean_baseline")
    
    if not baseline_dir.exists():
        print(f"❌ 结果目录不存在: {baseline_dir}")
        print("请先执行: rsync -avz keqin@172.30.31.98:~/chipmas/results/clean_baseline/ results/clean_baseline/")
        return None
    
    # 读取summary.json
    summary_file = baseline_dir / "summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        print(f"📊 Summary文件时间戳: {summary.get('timestamp', 'N/A')}")
        print(f"   总计: {summary.get('total', 0)}, 成功: {summary.get('success', 0)}, 失败: {summary.get('fail', 0)}")
    else:
        summary = None
        print("⚠️  未找到summary.json")
    
    # 收集所有设计的结果
    results = []
    
    # 遍历所有设计目录
    for design_dir in sorted(baseline_dir.iterdir()):
        if not design_dir.is_dir():
            continue
        
        result_file = design_dir / "result.json"
        if not result_file.exists():
            continue
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        results.append(result)
    
    # 按组件数排序
    results.sort(key=lambda x: x.get('component_count', 0))
    
    return {
        'summary': summary,
        'results': results,
        'total': len(results),
        'success': sum(1 for r in results if r.get('status') == 'success'),
        'fail': sum(1 for r in results if r.get('status') == 'error')
    }


def format_die_size(die_area_str):
    """格式化die size为更易读的形式"""
    # "0 0 5000 5000" -> "5000×5000"
    parts = die_area_str.strip().split()
    if len(parts) == 4:
        width = int(parts[2]) - int(parts[0])
        height = int(parts[3]) - int(parts[1])
        return f"{width}×{height}"
    return die_area_str


def format_core_area(core_area_str):
    """格式化core area"""
    parts = core_area_str.strip().split()
    if len(parts) == 4:
        width = int(parts[2]) - int(parts[0])
        height = int(parts[3]) - int(parts[1])
        return f"{width}×{height}"
    return core_area_str


def generate_markdown_table(data):
    """生成Markdown表格"""
    if not data or not data['results']:
        return "❌ 无结果数据"
    
    # 统计信息
    total = data['total']
    success = data['success']
    fail = data['fail']
    success_rate = (success / total * 100) if total > 0 else 0
    
    # 表格头
    lines = []
    lines.append(f"\n**✅ 运行结果：{success}/{total} 成功 ({success_rate:.1f}%)**\n")
    
    if success > 0:
        lines.append("### 成功的设计\n")
        lines.append("| # | 设计 | 组件数 | 网络数 | Die Size | Core Area | Global HPWL | Legalized HPWL | Delta | 运行时间 |")
        lines.append("|---|------|--------|--------|----------|-----------|-------------|----------------|-------|----------|")
        
        idx = 1
        for result in data['results']:
            if result.get('status') != 'success':
                continue
            
            design = result['design']
            components = f"{result['component_count']:,}"
            nets = f"{result['net_count']:,}"
            
            die_size_info = result.get('die_size_used', {})
            die_size = format_die_size(die_size_info.get('die_area', 'N/A'))
            core_area = format_core_area(die_size_info.get('core_area', 'N/A'))
            
            global_hpwl = result.get('global_placement_hpwl')
            legalized_hpwl = result.get('legalized_hpwl')
            
            global_hpwl_str = f"{global_hpwl:,.1f}" if global_hpwl else "N/A"
            legalized_hpwl_str = f"{legalized_hpwl:,.1f}" if legalized_hpwl else "N/A"
            
            # 计算delta
            if global_hpwl and legalized_hpwl:
                delta = ((legalized_hpwl - global_hpwl) / global_hpwl) * 100
                delta_str = f"{delta:+.1f}%"
            else:
                delta_str = "N/A"
            
            runtime = result.get('runtime_seconds', 0)
            if runtime < 60:
                runtime_str = f"{runtime:.1f}s"
            elif runtime < 3600:
                runtime_str = f"{runtime/60:.1f}m"
            else:
                runtime_str = f"{runtime/3600:.1f}h"
            
            lines.append(f"| {idx} | {design} | {components} | {nets} | {die_size} | {core_area} | {global_hpwl_str} | {legalized_hpwl_str} | {delta_str} | {runtime_str} |")
            idx += 1
        
        # 添加路径信息
        lines.append("\n**文件路径**:\n")
        for result in data['results']:
            if result.get('status') != 'success':
                continue
            design = result['design']
            output_def = result.get('output_def', 'N/A')
            log_file = result.get('log_file', 'N/A')
            tcl_file = result.get('tcl_file', 'N/A')
            lines.append(f"- **{design}**:")
            lines.append(f"  - DEF输出: `{output_def}`")
            lines.append(f"  - 日志: `{log_file}`")
            lines.append(f"  - TCL: `{tcl_file}`")
    
    if fail > 0:
        lines.append("\n### 失败的设计\n")
        lines.append("| # | 设计 | 组件数 | 网络数 | Die Size | 运行时间 | 错误 |")
        lines.append("|---|------|--------|--------|----------|---------|------|")
        
        idx = 1
        for result in data['results']:
            if result.get('status') != 'error':
                continue
            
            design = result['design']
            components = f"{result['component_count']:,}"
            nets = f"{result['net_count']:,}"
            
            die_size_info = result.get('die_size_used', {})
            die_size = format_die_size(die_size_info.get('die_area', 'N/A'))
            
            runtime = result.get('runtime_seconds', 0)
            runtime_str = f"{runtime:.1f}s" if runtime < 60 else f"{runtime/60:.1f}m"
            
            error = result.get('error', 'Unknown')
            
            lines.append(f"| {idx} | {design} | {components} | {nets} | {die_size} | {runtime_str} | {error} |")
            idx += 1
    
    # 添加时间戳
    if data['summary']:
        timestamp = data['summary'].get('timestamp', 'Unknown')
        lines.append(f"\n**实验时间**: {timestamp}")
    
    return '\n'.join(lines)


def main():
    print("🔍 解析Clean Baseline结果...")
    print()
    
    data = parse_results()
    
    if not data:
        return
    
    print()
    print("=" * 80)
    print("📊 结果汇总")
    print("=" * 80)
    
    table = generate_markdown_table(data)
    print(table)
    
    print()
    print("=" * 80)
    
    # 保存到文件
    output_file = Path("EXP-002_RESULTS.md")
    with open(output_file, 'w') as f:
        f.write("# EXP-002: ISPD 2015 Clean Baseline 结果\n\n")
        f.write(table)
    
    print(f"✅ 结果已保存到: {output_file}")
    print()
    print("💡 提示：可以将生成的Markdown表格复制到 WORK_SUMMARY_AND_PLAN.md 中")


if __name__ == "__main__":
    main()

