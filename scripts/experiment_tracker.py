#!/usr/bin/env python3
"""
实验跟踪工具
用于记录、更新和查询实验信息
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse


class ExperimentTracker:
    """实验跟踪器"""
    
    def __init__(self, db_path: str = "experiments.json"):
        """
        初始化实验跟踪器
        
        Args:
            db_path: 实验数据库文件路径
        """
        self.db_path = Path(db_path)
        self.experiments = self._load_experiments()
    
    def _load_experiments(self) -> Dict:
        """加载实验数据"""
        if self.db_path.exists():
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"experiments": []}
    
    def _save_experiments(self):
        """保存实验数据"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.experiments, f, indent=2, ensure_ascii=False)
    
    def _generate_exp_id(self) -> str:
        """生成新的实验ID"""
        existing_ids = [exp['id'] for exp in self.experiments['experiments']]
        if not existing_ids:
            return "EXP-001"
        
        # 提取数字部分并找到最大值
        numbers = [int(exp_id.split('-')[1]) for exp_id in existing_ids if exp_id.startswith('EXP-')]
        next_num = max(numbers) + 1 if numbers else 1
        return f"EXP-{next_num:03d}"
    
    def register_experiment(self,
                          name: str,
                          purpose: str,
                          location: str,
                          script: str,
                          **kwargs) -> str:
        """
        登记新实验
        
        Args:
            name: 实验名称
            purpose: 实验目的
            location: 运行位置（服务器/本地）
            script: 运行脚本/命令
            **kwargs: 其他可选参数
        
        Returns:
            实验ID
        """
        exp_id = self._generate_exp_id()
        
        experiment = {
            "id": exp_id,
            "name": name,
            "purpose": purpose,
            "status": "⏳ 计划中",
            "location": location,
            "script": script,
            "registered_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_time": None,
            "end_time": None,
            "duration_seconds": None,
            "pid": kwargs.get('pid'),
            "parallel": kwargs.get('parallel', 1),
            "results": {
                "success_count": 0,
                "fail_count": 0,
                "total_count": 0
            },
            "output_path": kwargs.get('output_path'),
            "log_path": kwargs.get('log_path'),
            "metrics": {},
            "findings": [],
            "issues": [],
            "next_actions": []
        }
        
        self.experiments['experiments'].append(experiment)
        self._save_experiments()
        
        print(f"✅ 实验已登记: {exp_id} - {name}")
        return exp_id
    
    def start_experiment(self, exp_id: str, pid: Optional[int] = None):
        """
        标记实验开始运行
        
        Args:
            exp_id: 实验ID
            pid: 进程ID
        """
        exp = self._find_experiment(exp_id)
        if not exp:
            print(f"❌ 未找到实验: {exp_id}")
            return
        
        exp['status'] = "🚀 运行中"
        exp['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if pid:
            exp['pid'] = pid
        
        self._save_experiments()
        print(f"🚀 实验已启动: {exp_id} - {exp['name']}")
        if pid:
            print(f"   PID: {pid}")
    
    def finish_experiment(self, 
                         exp_id: str,
                         status: str = "✅ 完成",
                         success_count: int = 0,
                         fail_count: int = 0,
                         total_count: int = 0,
                         metrics: Optional[Dict] = None):
        """
        标记实验完成
        
        Args:
            exp_id: 实验ID
            status: 最终状态（✅ 完成 / ⚠️ 部分成功 / ❌ 失败）
            success_count: 成功数量
            fail_count: 失败数量
            total_count: 总数量
            metrics: 核心指标字典
        """
        exp = self._find_experiment(exp_id)
        if not exp:
            print(f"❌ 未找到实验: {exp_id}")
            return
        
        exp['status'] = status
        exp['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 计算运行时间
        if exp['start_time']:
            start = datetime.strptime(exp['start_time'], "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(exp['end_time'], "%Y-%m-%d %H:%M:%S")
            exp['duration_seconds'] = (end - start).total_seconds()
        
        # 更新结果统计
        exp['results']['success_count'] = success_count
        exp['results']['fail_count'] = fail_count
        exp['results']['total_count'] = total_count
        
        # 更新指标
        if metrics:
            exp['metrics'].update(metrics)
        
        self._save_experiments()
        print(f"{status} 实验已完成: {exp_id} - {exp['name']}")
        print(f"   成功/失败/总计: {success_count}/{fail_count}/{total_count}")
        if exp['duration_seconds']:
            hours = int(exp['duration_seconds'] // 3600)
            minutes = int((exp['duration_seconds'] % 3600) // 60)
            print(f"   耗时: {hours}h {minutes}m")
    
    def update_experiment(self, exp_id: str, **updates):
        """
        更新实验信息
        
        Args:
            exp_id: 实验ID
            **updates: 要更新的字段
        """
        exp = self._find_experiment(exp_id)
        if not exp:
            print(f"❌ 未找到实验: {exp_id}")
            return
        
        # 更新指定字段
        for key, value in updates.items():
            if key in exp:
                exp[key] = value
            elif key in ['output_path', 'log_path', 'pid', 'parallel']:
                exp[key] = value
            elif key == 'metrics':
                exp['metrics'].update(value)
            elif key == 'findings':
                if isinstance(value, list):
                    exp['findings'].extend(value)
                elif isinstance(value, str):
                    exp['findings'].append(value)
            elif key == 'issues':
                if isinstance(value, list):
                    exp['issues'].extend(value)
                elif isinstance(value, str):
                    exp['issues'].append(value)
            elif key == 'next_actions':
                if isinstance(value, list):
                    exp['next_actions'].extend(value)
                elif isinstance(value, str):
                    exp['next_actions'].append(value)
        
        self._save_experiments()
        print(f"✅ 实验已更新: {exp_id}")
    
    def _find_experiment(self, exp_id: str) -> Optional[Dict]:
        """查找实验"""
        for exp in self.experiments['experiments']:
            if exp['id'] == exp_id:
                return exp
        return None
    
    def list_experiments(self, status: Optional[str] = None):
        """
        列出实验
        
        Args:
            status: 过滤状态（可选）
        """
        experiments = self.experiments['experiments']
        
        if status:
            experiments = [e for e in experiments if e['status'] == status]
        
        if not experiments:
            print("📭 没有找到实验")
            return
        
        print("\n" + "=" * 100)
        print("实验列表")
        print("=" * 100)
        print(f"{'ID':<10} {'名称':<30} {'状态':<12} {'成功/总数':<12} {'日期':<20}")
        print("-" * 100)
        
        for exp in experiments:
            success = exp['results']['success_count']
            total = exp['results']['total_count']
            date = exp['start_time'] or exp['registered_time']
            date = date.split()[0] if date else "N/A"
            
            print(f"{exp['id']:<10} {exp['name']:<30} {exp['status']:<12} "
                  f"{success}/{total if total > 0 else '?':<12} {date:<20}")
        
        print("-" * 100)
        print(f"总计: {len(experiments)} 个实验\n")
    
    def show_experiment(self, exp_id: str):
        """
        显示实验详情
        
        Args:
            exp_id: 实验ID
        """
        exp = self._find_experiment(exp_id)
        if not exp:
            print(f"❌ 未找到实验: {exp_id}")
            return
        
        print("\n" + "=" * 80)
        print(f"实验详情: {exp['id']}")
        print("=" * 80)
        print(f"名称:     {exp['name']}")
        print(f"状态:     {exp['status']}")
        print(f"目的:     {exp['purpose']}")
        print(f"位置:     {exp['location']}")
        print(f"脚本:     {exp['script']}")
        
        if exp['pid']:
            print(f"PID:      {exp['pid']}")
        if exp['parallel'] > 1:
            print(f"并行度:   {exp['parallel']}")
        
        print(f"\n时间信息:")
        print(f"  登记时间: {exp['registered_time']}")
        if exp['start_time']:
            print(f"  启动时间: {exp['start_time']}")
        if exp['end_time']:
            print(f"  结束时间: {exp['end_time']}")
        if exp['duration_seconds']:
            hours = int(exp['duration_seconds'] // 3600)
            minutes = int((exp['duration_seconds'] % 3600) // 60)
            print(f"  总耗时:   {hours}h {minutes}m")
        
        print(f"\n运行结果:")
        print(f"  成功: {exp['results']['success_count']}")
        print(f"  失败: {exp['results']['fail_count']}")
        print(f"  总计: {exp['results']['total_count']}")
        
        if exp['output_path']:
            print(f"\n产出路径: {exp['output_path']}")
        if exp['log_path']:
            print(f"日志路径: {exp['log_path']}")
        
        if exp['metrics']:
            print(f"\n核心指标:")
            for key, value in exp['metrics'].items():
                print(f"  {key}: {value}")
        
        if exp['findings']:
            print(f"\n关键发现:")
            for finding in exp['findings']:
                print(f"  - {finding}")
        
        if exp['issues']:
            print(f"\n问题:")
            for issue in exp['issues']:
                print(f"  - {issue}")
        
        if exp['next_actions']:
            print(f"\n后续行动:")
            for action in exp['next_actions']:
                print(f"  - {action}")
        
        print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="实验跟踪工具")
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 登记实验
    register_parser = subparsers.add_parser('register', help='登记新实验')
    register_parser.add_argument('--name', required=True, help='实验名称')
    register_parser.add_argument('--purpose', required=True, help='实验目的')
    register_parser.add_argument('--location', required=True, help='运行位置')
    register_parser.add_argument('--script', required=True, help='运行脚本')
    register_parser.add_argument('--output', help='产出路径')
    register_parser.add_argument('--log', help='日志路径')
    
    # 启动实验
    start_parser = subparsers.add_parser('start', help='标记实验开始')
    start_parser.add_argument('exp_id', help='实验ID')
    start_parser.add_argument('--pid', type=int, help='进程ID')
    
    # 完成实验
    finish_parser = subparsers.add_parser('finish', help='标记实验完成')
    finish_parser.add_argument('exp_id', help='实验ID')
    finish_parser.add_argument('--status', default='✅ 完成', help='最终状态')
    finish_parser.add_argument('--success', type=int, default=0, help='成功数量')
    finish_parser.add_argument('--fail', type=int, default=0, help='失败数量')
    finish_parser.add_argument('--total', type=int, default=0, help='总数量')
    
    # 更新实验
    update_parser = subparsers.add_parser('update', help='更新实验信息')
    update_parser.add_argument('exp_id', help='实验ID')
    update_parser.add_argument('--output', help='产出路径')
    update_parser.add_argument('--log', help='日志路径')
    update_parser.add_argument('--finding', help='添加关键发现')
    update_parser.add_argument('--issue', help='添加问题')
    update_parser.add_argument('--action', help='添加后续行动')
    
    # 列出实验
    list_parser = subparsers.add_parser('list', help='列出实验')
    list_parser.add_argument('--status', help='过滤状态')
    
    # 显示实验
    show_parser = subparsers.add_parser('show', help='显示实验详情')
    show_parser.add_argument('exp_id', help='实验ID')
    
    args = parser.parse_args()
    
    tracker = ExperimentTracker()
    
    if args.command == 'register':
        tracker.register_experiment(
            name=args.name,
            purpose=args.purpose,
            location=args.location,
            script=args.script,
            output_path=args.output,
            log_path=args.log
        )
    elif args.command == 'start':
        tracker.start_experiment(args.exp_id, args.pid)
    elif args.command == 'finish':
        tracker.finish_experiment(
            args.exp_id,
            status=args.status,
            success_count=args.success,
            fail_count=args.fail,
            total_count=args.total
        )
    elif args.command == 'update':
        updates = {}
        if args.output:
            updates['output_path'] = args.output
        if args.log:
            updates['log_path'] = args.log
        if args.finding:
            updates['findings'] = args.finding
        if args.issue:
            updates['issues'] = args.issue
        if args.action:
            updates['next_actions'] = args.action
        tracker.update_experiment(args.exp_id, **updates)
    elif args.command == 'list':
        tracker.list_experiments(args.status)
    elif args.command == 'show':
        tracker.show_experiment(args.exp_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

