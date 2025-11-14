"""
更新知识库中DREAMPlace案例的HPWL值
对于HPWL为0的案例，从对应的布局文件中重新提取
"""

import os
import sys
from pathlib import Path
import yaml

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_base import KnowledgeBase
from scripts.build_kb import KnowledgeBaseBuilder


def find_dreamplace_layout_files(
    remote_server: str,
    remote_user: str,
    dreamplace_dir: str = "~/dreamplace_experiment/DREAMPlace"
) -> dict:
    """
    查找DREAMPlace生成的布局文件
    
    Returns:
        {design_id: layout_file_path}
    """
    import subprocess
    
    layouts = {}
    
    try:
        ssh_cmd = f"ssh -o ServerAliveInterval=10 {remote_user}@{remote_server}"
        # DREAMPlace通常将所有结果输出到同一个design.gp.def文件
        # 我们需要根据时间戳或从知识库中的设计ID来匹配
        check_cmd = f"ls -lt {dreamplace_dir}/install/results/design/design.gp.def 2>/dev/null | head -1"
        
        result = subprocess.run(
            f"{ssh_cmd} '{check_cmd}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # 如果存在统一的design.gp.def文件，我们需要为每个设计单独处理
        # 或者从知识库中已有的案例信息来推断
        # 由于DREAMPlace每次运行会覆盖design.gp.def，我们需要：
        # 1. 检查是否有按设计名称组织的目录
        # 2. 或者使用统一的design.gp.def文件（需要知道当前是哪个设计）
        
        # 先查找所有可能的布局文件
        find_cmd = f"find {dreamplace_dir}/install/results -name '*.gp.def' -type f 2>/dev/null"
        result = subprocess.run(
            f"{ssh_cmd} '{find_cmd}'",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # 如果只有一个统一的design.gp.def，我们需要特殊处理
            def_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            if len(def_files) == 1 and 'design/design.gp.def' in def_files[0]:
                # 只有一个统一的文件，我们需要为所有设计使用它
                # 但这样无法区分不同设计，所以我们需要重新运行或从其他地方获取
                print(f"  找到统一的布局文件: {def_files[0]}")
                print(f"  注意: 由于DREAMPlace使用统一的输出文件，")
                print(f"  需要为每个设计单独运行或使用其他方法区分")
                # 暂时不添加，需要改进逻辑
            else:
                # 有多个文件，尝试提取设计名称
                for line in def_files:
                    path_parts = line.strip().split('/')
                    design_id = None
                    
                    # 查找设计名称
                    for i, part in enumerate(path_parts):
                        if part.startswith('mgc_') or part.startswith('adaptec') or part.startswith('bigblue'):
                            design_id = part
                            break
                    
                    if design_id:
                        layouts[design_id] = line.strip()
    except Exception as e:
        print(f"查找布局文件失败: {e}")
    
    return layouts


def update_case_hpwl(
    builder: KnowledgeBaseBuilder,
    kb: KnowledgeBase,
    design_id: str,
    layout_file: str
) -> bool:
    """
    更新案例的HPWL值
    
    Returns:
        是否成功更新
    """
    try:
        # 同步布局文件到本地
        local_temp_dir = Path(f"data/dreamplace_temp/{design_id}")
        local_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果是远程路径，需要同步
        if layout_file.startswith('~') or ':' in layout_file:
            import subprocess
            rsync_cmd = [
                'rsync', '-avz',
                f"{layout_file}",
                str(local_temp_dir / 'design.gp.def')
            ]
            
            sync_result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if sync_result.returncode != 0:
                print(f"  ✗ 同步布局文件失败: {layout_file}")
                return False
            
            layout_file_local = str(local_temp_dir / 'design.gp.def')
        else:
            layout_file_local = layout_file
        
        # 提取质量指标
        quality_metrics = builder.extract_quality_metrics(layout_file_local)
        
        # 更新知识库中的案例
        for i, case in enumerate(kb.cases):
            if case.get('design_id') == design_id:
                # 更新质量指标
                case['quality_metrics'] = quality_metrics
                print(f"  ✓ 更新 {design_id}: HPWL={quality_metrics.get('hpwl', 0):.2f}")
                return True
        
        print(f"  ✗ 未找到案例: {design_id}")
        return False
    except Exception as e:
        print(f"  ✗ 更新失败 {design_id}: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='更新知识库中DREAMPlace案例的HPWL值')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--remote-server', type=str, default=None,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default='keqin',
                       help='远程用户')
    parser.add_argument('--kb-file', type=str, default=None,
                       help='知识库文件路径（覆盖配置文件）')
    
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        kb_file = args.kb_file or config.get('knowledge_base', {}).get('case_file', 'data/knowledge_base/kb_cases.json')
    else:
        kb_file = args.kb_file or 'data/knowledge_base/kb_cases.json'
    
    # 加载知识库
    kb = KnowledgeBase(kb_file)
    kb.load()
    
    print(f"知识库中有 {len(kb.cases)} 个案例")
    
    # 查找HPWL为0的DREAMPlace案例
    dreamplace_cases = []
    for case in kb.cases:
        hpwl = case.get('quality_metrics', {}).get('hpwl', 0)
        # DREAMPlace案例通常没有partition_strategy
        if not case.get('partition_strategy') and hpwl == 0.0:
            dreamplace_cases.append(case.get('design_id'))
    
    print(f"找到 {len(dreamplace_cases)} 个HPWL为0的DREAMPlace案例")
    
    if not dreamplace_cases:
        print("没有需要更新的案例")
        return
    
    # 创建构建器
    builder = KnowledgeBaseBuilder(kb_file=kb_file, config_file=str(config_path) if config_path.exists() else None)
    
    # 查找布局文件
    if args.remote_server:
        print(f"\n从远程服务器查找布局文件...")
        layouts = find_dreamplace_layout_files(
            args.remote_server,
            args.remote_user
        )
        print(f"找到 {len(layouts)} 个布局文件")
    else:
        # 从本地查找
        layouts = {}
        results_dir = Path("data/dreamplace_temp")
        if results_dir.exists():
            for design_dir in results_dir.iterdir():
                layout_file = design_dir / "design.gp.def"
                if layout_file.exists():
                    layouts[design_dir.name] = str(layout_file)
    
    # 更新案例
    updated_count = 0
    for design_id in dreamplace_cases:
        if design_id in layouts:
            print(f"\n更新: {design_id}")
            if update_case_hpwl(builder, kb, design_id, layouts[design_id]):
                updated_count += 1
        else:
            print(f"\n未找到布局文件: {design_id}")
    
    # 保存知识库
    if updated_count > 0:
        kb.save()
        print(f"\n✓ 成功更新 {updated_count} 个案例")
    else:
        print("\n没有案例被更新")


if __name__ == '__main__':
    main()

