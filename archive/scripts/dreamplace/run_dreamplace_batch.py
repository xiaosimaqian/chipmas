"""
批量运行DREAMPlace并收集结果到知识库
从test目录查找所有设计配置，运行DREAMPlace，然后构建知识库案例
"""

import warnings
# 抑制torchvision的Beta警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchvision')

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import yaml

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.build_kb_from_dreamplace import find_dreamplace_configs_from_test, build_case_from_dreamplace
from scripts.build_kb import KnowledgeBaseBuilder


def run_dreamplace_local(
    config_json: str,
    dreamplace_dir: str = "~/dreamplace_experiment/DREAMPlace",
    output_dir: Optional[str] = None
) -> Optional[str]:
    """
    在本地（远程服务器上）运行DREAMPlace
    
    根据DREAMPlace文档，需要在install目录下运行：
    cd install
    python dreamplace/Placer.py test/ispd2005/adaptec1.json
    
    Args:
        config_json: 配置文件路径（绝对路径或相对于dreamplace_dir）
        dreamplace_dir: DREAMPlace根目录
        output_dir: 输出目录（可选）
    
    Returns:
        布局DEF文件路径或None
    """
    import os
    from pathlib import Path
    
    # 展开路径
    dreamplace_path = Path(os.path.expanduser(dreamplace_dir))
    install_path = dreamplace_path / "install"
    config_path = Path(config_json)
    
    # 检查install目录是否存在
    if not install_path.exists():
        print(f"install目录不存在: {install_path}")
        # 尝试使用根目录
        install_path = dreamplace_path
    
    # 如果config_json是相对路径，转换为相对于dreamplace根目录的路径
    if not config_path.is_absolute():
        # 配置文件应该在test目录下，相对于dreamplace根目录
        config_path = dreamplace_path / config_json
    else:
        # 如果是绝对路径，转换为相对于dreamplace根目录的路径（用于运行）
        try:
            config_relative = config_path.relative_to(dreamplace_path)
        except ValueError:
            # 如果不在dreamplace目录下，使用绝对路径
            config_relative = config_path
    
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return None
    
    # 检查Placer.py是否存在
    placer_script = install_path / "dreamplace" / "Placer.py"
    if not placer_script.exists():
        # 尝试在根目录查找
        placer_script = dreamplace_path / "dreamplace" / "Placer.py"
        if not placer_script.exists():
            print(f"Placer.py不存在: {placer_script}")
            return None
        install_path = dreamplace_path
    
    # 运行DREAMPlace
    # 根据DREAMPlace文档，需要在install目录下运行
    try:
        original_cwd = os.getcwd()
        os.chdir(str(install_path))
        
        # 运行DREAMPlace
        log_file = None
        if output_dir:
            log_path = Path(os.path.expanduser(output_dir))
            log_path.mkdir(parents=True, exist_ok=True)
            log_file = log_path / "dreamplace.log"
        
        # 设置PYTHONPATH，确保可以导入dreamplace模块
        env = os.environ.copy()
        pythonpath = env.get('PYTHONPATH', '')
        if str(install_path) not in pythonpath:
            env['PYTHONPATH'] = f"{install_path}:{pythonpath}" if pythonpath else str(install_path)
        
        # 检查并修改配置文件，确保gpu设置为0（如果CUDA未编译）
        # 创建临时配置文件
        import json
        import tempfile
        temp_config = None
        # 提前定义design_name，确保在except块中可用
        try:
            design_name = config_path.stem
        except:
            design_name = "unknown"
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # 如果gpu设置为1，但CUDA未编译，改为0
            if config_data.get('gpu', 0) == 1:
                # 检查CUDA是否可用
                try:
                    import dreamplace.configure as configure
                    cuda_found = configure.compile_configurations.get("CUDA_FOUND") == 'TRUE'
                except:
                    cuda_found = False
                
                if not cuda_found:
                    print(f"  检测到gpu=1但CUDA未编译，自动改为gpu=0")
                    config_data['gpu'] = 0
                    # 创建临时配置文件（在install目录下，使用相对于install的路径）
                    temp_config_path = install_path / f"temp_config_{design_name}.json"
                    with open(temp_config_path, 'w') as f:
                        json.dump(config_data, f, indent=2)
                    temp_config = type('obj', (object,), {'name': str(temp_config_path)})()
                    # 使用相对于install目录的路径（在install目录下运行）
                    config_relative = f"temp_config_{design_name}.json"
                else:
                    # 使用原始配置文件
                    if config_path.is_absolute() and str(config_path).startswith(str(dreamplace_path)):
                        config_relative = "../" + str(config_path.relative_to(dreamplace_path))
                    else:
                        config_relative = str(config_path) if config_path.is_absolute() else f"../{config_json}"
            else:
                # 使用原始配置文件
                if config_path.is_absolute() and str(config_path).startswith(str(dreamplace_path)):
                    config_relative = "../" + str(config_path.relative_to(dreamplace_path))
                else:
                    config_relative = str(config_path) if config_path.is_absolute() else f"../{config_json}"
        except Exception as e:
            print(f"  读取配置文件失败: {e}，使用原始配置")
            if config_path.is_absolute() and str(config_path).startswith(str(dreamplace_path)):
                config_relative = "../" + str(config_path.relative_to(dreamplace_path))
            else:
                config_relative = str(config_path) if config_path.is_absolute() else f"../{config_json}"
        
        cmd = ["python3", "dreamplace/Placer.py", config_relative]
        
        if log_file:
            with open(log_file, 'w') as log:
                result = subprocess.run(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=3600,  # 1小时超时
                    cwd=str(install_path),
                    env=env
                )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(install_path),
                env=env
            )
        
        os.chdir(original_cwd)
        
        # 清理临时配置文件
        if temp_config:
            try:
                if hasattr(temp_config, 'name'):
                    os.unlink(temp_config.name)
            except:
                pass
        
        if result.returncode == 0:
            # 查找生成的布局文件
            # DREAMPlace通常输出到results目录（在install或根目录下）
            results_dirs = [
                install_path / "results",
                dreamplace_path / "results"
            ]
            
            design_name = config_path.stem
            
            for results_dir in results_dirs:
                if not results_dir.exists():
                    continue
                
                # 查找该设计的布局文件
                def_files = list(results_dir.glob(f"{design_name}/design/*.gp.def"))
                if def_files:
                    return str(def_files[0])
                
                # 也检查results目录下的其他位置
                def_files = list(results_dir.rglob(f"*.gp.def"))
                if def_files:
                    # 返回最新的
                    def_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    return str(def_files[0])
        
        return None
    except subprocess.TimeoutExpired:
        print(f"运行超时: {config_json}")
        return None
    except Exception as e:
        print(f"运行失败 {config_json}: {e}")
        import traceback
        print(traceback.format_exc())
        return None
    finally:
        try:
            os.chdir(original_cwd)
        except:
            pass


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='批量运行DREAMPlace并构建知识库')
    parser.add_argument('--config', type=str, default='configs/default.yaml',
                       help='配置文件路径')
    parser.add_argument('--remote-server', type=str, required=True,
                       help='远程服务器地址')
    parser.add_argument('--remote-user', type=str, default='keqin',
                       help='远程用户')
    parser.add_argument('--remote-test-dir', type=str,
                       default='~/dreamplace_experiment/DREAMPlace/test',
                       help='远程DREAMPlace test目录')
    parser.add_argument('--benchmark-type', type=str, default=None,
                       help='只处理特定benchmark类型（如ispd2015, ispd2005等）')
    parser.add_argument('--dry-run', action='store_true',
                       help='只查找配置，不实际运行')
    parser.add_argument('--kb-file', type=str, default=None,
                       help='知识库文件路径（覆盖配置文件）')
    
    args = parser.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        kb_config = config.get('knowledge_base', {})
        kb_file = args.kb_file or kb_config.get('case_file', 'data/knowledge_base/kb_cases.json')
        embedding_model = kb_config.get('embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        embedding_model_type = kb_config.get('embedding_model_type', 'auto')
        embedding_cache_dir = kb_config.get('embedding_cache_dir', None)
        ollama_base_url = kb_config.get('ollama_base_url', 'http://localhost:11434')
    else:
        kb_file = args.kb_file or 'data/knowledge_base/kb_cases.json'
        embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
        embedding_model_type = 'auto'
        embedding_cache_dir = None
        ollama_base_url = 'http://localhost:11434'
    
    # 创建构建器
    builder = KnowledgeBaseBuilder(
        kb_file=kb_file,
        embedding_model_name=embedding_model,
        embedding_model_type=embedding_model_type,
        embedding_cache_dir=embedding_cache_dir,
        ollama_base_url=ollama_base_url,
        config_file=str(config_path) if config_path.exists() else None
    )
    
    print("=" * 70)
    print("批量运行DREAMPlace并构建知识库")
    print("=" * 70)
    
    # 1. 查找所有设计配置
    print(f"\n1. 查找所有设计配置...")
    configs = find_dreamplace_configs_from_test(
        args.remote_server,
        args.remote_user,
        args.remote_test_dir
    )
    
    # 过滤benchmark类型
    if args.benchmark_type:
        configs = [c for c in configs if c['benchmark_type'] == args.benchmark_type]
    
    print(f"找到 {len(configs)} 个设计配置")
    
    if not configs:
        print("未找到任何设计配置，退出")
        return
    
    # 显示找到的设计
    benchmark_groups = {}
    for config in configs:
        btype = config['benchmark_type']
        if btype not in benchmark_groups:
            benchmark_groups[btype] = []
        benchmark_groups[btype].append(config['design_id'])
    
    print(f"\n按benchmark类型分组:")
    for btype, design_ids in sorted(benchmark_groups.items()):
        print(f"  {btype}: {len(design_ids)} 个设计")
        if len(design_ids) <= 10:
            print(f"    {', '.join(design_ids)}")
        else:
            print(f"    {', '.join(design_ids[:10])} ... (还有{len(design_ids)-10}个)")
    
    if args.dry_run:
        print("\n[DRY RUN] 只查找配置，不实际运行")
        return
    
    # 2. 运行DREAMPlace并构建知识库
    print(f"\n2. 运行DREAMPlace并构建知识库...")
    print(f"⚠️  注意: 这可能需要很长时间，建议使用screen或tmux")
    
    added_count = 0
    failed_count = 0
    
    for i, config in enumerate(configs, 1):
        design_id = config['design_id']
        config_json = config['config_json']
        benchmark_type = config['benchmark_type']
        
        print(f"\n[{i}/{len(configs)}] 处理: {design_id} ({benchmark_type})")
        
        # 运行DREAMPlace
        print(f"  运行DREAMPlace...")
        # 注意：如果脚本在远程服务器上运行，直接调用本地函数
        # 如果脚本在本地运行，需要通过SSH调用
        if os.path.exists(os.path.expanduser("~/dreamplace_experiment/DREAMPlace")):
            # 在远程服务器上直接运行
            layout_def = run_dreamplace_local(
                config_json,
                "~/dreamplace_experiment/DREAMPlace",
                f"~/dreamplace_experiment/DREAMPlace/results/{design_id}"
            )
        else:
            # 在本地运行，需要通过SSH
            print(f"  ⚠️  需要在远程服务器上运行此脚本")
            print(f"  请使用: ssh {args.remote_user}@{args.remote_server}")
            print(f"  然后在远程服务器上运行此脚本")
            failed_count += 1
            continue
        
        if not layout_def:
            print(f"  ✗ 运行失败或未找到布局结果")
            failed_count += 1
            continue
        
        print(f"  ✓ 生成布局: {layout_def}")
        
        # 立即保存布局文件到设计特定的目录（避免被覆盖）
        # DREAMPlace使用统一的design.gp.def，我们需要立即复制
        dreamplace_path = Path(os.path.expanduser("~/dreamplace_experiment/DREAMPlace"))
        install_path = dreamplace_path / "install"
        unified_def = install_path / "results" / "design" / "design.gp.def"
        
        # 为每个设计创建独立的目录并复制文件
        design_result_dir = install_path / "results" / design_id
        design_result_dir.mkdir(parents=True, exist_ok=True)
        design_specific_def = design_result_dir / f"{design_id}.gp.def"
        
        if unified_def.exists():
            import shutil
            try:
                shutil.copy2(unified_def, design_specific_def)
                layout_def = str(design_specific_def)
                print(f"  ✓ 已保存设计特定布局文件: {layout_def}")
            except Exception as e:
                print(f"  ⚠️  保存设计特定布局文件失败: {e}，使用原始文件")
        
        # 构建知识库案例
        # 需要先同步布局文件到本地
        local_temp_dir = Path(f"data/dreamplace_temp/{design_id}")
        local_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 布局文件路径处理
        layout_def_local = layout_def
        if not Path(layout_def).exists():
            # 如果是远程路径，需要同步
            if args.remote_server and args.remote_user:
                rsync_cmd = [
                    'rsync', '-avz',
                    f"{args.remote_user}@{args.remote_server}:{layout_def}",
                    str(local_temp_dir / 'design.gp.def')
                ]
                
                sync_result = subprocess.run(
                    rsync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if sync_result.returncode != 0:
                    print(f"  ✗ 同步布局文件失败")
                    failed_count += 1
                    continue
                
                layout_def_local = str(local_temp_dir / 'design.gp.def')
            else:
                print(f"  ✗ 布局文件不存在且无法同步: {layout_def}")
                failed_count += 1
                continue
        else:
            # 本地文件，直接使用
            layout_def_local = layout_def
        
        # 构建案例
        local_design_dir = Path('data/ispd2015') / design_id
        design_source_dir = str(local_design_dir) if local_design_dir.exists() else None
        
        case = build_case_from_dreamplace(
            builder,
            design_id,
            layout_def_local,
            design_source_dir
        )
        
        if case and builder.add_case_to_kb(case, validate=True):
            added_count += 1
            print(f"  ✓ 成功添加案例: {design_id}")
            builder.save()
        else:
            print(f"  ✗ 添加失败: {design_id}")
            failed_count += 1
        
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(local_temp_dir)
        except:
            pass
    
    # 3. 显示统计
    print(f"\n" + "=" * 70)
    print(f"完成！")
    print(f"  成功: {added_count}/{len(configs)}")
    print(f"  失败: {failed_count}/{len(configs)}")
    stats = builder.get_statistics()
    print(f"\n知识库统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == '__main__':
    main()

