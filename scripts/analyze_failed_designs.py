#!/usr/bin/env python3
"""
分析失败设计的具体错误原因
"""

import re
from pathlib import Path


def analyze_log(log_file):
    """分析单个日志文件"""
    if not log_file.exists():
        return {"status": "no_log", "error": None}
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 检查是否完成
    if "Clean Baseline布局完成:" in content:
        return {"status": "success", "error": None}
    
    # 查找错误信息
    errors = []
    
    # GPL-0001: port not placed
    gpl_0001 = re.findall(r'\[ERROR GPL-0001\] (.+?) toplevel port is not placed', content)
    if gpl_0001:
        errors.append({
            "type": "GPL-0001",
            "message": "Toplevel ports not placed",
            "details": f"{len(gpl_0001)} ports: {', '.join(gpl_0001[:5])}" + ("..." if len(gpl_0001) > 5 else "")
        })
    
    # PPL errors
    ppl_errors = re.findall(r'\[ERROR PPL-\d+\] (.+)', content)
    if ppl_errors:
        errors.append({
            "type": "PPL",
            "message": "Pin placement error",
            "details": ppl_errors[0]
        })
    
    # ODB errors
    odb_errors = re.findall(r'\[ERROR ODB-\d+\] (.+)', content)
    if odb_errors:
        errors.append({
            "type": "ODB",
            "message": "Database error",
            "details": odb_errors[0]
        })
    
    # 通用错误
    general_errors = re.findall(r'Error: (.+)', content)
    if general_errors and not errors:
        errors.append({
            "type": "GENERAL",
            "message": "General error",
            "details": general_errors[0]
        })
    
    if not errors:
        # 检查是否还在运行
        if "[NesterovSolve]" in content and "Clean Baseline布局完成:" not in content:
            return {"status": "running", "error": None}
        return {"status": "unknown", "error": None}
    
    return {"status": "error", "error": errors}


def count_ports(verilog_file):
    """统计设计的端口数量"""
    if not verilog_file.exists():
        return None
    
    with open(verilog_file, 'r', encoding='utf-8', errors='ignore') as f:
        first_line = f.readline()
    
    # 统计端口数量（简单估计）
    ports = first_line.count(',') + 1
    return ports


def main():
    baseline_dir = Path("results/clean_baseline")
    data_dir = Path("data/ispd2015")
    
    print("🔍 分析失败设计的错误原因\n")
    print("=" * 80)
    
    failed_designs = []
    
    for design_dir in sorted(baseline_dir.iterdir()):
        if not design_dir.is_dir():
            continue
        
        design_name = design_dir.name
        
        # 找最新的日志
        log_dir = design_dir / "logs"
        if not log_dir.exists():
            continue
        
        log_files = sorted(log_dir.glob("openroad_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not log_files:
            continue
        
        latest_log = log_files[0]
        
        # 分析日志
        result = analyze_log(latest_log)
        
        if result["status"] in ["error", "running"]:
            # 统计端口数
            verilog_file = data_dir / design_name / "design.v"
            port_count = count_ports(verilog_file)
            
            failed_designs.append({
                "name": design_name,
                "status": result["status"],
                "error": result["error"],
                "port_count": port_count,
                "log": latest_log.name
            })
    
    # 按状态分组
    errors_by_type = {}
    running = []
    
    for design in failed_designs:
        if design["status"] == "running":
            running.append(design)
        elif design["error"]:
            error_type = design["error"][0]["type"]
            if error_type not in errors_by_type:
                errors_by_type[error_type] = []
            errors_by_type[error_type].append(design)
    
    # 输出报告
    print("\n📊 失败设计统计\n")
    print(f"总计失败/运行中: {len(failed_designs)}")
    print(f"  - 运行中: {len(running)}")
    print(f"  - 错误: {len(failed_designs) - len(running)}")
    print()
    
    if running:
        print("⏳ 运行中的设计:")
        for d in running:
            print(f"  - {d['name']} (端口数: {d['port_count'] if d['port_count'] else 'N/A'})")
            print(f"    日志: {d['log']}")
        print()
    
    print("❌ 错误类型分布:")
    for error_type, designs in errors_by_type.items():
        print(f"\n  {error_type}: {len(designs)} 个设计")
        for d in designs:
            print(f"    - {d['name']} (端口数: {d['port_count'] if d['port_count'] else 'N/A'})")
            if d['error']:
                print(f"      错误: {d['error'][0]['message']}")
                print(f"      详情: {d['error'][0]['details']}")
    
    print("\n" + "=" * 80)
    
    # 生成修复建议
    print("\n💡 修复建议:\n")
    
    if "GPL-0001" in errors_by_type:
        gpl_designs = errors_by_type["GPL-0001"]
        port_counts = [d['port_count'] for d in gpl_designs if d['port_count']]
        
        print("1. GPL-0001 错误（端口未放置）:")
        print(f"   影响设计: {len(gpl_designs)} 个")
        if port_counts:
            print(f"   端口数量范围: {min(port_counts)} - {max(port_counts)}")
        print("   可能原因:")
        print("   - place_pins命令未能处理所有端口")
        print("   - 端口数量过多或命名特殊")
        print("   建议方案:")
        print("   a) 检查TCL脚本中的端口放置命令")
        print("   b) 尝试不同的端口放置策略（如按区域放置）")
        print("   c) 检查是否有特殊端口（如时钟）需要单独处理")
        print()
    
    if "PPL" in errors_by_type:
        print("2. PPL 错误（Pin placement）:")
        print(f"   影响设计: {len(errors_by_type['PPL'])} 个")
        print("   建议: 调整pin placement参数")
        print()
    
    # 保存详细报告
    report_file = Path("EXP-002_FAILURE_ANALYSIS.md")
    with open(report_file, 'w') as f:
        f.write("# EXP-002 失败设计分析报告\n\n")
        f.write(f"生成时间: {Path().absolute()}\n\n")
        f.write("## 概览\n\n")
        f.write(f"- 总计: {len(failed_designs)} 个设计\n")
        f.write(f"- 运行中: {len(running)}\n")
        f.write(f"- 失败: {len(failed_designs) - len(running)}\n\n")
        
        if running:
            f.write("## 运行中的设计\n\n")
            for d in running:
                f.write(f"### {d['name']}\n")
                f.write(f"- 端口数: {d['port_count'] if d['port_count'] else 'N/A'}\n")
                f.write(f"- 日志: `{d['log']}`\n\n")
        
        f.write("## 失败的设计\n\n")
        for error_type, designs in errors_by_type.items():
            f.write(f"### {error_type} 错误\n\n")
            for d in designs:
                f.write(f"#### {d['name']}\n")
                f.write(f"- 端口数: {d['port_count'] if d['port_count'] else 'N/A'}\n")
                if d['error']:
                    f.write(f"- 错误类型: {d['error'][0]['type']}\n")
                    f.write(f"- 错误消息: {d['error'][0]['message']}\n")
                    f.write(f"- 详情: `{d['error'][0]['details']}`\n")
                f.write(f"- 日志: `{d['log']}`\n\n")
    
    print(f"✅ 详细报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

