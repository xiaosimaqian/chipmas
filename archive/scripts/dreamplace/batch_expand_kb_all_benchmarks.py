"""
批量扩展知识库 - 处理所有benchmark类型
按优先级和规模分批处理，避免资源冲突
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_benchmark_priority() -> List[Dict[str, any]]:
    """
    获取benchmark类型及其优先级
    优先级考虑：设计数量、重要性、处理时间
    """
    benchmarks = [
        # 小规模，快速完成
        {'type': 'ispd2005free', 'count': 8, 'priority': 1, 'description': 'ISPD2005 Free (小规模)'},
        {'type': 'iccad2014', 'count': 7, 'priority': 2, 'description': 'ICCAD2014 (中等规模)'},
        {'type': 'dac2012', 'count': 10, 'priority': 3, 'description': 'DAC2012 (中等规模)'},
        {'type': 'iccad2015.ot', 'count': 8, 'priority': 4, 'description': 'ICCAD2015.ot (中等规模)'},
        {'type': 'ispd2019', 'count': 10, 'priority': 5, 'description': 'ISPD2019 (中等规模)'},
        # 大规模，需要更多时间
        {'type': 'ispd2005', 'count': 24, 'priority': 6, 'description': 'ISPD2005 (大规模)'},
        {'type': 'mms', 'count': 16, 'priority': 7, 'description': 'MMS (大规模)'},
    ]
    return sorted(benchmarks, key=lambda x: x['priority'])


def check_running_processes(remote_server: str, remote_user: str) -> bool:
    """检查是否有DREAMPlace进程正在运行"""
    try:
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        cmd = f"{ssh_cmd} 'ps aux | grep -E \"Placer.py|run_dreamplace_batch\" | grep -v grep | wc -l'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        count = int(result.stdout.strip())
        return count > 0
    except:
        return False


def run_benchmark_batch(
    remote_server: str,
    remote_user: str,
    benchmark_type: str,
    config_file: str = 'configs/default.yaml',
    log_file: str = None
) -> int:
    """
    运行单个benchmark类型的批量处理
    
    Returns:
        进程ID或0（如果失败）
    """
    if log_file is None:
        log_file = f'/tmp/dreamplace_{benchmark_type}.log'
    
    script_path = 'scripts/run_dreamplace_batch.py'
    cmd = (
        f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server} "
        f"'cd ~/chipmas && nohup python3 {script_path} "
        f"--remote-server {remote_server} "
        f"--remote-user {remote_user} "
        f"--benchmark-type {benchmark_type} "
        f"--config {config_file} "
        f"> {log_file} 2>&1 & echo \$!'"
    )
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            pid = result.stdout.strip()
            if pid.isdigit():
                return int(pid)
    except Exception as e:
        print(f"启动失败: {e}")
    
    return 0


def check_kb_progress(remote_server: str, remote_user: str) -> Dict[str, int]:
    """检查知识库当前进度"""
    try:
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        cmd = f"{ssh_cmd} 'cd ~/chipmas && python3 -c \\\"import json; from pathlib import Path; kb_file = Path(\\\"data/knowledge_base/kb_cases.json\\\"); data = json.load(open(kb_file)) if kb_file.exists() else []; cases = data if isinstance(data, list) else data.get(\\\"cases\\\", []); print(len(cases))\\\"'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        count = int(result.stdout.strip())
        return {'total_cases': count}
    except:
        return {'total_cases': 0}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='批量扩展知识库 - 处理所有benchmark类型')
    parser.add_argument('--remote-server', type=str, required=True,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default='keqin',
                       help='远程用户')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--benchmark-type', type=str, default=None,
                       help='只处理特定benchmark类型（不指定则处理所有）')
    parser.add_argument('--max-concurrent', type=int, default=2,
                       help='最大并发数（默认2，避免资源冲突）')
    parser.add_argument('--wait-between', type=int, default=300,
                       help='批次之间等待时间（秒，默认5分钟）')
    parser.add_argument('--dry-run', action='store_true',
                       help='只显示计划，不实际运行')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("批量扩展知识库 - 处理所有benchmark类型")
    print("=" * 70)
    
    # 获取benchmark列表
    benchmarks = get_benchmark_priority()
    
    if args.benchmark_type:
        benchmarks = [b for b in benchmarks if b['type'] == args.benchmark_type]
        if not benchmarks:
            print(f"错误: 未找到benchmark类型: {args.benchmark_type}")
            return
    
    # 显示计划
    print(f"\n计划处理的benchmark类型 ({len(benchmarks)}个):")
    total_designs = 0
    for i, bench in enumerate(benchmarks, 1):
        print(f"  {i}. {bench['type']}: {bench['count']}个设计 - {bench['description']}")
        total_designs += bench['count']
    
    print(f"\n总计: {total_designs}个设计")
    
    # 检查当前知识库状态
    progress = check_kb_progress(args.remote_server, args.remote_user)
    print(f"\n当前知识库: {progress['total_cases']}个案例")
    
    if args.dry_run:
        print("\n[DRY RUN] 只显示计划，不实际运行")
        return
    
    # 检查是否有正在运行的进程
    if check_running_processes(args.remote_server, args.remote_user):
        print("\n⚠️  检测到有DREAMPlace进程正在运行")
        response = input("是否继续？(y/n): ")
        if response.lower() != 'y':
            print("已取消")
            return
    
    # 按优先级处理
    print(f"\n开始处理...")
    print(f"最大并发数: {args.max_concurrent}")
    print(f"批次间隔: {args.wait_between}秒")
    
    running_pids = {}
    
    for i, bench in enumerate(benchmarks):
        bench_type = bench['type']
        print(f"\n[{i+1}/{len(benchmarks)}] 处理: {bench_type} ({bench['count']}个设计)")
        
        # 检查并发数
        while len(running_pids) >= args.max_concurrent:
            print(f"  等待中... (当前运行: {len(running_pids)}个)")
            time.sleep(60)  # 等待1分钟
            # 清理已完成的进程
            running_pids = {k: v for k, v in running_pids.items() 
                          if check_running_processes(args.remote_server, args.remote_user)}
        
        # 启动新批次
        pid = run_benchmark_batch(
            args.remote_server,
            args.remote_user,
            bench_type,
            args.config
        )
        
        if pid > 0:
            running_pids[bench_type] = pid
            print(f"  ✓ 已启动 (PID: {pid})")
        else:
            print(f"  ✗ 启动失败")
        
        # 如果不是最后一个，等待一段时间
        if i < len(benchmarks) - 1:
            print(f"  等待 {args.wait_between}秒后处理下一个批次...")
            time.sleep(args.wait_between)
    
    print(f"\n所有批次已启动！")
    print(f"正在运行: {list(running_pids.keys())}")
    print(f"\n监控命令:")
    print(f"  ssh {args.remote_user}@{args.remote_server} 'ps aux | grep Placer.py | grep -v grep'")
    print(f"\n查看日志:")
    for bench_type in running_pids.keys():
        print(f"  ssh {args.remote_user}@{args.remote_server} 'tail -f /tmp/dreamplace_{bench_type}.log'")


if __name__ == '__main__':
    main()



